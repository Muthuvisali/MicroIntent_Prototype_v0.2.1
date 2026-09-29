from __future__ import annotations
from typing import Dict, List
from app.models import AnswerSection, MicroIntent, SponsoredPlacement

SECTION_COPY: Dict[str, tuple[str, str]] = {
    "oil cleanser": (
        "1. Oil cleanser",
        "Start with an oil-based first cleanse to remove sunscreen, makeup, and oil-soluble residue. Keep it gentle and emulsify thoroughly before rinsing.",
    ),
    "water cleanser": (
        "2. Water-based cleanser",
        "Follow with a mild water-based cleanser. For dry skin, prioritize a non-stripping formula and avoid cleansing longer than needed.",
    ),
    "toner": (
        "3. Toner",
        "Use a hydrating toner if it adds comfort and hydration. This step is optional; it should support the routine rather than make it more complicated.",
    ),
    "essence": (
        "4. Essence",
        "An essence can add a lightweight hydration layer. Choose one based on your skin goal rather than adding it simply because it is part of a traditional multi-step routine.",
    ),
    "serum": (
        "5. Serum",
        "Use one targeted serum rather than stacking many actives. For a hydration-focused routine, look for humectant and barrier-supporting ingredients.",
    ),
    "moisturizer": (
        "6. Moisturizer",
        "Seal in hydration with a moisturizer that suits your skin type. Dry skin generally benefits from a richer barrier-supporting texture.",
    ),
    "sunscreen": (
        "7. Sunscreen",
        "Finish the morning routine with broad-spectrum sunscreen. Consistency and adequate application matter more than maximizing the number of earlier steps.",
    ),
    "luxury sling bag": (
        "Luxury / design-led",
        "Prioritize construction, hardware, strap comfort, warranty, and whether the bag still works for your everyday capacity needs—not just the logo.",
    ),
    "leather sling bag": (
        "Genuine leather",
        "For leather options, compare leather type, weight, closure security, strap adjustability, and whether the dimensions fit what you actually carry.",
    ),
    "faux leather sling bag": (
        "Faux / vegan leather",
        "Faux leather can deliver the look at a lower price. Check abrasion resistance, edge finishing, lining quality, and return policy.",
    ),
    "travel sling bag": (
        "Travel / security",
        "For travel, prioritize secure zippers, passport access, strap comfort, low bulk, and enough capacity for your phone, wallet, and travel documents.",
    ),
    "sport sling bag": (
        "Sport / lightweight",
        "For active use, prioritize low weight, breathable contact surfaces, secure fit, and materials that are easy to clean.",
    ),
}


def base_answer(message: str) -> str:
    t = message.lower()
    if "skincare" in t:
        return (
            "A useful Korean-style routine should be organized around function, not around forcing every possible step. "
            "For dry skin, keep cleansing gentle, add hydration where it helps, protect the barrier, and finish with sunscreen."
        )
    if "sling bag" in t:
        return (
            "A useful way to compare sling bags is by the job they need to do: design-led, leather, faux leather, travel/security, or sport/lightweight. "
            "Capacity, comfort, closure, materials, return policy, and price are usually more decision-relevant than category labels alone."
        )
    return (
        "Here is a direct answer to your question. This prototype focuses on deciding whether a commercial recommendation is appropriate; "
        "it does not attempt to reproduce a production search engine."
    )


def compose_sections(
    message: str,
    intents: List[MicroIntent],
    placements: List[SponsoredPlacement],
) -> List[AnswerSection]:
    placement_by_id = {p.micro_intent_id: p for p in placements}
    sections: List[AnswerSection] = []
    for intent in intents:
        if intent.label == "general information":
            continue
        title, body = SECTION_COPY.get(
            intent.label,
            (intent.label.title(), f"Consider this need separately when evaluating your options: {intent.label}."),
        )
        sections.append(
            AnswerSection(
                micro_intent_id=intent.id,
                title=title,
                body=body,
                sponsored=placement_by_id.get(intent.id),
            )
        )
    if not sections:
        sections.append(
            AnswerSection(
                title="Answer",
                body=base_answer(message),
            )
        )
    return sections
