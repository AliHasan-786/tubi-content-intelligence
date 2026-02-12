import re
from typing import List, Optional


_BULLET_RE = re.compile(r"\s*·\s*")


def normalize_whitespace(s: str) -> str:
    # Normalize non-breaking spaces and collapse whitespace.
    s = s.replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def normalize_genres(raw: Optional[str]) -> List[str]:
    if raw is None:
        return []
    raw = str(raw)
    raw = normalize_whitespace(raw)
    if not raw:
        return []

    # Tubi genre strings tend to be `A · B · C` with the middle dot.
    parts = _BULLET_RE.split(raw)
    genres = []
    for p in parts:
        p = normalize_whitespace(p)
        if not p:
            continue
        genres.append(p)
    return genres

