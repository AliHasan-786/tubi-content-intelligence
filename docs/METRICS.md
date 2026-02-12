# Metrics & Instrumentation

This prototype has no real watch-time or ad-revenue data. The goal is to show **how a PM would define measurement**, even when working with proxies.

## North Star Metric (NSM)
**Qualified Play Start Rate (QPSR)** (proxy):
- Definition: % of search sessions where a user clicks a recommended title link.
- Why: aligns with “users find something they’ll actually watch”.

In this repo, we approximate “qualified” via offline expectations in `eval/` rather than real click logs.

## Supporting Metrics
### Engagement Proxies
- Time-to-first-result (latency)
- “No results” rate (filters too strict or retrieval fails)
- Repeat search rate per session (frustration signal)

### Monetization Proxies
- Avg `monetization_score` of top-5 results
- % of top results in `brand_safety.risk=high`
- Distribution of advertiser vertical suggestions

## Guardrails
- p95 search latency < 500ms on a small catalog
- Do not present `risk=high` items as top result when alpha heavily favors monetization without clear warning notes
- LLM output must:
  - be one sentence per field
  - select advertiser vertical from an allow-list

## Instrumentation (What’s Logged)
Events are appended to `data/events.jsonl`:
- `search`: query, alpha, filters, engine type, latency, result titles
- `insight`: query, title, model, advertiser vertical

## Dashboards (In-App)
The Insights tab surfaces:
- total searches
- top queries
- avg latency
- engine breakdown
- A/B sandbox comparing two `alpha` values (proxy experimentation workflow)

