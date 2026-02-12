# PRD: Smart-Scout & Ad-Insight (Product Dashboard)

## 1) Summary
**Smart-Scout & Ad-Insight** is a recruiter-facing prototype framed as an internal tool a Product Manager could use at an AVOD streaming service.

It combines:
- **Content Discovery:** semantic search for a specific viewer “vibe”
- **Commercial Awareness:** brand suitability + advertiser vertical fit (proxy)
- **Decision-Making:** explainable tradeoffs, metrics, and experimentation surfaces

This project is intentionally built to demonstrate product thinking, not just model-building.

## 2) Problem
### User Problem (Viewers)
Large catalogs create **choice overload**. Users often know the *vibe* they want, not a specific title.

### Business Problem (AVOD)
In AVOD, revenue depends on:
- **engagement/retention** (time spent, sessions)
- **ad suitability** (brand safety constraints)
- **contextual alignment** (matching advertiser demand to content context)

Traditional student recommenders optimize “similarity” but ignore revenue constraints and suitability guardrails.

## 3) Goals / Non-Goals
### Goals
1. Reduce time-to-find: help users quickly discover “right vibe” titles.
2. Provide commercial context: show *why* a title is monetizable (proxy) and *which* advertiser vertical fits best.
3. Make tradeoffs explicit: allow a user to tune ranking between relevance and monetization.
4. Enable measurement: instrument the workflow and expose telemetry in an Insights view.

### Non-Goals (Explicitly Out of Scope)
- True personalization (no user-level watch history in this dataset)
- Real ad targeting (no user identity, no auction data, no advertiser contracts)
- Guaranteeing brand safety (heuristics only; real systems require policy + classifiers + human review)

## 4) Personas (Internal + External)
1. **Viewer (External):** wants content that matches mood/vibe quickly.
2. **Product Manager (Internal):** needs to test search concepts, validate tradeoffs, and propose experiments.
3. **Ad Sales / Monetization (Internal):** cares about brand suitability and contextual fit.
4. **Content Ops (Internal):** cares about metadata quality and taxonomy consistency.

## 5) User Stories
### Discovery (Consumer Experience)
- As a viewer, I can type “90s action thrillers with a gritty vibe” and get relevant titles.
- As a viewer, I can filter by rating/year/content type to find something I can watch now.

### Monetization (Revenue + Suitability)
- As a PM, I can see a rules-based advertiser fit for each result.
- As Ad Sales, I can quickly spot brand-safety risk (e.g., TV-MA + Horror).

### Insights (Metrics + Experiments)
- As a PM, I can see top queries and basic performance stats from telemetry.
- As a PM, I can run a side-by-side “A/B sandbox” comparing two ranking weights.

## 6) Functional Requirements
### FR1: Deterministic Data Prep
- Normalize whitespace / separators (including non-breaking spaces).
- Parse runtime into minutes when possible.
- Preserve stable `combined_features` for retrieval.

### FR2: Semantic Retrieval
- Primary: sentence-transformer embeddings (`all-MiniLM-L6-v2`) with cached embeddings.
- Fallback: TF-IDF when embeddings are unavailable (demo resilience).

### FR3: Commercial-Aware Reranking (Multi-Objective)
- Score each title with:
  - `relevance_score` from retrieval similarity (proxy for “viewer value”)
  - `monetization_score` from explainable heuristics (proxy for “business value”)
- PM-facing control: `alpha` slider to tune tradeoff.

### FR4: Brand Safety + Advertiser Fit (Explainable)
- Brand safety tier + risk with notes (rating + genre heuristic).
- Rules-based advertiser vertical suggestions (genre + rating).

### FR5: AI Insight Layer (Optional)
- If `OPENAI_API_KEY` is provided:
  - Generate **The Hook** (1 sentence) and **The Ad-Strategy** (1 sentence)
  - Enforce advertiser vertical to a fixed set
- If missing:
  - Hide AI insights and show a friendly “enable AI” prompt.

### FR6: Telemetry
- Log searches and AI insight calls locally as JSONL events.
- Show summary in Insights (top queries, avg latency, engine breakdown).

## 7) Success Metrics (Proxy, Since No Real Usage Data)
### North Star (Proxy)
- **Qualified Recommendation Rate:** % of searches where at least one result matches the query intent (via heuristic relevance rules in `eval/`).

### Input Metrics
- Search latency (p50/p95)
- “No results” rate
- Share of searches using monetization-heavy ranking (alpha < 0.5)

### Guardrails
- Do not surface “brand unsafe” content as a top monetization pick without warning notes.
- Avoid LLM hallucination by forcing a fixed advertiser vertical set + JSON output.

## 8) Risks / Mitigations
- **LLM hallucination:** constrained output + explicit schema + fallback behavior.
- **Metadata quality:** deterministic cleaning, taxonomy normalization, and explicit missing-data handling.
- **Misinterpretation of proxies as truth:** UI copy + docs clearly label monetization scoring as heuristic/proxy.

## 9) Launch Plan (MVP)
- MVP is “recruiter-playable” via a deployed web UI + API.
- Provide demo script + screenshots + short recorded walkthrough (outside repo scope).

