# BrewBot ☕ — Specialty Coffee Q&A Chatbot

A domain-specific chatbot that answers questions about specialty coffee brewing, built with FastAPI + LiteLLM (Gemini) and deployed on GCP Cloud Run.

**Live URL:** `https://brewbot-XXXX-uc.a.run.app` *(update after deployment)*

---

## Domain

BrewBot is a friendly specialty coffee expert. It answers questions about:

- Brewing methods (pour-over, espresso, French press, AeroPress, cold brew, etc.)
- Grind size and extraction
- Coffee-to-water ratios and recipes
- Water temperature for different roasts
- Roast levels and flavor profiles
- Coffee origins and terroir
- Equipment care and troubleshooting

Out-of-scope: café business operations, non-coffee beverages, medical/health advice.

---

## Project Structure

```
brewbot/
├── pyproject.toml          # uv-based dependencies
├── Dockerfile              # for GCP Cloud Run
├── .env.example            # environment variable template
├── README.md
├── app/
│   ├── main.py             # FastAPI app + session management
│   ├── prompt.py           # System prompt with few-shot examples
│   ├── backstop.py         # Python keyword/regex safety filter
│   └── static/
│       └── index.html      # Chat UI
└── eval/
    ├── golden_dataset.json  # 20 test cases (in-domain, OOS, adversarial)
    └── run_eval.py          # Evaluation harness
```

---

## Prompting Strategy

The system prompt (`app/prompt.py`) includes:

1. **Role/persona** — BrewBot, friendly home barista expert
2. **Positive constraints** — explicit list of what it *can* answer
3. **5 few-shot examples** — concrete Q&A pairs with real numbers
4. **Escape hatch** — "I'm not 100% certain about that..." for uncertainty
5. **Out-of-scope handling** — 4 named categories with positive redirect phrases
6. **Python backstop** (`app/backstop.py`) — regex pre/post-generation filter for distress keywords and OOS topics

---

## Run Locally

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) installed
- GCP project with Vertex AI enabled (or Gemini API key)

### Setup

```bash
# Clone and enter project
git clone <your-repo-url>
cd brewbot

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your GCP project ID

# Run the app
uv run uvicorn app.main:app --reload --port 8000
```

Then open [http://localhost:8000](http://localhost:8000).

### Using Gemini AI Studio instead of Vertex AI

1. Get a free API key at [aistudio.google.com](https://aistudio.google.com)
2. Set `GEMINI_API_KEY=your-key` in `.env`
3. Change `MODEL` in `app/main.py` to `"gemini/gemini-2.0-flash-lite"`

---

## Run Evaluations

Make sure the app is running locally first, then:

```bash
BASE_URL=http://localhost:8000 uv run eval/run_eval.py
```

The eval script will:
- Run all 20 test cases
- Report pass/fail per test with reasoning
- Print pass rates by category (in_domain / out_of_scope / adversarial)
- Exit with code 1 if any test fails

### Eval Metrics

| Metric | Type | Count |
|--------|------|-------|
| Keyword/refusal detection | Deterministic | All 20 tests |
| Golden-reference MaaJ | LLM-as-judge | All 20 tests |
| Rubric MaaJ (accuracy, specificity, scope, helpfulness) | LLM-as-judge | 10 in-domain tests |

---

## Deploy to GCP Cloud Run

```bash
# Set your project
export PROJECT_ID=your-gcp-project-id
export REGION=us-central1
export SERVICE_NAME=brewbot

# Build and push image
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME

# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars VERTEX_PROJECT=$PROJECT_ID,VERTEX_LOCATION=$REGION
```

Cloud Run uses the attached service account for Vertex AI authentication — make sure it has the `Vertex AI User` role.
