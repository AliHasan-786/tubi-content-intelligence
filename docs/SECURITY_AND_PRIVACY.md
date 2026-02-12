# Security & Privacy Notes (Demo)

This project is a prototype and intentionally avoids collecting user-level data.

## API Keys
- Never hardcode API keys in code, docs, or commits.
- For deployments: store `OPENAI_API_KEY` as a server secret.
- The frontend “Settings” key input is for local demos only and is stored in `localStorage`.

## Telemetry
- Telemetry is written to `data/events.jsonl` as a lightweight demo of instrumentation.
- Logged fields are limited to: query text, filters, latency, engine type, and result titles.
- No user identifiers are collected.

## Model Output Risks
- LLM outputs can hallucinate; mitigations include:
  - strict allow-list for advertiser vertical
  - JSON-only output contract
  - graceful fallback if generation fails

## Production Hardening (Out of Scope)
- AuthN/AuthZ for internal tools
- Centralized logging with retention policies
- PII classification + redaction
- Full brand-safety policy enforcement beyond heuristics

