# MicroIntent — From Clicks to Conversations

A portfolio prototype exploring whether conversational AI can identify high-value **micro-intents** inside an answer and selectively attach a small number of clearly labeled sponsored recommendations.

> Independent concept study. Not affiliated with Google. It does not reproduce Google's proprietary ad auction and uses synthetic merchant data.

**Live demo:** https://visaliravi-microintent.static.hf.space (runs in your browser; first load takes about 10 seconds)

## What it does

A request such as *"Build me a Korean skincare routine for dry skin under $120"* is split into micro-intents (oil cleanser, toner, serum, sunscreen, …). Each one is scored and decided on independently, and every answer section keeps three surfaces apart:

- **AI guidance** — what to look for in this component
- **Organic options** — ranked on relevance, constraint fit and quality, with **no bid input**
- **Sponsored match** — at most one, clearly labeled, with a grounded "why this matches"

Three example patterns ship with synthetic inventory (36 fictional products from competing advertisers): a sequential **Korean skincare routine**, categorical **sling bags**, and a **Japan trip** plan.

## Pipeline

`conversation → topic-scoped session context → micro-intent extraction → safety gate → commercial eligibility → retrieval → ad ranking → placement selection → grounded explanation → answer composition → decision trace`

The LLM, when enabled, produces structured intent only. It **never selects the winning sponsored product**.

## How a placement is decided

1. **Is it commercial?** Each component gets a commercial-intent score from 0 to 1 and is eligible at **0.55**. Sensitive contexts (health, fertility, finance, gambling, politics) are blocked before any ad is retrieved, and that check covers the whole conversation.
2. **Is there a good enough ad?** Candidates are ranked with
   `0.40 relevance + 0.20 constraint fit + 0.15 quality + 0.15 normalized bid + 0.10 estimated user utility`.
   If the best ad scores below **0.75**, nothing is shown, however high the bid.
3. **Which slots win?** Eligible slots are ordered by `placement priority = 0.5 × commercial intent + 0.5 × ad score`. The cap is 2 per answer by default (configurable 0–3), and an advertiser can hold only one slot. Every rejected slot records why: `not_selected_saturation` or `not_selected_diversity`.
4. **What does the user see?** Organic options use `0.50 relevance + 0.30 constraint fit + 0.20 quality` (no bid) and never repeat the sponsored product.

These weights, thresholds and per-component priors are **hand-set**, inspectable choices, not values learned from data. They are a transparent simulator, **not Google's ranking formula**. Calibrating them against human-labeled conversations is the next step.

## Extractor modes

| Mode | When | Behavior |
|---|---|---|
| `gemini` | `MICROINTENT_MODE=gemini`, or `auto` with `GEMINI_API_KEY` set | Gemini structured output. It is given the catalog's component labels, splits routines and plans into one item per component, writes a short guidance line for each, and scores each component on its own. Free-form labels ("cleansing oil", "JR Pass") are mapped onto catalog categories. One retry on a transient 503. |
| `deterministic` | No key, `MICROINTENT_MODE=deterministic`, or demo mode | Transparent rule-based extractor. Same output schema. |
| fallback | Gemini call fails | Falls back to deterministic and records `deterministic_fallback:<Error>` in the trace. |

**Conversation handling.** The current message decides the topic. Earlier turns are used only when the message is a follow-up ("under $40", "it also has to fit a Kindle"), so a new topic doesn't inherit the old topic or its preferences. Only preferences the user states explicitly are used.

**Failure handling.** If retrieval, ranking or explanation fails, `/chat` still returns the organic answer and reports `monetization_status: failed:<Error>` in the trace.

## Run locally

From this folder:

```bash
python -m venv .venv
```

Install and start the app **with the virtual environment's Python** (a different Python won't have the Gemini SDK and will silently use the deterministic fallback):

Windows:

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload
```

macOS/Linux:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` (API docs at `/docs`).

Tests and evaluation:

```bash
python -m pytest -q              # 25 tests
python evaluation/run_eval.py    # 13 cases: ad count + safety expectations
```

### Enable Gemini

Copy `.env.example` to `.env`:

```text
MICROINTENT_MODE=auto
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.8-flash
```

The decision trace's **Extractor** row shows which mode answered each request.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /chat` | Full pipeline: answer, sections (guidance, organic, sponsored), placements and decision trace |
| `POST /compare` | One broad query-level sponsored result vs. MicroIntent placements |
| `GET /health` | Version and whether demo mode is on |

Request limits: message ≤ 1,000 characters, ≤ 40 history turns, sponsored cap 0–3.

## Public demo

The demo is a free Hugging Face **static** Space. The same Python pipeline runs in the visitor's browser with [Pyodide](https://pyodide.org), so there's no server and no LLM calls (deterministic extractor). `static_demo/shim.js` answers the UI's `/chat`, `/compare` and `/health` calls in the browser, so `static/index.html` is unchanged.

Rebuild and publish:

```bash
python scripts/build_static.py
python -c "from huggingface_hub import HfApi; HfApi().upload_folder(repo_id='visaliravi/microintent', repo_type='space', folder_path='dist')"
```

To run the server version as a container instead, `MICROINTENT_DEMO=1` (set in the `Dockerfile`) forces the deterministic extractor even when an API key is present:

```bash
docker build -t microintent .
docker run -p 7860:7860 microintent
```

## Suggested demo

1. `I need a sling bag.` → `Black leather under $100 for travel.` → `It also has to fit a Kindle.` Watch preferences accumulate in the trace, then click **Compare query-level vs MicroIntent**.
2. `Build me a Korean skincare routine for dry skin under $120`: two of seven steps are sponsored; the decision table shows which slots lost to the cap and which to the diversity rule.
3. `Plan a 7-day Japan trip under $3000`: six components compete for two slots.
4. `Explain photosynthesis to a 10-year-old`, `I have severe chest pain. What should I buy?`, `Which candidate should I vote for?`: non-commercial and sensitive suppression.

## Known limitations

- A stated budget is checked against each item separately, not allocated across a multi-item plan.
- Answer text for catalog components is templated; Gemini writes guidance only for components outside the catalog.
- Retrieval is category and keyword matching over a JSON catalog, not semantic search.
- 13 evaluation cases are a smoke test, not a benchmark.

See [CHANGELOG.md](CHANGELOG.md) for version history and [docs/](docs/) for the PRD and architecture notes.
