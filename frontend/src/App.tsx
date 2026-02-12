import React, { useEffect, useMemo, useState, useRef } from "react";
import type { InsightResponse, MovieResult, SearchFilters, SearchResponse } from "./types";
import { API_BASE, getInsights, health, search } from "./api";

type TabKey = "search" | "about";

const EXAMPLE_QUERIES = [
  "90s action thrillers with a gritty vibe",
  "sad movies for a rainy day",
  "something funny but not too cheesy",
  "sci-fi adventure with found-family energy",
  "crime drama that feels like a slow burn"
];

const RATINGS = ["TV-MA", "TV-14", "TV-PG", "TV-G", "TV-Y", "TV-Y7", "TV-Y7_FV", "R", "PG-13", "PG", "G"] as const;

function clamp(n: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, n));
}
function scoreFmt(x: number) {
  if (!Number.isFinite(x)) return "0.00";
  return x.toFixed(2);
}
function pctFmt(x: number) {
  if (!Number.isFinite(x)) return "0%";
  return `${Math.round(x * 100)}%`;
}
function riskColor(risk: "low" | "medium" | "high") {
  if (risk === "low") return "#29d49c";
  if (risk === "high") return "#ff4d4d";
  return "#ffb020";
}
function riskBg(risk: "low" | "medium" | "high") {
  if (risk === "low") return "rgba(41, 212, 156, 0.10)";
  if (risk === "high") return "rgba(255, 77, 77, 0.10)";
  return "rgba(255, 176, 32, 0.10)";
}

/* ── Genre visual mapping for poster placeholders ───────────────── */
const GENRE_VISUALS: Record<string, { icon: string; gradient: string }> = {
  Action: { icon: "💥", gradient: "linear-gradient(135deg, #b71c1c 0%, #d84315 100%)" },
  Comedy: { icon: "😂", gradient: "linear-gradient(135deg, #f9a825 0%, #ff8f00 100%)" },
  Horror: { icon: "😱", gradient: "linear-gradient(135deg, #1a0000 0%, #4a0020 100%)" },
  Drama: { icon: "🎭", gradient: "linear-gradient(135deg, #4a148c 0%, #7b1fa2 100%)" },
  Romance: { icon: "💕", gradient: "linear-gradient(135deg, #c2185b 0%, #e91e63 100%)" },
  "Sci-Fi": { icon: "🚀", gradient: "linear-gradient(135deg, #0d47a1 0%, #1565c0 100%)" },
  Thriller: { icon: "🔪", gradient: "linear-gradient(135deg, #263238 0%, #37474f 100%)" },
  Adventure: { icon: "🗺️", gradient: "linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%)" },
  Animation: { icon: "✨", gradient: "linear-gradient(135deg, #0288d1 0%, #7c4dff 100%)" },
  Crime: { icon: "🔫", gradient: "linear-gradient(135deg, #212121 0%, #424242 100%)" },
  Documentary: { icon: "📹", gradient: "linear-gradient(135deg, #33691e 0%, #558b2f 100%)" },
  Family: { icon: "👨‍👩‍👧‍👦", gradient: "linear-gradient(135deg, #039be5 0%, #ffb300 100%)" },
  Fantasy: { icon: "🧙", gradient: "linear-gradient(135deg, #6a1b9a 0%, #ab47bc 100%)" },
  Mystery: { icon: "🔍", gradient: "linear-gradient(135deg, #1a237e 0%, #283593 100%)" },
  Music: { icon: "🎵", gradient: "linear-gradient(135deg, #ad1457 0%, #d81b60 100%)" },
  War: { icon: "⚔️", gradient: "linear-gradient(135deg, #3e2723 0%, #5d4037 100%)" },
  Western: { icon: "🤠", gradient: "linear-gradient(135deg, #bf360c 0%, #e65100 100%)" },
};
const DEFAULT_VISUAL = { icon: "🎬", gradient: "linear-gradient(135deg, #ff5a1f 0%, #ff9100 100%)" };

function genreVisual(genres: string[]) {
  for (const g of genres) if (GENRE_VISUALS[g]) return GENRE_VISUALS[g];
  return DEFAULT_VISUAL;
}

/* ── Determine view mode from alpha ─────────────────────────────── */
type ViewMode = "viewer" | "blended" | "revenue";
function viewMode(alpha: number): ViewMode {
  if (alpha >= 0.65) return "viewer";
  if (alpha <= 0.35) return "revenue";
  return "blended";
}
function viewLabel(mode: ViewMode) {
  if (mode === "viewer") return { emoji: "🎬", label: "Viewer Mode", sub: "Ranked by what viewers want to watch" };
  if (mode === "revenue") return { emoji: "💰", label: "Revenue Mode", sub: "Ranked by advertiser value & ad revenue" };
  return { emoji: "⚖️", label: "Balanced Mode", sub: "Blending viewer relevance with commercial value" };
}

/* ── Fallback insight generator ──────────────────────────────────── */
function makeFallbackInsight(m: MovieResult): InsightResponse {
  const genre = m.genres[0] || "General";
  const hooks: Record<string, string> = {
    Action: `High-energy ${m.rating || ""} content drives strong session depth. ${m.title} pairs well with pre-roll auto and gaming spots.`,
    Comedy: `Feel-good comedy like ${m.title} delivers brand-safe impressions across CPG and retail.`,
    Horror: `Horror draws lean-in engagement. ${m.title} suits endemic advertisers (gaming, streaming) comfortable with edgier placements.`,
    Drama: `Premium drama like ${m.title} attracts upscale brand placements — financial services, automotive, luxury.`,
    Romance: `Romance viewers skew high-intent for lifestyle brands. ${m.title} is a natural fit for beauty and wellness.`,
  };
  const hook = hooks[genre] || `${m.title} offers solid reach across broad audience segments.`;
  return {
    title: m.title,
    hook,
    ad_strategy: `Position mid-roll inventory around emotional peaks. ${m.ad_opportunity.primary_vertical} brands are a natural contextual fit. Brand safety: ${m.brand_safety.tier}.`,
    advertiser_vertical: m.ad_opportunity.primary_vertical,
    model: "fallback-heuristic",
  };
}


/* ════════════════════════════════════════════════════════════════════
   MAIN APP
   ════════════════════════════════════════════════════════════════════ */

export function App() {
  const [tab, setTab] = useState<TabKey>("about");
  const [query, setQuery] = useState(EXAMPLE_QUERIES[0]);
  const [alpha, setAlpha] = useState(0.8);
  const [filters, setFilters] = useState<SearchFilters>({
    content_types: ["movie", "series", "unknown"],
    ratings: [],
    year_min: undefined,
    year_max: undefined,
  });
  const [resp, setResp] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [healthState, setHealthState] = useState<any>(null);
  const [showFilters, setShowFilters] = useState(false);

  const hasSearched = useRef(false);

  const mode = viewMode(alpha);
  const modeInfo = viewLabel(mode);

  const runSearch = async () => {
    setErr(null);
    setLoading(true);
    try {
      const r = await search({ query, top_k: 8, alpha, filters, include_debug: false });
      setResp(r);
    } catch (e: any) {
      setErr(e?.message ?? String(e));
      setResp(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    (async () => {
      try { setHealthState(await health()); } catch { setHealthState(null); }
    })();
  }, []);

  // Auto-search on first visit to search tab
  useEffect(() => {
    if (tab === "search" && !hasSearched.current && !resp) {
      hasSearched.current = true;
      runSearch();
    }
  }, [tab]);

  /* ── Accent color based on mode ────────────────────────────────── */
  const accentVar = mode === "viewer" ? "#ff5a1f" : mode === "revenue" ? "#00bfa5" : "#7c4dff";

  return (
    <div className="wrap" data-mode={mode}>
      {/* ─── Top Bar ──────────────────────────────────────────────── */}
      <header className="topbar fadeUp">
        <div className="brand" onClick={() => setTab("search")} style={{ cursor: "pointer" }}>
          <div className="brand-title">Tubi Content Intelligence</div>
        </div>
        <nav className="tabs">
          <div className={`tab ${tab === "search" ? "active" : ""}`} onClick={() => setTab("search")}>
            Search
          </div>
          <div className={`tab ${tab === "about" ? "active" : ""}`} onClick={() => setTab("about")}>
            About
          </div>
        </nav>
        <div className="pills">
          {healthState?.ok ? (
            <div className="pill"><span className="dot good" /><span>{healthState.catalog_rows} titles</span></div>
          ) : null}
        </div>
      </header>

      {tab === "about" ? <AboutPage onSearch={() => setTab("search")} /> : (
        <main className="search-layout fadeUp" style={{ animationDelay: "80ms" }}>
          {/* ── Left Column: Controls ──────────────────────────────── */}
          <aside className="controls-col">
            {/* Search Input */}
            <div className="card">
              <input
                className="search-input"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder='Try: "sad movies for a rainy day"'
                onKeyDown={(e) => { if (e.key === "Enter") runSearch(); }}
              />
              <div className="example-chips">
                {EXAMPLE_QUERIES.map((q) => (
                  <button key={q} className={`chip ${query === q ? "chip-active" : ""}`} onClick={() => { setQuery(q); }}>
                    {q}
                  </button>
                ))}
              </div>
            </div>

            {/* THE HERO: Alpha Slider */}
            <div className="card slider-card">
              <div className="slider-header">
                <span className="slider-title">{modeInfo.emoji} {modeInfo.label}</span>
                <span className="slider-alpha">α = {alpha.toFixed(2)}</span>
              </div>
              <p className="slider-sub">{modeInfo.sub}</p>
              <div className="slider-track-wrap">
                <input
                  className="hero-slider"
                  type="range"
                  min={0}
                  max={1}
                  step={0.01}
                  value={alpha}
                  onChange={(e) => setAlpha(clamp(parseFloat(e.target.value), 0, 1))}
                  style={{
                    background: `linear-gradient(90deg, #00bfa5 0%, #7c4dff 50%, #ff5a1f 100%)`
                  }}
                />
                <div className="slider-labels">
                  <span>💰 Revenue</span>
                  <span>⚖️ Balanced</span>
                  <span>🎬 Viewer</span>
                </div>
              </div>
              <div className="slider-formula">
                score = <span style={{ color: "#ff5a1f" }}>α</span> × relevance + <span style={{ color: "#00bfa5" }}>(1−α)</span> × monetization
              </div>
              <button className="btn search-btn" onClick={runSearch} disabled={loading}>
                {loading ? "Searching…" : "Search"}
              </button>
            </div>

            {/* Filters (collapsible) */}
            <button className="filter-toggle" onClick={() => setShowFilters(!showFilters)}>
              {showFilters ? "▾ Hide Filters" : "▸ Filters"}
            </button>
            {showFilters && (
              <div className="card filter-card fadeUp">
                <div className="filter-section">
                  <label>Ratings</label>
                  <div className="chips">
                    {RATINGS.map((r) => {
                      const sel = Boolean(filters.ratings?.includes(r));
                      return (
                        <button key={r} className={`chip ${sel ? "chip-active" : ""}`}
                          onClick={() => {
                            const cur = new Set(filters.ratings ?? []);
                            if (cur.has(r)) cur.delete(r); else cur.add(r);
                            setFilters({ ...filters, ratings: Array.from(cur) });
                          }}
                        >{r}</button>
                      );
                    })}
                  </div>
                </div>
                <div className="filter-section">
                  <label>Year Range</label>
                  <div className="year-row">
                    <input className="input" type="number" placeholder="Min" value={filters.year_min ?? ""}
                      onChange={(e) => setFilters({ ...filters, year_min: e.target.value ? parseInt(e.target.value) : undefined })} />
                    <span className="muted">–</span>
                    <input className="input" type="number" placeholder="Max" value={filters.year_max ?? ""}
                      onChange={(e) => setFilters({ ...filters, year_max: e.target.value ? parseInt(e.target.value) : undefined })} />
                  </div>
                </div>
                <div className="filter-section">
                  <label>Type</label>
                  <div className="chips">
                    {(["movie", "series", "unknown"] as const).map((t) => {
                      const sel = Boolean(filters.content_types?.includes(t));
                      return (
                        <button key={t} className={`chip ${sel ? "chip-active" : ""}`} style={{ textTransform: "capitalize" }}
                          onClick={() => {
                            const cur = new Set(filters.content_types ?? []);
                            if (cur.has(t)) cur.delete(t); else cur.add(t);
                            setFilters({ ...filters, content_types: Array.from(cur) });
                          }}
                        >{t}</button>
                      );
                    })}
                  </div>
                </div>
                <button className="btn ghost" style={{ marginTop: 8, fontSize: 12 }}
                  onClick={() => setFilters({ content_types: ["movie", "series", "unknown"], ratings: [], year_min: undefined, year_max: undefined })}>
                  Reset Filters
                </button>
              </div>
            )}
          </aside>

          {/* ── Right Column: Results ─────────────────────────────── */}
          <section className="results-col">
            {/* Mode Banner */}
            <div className="mode-banner" style={{ borderColor: accentVar }}>
              <span className="mode-emoji">{modeInfo.emoji}</span>
              <div>
                <div className="mode-label" style={{ color: accentVar }}>{modeInfo.label}</div>
                <div className="mode-sub">{modeInfo.sub}</div>
              </div>
            </div>

            {err ? <div className="error-msg">{err}</div> : null}

            {loading ? (
              <div className="loading-state">
                <div className="spinner" />
                <span>Searching catalog…</span>
              </div>
            ) : resp ? (
              <>
                <div className="results-meta">
                  {resp.results.length} results · {resp.latency_ms}ms · α={resp.alpha.toFixed(2)}
                </div>
                <div className="results-list">
                  {resp.results.map((m, idx) => (
                    <ResultCard key={`${m.title}-${idx}`} movie={m} mode={mode} query={query} rank={idx + 1} />
                  ))}
                </div>
              </>
            ) : (
              <div className="empty-state">Type a vibe and search to discover content</div>
            )}
          </section>
        </main>
      )}
    </div>
  );
}


/* ════════════════════════════════════════════════════════════════════
   RESULT CARD — adapts based on mode
   ════════════════════════════════════════════════════════════════════ */

function ResultCard(props: { movie: MovieResult; mode: ViewMode; query: string; rank: number }) {
  const { movie: m, mode, query, rank } = props;
  const vis = genreVisual(m.genres);
  const [expanded, setExpanded] = useState(false);
  const [insight, setInsight] = useState<InsightResponse | null>(null);
  const [insightLoading, setInsightLoading] = useState(false);
  const [posterError, setPosterError] = useState(false);

  // Use the backend image proxy directly — it resolves fresh CDN URLs and streams bytes
  const posterSrc = m.title_url
    ? `${API_BASE}/api/poster/image?tubi_url=${encodeURIComponent(m.title_url)}`
    : null;

  const fetchInsight = async () => {
    if (insight) { setExpanded(!expanded); return; }
    setExpanded(true);
    setInsightLoading(true);
    try {
      const r = await getInsights({ query, title: m.title });
      setInsight(r);
    } catch {
      setInsight(makeFallbackInsight(m));
    } finally {
      setInsightLoading(false);
    }
  };

  const showCommercial = mode === "revenue" || mode === "blended";
  const showPoster = posterSrc && !posterError;

  return (
    <div className={`result-card ${mode === "revenue" ? "card-revenue" : mode === "blended" ? "card-blended" : "card-viewer"}`}>
      {/* Poster */}
      <div className="card-poster" style={{ background: showPoster ? "#0a0a1a" : vis.gradient }}>
        <span className="poster-rank">#{rank}</span>
        {showPoster ? (
          <img
            src={posterSrc!}
            alt={m.title}
            className="poster-img"
            onError={() => setPosterError(true)}
          />
        ) : (
          <>
            <span className="poster-icon">{vis.icon}</span>
            <span className="poster-meta">{m.content_type?.toUpperCase()}<br />{m.release_year || "—"}</span>
          </>
        )}
      </div>

      {/* Info */}
      <div className="card-body">
        <div className="card-top-row">
          <h3 className="card-title">{m.title}</h3>
          {m.title_url ? (
            <a className="tubi-link" href={m.title_url} target="_blank" rel="noreferrer">▶ Watch on Tubi</a>
          ) : null}
        </div>

        <div className="card-meta">
          {m.rating && <span className="meta-tag">{m.rating}</span>}
          {m.runtime_minutes && <span className="meta-tag">{m.runtime_minutes}m</span>}
          {m.genres.slice(0, 4).map((g) => <span className="genre-tag" key={g}>{g}</span>)}
        </div>

        {/* Scores — adapt to mode */}
        <div className="card-scores">
          <ScoreBar label="Relevance" value={m.relevance_score} color="#ff5a1f" />
          {showCommercial && <ScoreBar label="Monetization" value={m.monetization_score} color="#00bfa5" />}
          {showCommercial && <ScoreBar label="Blended" value={m.final_score} color="#7c4dff" />}
        </div>

        {/* Commercial data — only in revenue/blended mode */}
        {showCommercial && (
          <div className="commercial-data">
            <div className="ad-fit">
              <span className="cd-label">Ad Fit:</span>
              <span className="ad-primary">{m.ad_opportunity.primary_vertical}</span>
              {m.ad_opportunity.secondary_verticals.slice(0, 3).map((v) => (
                <span className="ad-secondary" key={v}>{v}</span>
              ))}
            </div>
            <div className="brand-safety" style={{ borderColor: riskColor(m.brand_safety.risk), background: riskBg(m.brand_safety.risk) }}>
              <span>Brand Safety: <b style={{ color: riskColor(m.brand_safety.risk) }}>{m.brand_safety.risk.toUpperCase()}</b></span>
              <span className="bs-tier">{m.brand_safety.tier}</span>
            </div>
          </div>
        )}

        {/* AI Insight Toggle */}
        <button className="insight-btn" onClick={fetchInsight}>
          {insightLoading ? "Generating…" : insight ? (expanded ? "▾ Hide Insight" : "▸ Show Insight") : "💡 AI Insight"}
        </button>
        {expanded && insight && (
          <div className={`insight-panel ${insight.model === "fallback-heuristic" ? "insight-fallback" : ""}`}>
            <div className="insight-row"><b>Hook:</b> {insight.hook}</div>
            <div className="insight-row"><b>Ad Strategy ({insight.advertiser_vertical}):</b> {insight.ad_strategy}</div>
            {insight.model === "fallback-heuristic" && (
              <div className="insight-note">Generated using heuristic rules. Connect a Gemini or OpenAI key via .env for LLM-powered insights.</div>
            )}
            {insight.model !== "fallback-heuristic" && (
              <div className="insight-note" style={{ color: "#00bfa5" }}>Powered by {insight.model}</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}


/* ── Score Bar Component ─────────────────────────────────────────── */

function ScoreBar(props: { label: string; value: number; color: string }) {
  const pct = clamp(props.value, 0, 1) * 100;
  return (
    <div className="score-bar-row">
      <span className="sb-label">{props.label}</span>
      <div className="sb-track">
        <div className="sb-fill" style={{ width: `${pct}%`, background: props.color }} />
      </div>
      <span className="sb-val">{scoreFmt(props.value)}</span>
    </div>
  );
}


/* ════════════════════════════════════════════════════════════════════
   ABOUT PAGE — concise, punchy, tells the story
   ════════════════════════════════════════════════════════════════════ */

function AboutPage(props: { onSearch: () => void }) {
  return (
    <div className="about-page fadeUp" style={{ animationDelay: "100ms" }}>
      {/* Hero */}
      <section className="about-hero">
        <h1>What should Tubi recommend?</h1>
        <p className="hero-sub">
          In ad-supported streaming, the best content for the viewer isn't always the
          best content for revenue. This tool lets you explore that tradeoff — search by
          mood, drag a slider, and watch how recommendations change.
        </p>
        <button className="btn hero-cta" onClick={props.onSearch}>
          Try it →
        </button>
      </section>

      {/* Three cards */}
      <section className="about-cards">
        <div className="about-card">
          <div className="ac-icon">🎯</div>
          <h3>The Tradeoff</h3>
          <p>
            A user searches "dark crime thrillers." The top match is an obscure TV-MA title — great for the viewer,
            hard to monetize. A PG-13 crime drama ranks #4 but generates 3× the ad revenue.
            Which do you surface?
          </p>
        </div>
        <div className="about-card">
          <div className="ac-icon">⚙️</div>
          <h3>How It Works</h3>
          <p>
            Semantic search (sentence embeddings) understands <em>vibes</em>, not just keywords.
            Each title gets a relevance score and a monetization score.
            The alpha slider blends them: <code>α × relevance + (1−α) × monetization</code>.
          </p>
        </div>
        <div className="about-card">
          <div className="ac-icon">📊</div>
          <h3>Why It Matters</h3>
          <p>
            AVOD platforms balance user satisfaction against ad revenue daily.
            This tool models that decision explicitly — with brand safety tiers,
            advertiser-fit data, and AI-generated content strategy per title.
          </p>
        </div>
      </section>

      {/* Technical footer */}
      <section className="about-tech">
        <h3>Technical Architecture</h3>
        <div className="tech-pills">
          <span className="tp">FastAPI backend</span>
          <span className="tp">Sentence-Transformers (MiniLM-L6)</span>
          <span className="tp">Multi-objective ranking</span>
          <span className="tp">Brand safety heuristics</span>
          <span className="tp">GPT-4o-mini insights</span>
          <span className="tp">React + TypeScript</span>
          <span className="tp">302 real Tubi titles</span>
        </div>
      </section>
    </div>
  );
}
