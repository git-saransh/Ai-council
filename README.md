# AI Council System

A multi-agent AI deliberation system where multiple language models collaborate, evaluate, and synthesize high-quality answers. Inspired by Andrej Karpathy's *LLM Council* concept.

---

# 🚀 Overview

This project implements a **3-stage AI deliberation pipeline** that improves response quality through diversity, peer evaluation, and consensus-based synthesis.

---

# ⚙️ How It Works

## 🔹 Stage 1: Individual Responses

* Multiple AI models generate answers independently
* No shared context → ensures unbiased reasoning
* Executed in parallel for speed

## 🔹 Stage 2: Anonymized Peer Review

* Responses are anonymized (Response A, B, C...)
* Each model evaluates and ranks all responses
* Rankings are aggregated to determine best outputs

## 🔹 Stage 3: Chairman Synthesis

* A designated chairman model receives:

  * All responses
  * Aggregated rankings
* Produces a final, high-quality synthesized answer

---

# 🧩 Council Members

All models are accessed via OpenRouter:

| Model                 | Provider   |
| --------------------- | ---------- |
| Llama 3.3 70B         | Meta       |
| Mistral Small 3.1 24B | Mistral AI |
| Gemma 3 27B           | Google     |
| Qwen 3 32B            | Alibaba    |

**Chairman Model:** Llama 3.3 70B (configurable)

---

# 🏗️ Architecture

```
frontend/          React + Vite UI
  src/App.jsx      Main app with SSE streaming
  src/App.css      Styling

backend/           FastAPI backend
  config.py        Model configuration
  nvidia_client.py OpenRouter client
  council.py       3-stage pipeline logic
  main.py          API endpoints

Docker
  docker-compose.yml Full stack deployment
```

---

# 📡 API Endpoints

| Method | Endpoint            | Description            |
| ------ | ------------------- | ---------------------- |
| GET    | /api/health         | Health check           |
| GET    | /api/models         | List available models  |
| POST   | /api/council        | Run full pipeline      |
| POST   | /api/council/stream | Stream results via SSE |

---

# ⚡ Setup Instructions

## 1️⃣ Get OpenRouter API Key

* Sign up at [https://openrouter.ai](https://openrouter.ai)
* Copy your API key

## 2️⃣ Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
OPENROUTER_API_KEY=your_api_key_here
```

---

## 3️⃣ Run with Docker

```bash
docker compose up --build
```

* Frontend: [http://localhost:5173](http://localhost:5173)
* Backend: [http://localhost:8001](http://localhost:8001)

---

## 4️⃣ Run Locally (Development)

### Backend

```bash
cd backend
pip install -r requirements.txt
export OPENROUTER_API_KEY=your_key
python main.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

# 🔧 Customization

Edit `backend/config.py` to:

* Add/remove models
* Change chairman model
* Adjust temperature and token limits

---

# 🔥 Advanced Features (Recommended Enhancements)

## ✅ Weighted Voting System

Assign weights to models based on reliability:

```python
final_score = rank * weight
```

## ✅ Confidence Scoring

Each model returns:

```json
{
  "answer": "...",
  "confidence": 0.85
}
```

## ✅ Critique Phase (Stage 2.5)

* Models critique top responses
* Improves reasoning depth

## ✅ Memory Layer (RAG)

* Store past queries using vector DB (FAISS / Pinecone)
* Enables learning over time

## ✅ Tool Integration

* Add support for:

  * Web search
  * Code execution
  * Calculators

## ✅ Dynamic Chairman Selection

Choose chairman based on task type

---

# 💡 Use Cases

* AI Research Assistant
* Decision Support Systems
* Code Generation & Review
* Multi-perspective Q&A systems

---

# 🧾 Resume Description

Built a Multi-Agent AI Deliberation System integrating multiple LLMs via OpenRouter. Implemented a 3-stage pipeline (parallel generation, peer ranking, and synthesis) using FastAPI and React with SSE streaming to enhance answer accuracy through consensus-based reasoning.

---

# 📌 Future Scope

* Add adversarial model for stress testing answers
* Implement explainability layer
* Deploy on cloud (AWS/GCP)
* Add user voting and feedback loop

---

# 🏁 Conclusion

This system demonstrates how multiple AI models can collaborate to produce higher-quality outputs than any single model alone, leveraging collective intelligence and structured reasoning.

---

# ⭐ Contributing

Pull requests are welcome! Feel free to open issues or suggest improvements.

---

# 📄
