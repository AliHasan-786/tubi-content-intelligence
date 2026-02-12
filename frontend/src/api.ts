import type { InsightResponse, SearchRequest, SearchResponse, TelemetrySummary } from "./types";

export const API_BASE = (import.meta as any).env?.VITE_API_BASE_URL ?? "";

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    try {
      const j = JSON.parse(txt);
      const detail = j?.detail ?? j?.message;
      if (detail) throw new Error(String(detail));
    } catch {
      // ignore
    }
    throw new Error(txt || `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export async function search(req: SearchRequest): Promise<SearchResponse> {
  return jsonFetch<SearchResponse>("/api/search", {
    method: "POST",
    body: JSON.stringify(req)
  });
}

export async function getInsights(args: { query: string; title: string }): Promise<InsightResponse> {
  return jsonFetch<InsightResponse>("/api/insights", {
    method: "POST",
    body: JSON.stringify({
      query: args.query,
      title: args.title,
    })
  });
}

export async function telemetrySummary(): Promise<TelemetrySummary> {
  return jsonFetch<TelemetrySummary>("/api/telemetry/summary");
}

export async function health(): Promise<any> {
  return jsonFetch<any>("/health");
}
