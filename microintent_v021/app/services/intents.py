from __future__ import annotations
import os
import time
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
    "election", "political candidate", "vote for", "who should i vote", "voting for",
    "ballot", "political party"
]

# Relative purchase need of each answer component, applied in deterministic mode so
# steps in one answer are scored independently. Optional steps (toner, essence) and
# low-ticket extras score lower than core purchases (sunscreen, flight, hotel).
COMPONENT_PRIOR = {
    "oil cleanser": 0.94, "water cleanser": 0.84, "toner": 0.71, "essence": 0.76,
    "serum": 0.89, "moisturizer": 0.87, "sunscreen": 0.97,
    "luxury sling bag": 0.90, "leather sling bag": 0.97, "faux leather sling bag": 0.92,
    "travel sling bag": 0.96, "sport sling bag": 0.85,
    "flight": 0.98, "hotel": 0.96, "rail pass": 0.88, "activities": 0.80,
    "mobile data": 0.78, "dining": 0.70,
}

# Free-form LLM labels are mapped onto catalog categories so retrieval can find inventory.
# Longest phrases are checked first, so "faux leather sling" wins over "leather sling".
LABEL_SYNONYMS = {
    "oil cleanser": ["oil cleanser", "cleansing oil", "cleansing balm", "first cleanse", "oil cleanse"],
    "water cleanser": ["water cleanser", "water-based cleanser", "foam cleanser", "gel cleanser", "second cleanse", "water cleanse"],
    "toner": ["toner"],
    "essence": ["essence"],
    "serum": ["serum", "ampoule"],
    "moisturizer": ["moisturizer", "moisturiser", "face cream", "night cream"],
    "sunscreen": ["sunscreen", "spf", "sun protection"],
    "faux leather sling bag": ["faux leather sling", "vegan leather sling", "vegan sling"],
    "luxury sling bag": ["luxury sling", "designer sling"],
    "leather sling bag": ["leather sling"],
    "travel sling bag": ["travel sling", "anti-theft sling"],
    "sport sling bag": ["sport sling", "running sling", "athletic sling"],
    "flight": ["flight", "airfare", "plane ticket"],
    "hotel": ["hotel", "accommodation", "lodging", "ryokan"],
    "rail pass": ["rail pass", "jr pass", "train pass", "shinkansen"],
    "activities": ["activities", "tours", "sightseeing", "attractions"],
    "mobile data": ["mobile data", "esim", "sim card", "pocket wifi", "pocket wi-fi", "connectivity"],
    "dining": ["dining", "restaurant", "food tour"],
}
_SYNONYM_ORDER = sorted(
    ((phrase, label) for label, phrases in LABEL_SYNONYMS.items() for phrase in phrases),
    key=lambda x: len(x[0]), reverse=True,
)


def canonical_label(label: str) -> str:
    t = label.strip().lower()
    if t in COMPONENT_PRIOR:
        return t
    for phrase, known in _SYNONYM_ORDER:
        if phrase in t:
            return known
    return t


JAPAN_TRIP_WORDS = ["trip", "itinerary", "vacation", "holiday", "visit", "travel to", "traveling to", "travelling to"]

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


FOLLOW_UP_CUES = [" it ", " it's ", " also ", " that one ", " those ", " cheaper ", " instead ", " what about "]


def _topic(text: str):
    t = text.lower()
    if "skincare" in t or "skin care" in t:
        return "skincare"
    if "sling bag" in t:
        return "sling bags"
    if "japan" in t and any(x in t for x in JAPAN_TRIP_WORDS):
        return "japan trip"
    for label, pats in CATEGORY_RULES.items():
        if any(p in t for p in pats):
            return label
    return None


def _is_follow_up(message: str) -> bool:
    t = f" {message.lower().strip()} "
    if any(x in t for x in NONCOMMERCIAL_PATTERNS):
        return False
    return bool(extract_explicit_context(message)) or any(c in t for c in FOLLOW_UP_CUES)


def session_text(message: str, history: List[Turn]) -> str:
    """User text for the *current topic* only.

    The current message sets the topic. A message without a topic of its own inherits the
    most recent topic only when it reads as a follow-up ("black leather under $100",
    "it also has to fit a Kindle"); otherwise it stands alone, so "what is photosynthesis"
    after a skincare conversation is not treated as skincare.
    """
    turns = [x.content for x in history if x.role == "user"] + [message]
    topics = [_topic(x) for x in turns]
    anchor = len(turns) - 1
    if topics[anchor] is None:
        if not _is_follow_up(message):
            return message
        earlier = [i for i in range(anchor) if topics[i] is not None]
        if not earlier:
            return message
        anchor = earlier[-1]
    topic = topics[anchor]
    start = anchor
    for j in range(anchor - 1, -1, -1):
        if topics[j] == topic or (topics[j] is None and _is_follow_up(turns[j])):
            start = j
        else:
            break
    return " ".join(turns[start:anchor] + turns[anchor:])


def _deterministic(message: str, history: List[Turn]) -> Tuple[List[MicroIntent], str]:
    full = session_text(message, history).lower()
    constraints = extract_explicit_context(full)
    # Safety looks at the whole conversation on purpose: a sensitive context stated earlier
    # still blocks monetization of a vague follow-up like "what should I buy?".
    whole_session = " ".join([x.content for x in history if x.role == "user"] + [message]).lower()
    sensitive = any(x in whole_session for x in SENSITIVE)
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
    elif "japan" in full and any(x in full for x in JAPAN_TRIP_WORDS):
        structured_browse = True
        labels = ["flight", "hotel", "rail pass", "activities", "mobile data", "dining"]
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
            score = min(base, 0.98) * COMPONENT_PRIOR.get(label, 1.0)
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
        "non-commercial searches. Identify 1-10 semantically distinct needs. A commercial_score "
        "of 0 means no purchase/service-selection intent; 1 means explicit near-term transaction intent. "
        "Do not inflate informational research merely because a product could theoretically exist. "
        "Use only preferences explicitly stated in this session; do not infer demographic, health, "
        "financial, political, or historical-user attributes. Mark an item sensitive when monetizing "
        "that intent would be inappropriate or restricted. Prefer meaningful micro-intents over redundant variants.\n\n"
        "DECOMPOSITION RULES:\n"
        "- For a routine, plan, or category browse, return one item per component "
        "(e.g. each routine step, each part of a trip, each bag category), not one item for the whole request.\n"
        "- When a component matches one of these known labels, use the label exactly: "
        + ", ".join(COMPONENT_PRIOR) + ".\n"
        "- Otherwise use a short product or service noun phrase (e.g. 'eye cream', 'sheet mask'). "
        "Never use words like guide, tips, routine, products, sets or essentials in a label.\n"
        "- guidance: one or two neutral sentences on what to look for in that component. "
        "No brand names, and no preferences the user did not state.\n"
        "- Analyze the LATEST user message. Use earlier turns only when the latest message is a "
        "follow-up to them (e.g. adds a budget or color). If it changes topic, ignore earlier topics.\n\n"
        "SCORING GUIDE:\n"
        "0.00-0.19 = informational/non-commercial\n"
        "0.20-0.44 = weak/latent commercial possibility\n"
        "0.45-0.69 = active consideration/comparison\n"
        "0.70-0.89 = strong shopping/booking intent\n"
        "0.90-1.00 = explicit transaction/near-purchase intent\n\n"
        "SCORING RULES:\n"
        "- Score each component independently. Components rarely share one score: staples the user "
        "must acquire to follow the plan (e.g. sunscreen, a flight) score higher than optional extras "
        "(e.g. a sheet mask, a food tour).\n"
        "- Asking to build a routine or plan means the user will need its components, so core "
        "components are at least active consideration. Purely informational requests (history, "
        "explanations, comparisons of concepts) stay low.\n\n"
        "SESSION:\n" + session_text
    )
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=LLMIntentExtraction,
        temperature=0.0,
    )
    try:
        response = client.models.generate_content(model=model, contents=prompt, config=config)
    except Exception as exc:
        # One retry for transient overload (503); anything else falls back to deterministic.
        if "503" not in str(exc) and "UNAVAILABLE" not in str(exc):
            raise
        time.sleep(1.5)
        response = client.models.generate_content(model=model, contents=prompt, config=config)
    parsed = response.parsed
    if not parsed:
        raise RuntimeError("Gemini returned no structured intent payload")
    if not isinstance(parsed, LLMIntentExtraction):
        parsed = LLMIntentExtraction.model_validate(parsed)

    intents: List[MicroIntent] = []
    for item in parsed.items:
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
        label = canonical_label(item.label)
        existing = next((i for i in intents if i.label == label), None)
        if existing:
            # Two LLM items mapped to one catalog category: keep one, with the stronger score.
            existing.commercial_score = max(existing.commercial_score, round(item.commercial_score, 3))
            existing.sensitive_domain = existing.sensitive_domain or item.sensitive_domain
            existing.constraints.update(constraints)
            continue
        intents.append(
            MicroIntent(
                id=f"mi_{len(intents) + 1:03d}",
                label=label,
                commercial_score=round(item.commercial_score, 3),
                constraints=constraints,
                sensitive_domain=item.sensitive_domain,
                guidance=item.guidance.strip(),
            )
        )
    if not intents:
        return _deterministic(message, history)
    return intents, parsed.parent_intent.strip()


def extract_micro_intents(message: str, history: List[Turn]) -> Tuple[List[MicroIntent], str, str]:
    requested = os.getenv("MICROINTENT_MODE", "auto").lower().strip()
    if os.getenv("MICROINTENT_DEMO") == "1":
        requested = "deterministic"
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
