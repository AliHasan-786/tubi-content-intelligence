import json
import os
import threading
import time
from typing import Any, Dict, Optional


class EventLogger:
    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()

        # Ensure directory exists.
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)

    def log(self, event_type: str, payload: Dict[str, Any]) -> None:
        evt = {
            "ts": int(time.time() * 1000),
            "type": event_type,
            "payload": payload,
        }
        line = json.dumps(evt, ensure_ascii=True)
        with self._lock:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def summarize(self, max_lines: int = 5000) -> Dict[str, Any]:
        """
        Lightweight aggregation for the Insights tab.
        Reads last N lines to avoid large-file issues.
        """
        if not os.path.exists(self._path):
            return {
                "total_searches": 0,
                "top_queries": [],
                "avg_latency_ms": None,
                "engine_breakdown": {},
            }

        # Read last max_lines lines.
        with self._lock:
            with open(self._path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-max_lines:]

        total_searches = 0
        latency_sum = 0
        latency_n = 0
        engine_breakdown: Dict[str, int] = {}
        query_counts: Dict[str, int] = {}

        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                evt = json.loads(ln)
            except Exception:
                continue
            if evt.get("type") != "search":
                continue
            total_searches += 1
            p = evt.get("payload", {}) or {}
            q = str(p.get("query", "")).strip().lower()
            if q:
                query_counts[q] = query_counts.get(q, 0) + 1
            eng = str(p.get("engine_type", "")).strip() or "unknown"
            engine_breakdown[eng] = engine_breakdown.get(eng, 0) + 1
            lat = p.get("latency_ms")
            if isinstance(lat, (int, float)):
                latency_sum += float(lat)
                latency_n += 1

        top_queries = sorted(query_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
        return {
            "total_searches": total_searches,
            "top_queries": [{"query": q, "count": c} for q, c in top_queries],
            "avg_latency_ms": (latency_sum / latency_n) if latency_n else None,
            "engine_breakdown": engine_breakdown,
        }

