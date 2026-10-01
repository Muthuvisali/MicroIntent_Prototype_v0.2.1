# MicroIntent MVP PRD — v0.3.1

## Objective
Test whether component-level, context-aware sponsored matching can produce more useful commercial recommendations than generic query-level advertising without degrading trust.

## Product principles
1. Organic guidance stays primary.
2. Sponsored content is clearly labeled, visually distinct, and never replaces the best organic option.
3. High commercial precision beats ad volume.
4. Sensitive contexts are blocked before candidate retrieval.
5. Only explicit current-session preferences are used.
6. A failed LLM or ad subsystem must not block the base answer.
7. The system must expose why a placement was, or was not, selected.

## Functional scope (implemented)
- Single-turn and multi-turn chat; the current message sets the topic and follow-ups inherit it.
- Explicit preference extraction: budget, color, material, skin type, origin, capacity, use case.
- Micro-intent extraction with Gemini structured output or deterministic rules, same schema.
- Sensitive-domain safety gate (health, fertility, finance, gambling, politics).
- Synthetic catalog: 36 products from competing advertisers across skincare, sling bags and Japan travel.
- Ad ranking: relevance, constraint fit, quality, bid and estimated utility, with a hard 0.75 floor.
- Bid-free organic options in every non-sensitive section.
- Placement selection: priority ordering, configurable cap (default 2), one slot per advertiser, recorded rejection reasons.
- Grounded "why this matches" explanations.
- Graceful failure when the ad system errors.
- Decision trace with per-component status.
- Query-level vs. MicroIntent comparison.
- Public demo: static Hugging Face Space running the pipeline in the browser (Pyodide).
- 25 automated tests and a 13-case evaluation set.

## Non-goals
- Reproduce Google's proprietary ad auction.
- Use live advertiser data.
- Claim production performance or revenue lift.
- Infer sensitive or historical user traits.
- Perform real checkout or payment.

## Known limitations
- Weights, thresholds and component priors are hand-set, not learned.
- A stated budget is checked per item, not allocated across a multi-item plan.
- Retrieval is category and keyword matching, not semantic search.
- The evaluation set is a smoke test, not a benchmark.

## Next build
- Human-labeled conversation set (150–250, with hard negatives) to calibrate weights and measure Gemini vs. deterministic extraction.
- Batch evaluator reporting safety precision, explanation faithfulness and saturation compliance.
- Postgres + pgvector retrieval and persistent telemetry.
- Budget allocation across multi-item plans.
- Advertiser-facing intent insights, only after the consumer hypothesis is validated.
