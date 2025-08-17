import re, time

def sanitize_name(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r'[^a-z0-9_\-]+', '_', s)
    return s or f"user_{int(time.time())}"
