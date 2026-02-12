# Architecture

```mermaid
flowchart LR
  U["Recruiter / User (Web UI)"] --> FE["React SPA (Vite)"]
  FE -->|POST /api/search| BE["FastAPI Backend"]
  FE -->|POST /api/insights (optional)| BE
  BE --> CAT["Clean Catalog (data/clean_titles.csv)"]
  BE --> IDX["Retrieval Engine\nEmbeddings (preferred) or TF-IDF (fallback)"]
  IDX --> EMB["Embeddings Cache\n(data/embeddings.npy + meta)"]
  BE --> RANK["Commercial-Aware Reranker\nalpha * relevance + (1-alpha) * monetization"]
  RANK --> BS["Brand Safety Heuristics"]
  RANK --> ADV["Advertiser Vertical Heuristics"]
  BE --> LOG["Telemetry (data/events.jsonl)"]
  BE -->|Chat Completions| LLM["OpenAI API (optional)"]
```

## Key Design Decisions (Product-Framed)
- **Graceful degradation:** the app remains usable without embeddings or an LLM key (fallback retrieval + rules-based monetization view).
- **Explainability over magic:** monetization/brand safety are deliberately heuristic and surfaced with notes; the point is decision workflow clarity.
- **Explicit tradeoffs:** `alpha` is a “control surface” to communicate how product teams balance user value and business value.
- **Instrumented by default:** telemetry exists to model how a PM would iterate based on usage, not just ship a model.

