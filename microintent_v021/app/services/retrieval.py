from __future__ import annotations
import json
from pathlib import Path
from typing import List
from app.models import MicroIntent, Product

DATA=Path(__file__).resolve().parents[2]/"data"/"products.json"

def load_products() -> List[Product]:
    return [Product(**x) for x in json.loads(DATA.read_text())]

def retrieve(intent: MicroIntent, limit: int=8) -> List[Product]:
    products=load_products()
    label=intent.label.lower()
    # Inventory built for exactly this micro-intent wins; word overlap is only a fallback
    # (e.g. for free-form Gemini labels), so "faux leather" never pulls genuine-leather ads.
    exact=[p for p in products if p.category.lower()==label]
    if exact:
        return sorted(exact,key=lambda p:p.quality_score,reverse=True)[:limit]
    words=set(label.split())
    scored=[]
    for p in products:
        cat=set(p.category.lower().split())
        overlap=len(words & cat)
        if overlap or p.category.lower() in label or label in p.category.lower():
            scored.append((overlap,p))
    scored.sort(key=lambda x:(x[0],x[1].quality_score), reverse=True)
    return [p for _,p in scored[:limit]]
