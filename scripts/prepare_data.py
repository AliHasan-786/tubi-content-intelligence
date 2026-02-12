#!/usr/bin/env python3

import argparse
import os
import sys

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.utils.data_prep import prepare_clean_dataframe


def main() -> int:
    ap = argparse.ArgumentParser(description="Prepare a cleaned, deterministic catalog for retrieval + ranking.")
    ap.add_argument("--raw", default="Tubi-Data.csv", help="Path to raw Tubi CSV (default: Tubi-Data.csv)")
    ap.add_argument(
        "--persona",
        default="Tubi_with_Personas_and_Clusters.csv",
        help="Optional persona enrichment CSV (default: Tubi_with_Personas_and_Clusters.csv)",
    )
    ap.add_argument("--out", default="data/clean_titles.csv", help="Output path (default: data/clean_titles.csv)")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    df = prepare_clean_dataframe(raw_csv_path=args.raw, persona_csv_path=args.persona)
    df_to_save = df.copy()
    df_to_save["genres"] = df_to_save["genres"].apply(lambda xs: repr(xs or []))
    df_to_save.to_csv(args.out, index=False)

    print(f"Wrote {len(df_to_save)} rows -> {args.out}")
    print("Columns:", ", ".join(df_to_save.columns))
    print("Sample:")
    print(df_to_save.head(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
