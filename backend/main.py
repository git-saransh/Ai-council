"""
FastAPI backend for AI Council.
Provides REST and SSE endpoints for the council deliberation pipeline.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import COUNCIL_MODELS, CHAIRMAN_MODEL, OPENROUTER_API_KEY
from council import run_stage1, run_stage2, run_stage3

app = FastAPI(title="AI Council", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory conversation storage
conversations: dict[str, dict] = {}


class QueryRequest(BaseModel):
    query: str
    conversation_id: str | None = None


@app.get("/api/health")
async def health():
    return {"status": "ok", "api_key_set": bool(OPENROUTER_API_KEY)}


@app.get("/api/models")
async def get_models():
    return {
        "council": [
            {"name": m["name"], "provider": m["provider"], "id": m["id"]}
            for m in COUNCIL_MODELS
        ],
        "chairman": {
            "name": CHAIRMAN_MODEL["name"],
            "provider": CHAIRMAN_MODEL["provider"],
        },
    }


@app.post("/api/council")
async def run_council_endpoint(req: QueryRequest):
    """Run the full council deliberation (non-streaming)."""
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not set")

    conv_id = req.conversation_id or str(uuid.uuid4())

    stage1 = await run_stage1(req.query)
    stage2 = await run_stage2(req.query, stage1)
    stage3 = await run_stage3(req.query, stage1, stage2)

    # Format response
    stage1_named = {}
    for model in COUNCIL_MODELS:
        stage1_named[model["name"]] = {
            "provider": model["provider"],
            "model_id": model["id"],
            "response": stage1.get(model["id"]),
        }

    result = {
        "conversation_id": conv_id,
        "query": req.query,
        "timestamp": datetime.now(timezone.utc).isoformat(),
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

    conversations[conv_id] = result
    return result


@app.post("/api/council/stream")
async def stream_council(req: QueryRequest):
    """Run the council deliberation with SSE streaming for progress updates."""
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not set")

    async def event_generator():
        conv_id = req.conversation_id or str(uuid.uuid4())

        def send_event(event_type: str, data: dict) -> str:
            return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

        yield send_event("start", {"conversation_id": conv_id, "query": req.query})

        # Stage 1
        yield send_event("stage", {"stage": 1, "status": "running"})
        stage1 = await run_stage1(req.query)

        stage1_named = {}
        for model in COUNCIL_MODELS:
            stage1_named[model["name"]] = {
                "provider": model["provider"],
                "model_id": model["id"],
                "response": stage1.get(model["id"]),
            }
        yield send_event("stage1_complete", {"responses": stage1_named})

        # Stage 2
        yield send_event("stage", {"stage": 2, "status": "running"})
        stage2 = await run_stage2(req.query, stage1)

        stage2_data = {
            "reviews": {
                next(
                    (m["name"] for m in COUNCIL_MODELS if m["id"] == mid), mid
                ): review
                for mid, review in (stage2.get("reviews") or {}).items()
            },
            "rankings": stage2.get("aggregate", []),
            "label_map": stage2.get("label_map", {}),
        }
        yield send_event("stage2_complete", stage2_data)

        # Stage 3
        yield send_event("stage", {"stage": 3, "status": "running"})
        stage3 = await run_stage3(req.query, stage1, stage2)

        stage3_data = {
            "chairman": CHAIRMAN_MODEL["name"],
            "response": stage3,
        }
        yield send_event("stage3_complete", stage3_data)

        yield send_event("done", {
            "conversation_id": conv_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
