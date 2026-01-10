# 🛡️ PromptArmor

**A prompt injection defense testing sandbox — explore real-world attacks, benchmark your defenses, and see exactly where they fail.**

Prompt injection is the [#1 vulnerability](https://owasp.org/www-project-top-10-for-large-language-model-applications/) in the OWASP Top 10 for LLM Applications. Yet most teams deploying LLMs have no systematic way to test whether their system prompt or guardrails actually resist known attacks. PromptArmor fills that gap.

---

## ✨ Features

### 🔍 Attack Taxonomy Browser
Explore **194,000+ real-world prompt injection attempts** sourced from 4 Hugging Face datasets. Every prompt is classified into one of 10 technique categories (instruction override, roleplay exploit, encoding tricks, context manipulation, and more) with difficulty ratings from 1–5.

### ⚔️ Defense Sandbox
Configure a multi-layered defense and stress-test it against real attacks:
- **System prompt hardening** — write your own or pick a preset (weak → strong)
- **Input filters** — keyword blocklist + OpenAI Moderation API with tunable thresholds
- **Output filters** — secret leak detection with exact string and regex matching
- **Attack selection** — choose techniques, difficulty range, prompt count, and benign mix ratio

### 📊 Live Results & Scorecard
Watch results stream in real-time via SSE as each prompt runs through your defense pipeline. When complete, get a scorecard with:
- 🟢 Overall attack block rate (animated ring chart)
- 🔴 False positive rate
- 📈 Block rate by technique (which attacks get through?)
- 📉 Block rate by difficulty (does your defense scale?)
- 🧱 Blocks by defense layer (input filter vs. LLM refusal vs. output filter)

### 🔗 Shareable Results
Every eval run gets a unique URL (`/sandbox/:runId`). Bookmark it, share it with your team, or come back later — the scorecard persists.

---

## 🏗️ Architecture

```
┌───────────────────────────────────────────────────────┐
│                      FRONTEND                         │
│              React · TypeScript · Chakra UI v3         │
│                                                       │
│   Dashboard  ·  Taxonomy  ·  Sandbox  ·  Results      │
│               Browser         Config     Scorecard    │
└───────────┬───────────────────────┬───────────────────┘
            │       SSE stream      │
            ▼                       ▼
┌───────────────────────────────────────────────────────┐
│                      BACKEND                          │
│               FastAPI · Python 3.12+                  │
│                                                       │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │ Dataset  │  │   Defense    │  │   Evaluation    │ │
│  │ Service  │  │   Pipeline   │  │   Scoring       │ │
│  │          │  │              │  │                 │ │
│  │ Query &  │  │ Input filter │  │ Classify        │ │
│  │ filter   │  │ → Claude LLM │  │ injection       │ │
│  │ attacks  │  │ → Output     │  │ success &       │ │
│  │          │  │   filter     │  │ aggregate       │ │
│  └────┬─────┘  └──────┬───────┘  └────────┬────────┘ │
│       │               │                   │          │
│  ┌────▼────┐   ┌──────▼──────┐   ┌────────▼───────┐ │
│  │ SQLite  │   │ Claude API  │   │ OpenAI         │ │
│  │ (local) │   │ (target)    │   │ Moderation API │ │
│  └─────────┘   └─────────────┘   └────────────────┘ │
└───────────────────────────────────────────────────────┘
```

### 🔄 Defense Pipeline (per prompt)

```
User Prompt
    │
    ▼
┌──────────────┐    blocked    ┌──────────┐
│ Input Filter ├──────────────►│ BLOCKED  │
│ (keyword /   │               │ (skip    │
│  moderation) │               │  LLM)    │
└──────┬───────┘               └──────────┘
       │ passed
       ▼
┌──────────────┐
│ Claude LLM   │ ◄─── system prompt + user prompt
│ (target)     │
└──────┬───────┘
       │ response
       ▼
┌──────────────┐    blocked    ┌──────────┐
│ Output Filter├──────────────►│ BLOCKED  │
│ (secret leak │               │          │
│  detector)   │               └──────────┘
└──────┬───────┘
       │ passed
       ▼
┌──────────────┐
│ Score Result │ ──► injection succeeded? refused? false positive?
└──────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+** (with [uv](https://docs.astral.sh/uv/) package manager)
- **Node.js 18+** (with npm)
- **Anthropic API key** (for Claude — the LLM target)
- **OpenAI API key** *(optional, for the moderation filter)*

### 1️⃣ Clone & configure

```bash
git clone https://github.com/your-username/prompt-armor.git
cd prompt-armor
cp .env.example .env
# Edit .env and add your API keys:
#   ANTHROPIC_API_KEY=sk-ant-...
#   OPENAI_API_KEY=sk-...        (optional)
```

### 2️⃣ Ingest the datasets

```bash
cd backend
uv sync --all-extras
uv run python -m promptarmor.ingestion --skip-llm
# ⏱️ ~2-3 min — downloads 4 HF datasets, normalizes & classifies 194K prompts
```

### 3️⃣ Start the backend

```bash
uv run uvicorn promptarmor.main:app --port 8000 --reload
# ✅ API running at http://localhost:8000
# 📖 Swagger docs at http://localhost:8000/docs
```

### 4️⃣ Start the frontend

```bash
cd ../frontend
npm install
npm run dev
# ✅ App running at http://localhost:5173
```

### 5️⃣ Try it!

1. Open **http://localhost:5173**
2. Browse the attack taxonomy — 10 technique categories, 194K+ prompts
3. Go to **Sandbox** → pick a system prompt preset → enable a keyword blocklist → hit **Run Test**
4. Watch results stream in live → see your scorecard 📊

---

## 📁 Project Structure

```
prompt-armor/
├── backend/
│   ├── promptarmor/
│   │   ├── main.py              # FastAPI app entrypoint
│   │   ├── config.py            # Pydantic settings (env vars)
│   │   ├── database.py          # SQLite schema + async connection
│   │   ├── models/              # Pydantic v2 request/response models
│   │   ├── routers/             # API route handlers
│   │   │   ├── taxonomy.py      #   GET /api/v1/taxonomy
│   │   │   ├── attacks.py       #   GET /api/v1/attacks
│   │   │   ├── system_prompts.py#   GET /api/v1/system-prompts
│   │   │   └── eval.py          #   POST + SSE /api/v1/eval/run
│   │   ├── services/            # Business logic
│   │   │   ├── filters.py       #   Input filter pipeline
│   │   │   ├── output_filters.py#   Output filter pipeline
│   │   │   ├── llm_target.py    #   Claude API executor
│   │   │   ├── scoring.py       #   Injection classifier + scorecard
│   │   │   ├── attack_selector.py#  Stratified attack sampling
│   │   │   └── eval_runner.py   #   Pipeline orchestrator (SSE generator)
│   │   ├── middleware/           # Rate limiting
│   │   └── ingestion/           # HF dataset download + classification
│   └── tests/                   # 91 tests (pytest + pytest-asyncio)
├── frontend/
│   └── src/
│       ├── api/                 # Typed fetch client + SSE helper
│       ├── components/          # Layout, LiveResultsStream, ScorecardView
│       ├── pages/               # Dashboard, TaxonomyBrowser, Sandbox, etc.
│       └── theme/               # Chakra UI v3 system config + constants
├── data/                        # SQLite DB (generated by ingestion)
├── docker-compose.yml           # Container setup (WIP)
└── .env.example                 # Required environment variables
```

---

## 🧪 Testing

```bash
cd backend

# Run all 91 tests
uv run pytest -v

# Run specific test suites
uv run pytest tests/test_filters.py -v       # 🔒 Input/output filter tests
uv run pytest tests/test_scoring.py -v       # 📊 Scoring + scorecard tests
uv run pytest tests/test_rate_limit.py -v    # 🚦 Rate limiter tests
uv run pytest tests/test_classifier.py -v    # 🏷️ Technique classifier tests

# Linting & type checking
uv run ruff check .                          # 🧹 Lint (zero issues)
uv run mypy promptarmor/                     # 🔍 Strict type check (zero issues)
```

```bash
cd frontend

# Type check & lint
npx tsc --noEmit                             # ✅ Zero TypeScript errors
npx eslint src/                              # ✅ Zero lint errors

# Production build
npm run build                                # 📦 Builds to dist/
```

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| 🐍 Backend | **FastAPI** + Python 3.12 | Async-first, Pydantic v2 validation, auto-generated OpenAPI docs |
| 💾 Database | **SQLite** + aiosqlite | Zero-config, single-file DB perfect for local-first tool |
| ⚛️ Frontend | **React 19** + TypeScript + Vite | Type safety, fast HMR, modern tooling |
| 🎨 UI | **Chakra UI v3** | Component composition, dark mode, accessible by default |
| 📊 Charts | **Recharts** | Declarative charts with React components |
| 🔄 Data fetching | **TanStack Query** | Caching, background refetch, conditional polling |
| 📡 Real-time | **SSE** (Server-Sent Events) | Simpler than WebSockets for unidirectional streaming |
| 🤖 LLM | **Claude** (Anthropic API) | Target model for defense testing |
| 🛑 Moderation | **OpenAI Moderation API** | Free content classification as an input filter layer |
| 📦 Package mgmt | **uv** (Python) + npm | Fast, modern dependency resolution |
| ✅ Quality | **ruff** + **mypy** (strict) + **ESLint** + **Prettier** | Zero-tolerance linting, full type coverage |

---

## 📊 Datasets

PromptArmor ingests and normalizes prompts from 4 Hugging Face datasets:

| Dataset | Prompts | Type | License |
|---------|---------|------|---------|
| 🏰 [Lakera/mosscap](https://huggingface.co/datasets/Lakera/mosscap_prompt_injection) | ~173K | DEF CON 31 CTF attacks | MIT |
| 📝 [SPML Chatbot](https://huggingface.co/datasets/reshabhs/SPML_Chatbot_Prompt_Injection) | ~16K | System prompt + injection pairs | MIT |
| 🧪 [neuralchemy](https://huggingface.co/datasets/neuralchemy/Prompt-injection-dataset) | ~4.6K | Balanced injection/benign | Apache 2.0 |
| 🏷️ [deepset](https://huggingface.co/datasets/deepset/prompt-injections) | ~662 | Clean labeled (EN + DE) | Apache 2.0 |

**Total: 194,202 prompts** across 10 technique categories + unclassified, with difficulty estimates 1–5.

---

## 🗺️ Roadmap

- [x] 📦 Phase 1 — Project scaffolding & database foundation
- [x] 📥 Phase 2 — Dataset ingestion pipeline (4 HF datasets, 194K prompts)
- [x] ⚔️ Phase 3 — Backend defense pipeline (filters → LLM → scoring → SSE)
- [x] 🖥️ Phase 4 — Frontend (taxonomy browser, sandbox, live results, scorecard)
- [ ] ⚖️ Phase 5 — Comparison mode (side-by-side defense evaluation)
- [ ] 📄 Phase 6 — Red team report generator (Markdown export)
- [ ] 🚢 Phase 7 — Polish, deploy, demo video

---

## 📜 License

MIT

---

<p align="center">
  🛡️ Built with <b>FastAPI</b>, <b>React</b>, and <b>Claude</b>
</p>
