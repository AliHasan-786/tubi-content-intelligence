from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    ratings: Optional[List[str]] = None
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    content_types: Optional[List[Literal["movie", "series", "unknown"]]] = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    top_k: int = Field(5, ge=1, le=20)
    alpha: float = Field(0.8, ge=0.0, le=1.0, description="User relevance weight (1=relevance only, 0=monetization only)")
    filters: Optional[SearchFilters] = None
    include_debug: bool = False


class BrandSafety(BaseModel):
    tier: str
    risk: Literal["low", "medium", "high"]
    notes: List[str]


class AdOpportunity(BaseModel):
    primary_vertical: str
    secondary_verticals: List[str]
    rationale: str


class MovieResult(BaseModel):
    title: str
    title_url: Optional[str] = None
    release_year: Optional[int] = None
    runtime_minutes: Optional[int] = None
    rating: Optional[str] = None
    genres: List[str]
    persona: Optional[str] = None
    content_type: Literal["movie", "series", "unknown"]

    relevance_score: float
    monetization_score: float
    final_score: float

    brand_safety: BrandSafety
    ad_opportunity: AdOpportunity

    debug: Optional[Dict[str, Any]] = None


class EngineInfo(BaseModel):
    type: Literal["embeddings", "tfidf"]
    model: Optional[str] = None
    data_hash: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    top_k: int
    alpha: float
    filters: Optional[SearchFilters] = None
    engine: EngineInfo
    results: List[MovieResult]
    latency_ms: int


class InsightRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    title: str = Field(..., min_length=1, max_length=200)
    # Optional per-request key for local demo usage; prefer server-side key in deployment.
    openai_api_key: Optional[str] = None


class InsightResponse(BaseModel):
    title: str
    hook: str
    ad_strategy: str
    advertiser_vertical: str
    model: str


class TelemetrySummary(BaseModel):
    total_searches: int
    top_queries: List[Dict[str, Any]]
    avg_latency_ms: Optional[float] = None
    engine_breakdown: Dict[str, int]

