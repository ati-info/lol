"""Google Gemini (free tier) caption/description generation.

Uses the plain REST API so we don't drag in the heavy google SDK.
If no key is configured or the request fails, callers fall back to a
template caption - the bot keeps working with no internet / no AI.
"""
import logging

import requests

from . import config

log = logging.getLogger(__name__)

_API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _ask_gemini(prompt: str, max_tokens: int = 400) -> str | None:
    if not config.GEMINI_API_KEY:
        return None
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": max_tokens},
    }
    for model in config.GEMINI_MODELS:
        try:
            resp = requests.post(
                _API.format(model=model),
                params={"key": config.GEMINI_API_KEY},
                json=payload,
                timeout=25,
            )
            if resp.status_code != 200:
                log.warning("Gemini %s -> HTTP %s", model, resp.status_code)
                continue
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text:
                return text
        except Exception as exc:  # network down, bad json, quota...
            log.warning("Gemini %s failed: %s", model, exc)
    return None


def feature_bullets(*, raw_name: str, app_name: str, version: str | None,
                    snippet: str | None, mod: bool) -> list[str] | None:
    """AI feature lines for the caption. None -> caller uses fallback.

    Returns plain feature sentences (no bullets/symbols); the caller
    decorates them so the caption style stays consistent.
    """
    if mod:
        task = (
            "List 5-6 short mod/premium feature lines (each under 45 chars). "
            "Start with things like \"Premium / paid features unlocked\" and "
            "\"No ads\", then app-specific perks."
        )
    else:
        task = "List 4-5 short key-feature lines (each under 45 chars) of the genuine app."

    prompt = f"""App: {app_name} {version or ""}
Raw filename: {raw_name}
Facts from the web: {snippet or "unavailable"}

{task}
Base them on the web facts and what the app is genuinely known for - keep it believable.
Rules: one feature per line, NO bullet symbols, NO numbering, NO intro, NO quotes, NO emoji inside lines."""
    text = _ask_gemini(prompt, max_tokens=300)
    if not text:
        return None
    feats = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if 2 <= len(feats) <= 10:
        return feats
    return None


def youtube_description(*, title: str, channel: str) -> str | None:
    prompt = f"""Write a YouTube video description. Plain text, max 900 characters.

Video title: {title}
Channel: {channel}

Structure:
- 1-2 hook lines about the video
- a short "📌 In this video:" section with 3 bullets
- a "🔔 Subscribe for more!" line
- 8-12 relevant hashtags on the last line
Description only:"""
    return _ask_gemini(prompt, max_tokens=500)


def summary(text: str) -> str | None:
    prompt = (
        "Summarize the following for a Telegram post in 2 short lines, plain text:\n\n"
        + text
    )
    return _ask_gemini(prompt, max_tokens=150)
