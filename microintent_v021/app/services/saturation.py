from __future__ import annotations
from typing import Dict, List, Tuple
from app.models import MicroIntent, RankedCandidate

MIN_SCORE = 0.75


def placement_priority(intent: MicroIntent, candidate: RankedCandidate) -> float:
    """Order eligible slots by how commercial the need is and how good the best ad is."""
    return round(0.5 * intent.commercial_score + 0.5 * candidate.final_score, 3)


def select(
    candidates: List[Tuple[MicroIntent, RankedCandidate]],
    max_sponsored: int = 2,
) -> Tuple[List[Tuple[MicroIntent, RankedCandidate]], Dict[str, str]]:
    """Pick at most `max_sponsored` placements.

    Returns the selected placements and, for every rejected intent id, the reason:
    - "not_selected_diversity": the same advertiser already holds a slot in this answer
      (reported first, even if the cap was also reached, because it is the stronger reason)
    - "not_selected_saturation": the cap was reached by higher-priority placements
    """
    valid = [x for x in candidates if x[1].final_score >= MIN_SCORE]
    valid.sort(key=lambda x: placement_priority(*x), reverse=True)
    selected: List[Tuple[MicroIntent, RankedCandidate]] = []
    rejected: Dict[str, str] = {}
    seen_advertisers = set()
    seen_categories = set()
    for intent, cand in valid:
        if cand.product.advertiser in seen_advertisers or cand.product.category in seen_categories:
            rejected[intent.id] = "not_selected_diversity"
            continue
        if len(selected) >= max_sponsored:
            rejected[intent.id] = "not_selected_saturation"
            continue
        selected.append((intent, cand))
        seen_advertisers.add(cand.product.advertiser)
        seen_categories.add(cand.product.category)
    return selected, rejected
