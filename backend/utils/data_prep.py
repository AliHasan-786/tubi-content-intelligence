import hashlib
import re
from typing import Dict, Optional, Tuple

import pandas as pd

from backend.utils.text import normalize_whitespace, normalize_genres


_RUNTIME_RE = re.compile(r"(?:(?P<hours>\d+)\s*hr)?\s*(?:(?P<minutes>\d+)\s*min)?", re.IGNORECASE)


def parse_runtime_minutes(raw: Optional[str]) -> Optional[int]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = normalize_whitespace(str(raw)).lower()
    if not s or s in {"0", "nan", "none"}:
        return None

    m = _RUNTIME_RE.fullmatch(s)
    if not m:
        return None
    hours = int(m.group("hours") or 0)
    minutes = int(m.group("minutes") or 0)
    total = hours * 60 + minutes
    return total if total > 0 else None


def infer_content_type(title_url: Optional[str]) -> str:
    if not title_url:
        return "unknown"
    u = str(title_url)
    if "/series/" in u:
        return "series"
    if "/movies/" in u:
        return "movie"
    return "unknown"


def load_persona_map(persona_csv_path: str) -> Dict[str, str]:
    try:
        df_p = pd.read_csv(persona_csv_path, usecols=["Title", "Persona"])
    except Exception:
        return {}
    df_p["Title"] = df_p["Title"].astype(str).map(normalize_whitespace)
    df_p["Persona"] = df_p["Persona"].astype(str).map(normalize_whitespace)
    df_p = df_p.dropna(subset=["Title", "Persona"])
    return dict(zip(df_p["Title"], df_p["Persona"]))


def dataframe_hash(df: pd.DataFrame, cols: Tuple[str, ...]) -> str:
    h = hashlib.sha256()
    # Stable: iterate rows and hash selected columns only.
    for row in df.loc[:, list(cols)].itertuples(index=False, name=None):
        h.update(("|".join("" if x is None else str(x) for x in row) + "\n").encode("utf-8"))
    return h.hexdigest()


def prepare_clean_dataframe(raw_csv_path: str, persona_csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(raw_csv_path)

    # Normalize / rename to internal columns.
    df["Title"] = df["Title"].astype(str).map(normalize_whitespace)
    df["Title_URL"] = df["Title_URL"].astype(str).where(df["Title_URL"].notna(), None)

    # Release year: enforce int where possible.
    def _coerce_year(x):
        try:
            if pd.isna(x):
                return None
            y = int(float(x))
            return y if 1800 <= y <= 2100 else None
        except Exception:
            return None

    df["release_year"] = df["Release Date"].map(_coerce_year)
    df["runtime_minutes"] = df["Movie Length"].map(parse_runtime_minutes)
    df["rating"] = df["Movie Rating"].astype(str).where(df["Movie Rating"].notna(), None)
    df["genres"] = df["Movie Genre"].map(normalize_genres)

    persona_map = load_persona_map(persona_csv_path)
    df["persona"] = df["Title"].map(lambda t: persona_map.get(t))
    df["content_type"] = df["Title_URL"].map(infer_content_type)

    # Retrieval text.
    def _combined(row) -> str:
        title = row["Title"] or ""
        genres = " ".join(row["genres"] or [])
        return normalize_whitespace(f"{title} {genres}")

    df["combined_features"] = df.apply(_combined, axis=1)

    # Keep only columns we actually use (makes downstream deterministic).
    out = df.loc[
        :,
        [
            "Title",
            "Title_URL",
            "release_year",
            "runtime_minutes",
            "rating",
            "genres",
            "persona",
            "content_type",
            "combined_features",
        ],
    ].copy()

    # Replace NaNs with None for JSON friendliness.
    out = out.where(pd.notna(out), None)
    return out
