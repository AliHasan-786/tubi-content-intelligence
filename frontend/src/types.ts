export type BrandSafety = {
  tier: string;
  risk: "low" | "medium" | "high";
  notes: string[];
};

export type AdOpportunity = {
  primary_vertical: string;
  secondary_verticals: string[];
  rationale: string;
};

export type MovieResult = {
  title: string;
  title_url?: string | null;
  release_year?: number | null;
  runtime_minutes?: number | null;
  rating?: string | null;
  genres: string[];
  persona?: string | null;
  content_type: "movie" | "series" | "unknown";

  relevance_score: number;
  monetization_score: number;
  final_score: number;

  brand_safety: BrandSafety;
  ad_opportunity: AdOpportunity;
  debug?: Record<string, unknown> | null;
};

export type SearchFilters = {
  ratings?: string[];
  year_min?: number;
  year_max?: number;
  content_types?: Array<"movie" | "series" | "unknown">;
};

export type SearchRequest = {
  query: string;
  top_k: number;
  alpha: number;
  filters?: SearchFilters;
  include_debug?: boolean;
};

export type EngineInfo = {
  type: "embeddings" | "tfidf";
  model?: string | null;
  data_hash?: string | null;
};

export type SearchResponse = {
  query: string;
  top_k: number;
  alpha: number;
  filters?: SearchFilters;
  engine: EngineInfo;
  results: MovieResult[];
  latency_ms: number;
};

export type InsightResponse = {
  title: string;
  hook: string;
  ad_strategy: string;
  advertiser_vertical: string;
  model: string;
};

export type TelemetrySummary = {
  total_searches: number;
  top_queries: Array<{ query: string; count: number }>;
  avg_latency_ms?: number | null;
  engine_breakdown: Record<string, number>;
};

