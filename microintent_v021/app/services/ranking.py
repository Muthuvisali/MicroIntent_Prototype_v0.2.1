from __future__ import annotations
from typing import List
from app.models import MicroIntent, Product, RankedCandidate

def _match(intent: MicroIntent, p: Product):
    c=intent.constraints
    fits=[]
    if "max_price" in c: fits.append(p.price <= float(c["max_price"]))
    if "color" in c: fits.append(str(p.attributes.get("color","")).lower()==str(c["color"]).lower())
    if "material" in c: fits.append(str(p.attributes.get("material","")).lower()==str(c["material"]).lower())
    if "skin_type" in c:
        fits.append(str(c["skin_type"]).lower() in [str(x).lower() for x in p.attributes.get("skin_types",[])])
    if "origin_preference" in c: fits.append(str(p.attributes.get("origin","")).lower()==str(c["origin_preference"]).lower())
    if "capacity_requirement" in c:
        fits.append(str(c["capacity_requirement"]).lower() in [str(x).lower() for x in p.attributes.get("fits",[])])
    if "use_case" in c:
        fits.append(str(c["use_case"]).lower() in [str(x).lower() for x in p.attributes.get("use_cases",[])])
    constraint_fit = sum(fits)/len(fits) if fits else .8
    label=intent.label.lower(); cat=p.category.lower()
    relevance=.95 if cat==label else .88 if cat in label or label in cat else .72
    return relevance, constraint_fit

def rank(intent: MicroIntent, products: List[Product]) -> List[RankedCandidate]:
    if not products: return []
    max_bid=max(p.bid for p in products) or 1
    out=[]
    for p in products:
        rel,fit=_match(intent,p)
        bid=p.bid/max_bid
        utility=(rel+fit)/2
        score=.40*rel + .20*fit + .15*p.quality_score + .15*bid + .10*utility
        out.append(RankedCandidate(product=p,relevance=round(rel,3),constraint_fit=round(fit,3),user_utility=round(utility,3),normalized_bid=round(bid,3),final_score=round(score,3)))
    return sorted(out,key=lambda x:x.final_score,reverse=True)


def rank_organic(intent: MicroIntent, products: List[Product]) -> List[RankedCandidate]:
    """Organic ordering: relevance, constraint fit and quality only. Bid is never an input."""
    out = []
    for p in products:
        rel, fit = _match(intent, p)
        utility = (rel + fit) / 2
        score = .50 * rel + .30 * fit + .20 * p.quality_score
        out.append(RankedCandidate(product=p, relevance=round(rel, 3), constraint_fit=round(fit, 3), user_utility=round(utility, 3), normalized_bid=0.0, final_score=round(score, 3)))
    return sorted(out, key=lambda x: x.final_score, reverse=True)
