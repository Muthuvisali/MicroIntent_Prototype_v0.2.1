from __future__ import annotations
from typing import Dict, List, Tuple
from app.models import (
    ChatRequest,
    ChatResponse,
    DecisionTrace,
    IntentDecision,
    MicroIntent,
    OrganicOption,
    RankedCandidate,
    SponsoredPlacement,
)
from app.services.answer import base_answer, compose_sections
from app.services.explanation import explain, explain_organic
from app.services.intents import extract_explicit_context, extract_micro_intents
from app.services.ranking import rank, rank_organic
from app.services.retrieval import retrieve
from app.services.safety import is_commercially_eligible
from app.services.saturation import MIN_SCORE, placement_priority, select

ORGANIC_PER_SECTION = 2


def _organic_options(intents: List[MicroIntent]) -> Dict[str, List[OrganicOption]]:
    """Organic options are independent of the ad system: no bid, no eligibility gate.

    Sensitive intents get no product listings at all.
    """
    out: Dict[str, List[OrganicOption]] = {}
    for intent in intents:
        if intent.sensitive_domain:
            continue
        ranked = rank_organic(intent, retrieve(intent))[:ORGANIC_PER_SECTION + 1]
        out[intent.id] = [
            OrganicOption(
                product_id=r.product.product_id,
                name=r.product.name,
                merchant=r.product.advertiser,
                price=r.product.price,
                organic_score=r.final_score,
                reason=explain_organic(intent, r.product),
            )
            for r in ranked
        ]
    return out


def _monetize(req: ChatRequest, intents: List[MicroIntent]):
    blocked: List[str] = []
    eligible: List[str] = []
    considered = 0
    candidate_winners: List[Tuple[MicroIntent, RankedCandidate]] = []
    preliminary: Dict[str, IntentDecision] = {}

    for intent in intents:
        base = dict(micro_intent_id=intent.id, label=intent.label, commercial_score=intent.commercial_score)
        # Safety runs before retrieval: sensitive intents never reach the ad inventory.
        if intent.sensitive_domain:
            blocked.append(intent.id)
            preliminary[intent.id] = IntentDecision(status="blocked_sensitive", **base)
            continue
        if not is_commercially_eligible(intent):
            preliminary[intent.id] = IntentDecision(status="not_commercial", **base)
            continue

        eligible.append(intent.id)
        ranked = rank(intent, retrieve(intent))
        considered += len(ranked)
        if not ranked:
            preliminary[intent.id] = IntentDecision(status="no_candidates", **base)
            continue

        top = ranked[0]
        scored = dict(base, top_candidate_score=top.final_score, top_candidate_name=top.product.name)
        if top.final_score < MIN_SCORE:
            preliminary[intent.id] = IntentDecision(status="below_threshold", **scored)
            continue

        candidate_winners.append((intent, top))
        preliminary[intent.id] = IntentDecision(
            status="eligible_not_selected",
            placement_priority=placement_priority(intent, top),
            **scored,
        )

    chosen, rejected = select(candidate_winners, max_sponsored=max(0, min(req.max_sponsored, 3)))

    placements: List[SponsoredPlacement] = []
    for intent, ranked in chosen:
        placements.append(
            SponsoredPlacement(
                micro_intent_id=intent.id,
                micro_intent_label=intent.label,
                product=ranked.product,
                final_score=ranked.final_score,
                explanation=explain(intent, ranked.product),
            )
        )
        preliminary[intent.id] = preliminary[intent.id].model_copy(update={"status": "selected"})
    for intent_id, reason in rejected.items():
        preliminary[intent_id] = preliminary[intent_id].model_copy(update={"status": reason})

    decisions = [preliminary[i.id] for i in intents if i.id in preliminary]
    return placements, decisions, blocked, eligible, considered


def run_pipeline(req: ChatRequest) -> ChatResponse:
    answer = base_answer(req.message)
    intents, extractor_mode, parent_intent = extract_micro_intents(req.message, req.history)

    user_session_text = " ".join(
        [t.content for t in req.history if t.role == "user"] + [req.message]
    )
    explicit_context = extract_explicit_context(user_session_text)

    # Graceful failure: if the ad system or organic retrieval breaks, the answer still ships.
    try:
        placements, decisions, blocked, eligible, considered = _monetize(req, intents)
        monetization_status = "ok"
    except Exception as exc:
        placements, decisions, blocked, eligible, considered = [], [], [], [], 0
        monetization_status = f"failed:{type(exc).__name__}"
    try:
        organic = _organic_options(intents)
    except Exception:
        organic = {}

    sponsored_ids = {p.product.product_id for p in placements}
    for intent_id, options in organic.items():
        organic[intent_id] = [o for o in options if o.product_id not in sponsored_ids][:ORGANIC_PER_SECTION]

    sections = compose_sections(req.message, intents, placements, organic)
    session_score = max((i.commercial_score for i in intents), default=0.0)
    if session_score < 0.20:
        intent_band = "none"
    elif session_score < 0.45:
        intent_band = "low"
    elif session_score < 0.70:
        intent_band = "medium"
    else:
        intent_band = "high"

    trace = DecisionTrace(
        extractor_mode=extractor_mode,
        parent_intent=parent_intent,
        session_commercial_score=round(session_score, 3),
        commercial_intent_band=intent_band,
        explicit_session_context=explicit_context,
        micro_intents=intents,
        decisions=decisions,
        blocked_intents=blocked,
        eligible_intents=eligible,
        placements_considered=considered,
        placements_selected=len(placements),
        monetization_status=monetization_status,
    )
    return ChatResponse(
        answer=answer,
        sections=sections,
        placements=placements,
        trace=trace,
    )
