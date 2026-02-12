from typing import List, Optional, Tuple


_RATING_TIER = {
    "TV-Y": ("Kids", "low"),
    "TV-Y7": ("Kids", "low"),
    "TV-Y7_FV": ("Kids", "low"),
    "TV-G": ("Family", "low"),
    "G": ("Family", "low"),
    "TV-PG": ("General", "low"),
    "PG": ("General", "low"),
    "PG-13": ("Teen", "medium"),
    "TV-14": ("Teen", "medium"),
    "R": ("Mature", "high"),
    "TV-MA": ("Mature", "high"),
}


def brand_safety(rating: Optional[str], genres: List[str]) -> Tuple[str, str, List[str]]:
    """
    Simple, explainable brand-safety heuristic.
    Returns: (tier, risk, notes)
    """
    tier, risk = _RATING_TIER.get(str(rating or "").strip(), ("Unrated", "medium"))
    notes: List[str] = []

    if tier == "Unrated":
        notes.append("No rating available; treating as medium risk by default.")
    else:
        notes.append(f"Rating-based tier: {tier} ({rating}).")

    gset = {g.lower() for g in (genres or [])}
    # Content-based adjustments (still heuristic; explicitly communicated in UI/docs).
    if any(x in gset for x in ["horror", "crime", "thriller"]):
        if risk == "low":
            risk = "medium"
        notes.append("Genre includes Horror/Crime/Thriller: elevated brand-safety risk.")
    if "kids & family" in gset:
        notes.append("Kids & Family content tends to be broadly brand-safe.")

    return tier, risk, notes

