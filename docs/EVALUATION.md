# Evaluation (Proxy, Offline)

This repo includes an offline evaluation harness to demonstrate **data-driven decision making** even without production logs.

## Why “Proxy”?
We do not have:
- watch history
- session context
- click / play outcomes
- ad revenue / auction data

So we define relevance heuristically via expected genres, year ranges, ratings, and runtime constraints.

## What’s Included
- `eval/queries.jsonl`: a small query set with “expected” constraints
- `eval/run_eval.py`: compares TF-IDF vs embeddings (when available)

## How to Run
1. Prepare clean data:
   - `python scripts/prepare_data.py`
2. (Optional) Build embeddings:
   - `python scripts/build_embeddings.py`
3. Run eval:
   - `python eval/run_eval.py --k 5`

## Metrics
- **Hit Rate@K:** at least one relevant result in top K
- **MRR@K:** how early the first relevant result appears
- **nDCG@K:** ranking quality for binary relevance

## Interpretation
Treat these as directional signals to:
- validate that semantic search is better than TF-IDF for “vibe” queries
- detect regressions when tweaking combined features or ranking logic

