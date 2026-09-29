from __future__ import annotations
import os
import re
from typing import Dict, List, Tuple
from app.models import LLMIntentExtraction, MicroIntent, Turn

CATEGORY_RULES = {
    "oil cleanser": ["oil cleanser", "cleansing oil", "first cleanse"],
    "water cleanser": ["water cleanser", "gel cleanser", "foam cleanser", "second cleanse"],
    "toner": ["toner"],
    "essence": ["essence"],
    "serum": ["serum"],
    "moisturizer": ["moisturizer", "moisturiser", "cream"],
    "sunscreen": ["sunscreen", "spf"],
    "running shoes": ["running shoe", "running shoes"],
    "laptop": ["laptop"],
}

SENSITIVE = [
    "cancer", "chest pain", "pregnant", "pregnancy", "fertility", "trying to conceive",
    "severe acne", "diagnosis", "prescription", "loan approval", "credit score", "gambling",
    "election", "political candidate"
]

HIGH_INTENT = [
    "buy", "purchase", "shop", "order", "book", "reserve", "deal", "discount", "coupon",
    "price", "pricing", "cost", "under $", "below $", "best", "recommend", "compare",
    "which should i get", "which one should i get", "where can i buy", "for sale"
]
MEDIUM_INTENT = [
    "options", "types", "kinds", "top", "review", "reviews", "alternative", "alternatives",
    "good for", "what should i use", "what should i get", "looking for", "need a"
]
NONCOMMERCIAL_PATTERNS = [
    "explain", "what is", "why does", "how does", "history of", "meaning of", "definition of",
    "summarize", "who is", "when did"
]


def extract_explicit_context(text: str) -> Dict[str, object]:
    """Extract only preferences explicitly stated in the current session text."""
    t = text.lower()
    c: Dict[str, object] = {}
    m = re.search(r"(?:under|below|less than|<=?)\s*\$?(\d{1,5})", t)
    if m:
        c["max_price"] = float(m.group(1))
    for color in ["black", "brown", "red", "blue", "white", "green"]:
        if color in t:
            c["color"] = color
    if "faux leather" in t or "vegan leather" in t:
        c["material"] = "faux leather"
    elif "leather" in t:
        c["material"] = "leather"
    for skin in ["dry", "oily", "combination", "sensitive"]:
        if f"{skin} skin" in t:
            c["skin_type"] = skin
    if "korean" in t:
        c["origin_preference"] = "Korean"
    if "kindle" in t:
        c["capacity_requirement"] = "Kindle"
    if "travel" in t or "airport" in t:
        c["use_case"] = "travel"
    return c


def _generic_query_score(full: str, constraints: Dict[str, object]) -> float:
    """Fallback score for *every* query, even if its category is unknown.

    This is deliberately transparent and conservative. Gemini mode is the preferred
    general-purpose semantic scorer; this rule scorer exists so the UI never loses
    the commercial-intent signal when the model is unavailable.
    """
    t = full.lower()
    if any(x in t for x in SENSITIVE):
        return 0.0

    score = 0.18
    high_hits = sum(1 for x in HIGH_INTENT if x in t)
    medium_hits = sum(1 for x in MEDIUM_INTENT if x in t)
    noncommercial_hits = sum(1 for x in NONCOMMERCIAL_PATTERNS if x in t)

    score += min(high_hits * 0.18, 0.54)
    score += min(medium_hits * 0.09, 0.27)
    if constraints:
        score += min(0.04 * len(constraints), 0.16)
    if re.search(r"\$\s*\d+", t) or re.search(r"\b\d+\s*(?:dollars|usd)\b", t):
        score += 0.12
    if noncommercial_hits and high_hits == 0 and medium_hits == 0:
        score -= min(0.08 * noncommercial_hits, 0.16)

    return round(max(0.02, min(score, 0.98)), 2)


def _fallback_label(message: str, score: float) -> str:
    # Keep the label useful in the trace without pretending we know the taxonomy.
    cleaned = re.sub(r"\s+", " ", message.strip())
    if score >= 0.55:
        return "unmapped commercial intent"
    return "general information"


def _deterministic(message: str, history: List[Turn]) -> Tuple[List[MicroIntent], str]:
    full = " ".join([x.content for x in history if x.role == "user"] + [message]).lower()
    constraints = extract_explicit_context(full)
    sensitive = any(x in full for x in SENSITIVE)
    labels: List[str] = []
    structured_browse = False

    if "skincare" in full and ("routine" in full or "step" in full):
        structured_browse = True
        labels = [
            "oil cleanser", "water cleanser", "toner", "essence",
            "serum", "moisturizer", "sunscreen"
        ]
    elif "sling bag" in full or "sling bags" in full:
        structured_browse = True
        if any(x in full for x in ["types", "kinds", "recommend", "best", "women", "woman"]):
            labels = [
                "luxury sling bag", "leather sling bag", "faux leather sling bag",
                "travel sling bag", "sport sling bag"
            ]
        else:
            labels = [
                "leather sling bag" if "leather" in full else
                "travel sling bag" if "travel" in full else
                "sling bag"
            ]
    else:
        for label, pats in CATEGORY_RULES.items():
            if any(p in full for p in pats):
                labels.append(label)

    generic_score = _generic_query_score(full, constraints)
    if not labels:
        labels = [_fallback_label(message, generic_score)]

    out: List[MicroIntent] = []
    for i, label in enumerate(dict.fromkeys(labels), 1):
        if label in {"general information", "unmapped commercial intent"}:
            score = generic_score
        else:
            base = 0.68 if structured_browse else 0.45
            if any(x in full for x in HIGH_INTENT):
                base += 0.18
            if constraints:
                base += 0.08
            score = min(base, 0.98)
        out.append(
            MicroIntent(
                id=f"mi_{i:03d}",
                label=label,
                commercial_score=round(score, 2),
                constraints=constraints.copy(),
                sensitive_domain=sensitive,
            )
        )
    parent = re.sub(r"\s+", " ", message.strip())[:120]
    return out, parent


def _gemini(message: str, history: List[Turn]) -> Tuple[List[MicroIntent], str]:
    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    client = genai.Client(api_key=api_key)
    session_text = "\n".join(
        [f"{turn.role.upper()}: {turn.content}" for turn in history]
        + [f"USER: {message}"]
    )
    prompt = (
        "Analyze this conversational search session for a sponsored-recommendation prototype. "
        "You MUST return a commercial-intent assessment for every search, including clearly "
        "non-commercial searches. Identify 1-6 semantically distinct needs. A commercial_score "
        "of 0 means no purchase/service-selection intent; 1 means explicit near-term transaction intent. "
        "Do not inflate informational research merely because a product could theoretically exist. "
        "Use only preferences explicitly stated in this session; do not infer demographic, health, "
        "financial, political, or historical-user attributes. Mark an item sensitive when monetizing "
        "that intent would be inappropriate or restricted. Prefer meaningful micro-intents over redundant variants.\n\n"
        "SCORING GUIDE:\n"
        "0.00-0.19 = informational/non-commercial\n"
        "0.20-0.44 = weak/latent commercial possibility\n"
        "0.45-0.69 = active consideration/comparison\n"
        "0.70-0.89 = strong shopping/booking intent\n"
        "0.90-1.00 = explicit transaction/near-purchase intent\n\n"
        "SESSION:\n" + session_text
    )
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=LLMIntentExtraction,
            temperature=0.0,
        ),
    )
    parsed = response.parsed
    if not parsed:
        raise RuntimeError("Gemini returned no structured intent payload")
    if not isinstance(parsed, LLMIntentExtraction):
        parsed = LLMIntentExtraction.model_validate(parsed)

    intents: List[MicroIntent] = []
    for idx, item in enumerate(parsed.items, 1):
        constraints = {
            k: v
            for k, v in {
                "max_price": item.max_price,
                "color": item.color,
                "material": item.material,
                "skin_type": item.skin_type,
                "origin_preference": item.origin_preference,
                "capacity_requirement": item.capacity_requirement,
                "use_case": item.use_case,
            }.items()
            if v is not None
        }
        intents.append(
            MicroIntent(
                id=f"mi_{idx:03d}",
                label=item.label.strip().lower(),
                commercial_score=round(item.commercial_score, 3),
                constraints=constraints,
                sensitive_domain=item.sensitive_domain,
            )
        )
    if not intents:
        return _deterministic(message, history)
    return intents, parsed.parent_intent.strip()


def extract_micro_intents(message: str, history: List[Turn]) -> Tuple[List[MicroIntent], str, str]:
    requested = os.getenv("MICROINTENT_MODE", "auto").lower().strip()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    should_try_gemini = requested == "gemini" or (requested == "auto" and bool(api_key))
    if should_try_gemini:
        try:
            intents, parent = _gemini(message, history)
            return intents, "gemini", parent
        except Exception as exc:
            intents, parent = _deterministic(message, history)
            return intents, f"deterministic_fallback:{type(exc).__name__}", parent

    intents, parent = _deterministic(message, history)
    return intents, "deterministic", parent
