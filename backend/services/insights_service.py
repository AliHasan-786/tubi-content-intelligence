from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests

from backend.utils.ranking import AD_VERTICALS, suggest_ad_verticals


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _load_prompt_template() -> str:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    path = os.path.join(repo_root, "prompts", "hook_and_ad_strategy.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        # Fallback to an inline template if the file is missing.
        return (
            "You are an Associate Product Manager at an AVOD streaming service. "
            "Return ONLY valid JSON with keys: hook, ad_strategy, advertiser_vertical."
        )


def _extract_json(text: str) -> Optional[Dict]:
    """
    Tries to parse a JSON object from a model response even if extra text surrounds it.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    m = _JSON_BLOCK_RE.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _build_prompt(
    *,
    query: str,
    title: str,
    genres: List[str],
    rating: Optional[str],
    release_year: Optional[int],
    runtime_minutes: Optional[int],
    content_type: str,
    allowed_verticals: List[str],
) -> str:
    """Build the prompt. Uses the template file if available, otherwise inline."""
    tmpl = _load_prompt_template()
    try:
        return tmpl.format(
            query=query,
            title=title,
            content_type=content_type,
            genres_csv=(", ".join(genres) if genres else "Unknown"),
            rating=(rating or "Unknown"),
            release_year=(release_year or "Unknown"),
            runtime_minutes=(runtime_minutes or "Unknown"),
            allowed_verticals_csv=", ".join(allowed_verticals),
        )
    except (KeyError, IndexError):
        # If template formatting fails, use a direct prompt
        return (
            f"You are an AVOD content strategist. "
            f"A user searched for \"{query}\" and the top result is \"{title}\" "
            f"({content_type}, {', '.join(genres) if genres else 'Unknown'}, "
            f"rated {rating or 'Unknown'}, {release_year or 'Unknown'}, {runtime_minutes or 'Unknown'}min). "
            f"Return ONLY valid JSON with these keys:\n"
            f"- hook: a compelling 1-2 sentence pitch for why this content is valuable\n"
            f"- ad_strategy: 1-2 sentences on ad placement strategy\n"
            f"- advertiser_vertical: one of [{', '.join(allowed_verticals)}]\n"
            f"JSON only, no markdown."
        )


def generate_hook_and_ad_strategy_gemini(
    *,
    gemini_api_key: str,
    gemini_model: str,
    query: str,
    title: str,
    genres: List[str],
    rating: Optional[str],
    release_year: Optional[int],
    runtime_minutes: Optional[int],
    content_type: str,
) -> Tuple[str, str, str]:
    """Generate insight using Google Gemini API."""
    if not gemini_api_key:
        raise RuntimeError("Missing Gemini API key.")

    candidate_verticals = suggest_ad_verticals(genres=genres, rating=rating)
    allowed_verticals = list(dict.fromkeys(candidate_verticals + list(AD_VERTICALS)))

    prompt = _build_prompt(
        query=query,
        title=title,
        genres=genres,
        rating=rating,
        release_year=release_year,
        runtime_minutes=runtime_minutes,
        content_type=content_type,
        allowed_verticals=allowed_verticals,
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={gemini_api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": "You write concise, product-oriented insights for AVOD content strategy. Return ONLY valid JSON."},
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 250,
            "temperature": 0.4,
        },
    }

    r = requests.post(url, json=payload, timeout=20)
    if r.status_code >= 400:
        raise RuntimeError(f"Gemini error {r.status_code}: {r.text}")

    j = r.json()
    try:
        content = j["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise RuntimeError(f"Unexpected Gemini response: {j}")

    parsed = _extract_json(content) or {}
    hook = str(parsed.get("hook") or "").strip()
    ad_strategy = str(parsed.get("ad_strategy") or "").strip()
    vertical = str(parsed.get("advertiser_vertical") or "").strip()

    if not hook or not ad_strategy or not vertical:
        raise RuntimeError(f"Could not parse model JSON. Raw: {content}")

    if vertical not in allowed_verticals:
        # Soft fix: use the first candidate vertical instead of failing
        vertical = candidate_verticals[0] if candidate_verticals else allowed_verticals[0]

    return hook, ad_strategy, vertical


def generate_hook_and_ad_strategy(
    *,
    openai_api_key: str,
    openai_model: str,
    query: str,
    title: str,
    genres: List[str],
    rating: Optional[str],
    release_year: Optional[int],
    runtime_minutes: Optional[int],
    content_type: str,
    api_base_url: str = "https://api.openai.com/v1/chat/completions",
) -> Tuple[str, str, str]:
    """Generate insight using an OpenAI-compatible API (works with llmapi.ai, OpenAI, etc.)."""
    if not openai_api_key:
        raise RuntimeError("Missing API key.")

    candidate_verticals = suggest_ad_verticals(genres=genres, rating=rating)
    allowed_verticals = list(dict.fromkeys(candidate_verticals + list(AD_VERTICALS)))

    prompt = _build_prompt(
        query=query,
        title=title,
        genres=genres,
        rating=rating,
        release_year=release_year,
        runtime_minutes=runtime_minutes,
        content_type=content_type,
        allowed_verticals=allowed_verticals,
    )

    url = api_base_url
    headers = {"Authorization": f"Bearer {openai_api_key}", "Content-Type": "application/json"}
    payload = {
        "model": openai_model,
        "messages": [
            {"role": "system", "content": "You write concise, product-oriented insights for AVOD content strategy."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 180,
        "temperature": 0.4,
    }

    r = requests.post(url, headers=headers, json=payload, timeout=20)
    if r.status_code >= 400:
        raise RuntimeError(f"API error {r.status_code}: {r.text}")
    j = r.json()
    try:
        content = j["choices"][0]["message"]["content"]
    except Exception:
        raise RuntimeError(f"Unexpected OpenAI response: {j}")

    parsed = _extract_json(content) or {}
    hook = str(parsed.get("hook") or "").strip()
    ad_strategy = str(parsed.get("ad_strategy") or "").strip()
    vertical = str(parsed.get("advertiser_vertical") or "").strip()

    if not hook or not ad_strategy or not vertical:
        raise RuntimeError(f"Could not parse model JSON. Raw: {content}")

    if vertical not in allowed_verticals:
        raise RuntimeError(f"Model returned invalid advertiser_vertical: {vertical}")

    return hook, ad_strategy, vertical


def lookup_title_row(df: pd.DataFrame, title: str) -> Optional[pd.Series]:
    m = df["Title"].astype(str) == str(title)
    hits = df.loc[m]
    if hits.empty:
        return None
    return hits.iloc[0]
