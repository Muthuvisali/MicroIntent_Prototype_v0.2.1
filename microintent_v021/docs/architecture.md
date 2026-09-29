# MicroIntent v0.2 Architecture

## Runtime pipeline

`conversation → context extraction → micro-intent extraction → safety gate → commercial eligibility → candidate retrieval → contextual ranking → saturation → grounded explanation → inline answer composition → decision trace`

## Extractor modes

### Deterministic
Used for repeatable local development and evaluation. Rule-based extraction maps the current conversation into a stable `MicroIntent` schema.

### Gemini structured output
When `MICROINTENT_MODE=gemini` and `GEMINI_API_KEY` are configured, the extractor calls the Google Gen AI SDK and requests a typed Pydantic response. The downstream ranking pipeline is unchanged.

If Gemini is unavailable, the prototype falls back to deterministic extraction. The active mode is exposed in the decision trace so failure is visible rather than silent.

## Design principles

1. **The ad subsystem is optional.** Base answer generation must still work if commercial services fail.
2. **Only explicit current-session preferences are used.** No historical profiling is required for the MVP.
3. **The LLM does not pick the winning ad.** It produces structured intent; retrieval and ranking are downstream services.
4. **Sensitive contexts are blocked before candidate retrieval.**
5. **Scarcity is deliberate.** The saturation controller can reject otherwise eligible placements.
6. **Every placement is explainable.** The trace exposes intent, eligibility, candidate score, and selection outcome.

## Strategy experiment

`POST /compare` contrasts:

- **Query-level baseline:** one broad-category sponsored recommendation.
- **MicroIntent strategy:** answer components are independently scored and up to the requested cap can receive a sponsored match.

The comparison is an experiment simulator, not a claim about Google's proprietary auction or production performance.
