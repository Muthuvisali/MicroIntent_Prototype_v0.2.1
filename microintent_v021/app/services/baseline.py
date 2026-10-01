from __future__ import annotations
from typing import List
from app.models import BaselinePlacement, ChatRequest, Product
from app.services.intents import JAPAN_TRIP_WORDS, extract_explicit_context, session_text
from app.services.retrieval import load_products


def _constraint_fit(product: Product, constraints: dict) -> float:
    tests = []
    if "max_price" in constraints:
        tests.append(product.price <= float(constraints["max_price"]))
    if "color" in constraints:
        tests.append(str(product.attributes.get("color", "")).lower() == str(constraints["color"]).lower())
    if "material" in constraints:
        tests.append(str(product.attributes.get("material", "")).lower() == str(constraints["material"]).lower())
    if "skin_type" in constraints:
        tests.append(str(constraints["skin_type"]).lower() in [str(x).lower() for x in product.attributes.get("skin_types", [])])
    if "origin_preference" in constraints:
        tests.append(str(product.attributes.get("origin", "")).lower() == str(constraints["origin_preference"]).lower())
    if "capacity_requirement" in constraints:
        tests.append(str(constraints["capacity_requirement"]).lower() in [str(x).lower() for x in product.attributes.get("fits", [])])
    if "use_case" in constraints:
        tests.append(str(constraints["use_case"]).lower() in [str(x).lower() for x in product.attributes.get("use_cases", [])])
    return sum(tests) / len(tests) if tests else 0.75


def query_level_baseline(req: ChatRequest) -> BaselinePlacement:
    full = session_text(req.message, req.history).lower()
    constraints = extract_explicit_context(full)
    products = load_products()

    if "skincare" in full:
        family: List[Product] = [p for p in products if p.product_id.startswith("skin")]
    elif "sling bag" in full or "sling bags" in full:
        family = [p for p in products if p.product_id.startswith("bag")]
    elif "japan" in full and any(x in full for x in JAPAN_TRIP_WORDS):
        family = [p for p in products if p.product_id.startswith("trip")]
    else:
        return BaselinePlacement(
            explanation="The query-level baseline found no broad commercial category for this request."
        )

    if not family:
        return BaselinePlacement(explanation="No baseline products were available.")

    max_bid = max(p.bid for p in family) or 1.0
    scored = []
    for product in family:
        fit = _constraint_fit(product, constraints)
        bid = product.bid / max_bid
        score = 0.45 * fit + 0.30 * product.quality_score + 0.25 * bid
        scored.append((score, product, fit))
    scored.sort(key=lambda x: x[0], reverse=True)
    score, product, fit = scored[0]
    return BaselinePlacement(
        product=product,
        score=round(score, 3),
        explanation=(
            "Query-level baseline: one sponsored result selected from the broad query category "
            f"using explicit session constraints, product quality, and simulated bid (constraint fit {fit:.0%})."
        ),
    )
