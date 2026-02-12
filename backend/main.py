from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.models import InsightRequest, InsightResponse, SearchRequest, SearchResponse, TelemetrySummary
from backend.services.data_store import ensure_clean_catalog, filter_mask
from backend.services.insights_service import generate_hook_and_ad_strategy, generate_hook_and_ad_strategy_gemini, lookup_title_row
from backend.services.logging_service import EventLogger
from backend.services.search_service import SearchService


app = FastAPI(title="Tubi Smart-Scout & Ad-Insight API", version="0.1.0")

origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


catalog = ensure_clean_catalog(
    raw_csv_path=settings.raw_csv_path,
    persona_csv_path=settings.persona_csv_path,
    clean_csv_path=settings.clean_csv_path,
)
search_service = SearchService(
    df=catalog.df,
    data_hash=catalog.data_hash,
    embeddings_npy_path=settings.embeddings_npy_path,
    embeddings_meta_path=settings.embeddings_meta_path,
    model_name=settings.embedding_model_name,
)
event_logger = EventLogger(settings.events_log_path)


@app.get("/health")
def health() -> Dict[str, Any]:
    m = search_service.meta()
    return {
        "ok": True,
        "engine": {"type": m.engine_type, "model": m.model_name, "data_hash": m.data_hash},
        "catalog_rows": len(catalog.df),
    }


@app.post("/api/search", response_model=SearchResponse)
def api_search(req: SearchRequest) -> SearchResponse:
    t0 = time.time()

    f = req.filters
    mask = filter_mask(
        catalog.df,
        ratings=f.ratings if f else None,
        year_min=f.year_min if f else None,
        year_max=f.year_max if f else None,
        content_types=f.content_types if f else None,
    )
    results, latency_ms = search_service.search(
        query=req.query,
        mask=mask,
        top_k=req.top_k,
        alpha=req.alpha,
        include_debug=req.include_debug,
    )

    meta = search_service.meta()
    resp = SearchResponse(
        query=req.query,
        top_k=req.top_k,
        alpha=req.alpha,
        filters=req.filters,
        engine={"type": meta.engine_type, "model": meta.model_name, "data_hash": meta.data_hash},
        results=results,
        latency_ms=latency_ms,
    )

    # Best-effort telemetry (never fail user requests).
    try:
        filters_payload = None
        if req.filters:
            # Pydantic v1: dict(); v2: model_dump()
            filters_payload = req.filters.model_dump() if hasattr(req.filters, "model_dump") else req.filters.dict()
        event_logger.log(
            "search",
            {
                "query": req.query,
                "top_k": req.top_k,
                "alpha": req.alpha,
                "filters": filters_payload,
                "engine_type": meta.engine_type,
                "latency_ms": latency_ms,
                "result_titles": [r.title for r in results],
            },
        )
    except Exception:
        pass

    _ = t0
    return resp


@app.post("/api/insights", response_model=InsightResponse)
def api_insights(req: InsightRequest) -> InsightResponse:
    row = lookup_title_row(catalog.df, req.title)
    if row is None:
        raise HTTPException(status_code=404, detail="Title not found in catalog.")

    # Common kwargs for all providers.
    common_kwargs = dict(
        query=req.query,
        title=str(row.get("Title")),
        genres=list(row.get("genres") or []),
        rating=row.get("rating"),
        release_year=(int(row.get("release_year")) if row.get("release_year") is not None else None),
        runtime_minutes=(int(row.get("runtime_minutes")) if row.get("runtime_minutes") is not None else None),
        content_type=str(row.get("content_type") or "unknown"),
    )

    # Priority: llmapi.ai → Gemini → OpenAI.
    hook = ad_strategy = vertical = model_name = None
    last_error = None

    # 1) LLM API gateway (OpenAI-compatible proxy)
    if settings.llmapi_key:
        try:
            hook, ad_strategy, vertical = generate_hook_and_ad_strategy(
                openai_api_key=settings.llmapi_key,
                openai_model=settings.llmapi_model,
                api_base_url=settings.llmapi_base_url,
                **common_kwargs,
            )
            model_name = settings.llmapi_model
        except Exception as e:
            last_error = e

    # 2) Gemini fallback
    if hook is None and settings.gemini_api_key:
        try:
            hook, ad_strategy, vertical = generate_hook_and_ad_strategy_gemini(
                gemini_api_key=settings.gemini_api_key,
                gemini_model=settings.gemini_model,
                **common_kwargs,
            )
            model_name = settings.gemini_model
        except Exception as e:
            last_error = e

    # 3) Direct OpenAI fallback
    if hook is None:
        api_key = (req.openai_api_key or "").strip() or settings.openai_api_key
        if api_key:
            try:
                hook, ad_strategy, vertical = generate_hook_and_ad_strategy(
                    openai_api_key=api_key,
                    openai_model=settings.openai_model,
                    **common_kwargs,
                )
                model_name = settings.openai_model
            except Exception as e:
                last_error = e

    if hook is None:
        raise HTTPException(status_code=502, detail=f"All LLM providers failed. Last error: {last_error}")

    # Telemetry (best effort).
    try:
        event_logger.log(
            "insight",
            {
                "query": req.query,
                "title": req.title,
                "model": model_name,
                "advertiser_vertical": vertical,
            },
        )
    except Exception:
        pass

    return InsightResponse(
        title=req.title,
        hook=hook,
        ad_strategy=ad_strategy,
        advertiser_vertical=vertical,
        model=model_name or "unknown",
    )


# ─── Poster image proxy (resolves & streams image bytes) ───────────────
import re as _re
import requests as _requests
import time as _time
from fastapi.responses import Response

# TTL cache: {tubi_url: (poster_cdn_url, timestamp)}
_poster_cache: Dict[str, tuple] = {}
_POSTER_TTL = 600  # 10 minutes – re-resolve if CDN URL expires
_OG_IMG_RE = _re.compile(r'property="og:image"\s+content="([^"]+)"', _re.IGNORECASE)
_OG_IMG_RE2 = _re.compile(r'og:image["\']?\s+content=["\']([^"\']+)', _re.IGNORECASE)

_GOOGLEBOT_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


def _resolve_poster_url(tubi_url: str) -> Optional[str]:
    """Scrape og:image from a Tubi page. Uses Googlebot UA for reliable results."""
    now = _time.time()
    cached = _poster_cache.get(tubi_url)
    if cached and (now - cached[1]) < _POSTER_TTL:
        return cached[0]
    try:
        r = _requests.get(tubi_url, timeout=8, headers={"User-Agent": _GOOGLEBOT_UA})
        m = _OG_IMG_RE.search(r.text[:30_000]) or _OG_IMG_RE2.search(r.text[:30_000])
        url = m.group(1) if m else None
    except Exception:
        url = None
    _poster_cache[tubi_url] = (url, now)
    return url


@app.get("/api/poster")
def api_poster(tubi_url: str) -> Dict[str, Any]:
    """Resolve a Tubi URL to its poster image URL (JSON)."""
    poster = _resolve_poster_url(tubi_url)
    return {"tubi_url": tubi_url, "poster_url": poster}


@app.get("/api/poster/image")
def api_poster_image(tubi_url: str) -> Response:
    """Proxy poster image bytes from Tubi CDN. Avoids CORS and CDN expiry issues."""
    poster_url = _resolve_poster_url(tubi_url)
    if not poster_url:
        return Response(status_code=404, content=b"No poster found")
    try:
        r = _requests.get(poster_url, timeout=8, headers={"User-Agent": _GOOGLEBOT_UA})
        if r.status_code >= 400:
            # CDN URL expired mid-cache; clear cache and retry once
            _poster_cache.pop(tubi_url, None)
            poster_url = _resolve_poster_url(tubi_url)
            if not poster_url:
                return Response(status_code=404, content=b"No poster found")
            r = _requests.get(poster_url, timeout=8, headers={"User-Agent": _GOOGLEBOT_UA})
            if r.status_code >= 400:
                return Response(status_code=502, content=b"Poster CDN error")
        content_type = r.headers.get("content-type", "image/jpeg")
        return Response(
            content=r.content,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=3600"},
        )
    except Exception:
        return Response(status_code=502, content=b"Poster fetch failed")


@app.get("/api/telemetry/summary", response_model=TelemetrySummary)
def api_telemetry_summary() -> TelemetrySummary:
    s = event_logger.summarize()
    return TelemetrySummary(**s)


@app.get("/api/catalog/stats")
def api_catalog_stats() -> Dict[str, Any]:
    df = catalog.df
    ratings = df["rating"].fillna("Unknown").astype(str).value_counts().to_dict()
    ctype = df["content_type"].fillna("unknown").astype(str).value_counts().to_dict()
    years = df["release_year"].dropna()
    return {
        "rows": len(df),
        "ratings": ratings,
        "content_types": ctype,
        "year_min": int(years.min()) if not years.empty else None,
        "year_max": int(years.max()) if not years.empty else None,
    }


# Optional: serve the built React app from the backend for a single-URL deployment.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_FRONTEND_DIST = os.path.join(_REPO_ROOT, "frontend", "dist")
if os.path.isdir(_FRONTEND_DIST):
    # Important: mount after API routes so /api/* still resolves first.
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
