"""
Core AI Council logic - 3-stage deliberation pipeline.

Stage 1: Each model answers the user query independently (in parallel).
Stage 2: Models peer-review anonymized responses and rank them.
Stage 3: Chairman synthesizes a final answer using all responses + rankings.
"""

import asyncio
import random
import re
import string

from config import COUNCIL_MODELS, CHAIRMAN_MODEL
from nvidia_client import query_model


def _make_label_mapping(models: list[dict]) -> dict[str, dict]:
    """Create anonymous labels for models (Response A, B, C, ...)."""
    labels = list(string.ascii_uppercase[: len(models)])
    random.shuffle(labels)
    return {f"Response {label}": model for label, model in zip(labels, models)}


def _parse_ranking(text: str, labels: list[str]) -> list[str] | None:
    """Extract FINAL RANKING section and parse ordered labels."""
    match = re.search(r"FINAL RANKING:(.*?)($|\n\n)", text, re.DOTALL | re.IGNORECASE)
    if not match:
        return None

    ranking_text = match.group(1)
    ranked = []
    for line in ranking_text.strip().split("\n"):
        for label in labels:
            if label in line and label not in ranked:
                ranked.append(label)
                break
    return ranked if len(ranked) >= 2 else None


def _aggregate_rankings(
    rankings: dict[str, list[str] | None], labels: list[str]
) -> list[dict]:
    """Compute average rank position across all peer evaluations."""
    scores: dict[str, list[int]] = {label: [] for label in labels}

    for _evaluator, ranking in rankings.items():
        if ranking is None:
            continue
        for position, label in enumerate(ranking):
            if label in scores:
                scores[label].append(position + 1)

    results = []
    for label in labels:
        positions = scores[label]
        avg = sum(positions) / len(positions) if positions else float("inf")
        results.append({"label": label, "avg_rank": round(avg, 2), "votes": len(positions)})

    results.sort(key=lambda x: x["avg_rank"])
    return results


async def run_stage1(user_query: str) -> dict[str, str | None]:
    """Stage 1: Each model answers independently in parallel."""
    system_prompt = (
        "You are a helpful AI assistant participating in a council discussion. "
        "Provide a thorough, well-reasoned answer to the user's question. "
        "Be concise but comprehensive."
    )

    tasks = {}
    for model in COUNCIL_MODELS:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ]
        tasks[model["id"]] = query_model(model["id"], messages)

    results = {}
    gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
    for model_id, result in zip(tasks.keys(), gathered):
        if isinstance(result, Exception):
            print(f"[ERROR] Stage 1 - {model_id}: {result}")
            results[model_id] = None
        else:
            results[model_id] = result

    return results


async def run_stage2(
    user_query: str,
    stage1_responses: dict[str, str | None],
) -> dict:
    """Stage 2: Anonymized peer review and ranking."""
    # Filter out failed responses
    valid = {k: v for k, v in stage1_responses.items() if v is not None}
    if len(valid) < 2:
        return {"rankings": {}, "aggregate": [], "label_map": {}}

    # Create anonymous label mapping
    valid_models = [m for m in COUNCIL_MODELS if m["id"] in valid]
    label_map = _make_label_mapping(valid_models)
    labels = sorted(label_map.keys())

    # Build anonymized responses text
    responses_text = ""
    for label in labels:
        model = label_map[label]
        responses_text += f"\n\n### {label}:\n{valid[model['id']]}"

    review_prompt = f"""You are evaluating multiple AI responses to this question:

**Question:** {user_query}

Here are the anonymized responses:
{responses_text}

Please evaluate each response for:
1. Accuracy and correctness
2. Depth and insight
3. Clarity and usefulness

Then provide your ranking from best to worst.

IMPORTANT: End your evaluation with a section titled "FINAL RANKING:" followed by a numbered list.
Example:
FINAL RANKING:
1. Response B
2. Response A
3. Response C
"""

    # Each model reviews all responses
    tasks = {}
    for model in COUNCIL_MODELS:
        messages = [
            {
                "role": "system",
                "content": "You are a fair and thorough evaluator of AI responses. "
                "Evaluate objectively without bias.",
            },
            {"role": "user", "content": review_prompt},
        ]
        tasks[model["id"]] = query_model(model["id"], messages)

    raw_reviews = {}
    parsed_rankings = {}
    gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
    for model_id, result in zip(tasks.keys(), gathered):
        if isinstance(result, Exception):
            raw_reviews[model_id] = None
            parsed_rankings[model_id] = None
        else:
            raw_reviews[model_id] = result
            parsed_rankings[model_id] = (
                _parse_ranking(result, labels) if result else None
            )

    aggregate = _aggregate_rankings(parsed_rankings, labels)

    # Reverse label map for frontend (label -> model name)
    reverse_map = {label: model["name"] for label, model in label_map.items()}

    return {
        "reviews": raw_reviews,
        "rankings": parsed_rankings,
        "aggregate": aggregate,
        "label_map": reverse_map,
    }


async def run_stage3(
    user_query: str,
    stage1_responses: dict[str, str | None],
    stage2_data: dict,
) -> str | None:
    """Stage 3: Chairman synthesizes a final answer."""
    # Build context with all responses and rankings
    responses_section = ""
    for model in COUNCIL_MODELS:
        resp = stage1_responses.get(model["id"])
        if resp:
            responses_section += f"\n\n### {model['name']} ({model['provider']}):\n{resp}"

    ranking_section = ""
    if stage2_data.get("aggregate"):
        ranking_section = "\n\n## Peer Review Rankings (best to worst):\n"
        for item in stage2_data["aggregate"]:
            label = item["label"]
            real_name = stage2_data["label_map"].get(label, label)
            ranking_section += (
                f"- {real_name}: avg rank {item['avg_rank']} "
                f"({item['votes']} votes)\n"
            )

    chairman_prompt = f"""You are the Chairman of an AI Council. Multiple AI models have answered a user's question, and their peers have ranked the responses.

**Original Question:** {user_query}

## Council Responses:
{responses_section}

{ranking_section}

Your task: Synthesize the BEST possible answer by combining the strongest insights from all responses. Weight higher-ranked responses more, but include valuable points from any response.

Provide a clear, comprehensive, and well-structured final answer. Do NOT mention that you are synthesizing from multiple models - just give the best answer directly."""

    messages = [
        {
            "role": "system",
            "content": "You are the Chairman of an AI Council. Provide the definitive, synthesized answer.",
        },
        {"role": "user", "content": chairman_prompt},
    ]

    return await query_model(CHAIRMAN_MODEL["id"], messages, temperature=0.5)


async def run_council(user_query: str) -> dict:
    """Run the full 3-stage council deliberation."""
    # Stage 1
    stage1 = await run_stage1(user_query)

    # Stage 2
    stage2 = await run_stage2(user_query, stage1)

    # Stage 3
    stage3 = await run_stage3(user_query, stage1, stage2)

    # Format stage1 with model names for frontend
    stage1_named = {}
    for model in COUNCIL_MODELS:
        stage1_named[model["name"]] = {
            "provider": model["provider"],
            "model_id": model["id"],
            "response": stage1.get(model["id"]),
        }

    return {
        "stage1": stage1_named,
        "stage2": {
            "reviews": {
                next(
                    (m["name"] for m in COUNCIL_MODELS if m["id"] == mid), mid
                ): review
                for mid, review in (stage2.get("reviews") or {}).items()
            },
            "rankings": stage2.get("aggregate", []),
            "label_map": stage2.get("label_map", {}),
        },
        "stage3": {
            "chairman": CHAIRMAN_MODEL["name"],
            "response": stage3,
        },
    }
