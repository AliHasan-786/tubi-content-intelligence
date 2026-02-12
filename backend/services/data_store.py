import os
import ast
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd

from backend.utils.data_prep import dataframe_hash, prepare_clean_dataframe


@dataclass(frozen=True)
class Catalog:
    df: pd.DataFrame
    data_hash: str


def ensure_clean_catalog(raw_csv_path: str, persona_csv_path: str, clean_csv_path: str) -> Catalog:
    os.makedirs(os.path.dirname(clean_csv_path) or ".", exist_ok=True)

    if os.path.exists(clean_csv_path):
        df = pd.read_csv(clean_csv_path)
        # `genres` is serialized; restore to list for internal usage.
        df["genres"] = df["genres"].apply(
            lambda x: [] if pd.isna(x) else ast.literal_eval(x) if isinstance(x, str) else x
        )

        def _to_int_or_none(x):
            if x is None or (isinstance(x, float) and pd.isna(x)) or pd.isna(x):
                return None
            try:
                return int(float(x))
            except Exception:
                return None

        df["release_year"] = df["release_year"].apply(_to_int_or_none)
        df["runtime_minutes"] = df["runtime_minutes"].apply(_to_int_or_none)
        df["rating"] = df["rating"].apply(lambda x: None if pd.isna(x) else str(x))
        df["Title_URL"] = df["Title_URL"].apply(lambda x: None if pd.isna(x) else str(x))
        df["persona"] = df["persona"].apply(lambda x: None if pd.isna(x) else str(x))
        df["content_type"] = df["content_type"].apply(lambda x: None if pd.isna(x) else str(x))
    else:
        df = prepare_clean_dataframe(raw_csv_path=raw_csv_path, persona_csv_path=persona_csv_path)
        # Persist as CSV with genres as a stable string representation.
        df_to_save = df.copy()
        df_to_save["genres"] = df_to_save["genres"].apply(lambda xs: repr(xs or []))
        df_to_save.to_csv(clean_csv_path, index=False)

    # Hash only deterministic, model-relevant columns.
    h = dataframe_hash(df, cols=("Title", "combined_features", "release_year", "rating", "content_type"))
    return Catalog(df=df, data_hash=h)


def filter_mask(
    df: pd.DataFrame,
    ratings: Optional[List[str]] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    content_types: Optional[List[str]] = None,
) -> List[bool]:
    mask = [True] * len(df)

    if ratings:
        allowed = {str(r).strip() for r in ratings}
        mask = [m and (str(df.iloc[i].get("rating") or "").strip() in allowed) for i, m in enumerate(mask)]

    if year_min is not None:
        mask = [m and ((df.iloc[i].get("release_year") or 0) >= year_min) for i, m in enumerate(mask)]

    if year_max is not None:
        mask = [m and ((df.iloc[i].get("release_year") or 10 ** 9) <= year_max) for i, m in enumerate(mask)]

    if content_types:
        allowed = {str(c).strip() for c in content_types}
        mask = [m and (str(df.iloc[i].get("content_type") or "unknown") in allowed) for i, m in enumerate(mask)]

    return mask
