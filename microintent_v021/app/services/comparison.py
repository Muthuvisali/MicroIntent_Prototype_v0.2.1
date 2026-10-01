from __future__ import annotations
from app.models import ChatRequest, StrategyComparison
from app.services.baseline import query_level_baseline
from app.services.pipeline import run_pipeline


def compare_strategies(req: ChatRequest) -> StrategyComparison:
    result = run_pipeline(req)
    baseline = query_level_baseline(req)
    return StrategyComparison(
        query_level=baseline,
        micro_intent=result.placements,
        extracted_preferences=result.trace.explicit_session_context,
        note=(
            "The query-level baseline intentionally selects one broad-category sponsored result. "
            "MicroIntent can select up to the requested cap across independently scored answer components. "
            "This is a product experiment simulator, not a reproduction of Google's ad auction."
        ),
    )
