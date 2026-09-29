from app.models import MicroIntent

def is_commercially_eligible(intent: MicroIntent) -> bool:
    return (not intent.sensitive_domain) and intent.commercial_score >= 0.55 and intent.label not in {"general information", "unmapped commercial intent"}
