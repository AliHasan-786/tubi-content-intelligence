# Experiment Plan

## Experiment 1: Multi-Objective Ranking Slider
### Hypothesis
Giving users an explicit control to trade off relevance vs monetization (`alpha`) will:
- reduce “no good options” frustration for some queries (higher relevance)
- increase monetization proxy score for others (lower relevance)

### Variants
- **A (Relevance-heavy):** default alpha = 0.85
- **B (Balanced):** default alpha = 0.65
- **C (Monetization-heavy):** default alpha = 0.35

### Primary Success
- QPSR proxy improves in A/B vs baseline.

### Secondary
- Avg monetization_score of top-5 does not degrade by >X% for relevance-heavy variants.
- Brand-safety risk distribution does not worsen.

### Segmentation
- Query intent: “genre-forward” vs “mood-forward” queries
- Ratings filters present vs absent

### Risks
- Users may not understand the slider: mitigate with clear labels and default value.
- Proxy metrics may mislead: mitigate by clearly labeling proxies and using qualitative review.

## Experiment 2: AI Hook + Ad Strategy (LLM Layer)
### Hypothesis
Showing a concise hook and an advertiser fit narrative increases user confidence and speeds selection.

### Variants
- A: no AI insights
- B: AI insights for top match only

### Success
- QPSR proxy increases
- reduced repeat-search rate

### Guardrails
- enforce allow-listed advertiser verticals
- keep explanations short; never present them as “truth”

