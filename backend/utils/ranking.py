from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


AD_VERTICALS: Tuple[str, ...] = (
    "CPG",
    "Auto",
    "Insurance",
    "Travel",
    "Gaming",
    "QSR",
    "Tech",
    "Retail",
    "Financial Services",
    "Health & Wellness",
    "Entertainment",
)


# Higher = more advertiser friendly (proxy).
_RATING_BRAND_FRIENDLINESS: Dict[str, float] = {
    "TV-Y": 1.00,
    "TV-Y7": 0.98,
    "TV-Y7_FV": 0.98,
    "TV-G": 0.96,
    "G": 0.96,
    "TV-PG": 0.86,
    "PG": 0.86,
    "PG-13": 0.76,
    "TV-14": 0.70,
    "R": 0.55,
    "TV-MA": 0.40,
}


_GENRE_PREMIUM: Dict[str, float] = {
    # Proxy demand: not "truth", but an explainable, tunable heuristic.
    "kids & family": 0.90,
    "animation": 0.88,
    "comedy": 0.82,
    "action": 0.78,
    "sci-fi": 0.78,
    "adventure": 0.76,
    "drama": 0.72,
    "romance": 0.70,
    "documentary": 0.68,
    "reality": 0.74,
    "thriller": 0.62,
    "crime": 0.60,
    "horror": 0.55,
}


@dataclass(frozen=True)
class MonetizationBreakdown:
    rating_score: float
    length_score: float
    genre_score: float


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else float(x)


def runtime_inventory_score(runtime_minutes: Optional[int], content_type: str) -> float:
    """
    Proxy for ad inventory opportunity.
    - Movies: longer runtime => more ad slots (up to a cap).
    - Series: runtime in this dataset is usually missing; use a neutral value.
    """
    if content_type == "series":
        return 0.60
    if not runtime_minutes:
        return 0.50
    # 90-120 minutes is "full feature"; cap beyond 140.
    return clamp01((runtime_minutes - 60) / 80.0)


def genre_premium_score(genres: List[str]) -> float:
    if not genres:
        return 0.65
    scores = []
    for g in genres:
        s = _GENRE_PREMIUM.get(str(g).strip().lower())
        if s is not None:
            scores.append(s)
    if not scores:
        return 0.65
    # If multiple genres, take the max as "primary appeal" proxy.
    return float(max(scores))


def monetization_score(
    rating: Optional[str],
    runtime_minutes: Optional[int],
    genres: List[str],
    content_type: str,
) -> Tuple[float, MonetizationBreakdown]:
    r_score = _RATING_BRAND_FRIENDLINESS.get(str(rating or "").strip(), 0.65)
    l_score = runtime_inventory_score(runtime_minutes, content_type)
    g_score = genre_premium_score(genres)

    # Weighting: brand suitability tends to dominate demand-side constraints.
    score = 0.50 * r_score + 0.20 * l_score + 0.30 * g_score
    return clamp01(score), MonetizationBreakdown(rating_score=r_score, length_score=l_score, genre_score=g_score)


def suggest_ad_verticals(genres: List[str], rating: Optional[str]) -> List[str]:
    """
    Rules-based vertical suggestions (used both as a fallback and as context for the LLM).
    """
    gset = {str(g).strip().lower() for g in (genres or [])}
    verticals: List[str] = []

    if "kids & family" in gset or str(rating or "").strip() in {"TV-Y", "TV-Y7", "TV-Y7_FV", "TV-G", "G"}:
        verticals += ["CPG", "QSR", "Retail"]
    if any(g in gset for g in ["action", "thriller", "sci-fi", "adventure"]):
        verticals += ["Auto", "Gaming", "Tech"]
    if any(g in gset for g in ["drama", "romance"]):
        verticals += ["Insurance", "Travel", "Retail"]
    if "documentary" in gset:
        verticals += ["Financial Services", "Tech", "Health & Wellness"]
    if any(g in gset for g in ["comedy"]):
        verticals += ["QSR", "CPG", "Retail"]
    if any(g in gset for g in ["horror", "crime"]):
        verticals += ["Entertainment", "Gaming"]

    # De-dupe while preserving order.
    seen = set()
    out: List[str] = []
    for v in verticals:
        if v in AD_VERTICALS and v not in seen:
            out.append(v)
            seen.add(v)
    if not out:
        out = ["CPG", "Retail", "Entertainment"]
    return out[:5]

