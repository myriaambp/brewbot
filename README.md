# BrewBot ☕ — Specialty Coffee Q&A Chatbot

A domain-specific chatbot that answers questions about specialty coffee brewing, built with FastAPI + LiteLLM (Gemini) and deployed on GCP Cloud Run.

**Live URL:** https://brewbot-879618059262.us-central1.run.app

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
├── pyproject.toml          # Dependencies (uv)
├── Dockerfile              # Container for GCP Cloud Run
├── .env.example            # Environment variable template
├── app/
│   ├── main.py             # FastAPI app, session management, LLM calls
│   ├── prompt.py           # System prompt with few-shot examples
│   ├── backstop.py         # Pre/post-generation safety filter (regex)
│   └── static/
│       └── index.html      # Chat UI
└── eval/
    ├── golden_dataset.json  # 20 test cases (in-domain, OOS, adversarial)
    └── run_eval.py          # Evaluation harness (deterministic + MaaJ)
```

---

## Prompting Strategy

The system prompt (`app/prompt.py`) uses a layered context engineering approach:

1. **Role/persona** — BrewBot, a friendly home barista expert with a named identity
2. **Positive constraints** — explicit enumeration of what the bot *can* answer (brewing methods, grind sizes, ratios, temps, origins, tasting notes, equipment)
3. **Tone instructions** — warm, encouraging, precise; prefers concrete numbers over vague advice
4. **5 few-shot examples** — hand-crafted Q&A pairs with real numbers that calibrate response format and length
5. **Out-of-scope handling** — 4 named categories (business, non-coffee beverages, medical, unrelated) with specific redirect phrases
6. **Escape hatch** — "I'm not 100% certain..." for genuine uncertainty, preventing hallucination

---

## Safety & Guardrails

`app/backstop.py` implements a defense-in-depth strategy with three layers:

| Layer | When | What it catches |
|-------|------|----------------|
| `check_input()` | Before LLM call | Distress/crisis keywords, adversarial/jailbreak attempts, out-of-scope topics |
| System prompt | During LLM generation | General OOS questions, ambiguous edge cases |
| `check_output()` | After LLM call | Cases where the LLM failed to refuse (e.g., answered a non-coffee question) |

Priority order for `check_input()`:
1. **Distress detection** — returns 988 crisis resource (highest priority)
2. **Adversarial/jailbreak** — catches prompt injections and dangerous requests before they hit Gemini's safety filter
3. **Out-of-scope topics** — business, beverages, medical, career questions

---

## Evaluation Harness

### Golden Dataset

`eval/golden_dataset.json` contains **20 test cases** across three categories:

| Category | Count | Purpose |
|----------|-------|---------|
| `in_domain` | 10 | Accurate, specific coffee answers |
| `out_of_scope` | 5 | Polite refusal with persona |
| `adversarial` | 5 | Jailbreaks, dangerous requests, distress handling |

### Evaluation Methods

Each test runs **deterministic checks** and **Model-as-a-Judge (MaaJ)** evaluation:

| Method | Type | Applied to |
|--------|------|-----------|
| Keyword matching | Deterministic | All 20 tests — checks expected terms appear in response |
| Refusal detection | Deterministic | 10 refusal tests — checks for known refusal phrases |
| Golden-reference judge | MaaJ (Gemini) | All 20 tests — compares response to reference answer |
| Rubric judge (accurate, specific, in-scope, helpful) | MaaJ (Gemini) | 10 in-domain tests — 4-criteria quality grade |

### Running the Eval

```bash
# Start the app locally first, then:
uv run python eval/run_eval.py
```

### Results

```
Overall: 20/20 passed (100%)

  in_domain            10/10  [██████████] 100%
  out_of_scope          5/5   [██████████] 100%
  adversarial           5/5   [██████████] 100%
```

---

## Run Locally

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv)
- GCP project with Vertex AI enabled (or a Gemini API key)

### Setup

```bash
git clone https://github.com/myriaambp/brewbot.git
cd brewbot
uv sync
cp .env.example .env
# Edit .env with your GCP project ID or Gemini API key
uv run uvicorn app.main:app --reload --port 8000
```

Then open http://localhost:8000.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Gemini 2.0 Flash Lite (Vertex AI) |
| LLM abstraction | LiteLLM |
| Backend | FastAPI + Uvicorn |
| Frontend | HTML/CSS/JS + marked.js |
| Package manager | uv |
| Deployment | Docker + GCP Cloud Run |
| Eval judge | Gemini 2.0 Flash Lite (MaaJ) |
