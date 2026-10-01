# MicroIntent v0.3.1 Architecture

## Runtime pipeline

`conversation → topic-scoped session context → micro-intent extraction → safety gate → commercial eligibility → candidate retrieval → ad ranking → placement selection → grounded explanation → answer composition → decision trace`

| Stage | Module | Notes |
|---|---|---|
| Session context | `services/intents.py` (`session_text`) | The current message sets the topic; earlier turns join only for follow-ups. Only explicitly stated preferences are extracted. |
| Micro-intent extraction | `services/intents.py` | Gemini structured output or deterministic rules, same `MicroIntent` schema. |
| Safety gate | `services/pipeline.py`, `services/intents.py` | Sensitive intents are blocked before retrieval. The check covers the whole conversation. |
| Commercial eligibility | `services/safety.py` | Commercial score ≥ 0.55 and a concrete component label. |
| Retrieval | `services/retrieval.py` | Exact-category inventory first; keyword overlap only as a fallback. |
| Ad ranking | `services/ranking.py` (`rank`) | `0.40R + 0.20C + 0.15Q + 0.15B + 0.10U`; the best ad must reach 0.75. |
| Organic ranking | `services/ranking.py` (`rank_organic`) | `0.50R + 0.30C + 0.20Q`; no bid term. |
| Placement selection | `services/saturation.py` | Priority `0.5 × intent + 0.5 × ad score`; cap (default 2); one slot per advertiser; records the rejection reason. |
| Explanation | `services/explanation.py` | Reasons drawn only from user-stated constraints and catalog facts. |
| Answer composition | `services/answer.py` | Each section: guidance, organic options, at most one sponsored match. |
| Comparison | `services/comparison.py` | One query-level sponsored result vs. MicroIntent placements. |

## Extractor modes

### Deterministic
Repeatable and needs no API key. Rules recognize the three demo patterns (skincare routine, sling bags, Japan trip) and score each component as a base score (request type, buying language, stated preferences) times a hand-set component prior.

### Gemini structured output
Used when `MICROINTENT_MODE=gemini`, or `auto` with `GEMINI_API_KEY` set. The prompt gives Gemini the catalog's component labels, asks for one item per component with a short guidance line, tells it to score components independently, and tells it to analyze the latest message rather than earlier topics. Returned labels are mapped onto catalog categories (`canonical_label`), and duplicates are merged. A transient 503 gets one retry.

If Gemini fails, extraction falls back to deterministic, and the trace records `deterministic_fallback:<Error>` so failure is visible rather than silent.

### Demo mode
`MICROINTENT_DEMO=1` forces deterministic extraction even when a key is present. `/health` reports it and the UI shows a banner.

## Deployment

- **Server:** FastAPI (`app/main.py`), or the `Dockerfile` (port 7860, demo mode on).
- **Public demo:** a static Hugging Face Space. `scripts/build_static.py` packages the unchanged pipeline, and `static_demo/shim.js` runs it in the browser with Pyodide by answering `/chat`, `/compare` and `/health` locally.

## Design principles

1. **The ad subsystem is optional.** If retrieval, ranking or explanation fails, `/chat` still returns the organic answer and reports `monetization_status` in the trace.
2. **Only explicit current-session preferences are used.** No historical profiling, and a new topic drops the old topic's preferences.
3. **The LLM does not pick the winning ad.** It produces structured intent; retrieval, ranking and selection are downstream and deterministic.
4. **Sensitive contexts are blocked before candidate retrieval.**
5. **Scarcity is deliberate.** Eligible slots can still lose to the cap or the advertiser-diversity rule, and the trace says which.
6. **Organic and sponsored stay distinct.** Organic options are ranked without bid input and never repeat the sponsored product.
7. **Every decision is explainable.** The trace exposes each component's intent score, status, top candidate and placement priority.
8. **Weights are hand-set and inspectable.** None are learned; calibration against human labels is future work.

## Strategy experiment

`POST /compare` contrasts:

- **Query-level baseline:** one broad-category sponsored recommendation.
- **MicroIntent strategy:** components scored independently, with up to the cap receiving a sponsored match.

The comparison is an experiment simulator, not a claim about Google's proprietary auction or production performance.
