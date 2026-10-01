from __future__ import annotations
from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: List[Turn] = Field(default_factory=list, max_length=40)
    max_sponsored: int = Field(default=2, ge=0, le=3)


class MicroIntent(BaseModel):
    id: str
    label: str
    commercial_score: float = Field(ge=0.0, le=1.0)
    constraints: Dict[str, object] = Field(default_factory=dict)
    sensitive_domain: bool = False
    guidance: str = ""


class Product(BaseModel):
    product_id: str
    advertiser: str
    name: str
    category: str
    price: float
    attributes: Dict[str, object]
    bid: float
    quality_score: float


class RankedCandidate(BaseModel):
    product: Product
    relevance: float
    constraint_fit: float
    user_utility: float
    normalized_bid: float
    final_score: float


class SponsoredPlacement(BaseModel):
    micro_intent_id: str
    micro_intent_label: str
    product: Product
    final_score: float
    explanation: str


class OrganicOption(BaseModel):
    """Non-sponsored option ranked without any bid input."""
    product_id: str
    name: str
    merchant: str
    price: float
    organic_score: float
    reason: str


class AnswerSection(BaseModel):
    micro_intent_id: Optional[str] = None
    title: str
    body: str
    organic: List[OrganicOption] = Field(default_factory=list)
    sponsored: Optional[SponsoredPlacement] = None


class IntentDecision(BaseModel):
    micro_intent_id: str
    label: str
    status: Literal[
        "blocked_sensitive",
        "not_commercial",
        "no_candidates",
        "below_threshold",
        "eligible_not_selected",
        "not_selected_saturation",
        "not_selected_diversity",
        "selected",
    ]
    commercial_score: float
    top_candidate_score: Optional[float] = None
    top_candidate_name: Optional[str] = None
    placement_priority: Optional[float] = None


class DecisionTrace(BaseModel):
    extractor_mode: str
    parent_intent: str = ""
    session_commercial_score: float = Field(default=0.0, ge=0.0, le=1.0)
    commercial_intent_band: Literal["none", "low", "medium", "high"] = "none"
    explicit_session_context: Dict[str, object] = Field(default_factory=dict)
    micro_intents: List[MicroIntent]
    decisions: List[IntentDecision]
    blocked_intents: List[str]
    eligible_intents: List[str]
    placements_considered: int
    placements_selected: int
    monetization_status: str = "ok"


class ChatResponse(BaseModel):
    answer: str
    sections: List[AnswerSection]
    placements: List[SponsoredPlacement]
    trace: DecisionTrace


class BaselinePlacement(BaseModel):
    product: Optional[Product] = None
    score: Optional[float] = None
    explanation: Optional[str] = None


class StrategyComparison(BaseModel):
    query_level: BaselinePlacement
    micro_intent: List[SponsoredPlacement]
    extracted_preferences: Dict[str, object]
    note: str


# Gemini structured-output schema. Keep this narrow and typed so the model
# cannot invent arbitrary profile fields.
class LLMIntentItem(BaseModel):
    label: str
    guidance: str = ""
    commercial_score: float = Field(ge=0.0, le=1.0)
    sensitive_domain: bool = False
    max_price: Optional[float] = None
    color: Optional[str] = None
    material: Optional[str] = None
    skin_type: Optional[str] = None
    origin_preference: Optional[str] = None
    capacity_requirement: Optional[str] = None
    use_case: Optional[str] = None


class LLMIntentExtraction(BaseModel):
    parent_intent: str
    items: List[LLMIntentItem]
