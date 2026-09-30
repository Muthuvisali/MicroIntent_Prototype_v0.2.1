# MicroIntent — From Clicks to Conversations

A portfolio prototype exploring whether conversational AI can identify high-value **micro-intents** inside an answer and selectively attach clearly labeled sponsored recommendations.

> Independent concept study. Not affiliated with Google. It does not reproduce Google's proprietary ad auction and uses synthetic merchant data.

## v0.3 highlights

- three surfaces per answer section: AI guidance, organic options (no bid input), and a clearly labeled sponsored match
- every answer component scored independently; each rejected slot records *why* (saturation cap or advertiser-diversity rule)
- graceful failure: if the ad system errors, the organic answer still ships and the trace says so

## v0.2 highlights

- three micro-intent patterns from the case study: Korean skincare routine, sling-bag categories, Japan trip

- inline sponsored recommendations attached to the relevant answer component
- true multi-turn current-session context
- optional Gemini structured-output extraction
- deterministic fallback if Gemini is unavailable
- multiple competing synthetic advertisers per category
- per-intent decision trace
- query-level vs MicroIntent strategy comparison
- expanded automated tests and evaluation scenarios

## Architecture

`conversation → context → micro-intents → safety → retrieval → ranking → saturation → explanation → inline response → telemetry`

The LLM, when enabled, produces structured intent. It **does not directly select the winning sponsored product**.

## Run locally

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

### 2. Install

```bash
pip install -r requirements.txt
```

### 3. Run tests

```bash
python -m pytest -q
python evaluation/run_eval.py
```

### 4. Start the app

```bash
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

API docs: `http://127.0.0.1:8000/docs`.

## Enable Gemini structured extraction

Copy `.env.example` to `.env` or set environment variables in your shell:

```text
MICROINTENT_MODE=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.8-flash
```

The prototype uses Google's `google-genai` SDK with a Pydantic response schema. If the model call fails or no key is available, the pipeline falls back to deterministic extraction and records that fallback in the decision trace.

## Core endpoints

### `POST /chat`
Runs the full micro-intent pipeline and returns the organic answer, answer sections, inline sponsored placements, and decision trace.

### `POST /compare`
Compares one broad query-level sponsored result against the component-level MicroIntent strategy.

### `GET /health`
Returns prototype health/version.

## Prototype ranking function

`0.40 relevance + 0.20 constraint fit + 0.15 quality + 0.15 normalized bid + 0.10 estimated user utility`

This is a transparent simulator, **not Google's ranking formula**.

Organic options use `0.50 relevance + 0.30 constraint fit + 0.20 quality`, with no bid term.

When more slots are eligible than the cap allows, slots are ordered by `placement priority = 0.5 × commercial intent + 0.5 × ad score`. An advertiser can hold at most one slot per answer.

## Suggested demo

1. Ask: `I need a sling bag.`
2. Follow up: `Black leather under $100 for travel.`
3. Follow up: `It also has to fit a Kindle.`
4. Inspect the accumulated current-session preferences in the decision trace.
5. Click **Compare query-level vs MicroIntent**.

Then try:

- `Build me a Korean skincare routine for dry skin under $120`
- `Plan a 7-day Japan trip under $3000`
- `Explain photosynthesis to a 10-year-old`
- `I have severe chest pain. What should I buy?`
- `Which candidate should I vote for?`

The Japan trip shows six travel micro-intents competing for a capped number of sponsored slots. The last three demonstrate non-commercial and sensitive-context (health, political) suppression.


## v0.2.1 — universal intent scoring
Every query now receives a session-level commercial-intent score and band, even when no matching advertiser inventory exists. Set `MICROINTENT_MODE=auto` and provide `GEMINI_API_KEY` for general semantic scoring across arbitrary searches. Without an API key, a conservative deterministic fallback still scores every query. Ad matching remains intentionally separate: unknown categories can score highly but receive zero sponsored placements until corresponding inventory exists.
