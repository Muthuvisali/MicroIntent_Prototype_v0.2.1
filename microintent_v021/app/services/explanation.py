from app.models import MicroIntent, Product

def explain(intent: MicroIntent, product: Product) -> str:
    reasons=[]
    c=intent.constraints
    if "max_price" in c and product.price <= float(c["max_price"]): reasons.append(f"within your stated budget of ${int(c['max_price'])}")
    if "material" in c and str(product.attributes.get("material","")).lower()==str(c["material"]).lower(): reasons.append(f"matches your {c['material']} preference")
    if "color" in c and str(product.attributes.get("color","")).lower()==str(c["color"]).lower(): reasons.append(f"available in {c['color']}")
    if "skin_type" in c and str(c["skin_type"]).lower() in [str(x).lower() for x in product.attributes.get("skin_types",[])]: reasons.append(f"cataloged for {c['skin_type']} skin")
    if "origin_preference" in c and str(product.attributes.get("origin","")).lower()==str(c["origin_preference"]).lower(): reasons.append("matches your Korean-product preference")
    if "capacity_requirement" in c and str(c["capacity_requirement"]).lower() in [str(x).lower() for x in product.attributes.get("fits",[])]: reasons.append(f"product data says it fits a {c['capacity_requirement']}")
    if "use_case" in c and str(c["use_case"]).lower() in [str(x).lower() for x in product.attributes.get("use_cases",[])]: reasons.append(f"designed for {c['use_case']} use")
    if not reasons: reasons=[f"strong contextual match for {intent.label}"]
    return "This sponsored option " + "; ".join(reasons[:3]) + "."
