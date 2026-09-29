from __future__ import annotations
from typing import Dict, List, Tuple
from app.models import (
    ChatRequest,
    ChatResponse,
    DecisionTrace,
    IntentDecision,
    RankedCandidate,
    SponsoredPlacement,
)
from app.services.answer import base_answer, compose_sections
from app.services.explanation import explain
from app.services.intents import extract_explicit_context, extract_micro_intents
from app.services.ranking import rank
from app.services.retrieval import retrieve
from app.services.safety import is_commercially_eligible
from app.services.saturation import MIN_SCORE, select


def run_pipeline(req: ChatRequest) -> ChatResponse:
    answer = base_answer(req.message)
    intents, extractor_mode, parent_intent = extract_micro_intents(req.message, req.history)

    user_session_text = " ".join(
        [t.content for t in req.history if t.role == "user"] + [req.message]
    )
    explicit_context = extract_explicit_context(user_session_text)

    blocked: List[str] = []
    eligible: List[str] = []
    considered = 0
    candidate_winners: List[Tuple[object, RankedCandidate]] = []
    preliminary: Dict[str, IntentDecision] = {}

    for intent in intents:
        if intent.sensitive_domain:
            blocked.append(intent.id)
            preliminary[intent.id] = IntentDecision(
                micro_intent_id=intent.id,
                label=intent.label,
                status="blocked_sensitive",
                commercial_score=intent.commercial_score,
            )
            continue
        if not is_commercially_eligible(intent):
            preliminary[intent.id] = IntentDecision(
                micro_intent_id=intent.id,
                label=intent.label,
                status="not_commercial",
                commercial_score=intent.commercial_score,
            )
            continue

        eligible.append(intent.id)
        ranked = rank(intent, retrieve(intent))
        considered += len(ranked)
        if not ranked:
            preliminary[intent.id] = IntentDecision(
                micro_intent_id=intent.id,
                label=intent.label,
                status="no_candidates",
                commercial_score=intent.commercial_score,
            )
            continue

        top = ranked[0]
        if top.final_score < MIN_SCORE:
            preliminary[intent.id] = IntentDecision(
                micro_intent_id=intent.id,
                label=intent.label,
                status="below_threshold",
                commercial_score=intent.commercial_score,
                top_candidate_score=top.final_score,
                top_candidate_name=top.product.name,
            )
            continue

        candidate_winners.append((intent, top))
        preliminary[intent.id] = IntentDecision(
            micro_intent_id=intent.id,
            label=intent.label,
            status="eligible_not_selected",
            commercial_score=intent.commercial_score,
            top_candidate_score=top.final_score,
            top_candidate_name=top.product.name,
        )

    chosen = select(candidate_winners, max_sponsored=max(0, min(req.max_sponsored, 3)))
    selected_ids = {intent.id for intent, _ in chosen}

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
        d = preliminary[intent.id]
        preliminary[intent.id] = d.model_copy(update={"status": "selected"})

    decisions = [preliminary[i.id] for i in intents if i.id in preliminary]
    sections = compose_sections(req.message, intents, placements)
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
    )
    return ChatResponse(
        answer=answer,
        sections=sections,
        placements=placements,
        trace=trace,
    )
