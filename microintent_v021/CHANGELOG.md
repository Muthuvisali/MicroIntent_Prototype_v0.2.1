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

## v0.2.2 — case-study alignment
- Added the Japan-trip sequential pattern from the case study (flight, hotel, rail pass, activities, mobile data, dining) with 12 synthetic travel products.
- Political-context safety now blocks voting/candidate questions (e.g. "Which candidate should I vote for?"), matching the case study's safety table.
- Query-level baseline recognizes the Japan-trip product family.
- Added 3 tests and 3 evaluation cases for the above; UI gains Japan-trip and political-safety sample buttons.
- Version strings aligned to 0.2.2.

## v0.3.0 — case-study claims made real
- **Three surfaces.** Every answer section now shows AI guidance, *organic options* (ranked on relevance, constraint fit and quality, with no bid input), and at most one sponsored match. A sponsored product is never duplicated in the organic list, and sensitive contexts list no products at all.
- **Independent component scoring.** Deterministic mode scores each answer component separately (e.g. sunscreen 0.91 vs toner 0.67) instead of one score for the whole answer.
- **Explicit placement decisions.** Eligible slots are ordered by placement priority (0.5 × commercial intent + 0.5 × ad score). Rejections are recorded as `not_selected_saturation` or `not_selected_diversity`; the diversity rule allows one slot per advertiser per answer.
- **Graceful failure.** If retrieval, ranking or explanation fails, `/chat` still returns the full organic answer and records `monetization_status: failed:<Error>` in the trace.
- **Retrieval fix.** Exact-category inventory is preferred over word overlap, so a "faux leather" slot can no longer be filled by a genuine-leather ad.
- Explanations now read "Why this matches: …" and remain limited to user-stated constraints and catalog facts.
- UI: organic-options block per section and a per-component decision table in the sidebar.
- Tests: 15 automated tests (was 10); evaluation 13/13.

## v0.3.1 — Gemini mode fixes and public demo
- Gemini is given the catalog's component labels and told to decompose routines, plans and category browses into one item per component; free-form labels ("cleansing oil", "JR Pass") are mapped onto catalog categories, and duplicates are merged.
- Gemini returns a short guidance line per component, used as section text where no curated copy exists (replaces the "Consider this need separately…" placeholder).
- Gemini is told to score components independently rather than giving every step the same score.
- One automatic retry on a transient 503 before falling back to deterministic extraction.
- The answer no longer assumes "dry skin" unless the user said so; informational questions ("history of…") no longer get routine text.
- Topic scoping: the current message decides the topic. Earlier turns are used only for follow-ups ("under $40", "it also has to fit a Kindle"), so "what is photosynthesis" after a skincare conversation is no longer treated as skincare, and preferences from an old topic no longer carry into a new one. Safety still checks the whole conversation.
- Gemini is told to analyze the latest message and ignore earlier topics after a topic change.
- Public demo mode: `MICROINTENT_DEMO=1` forces deterministic extraction, `/health` reports it, and the UI shows a demo banner. Dockerfile for Hugging Face Spaces (port 7860, non-root user; `.env` and `.venv` excluded from the image).
- Request limits for a public endpoint: message ≤ 1,000 chars, ≤ 40 history turns, sponsored cap 0–3.
- 25 automated tests (was 15).
