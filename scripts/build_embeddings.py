#!/usr/bin/env python3

import argparse
import ast
import json
import os
import sys
import time
from typing import Any, Dict

import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.utils.data_prep import dataframe_hash


def main() -> int:
    ap = argparse.ArgumentParser(description="Build and cache sentence-transformer embeddings for semantic search.")
    ap.add_argument("--clean", default="data/clean_titles.csv", help="Clean catalog path (default: data/clean_titles.csv)")
    ap.add_argument("--out", default="data/embeddings.npy", help="Embeddings output .npy (default: data/embeddings.npy)")
    ap.add_argument("--meta", default="data/embeddings_meta.json", help="Meta output .json (default: data/embeddings_meta.json)")
    ap.add_argument("--model", default="all-MiniLM-L6-v2", help="SentenceTransformer model name (default: all-MiniLM-L6-v2)")
    args = ap.parse_args()

    if not os.path.exists(args.clean):
        raise SystemExit(f"Missing {args.clean}. Run scripts/prepare_data.py first.")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.meta) or ".", exist_ok=True)

    df = pd.read_csv(args.clean)
    if "genres" in df.columns:
        df["genres"] = df["genres"].apply(lambda x: [] if pd.isna(x) else ast.literal_eval(x) if isinstance(x, str) else x)

    def _to_int_or_none(x):
        if x is None or (isinstance(x, float) and pd.isna(x)) or pd.isna(x):
            return None
        try:
            return int(float(x))
        except Exception:
            return None

    # Mirror backend normalization so data_hash matches at runtime.
    if "release_year" in df.columns:
        df["release_year"] = df["release_year"].apply(_to_int_or_none)
    if "rating" in df.columns:
        df["rating"] = df["rating"].apply(lambda x: None if pd.isna(x) else str(x))
    if "content_type" in df.columns:
        df["content_type"] = df["content_type"].apply(lambda x: None if pd.isna(x) else str(x))

    data_hash = dataframe_hash(df, cols=("Title", "combined_features", "release_year", "rating", "content_type"))

    # Lazy import: heavy deps.
    from sentence_transformers import SentenceTransformer  # type: ignore

    model = SentenceTransformer(args.model)
    texts = df["combined_features"].fillna("").astype(str).tolist()

    t0 = time.time()
    emb = model.encode(texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True)
    emb = np.asarray(emb, dtype=np.float32)
    np.save(args.out, emb)

    meta: Dict[str, Any] = {
        "created_at_ms": int(time.time() * 1000),
        "build_seconds": round(time.time() - t0, 3),
        "model_name": args.model,
        "data_hash": data_hash,
        "rows": int(len(df)),
        "dim": int(emb.shape[1]) if emb.ndim == 2 else None,
        "clean_path": args.clean,
    }
    with open(args.meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=True)
        f.write("\n")

    print(f"Wrote embeddings -> {args.out} ({emb.shape})")
    print(f"Wrote meta -> {args.meta}")
    print(f"data_hash={data_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
