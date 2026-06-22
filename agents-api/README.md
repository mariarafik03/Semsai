---
title: SemsAi Agents
emoji: 🏠
colorFrom: blue
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# SemsAi Agents API
FastAPI server for the SemsAi real estate AI agents pipeline.

## Run locally (for Flutter integration)

1. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`, `MONGO_URI`
2. Install: `pip install -r requirements.txt`
3. Start: `python run.py` (runs on port 8000)
4. Ensure semsai-backend runs on port 3000 and proxies `/conversation/step` → `http://127.0.0.1:8000/agents/step`

## Endpoints

- `GET /` — Health check
- `POST /agents/step` — Step-by-step chat for Flutter: `{state, user_input}` → `{message, state, done}`
- `POST /run` — Full graph run: `{state}` → `{state}`
