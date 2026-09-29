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
    words=set(intent.label.lower().split())
    scored=[]
    for p in products:
        cat=set(p.category.lower().split())
        overlap=len(words & cat)
        if overlap or p.category.lower() in intent.label.lower() or intent.label.lower() in p.category.lower():
            scored.append((overlap,p))
    scored.sort(key=lambda x:(x[0],x[1].quality_score), reverse=True)
    return [p for _,p in scored[:limit]]
