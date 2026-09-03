"""Safe labels for face-profile filenames."""

import re


def sanitize_name(s: str) -> str:
    if not isinstance(s, str):
        return ""
    normalized = re.sub(r"[^a-z0-9_-]+", "_", s.strip().lower())
    return normalized.strip("_")[:64]
