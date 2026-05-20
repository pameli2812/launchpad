# Resume AI Analyzer

An AI-powered career co-pilot that scores your resume against any job description, identifies gaps, generates targeted resume edits, and produces a revised PDF that preserves your original template.

## Features

- **Resume management** — upload PDF or DOCX resumes; view, download, and delete from a browser table with pagination
- **Goal sets** — define what you're looking for in your next role, either manually or by letting an LLM infer goals from your resume
- **JD analysis** — paste a job description and get a structured scorecard (Overall Fit, per-dimension scores, verdict, descriptive summary)
- **Gap analysis** — gaps are classified by type (Skills, Experience, Education, Domain, Seniority, etc.) and criticality (High / Medium / Low)
- **Resume change suggestions** — four categories (Text Edit / Add Data / Remove Text / Polish Content) with copy-pasteable before/after text, guided by an optional user prompt
- **Approval + PDF rewrite** — tick the suggestions you accept, click Apply, and download a revised PDF that preserves your original template (text replacement via PyMuPDF redaction)
- **Analysis history** — every analysis is auto-saved; revisit, delete, or review past runs
- **Multi-provider LLM chain** — Anthropic Claude (primary) → OpenAI (secondary) → Ollama (offline fallback), with prompt caching on the Claude path

## Tech stack

- **Backend**: FastAPI · Python 3.10+ · PyMuPDF · Anthropic SDK · OpenAI SDK
- **Frontend**: React 18 · TypeScript · Vite · TailwindCSS · TanStack Query · Zustand
- **LLM providers**: Anthropic Claude Sonnet 4.6 (default) · OpenAI gpt-4o-mini · Ollama (local)

## Project structure

```
resume-ai-analyzer/
├── app/
│   ├── backend/                # FastAPI app
│   │   ├── main.py             # entry point — uvicorn target
│   │   ├── routes/             # /api/setup, /api/analyze, /api/history
│   │   └── requirements.txt
│   └── frontend/               # React + Vite app
│       ├── src/
│       │   ├── pages/          # Setup, Analyze, History
│       │   ├── components/     # shared UI primitives
│       │   ├── api/            # axios client
│       │   ├── hooks/          # TanStack Query hooks
│       │   └── store/          # Zustand store
│       ├── package.json
│       └── vite.config.ts
└── launchpad/                  # shared Python package (imported by backend)
    ├── utils/                  # PDF parsing, scoring, suggestion, PDF editor
    └── data/                   # runtime storage (uploads, goal_sets.json, history.json)
```

## Prerequisites

- **Python 3.10+** (3.11 recommended)
- **Node.js 18+** and npm
- **An LLM provider** — at least one of:
  - An [Anthropic API key](https://console.anthropic.com/) (recommended)
  - An [OpenAI API key](https://platform.openai.com/)
  - [Ollama](https://ollama.com/) running locally with a model pulled (`ollama pull mistral`)

## Installation

### 1. Clone the repo

```sh
git clone https://github.com/YOUR_USERNAME/resume-ai-analyzer.git
cd resume-ai-analyzer
```

### 2. Backend setup

```sh
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install backend dependencies
pip install -r app/backend/requirements.txt
```

Create a `.env` file at the repo root (or inside `app/backend/`) with at least one provider configured:

```sh
# Provider chain — comma-separated, tried in order. Omit providers you don't use.
LLM_PROVIDERS=anthropic,openai,ollama

# Anthropic (primary — recommended)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6        # or claude-haiku-4-5 for lower cost
ANTHROPIC_MAX_TOKENS=8192
# ANTHROPIC_THINKING=adaptive            # uncomment to enable extended reasoning

# OpenAI (secondary fallback)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Ollama (offline fallback — only used if both above are unavailable)
OLLAMA_API_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# Backend port (optional, defaults to 8000)
API_PORT=8000
```

Missing keys make a provider auto-skip — no extra config needed if you only want Anthropic + Ollama.

### 3. Frontend setup

```sh
cd app/frontend
npm install
```

## Running the app

You need two terminals, one for each service.

### Terminal 1 — start the backend

```sh
source venv/bin/activate          # if not already active
cd app/backend
python main.py
```

The API will be available at `http://localhost:8000` with interactive Swagger docs at `http://localhost:8000/docs`.

### Terminal 2 — start the frontend

```sh
cd app/frontend
npm run dev
```

The React app will be available at `http://localhost:3000`. The Vite dev server proxies `/api` requests to the backend on port 8000.

### First-run workflow

1. Open `http://localhost:3000`. The app lands on the **Analyze** tab.
2. If you have no resumes or goal sets yet, click **Go to Setup**.
3. **Setup → Step 1**: upload a resume (PDF or DOCX, max 5MB).
4. **Setup → Step 2**: click **+ Add New Goal**, pick **Auto-Infer (AI)** to have the LLM suggest goals from your resume, or **Manual** to enter them yourself. Click **Save Goal Set**, then activate it.
5. Back on **Analyze**: select the resume + goal set, paste a job description, and click **Run Analysis**.
6. Review the scorecard, gaps, and verdict. If gaps exist, click **Get Suggestions**.
7. Tick the suggestions you accept and click **Apply approved changes to PDF**.
8. Click **Download revised resume** — the PDF preserves your original template.
9. Visit the **History** tab to revisit past analyses.

## Environment variables — full reference

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDERS` | `anthropic,openai,ollama` | Provider chain — first that succeeds wins |
| `ANTHROPIC_API_KEY` | — | Your Anthropic API key |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Claude model ID |
| `ANTHROPIC_MAX_TOKENS` | `8192` | Max output tokens per call |
| `ANTHROPIC_THINKING` | `disabled` | Set to `adaptive` to enable extended thinking |
| `OPENAI_API_KEY` | — | Your OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model |
| `OLLAMA_API_URL` | `http://localhost:11434` | Local Ollama endpoint |
| `OLLAMA_MODEL` | `mistral` | Ollama model name |
| `API_PORT` | `8000` | Backend HTTP port |

## Architecture notes

- **Provider chain with JSON validation** — each LLM call is tried against the provider chain in order. The chain falls through on connection errors, auth failures, *or* unparseable JSON output. So if Anthropic returns garbage one day, OpenAI gets a shot; if OpenAI is rate-limited, Ollama runs locally.
- **Prompt caching** — within a single analysis, the scorecard / suggestions / verify calls all share the same `resume + JD + goals` context block (via `cache_control: ephemeral`). Call 1 writes the cache; calls 2 and 3 read it at ~10% of base input price. Look for `anthropic[...] cache: read=N` lines in the backend logs to confirm hits.
- **PDF editing** — the "apply suggestions" step uses PyMuPDF redaction to replace text in place, preserving fonts and layout. "Add Data" suggestions are appended on a clearly-marked addendum page (template preservation isn't possible when inserting content into an unknown layout).
- **Storage** — all persistent state lives in `launchpad/data/`: uploaded PDFs in `uploads/`, goal sets in `goal_sets.json`, analysis history in `history.json`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'launchpad'` | The backend adds the project root to `sys.path` automatically. Make sure you run `python main.py` (not `uvicorn main:app` from a different directory). |
| `Anthropic not configured` in logs | Either set `ANTHROPIC_API_KEY` or remove `anthropic` from `LLM_PROVIDERS`. |
| `Ollama not running` errors | Either `ollama serve` in another terminal, or remove `ollama` from `LLM_PROVIDERS`. |
| Cache `read=0` across three calls | The resume + JD combined is probably under the 2,048-token cache minimum on Sonnet 4.6. Caching silently no-ops below that threshold — not an error, just no savings. |
| PDF edit "skipped" with "original text not found" | The suggestion's *before* text spans line breaks in the PDF; PyMuPDF can't always locate multi-line strings. The other accepted changes still apply. |
| Frontend "Failed to fetch" on every call | Backend isn't running. Check `http://localhost:8000/health` returns `{"status": "ok"}`. |

## License

MIT (or your preferred license — update this section).
