# Changelog

## v0.2.0

### Added
- optional Gemini structured-output micro-intent extraction
- deterministic fallback with extractor mode exposed in trace
- multi-turn current-session preference accumulation
- inline sponsored placements inside answer sections
- query-level vs MicroIntent comparison endpoint and UI
- richer decision trace with per-intent selection status
- multiple competing synthetic products per category
- `pytest.ini` / test path fix for plain `pytest`
- 10-scenario evaluation set

### Changed
- commercial scoring is more conservative for informational single-category queries
- synthetic ranking now demonstrates relevance/constraint fit competing with higher bids
- UI redesigned around a conversational demo rather than separate result cards

### Guardrails
- sensitive intents are blocked before retrieval
- only explicit current-session preferences are used
- sponsored density remains capped at 1–3 placements

## v0.2.1
- Added session-level commercial intent score for every query.
- Added intent bands: none / low / medium / high.
- Added parent-intent visibility in the decision trace.
- Added AUTO mode: Gemini semantic extraction when an API key is configured, conservative deterministic fallback otherwise.
- Generic commercial searches can now score highly even when the synthetic inventory has no matching ad candidate.
- Kept intent scoring separate from ad eligibility/inventory matching.
