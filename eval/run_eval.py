#!/usr/bin/env python3

import argparse
import ast
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.config import settings
from backend.services.data_store import ensure_clean_catalog


@dataclass(frozen=True)
class Expectation:
    genres_any: List[str]
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    ratings_any: Optional[List[str]] = None
    runtime_max: Optional[int] = None


def load_queries(path: str) -> List[Tuple[str, Expectation]]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            j = json.loads(ln)
            q = str(j["query"])
            e = j.get("expect", {}) or {}
            out.append(
                (
                    q,
                    Expectation(
                        genres_any=list(e.get("genres_any") or []),
                        year_min=e.get("year_min"),
                        year_max=e.get("year_max"),
                        ratings_any=e.get("ratings_any"),
                        runtime_max=e.get("runtime_max"),
                    ),
                )
            )
    return out


def is_relevant(row: pd.Series, exp: Expectation) -> bool:
    genres = row.get("genres") or []
    gset = {str(g) for g in genres}
    if exp.genres_any:
        if not any(g in gset for g in exp.genres_any):
            return False
    if exp.year_min is not None:
        y = row.get("release_year")
        if y is None or y < exp.year_min:
            return False
    if exp.year_max is not None:
        y = row.get("release_year")
        if y is None or y > exp.year_max:
            return False
    if exp.ratings_any:
        r = row.get("rating")
        if r is None or r not in set(exp.ratings_any):
            return False
    if exp.runtime_max is not None:
        rm = row.get("runtime_minutes")
        if rm is None or rm > exp.runtime_max:
            return False
    return True


def mrr_at_k(rels: List[int], k: int) -> float:
    for i, r in enumerate(rels[:k], start=1):
        if r:
            return 1.0 / i
    return 0.0


def ndcg_at_k(rels: List[int], k: int) -> float:
    # Binary relevance.
    dcg = 0.0
    for i, r in enumerate(rels[:k], start=1):
        if r:
            dcg += 1.0 / np.log2(i + 1)
    # Ideal DCG: all relevant first.
    ideal = sorted(rels[:k], reverse=True)
    idcg = 0.0
    for i, r in enumerate(ideal, start=1):
        if r:
            idcg += 1.0 / np.log2(i + 1)
    return float(dcg / idcg) if idcg > 0 else 0.0


def hit_rate_at_k(rels: List[int], k: int) -> float:
    return 1.0 if any(rels[:k]) else 0.0


def rank_tfidf(df: pd.DataFrame, query: str, k: int) -> List[int]:
    vec = TfidfVectorizer()
    X = vec.fit_transform(df["combined_features"].fillna("").astype(str).tolist())
    qv = vec.transform([query])
    sims = (X @ qv.T).toarray().reshape(-1)
    order = np.argsort(-sims)
    return [int(i) for i in order[:k]]


def rank_embeddings(df: pd.DataFrame, query: str, k: int) -> Optional[List[int]]:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception:
        return None
    if not os.path.exists(settings.embeddings_npy_path) or not os.path.exists(settings.embeddings_meta_path):
        return None
    emb = np.load(settings.embeddings_npy_path).astype(np.float32)
    norms = np.linalg.norm(emb, axis=1, keepdims=True) + 1e-12
    emb = emb / norms
    model = SentenceTransformer(settings.embedding_model_name)
    q = model.encode([query], normalize_embeddings=True)
    qv = np.asarray(q, dtype=np.float32).reshape(-1)
    sims = emb @ qv
    order = np.argsort(-sims)
    return [int(i) for i in order[:k]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", default="eval/queries.jsonl")
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()

    catalog = ensure_clean_catalog(settings.raw_csv_path, settings.persona_csv_path, settings.clean_csv_path)
    df = catalog.df.copy()
    # Ensure genres are lists (clean CSV stores repr strings).
    if isinstance(df.iloc[0].get("genres"), str):
        df["genres"] = df["genres"].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)

    qs = load_queries(args.queries)
    k = args.k

    engines = ["tfidf"]
    has_emb = rank_embeddings(df, "warmup", k=1) is not None
    if has_emb:
        engines.append("embeddings")

    rows: List[Dict[str, Any]] = []
    for q, exp in qs:
        for eng in engines:
            if eng == "tfidf":
                idxs = rank_tfidf(df, q, k=k)
            else:
                idxs = rank_embeddings(df, q, k=k) or []

            rels = [1 if is_relevant(df.iloc[i], exp) else 0 for i in idxs]
            rows.append(
                {
                    "engine": eng,
                    "query": q,
                    "mrr": mrr_at_k(rels, k),
                    "ndcg": ndcg_at_k(rels, k),
                    "hit_rate": hit_rate_at_k(rels, k),
                }
            )

    out_df = pd.DataFrame(rows)
    summary = out_df.groupby("engine")[["mrr", "ndcg", "hit_rate"]].mean().reset_index()

    print("=== Retrieval Evaluation (Proxy Relevance) ===")
    print(f"k={k}  queries={len(qs)}")
    print(summary.to_string(index=False))
    print()
    print("Note: relevance is defined via genre/year/rating heuristics in eval/queries.jsonl (proxy, not ground truth).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

