from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from backend.models import MovieResult
from backend.utils.brand_safety import brand_safety
from backend.utils.ranking import MonetizationBreakdown, monetization_score, suggest_ad_verticals


@dataclass(frozen=True)
class EngineMeta:
    engine_type: str  # embeddings|tfidf
    model_name: Optional[str] = None
    data_hash: Optional[str] = None


class BaseSearchEngine:
    def meta(self) -> EngineMeta:
        raise NotImplementedError

    def query_similarities(self, query: str) -> np.ndarray:
        """
        Returns similarity scores aligned to catalog row order.
        """
        raise NotImplementedError


class TfidfSearchEngine(BaseSearchEngine):
    def __init__(self, df: pd.DataFrame, data_hash: str) -> None:
        self._df = df
        self._data_hash = data_hash
        self._vectorizer = TfidfVectorizer()
        self._matrix = self._vectorizer.fit_transform(df["combined_features"].fillna("").astype(str).tolist())

    def meta(self) -> EngineMeta:
        return EngineMeta(engine_type="tfidf", model_name="tfidf", data_hash=self._data_hash)

    def query_similarities(self, query: str) -> np.ndarray:
        qv = self._vectorizer.transform([query])
        # cosine similarity for TF-IDF is just normalized dot product; sklearn sparse supports dot.
        sims = (self._matrix @ qv.T).toarray().reshape(-1)
        return sims.astype(np.float32)


class EmbeddingSearchEngine(BaseSearchEngine):
    def __init__(
        self,
        df: pd.DataFrame,
        data_hash: str,
        embeddings_npy_path: str,
        embeddings_meta_path: str,
        model_name: str,
    ) -> None:
        self._df = df
        self._data_hash = data_hash
        self._model_name = model_name

        if not os.path.exists(embeddings_npy_path) or not os.path.exists(embeddings_meta_path):
            raise RuntimeError("Embeddings cache not found. Run scripts/build_embeddings.py first.")

        with open(embeddings_meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        if meta.get("data_hash") != data_hash:
            raise RuntimeError("Embeddings cache is stale (data_hash mismatch). Rebuild embeddings.")
        if meta.get("model_name") != model_name:
            raise RuntimeError("Embeddings cache model mismatch. Rebuild embeddings.")

        self._emb = np.load(embeddings_npy_path)
        if self._emb.shape[0] != len(df):
            raise RuntimeError("Embeddings cache row count mismatch. Rebuild embeddings.")

        # Lazy import so the backend can still run in TF-IDF mode without the dependency.
        from sentence_transformers import SentenceTransformer  # type: ignore

        self._model = SentenceTransformer(model_name)

        # Ensure normalized for cosine via dot product.
        norms = np.linalg.norm(self._emb, axis=1, keepdims=True) + 1e-12
        self._emb = (self._emb / norms).astype(np.float32)

    def meta(self) -> EngineMeta:
        return EngineMeta(engine_type="embeddings", model_name=self._model_name, data_hash=self._data_hash)

    def query_similarities(self, query: str) -> np.ndarray:
        q = self._model.encode([query], normalize_embeddings=True)
        qv = np.asarray(q, dtype=np.float32).reshape(-1)
        sims = self._emb @ qv
        return sims.astype(np.float32)


def pick_engine(
    df: pd.DataFrame,
    data_hash: str,
    embeddings_npy_path: str,
    embeddings_meta_path: str,
    model_name: str,
) -> BaseSearchEngine:
    try:
        return EmbeddingSearchEngine(
            df=df,
            data_hash=data_hash,
            embeddings_npy_path=embeddings_npy_path,
            embeddings_meta_path=embeddings_meta_path,
            model_name=model_name,
        )
    except Exception:
        return TfidfSearchEngine(df=df, data_hash=data_hash)


def build_results(
    df: pd.DataFrame,
    sims: np.ndarray,
    mask: List[bool],
    top_k: int,
    alpha: float,
    include_debug: bool,
) -> List[MovieResult]:
    def _none_if_na(x):
        try:
            return None if x is None or pd.isna(x) else x
        except Exception:
            return None if x is None else x

    # Apply mask and rank by similarity first (recall layer).
    candidate_idxs = [i for i, ok in enumerate(mask) if ok]
    if not candidate_idxs:
        return []

    cand_sims = [(i, float(sims[i])) for i in candidate_idxs]
    cand_sims.sort(key=lambda x: x[1], reverse=True)
    anchor_idx = cand_sims[0][0]
    anchor_persona = _none_if_na(df.iloc[anchor_idx].get("persona"))
    top_idxs = [i for i, _ in cand_sims[: max(top_k * 5, top_k)]]  # widen before rerank

    results: List[Tuple[int, float, float, float, MonetizationBreakdown, Dict[str, Any]]] = []
    for i in top_idxs:
        row = df.iloc[i]
        genres = _none_if_na(row.get("genres")) or []
        rating = _none_if_na(row.get("rating"))
        runtime_minutes = _none_if_na(row.get("runtime_minutes"))
        content_type = _none_if_na(row.get("content_type")) or "unknown"

        rel = float(sims[i])
        mon, mon_dbg = monetization_score(
            rating=rating,
            runtime_minutes=(int(runtime_minutes) if runtime_minutes is not None else None),
            genres=genres,
            content_type=content_type,
        )
        fin = float(alpha) * rel + (1.0 - float(alpha)) * mon

        # Persona cohesion: keep recs coherent within a discovered segment.
        # This is intentionally a small boost so it doesn't override relevance/monetization.
        persona = _none_if_na(row.get("persona"))
        persona_bonus = 0.03 if (anchor_persona and persona == anchor_persona) else 0.0
        fin = fin + persona_bonus

        dbg: Dict[str, Any] = {}
        if include_debug:
            dbg = {
                "raw_similarity": rel,
                "monetization_breakdown": mon_dbg.__dict__,
                "anchor_persona": anchor_persona,
                "persona_bonus": persona_bonus,
            }
        results.append((i, rel, mon, fin, mon_dbg, dbg))

    # Final sort by multi-objective score.
    results.sort(key=lambda x: x[3], reverse=True)
    results = results[:top_k]

    out: List[MovieResult] = []
    for i, rel, mon, fin, _mon_dbg, dbg in results:
        row = df.iloc[i]
        genres = _none_if_na(row.get("genres")) or []
        rating = _none_if_na(row.get("rating"))
        release_year = _none_if_na(row.get("release_year"))
        runtime_minutes = _none_if_na(row.get("runtime_minutes"))
        content_type = _none_if_na(row.get("content_type")) or "unknown"
        tier, risk, notes = brand_safety(rating=rating, genres=genres)
        verticals = suggest_ad_verticals(genres=genres, rating=rating)
        out.append(
            MovieResult(
                title=str(row.get("Title")),
                title_url=row.get("Title_URL"),
                release_year=(int(release_year) if release_year is not None else None),
                runtime_minutes=(int(runtime_minutes) if runtime_minutes is not None else None),
                rating=rating,
                genres=list(genres),
                persona=_none_if_na(row.get("persona")),
                content_type=str(content_type),
                relevance_score=float(rel),
                monetization_score=float(mon),
                final_score=float(fin),
                brand_safety={"tier": tier, "risk": risk, "notes": notes},
                ad_opportunity={
                    "primary_vertical": verticals[0],
                    "secondary_verticals": verticals[1:],
                    "rationale": "Rules-based advertiser fit derived from genre + rating (proxy).",
                },
                debug=dbg or None,
            )
        )
    return out


class SearchService:
    def __init__(
        self,
        df: pd.DataFrame,
        data_hash: str,
        embeddings_npy_path: str,
        embeddings_meta_path: str,
        model_name: str,
    ) -> None:
        self._df = df
        self._engine = pick_engine(
            df=df,
            data_hash=data_hash,
            embeddings_npy_path=embeddings_npy_path,
            embeddings_meta_path=embeddings_meta_path,
            model_name=model_name,
        )
        self._meta = self._engine.meta()

    def meta(self) -> EngineMeta:
        return self._meta

    def search(
        self,
        query: str,
        mask: List[bool],
        top_k: int,
        alpha: float,
        include_debug: bool,
    ) -> Tuple[List[MovieResult], int]:
        t0 = time.time()
        sims = self._engine.query_similarities(query)
        results = build_results(
            df=self._df,
            sims=sims,
            mask=mask,
            top_k=top_k,
            alpha=alpha,
            include_debug=include_debug,
        )
        latency_ms = int((time.time() - t0) * 1000)
        return results, latency_ms
