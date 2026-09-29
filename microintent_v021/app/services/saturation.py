from __future__ import annotations
from typing import List, Tuple
from app.models import MicroIntent, RankedCandidate

MIN_SCORE=0.75

def select(candidates: List[Tuple[MicroIntent, RankedCandidate]], max_sponsored:int=2):
    valid=[x for x in candidates if x[1].final_score >= MIN_SCORE]
    valid.sort(key=lambda x:x[1].final_score,reverse=True)
    selected=[]
    seen_categories=set()
    for item in valid:
        cat=item[1].product.category
        if cat in seen_categories: continue
        selected.append(item); seen_categories.add(cat)
        if len(selected)>=max_sponsored: break
    return selected
