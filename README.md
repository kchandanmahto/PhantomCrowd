# 👻 PhantomCrowd

**AI Audience Simulator** — Preview how your content will be received before publishing.

PhantomCrowd summons a crowd of AI-powered personas that react to your content like real people would. Get sentiment analysis, engagement predictions, viral scores, and actionable suggestions — all before you hit "Post".

![Python](https://img.shields.io/badge/Python-3.12+-blue)
![Vue](https://img.shields.io/badge/Vue-3-green)
![LLM](https://img.shields.io/badge/LLM-Any%20OpenAI--compatible-blueviolet)
![License](https://img.shields.io/badge/License-MIT-yellow)

## How It Works

```
Your Content → 👻 Phantom Personas Generated → 💬 Each Reacts Independently → 📊 Analysis Dashboard
```

1. **Input** your content (ad copy, social post, product launch, email campaign...)
2. **PhantomCrowd generates** 10–500 diverse AI personas with unique demographics and personalities
3. **Each persona reacts** independently — comments, sentiment, engagement decisions
4. **Dashboard shows** sentiment distribution, viral score, engagement rate, and improvement suggestions

## Features

- **Multi-Persona Simulation** — Each phantom has age, occupation, interests, personality, and social media habits
- **Real-Time Progress** — Watch personas react one by one
- **Sentiment Analysis** — Positive / Negative / Neutral / Mixed breakdown with scores
- **Viral Score** — 0-100 prediction of content spread potential
- **Engagement Metrics** — Like / Share / Ignore / Dislike distribution
- **AI Suggestions** — Actionable improvements based on audience reactions
- **Dark UI** — Built for focus

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20+
- Any OpenAI-compatible API key (OpenAI, Ollama, Groq, Anthropic, etc.)

### 1. Clone & Setup Backend

```bash
git clone https://github.com/YOUR_USERNAME/PhantomCrowd.git
cd PhantomCrowd

cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your Anthropic API key
```

### 2. Setup Frontend

```bash
cd ../frontend
npm install
```

### 3. Run

```bash
# Terminal 1 — Backend
cd backend
uvicorn app.main:app --reload

# Terminal 2 — Frontend
cd frontend
npm run dev
```

Open http://localhost:5173

### Docker

```bash
export PC_ANTHROPIC_API_KEY=your-key-here
docker compose up --build
```

Open http://localhost:8000

## Architecture

```
PhantomCrowd/
├── backend/
│   └── app/
│       ├── api/            # FastAPI endpoints
│       ├── core/           # Config, database
│       ├── models/         # SQLAlchemy models
│       ├── schemas/        # Pydantic schemas
│       └── services/       # Persona generator, simulation engine
├── frontend/
│   └── src/
│       ├── api/            # API client
│       ├── components/     # ECharts visualizations
│       ├── stores/         # Pinia state management
│       └── views/          # Home + Simulation dashboard
└── docker-compose.yml
```

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/simulations/` | Create & start simulation |
| GET | `/api/simulations/` | List all simulations |
| GET | `/api/simulations/{id}` | Get simulation with reactions |
| GET | `/api/simulations/{id}/progress` | Poll simulation progress |
| DELETE | `/api/simulations/{id}` | Delete simulation |

## Supported LLM Providers

PhantomCrowd works with **any OpenAI-compatible API**. Configure via environment variables:

| Provider | Base URL | Models |
|----------|----------|--------|
| **OpenAI** | `https://api.openai.com/v1` | gpt-4o-mini, gpt-4o |
| **Ollama** (free, local) | `http://localhost:11434/v1` | llama3.1, qwen2.5 |
| **Groq** (fast) | `https://api.groq.com/openai/v1` | llama-3.1-8b-instant |
| **Together AI** | `https://api.together.xyz/v1` | meta-llama/Llama-3.1-8B |
| **Anthropic** | `https://api.anthropic.com/v1` | claude-haiku, claude-sonnet |

### Free Local Setup with Ollama

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1

# Set .env
PC_LLM_BASE_URL=http://localhost:11434/v1
PC_LLM_API_KEY=ollama
PC_LLM_MODEL=llama3.1
PC_LLM_ANALYSIS_MODEL=llama3.1
```

## Roadmap

- [ ] Image content analysis (upload screenshots, ads)
- [ ] A/B testing — compare multiple content versions
- [ ] Custom persona templates (target specific demographics)
- [ ] Export reports (PDF, CSV)
- [ ] Multi-language audience simulation
- [ ] Historical trend analysis

## License

MIT

---

Works with any OpenAI-compatible LLM API
