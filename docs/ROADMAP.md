# Roadmap

## MVP (by Feb 15, 2026)
- Deterministic data cleaning pipeline (`scripts/prepare_data.py`)
- Semantic retrieval + cached embeddings (`scripts/build_embeddings.py`)
- Multi-objective reranking with alpha slider (relevance vs monetization proxy)
- Brand safety + rules-based advertiser fit
- Optional LLM Hook + Ad Strategy (graceful degradation when no key)
- Telemetry logging + Insights tab with summary + A/B sandbox
- Deployed web UI + API (single URL)

## V1 (2–3 weeks)
- Better query understanding:
  - detect intent: “genre”, “mood”, “era”, “rating-safe”
  - apply query-aware filters automatically (with user override)
- Add explainable “why this matched” tokens (genres/era/rating evidence)
- Improve evaluation harness:
  - more queries, better relevance labeling
  - lightweight human review rubric

## V2 (1–2 months)
- Add real implicit feedback loop (click logs) and learn-to-rank prototype
- Add richer content metadata (descriptions, cast) to improve semantic search
- Brand safety classifier (beyond rating heuristics)
- Deployment hardening:
  - structured logging
  - auth (internal tool)
  - persistent analytics store

