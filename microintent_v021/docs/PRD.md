# MicroIntent MVP PRD — v0.2

## Objective
Test whether component-level, context-aware sponsored matching can produce more useful commercial recommendations than generic query-level advertising without degrading trust.

## Product principles
1. Organic guidance stays primary.
2. Sponsored content is clearly labeled and visually distinct.
3. High commercial precision beats ad volume.
4. Sensitive contexts are blocked before candidate retrieval.
5. Only explicit current-session preferences are used in the MVP.
6. A failed LLM or ad subsystem must not block the base answer.
7. The system must expose why a placement was selected.

## v0.2 functional scope
- Single-turn and multi-turn chat input.
- Explicit session-context accumulation.
- Deterministic or Gemini structured-output micro-intent extraction.
- Sensitive-domain safety gate.
- Synthetic merchant inventory with multiple competing products per category.
- Contextual ranking using relevance, constraint fit, quality, bid, and estimated user utility.
- Ad saturation cap.
- Inline placement inside the relevant answer component.
- Grounded “why this matches” explanation.
- Decision trace with per-intent selection status.
- Query-level vs MicroIntent comparison endpoint.
- Expanded automated evaluation set.

## Non-goals
- Reproduce Google's proprietary ad auction.
- Use live advertiser data.
- Claim production performance or revenue lift.
- Infer sensitive or historical user traits.
- Perform real checkout or payment.

## Next build
- human-rated relevance benchmark
- larger adversarial evaluation set
- persistent telemetry / experiment storage
- semantic retrieval with embeddings
- portfolio analytics dashboard
- deployable cloud configuration
