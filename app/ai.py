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


def file_caption(*, raw_name: str, app_name: str, version: str | None,
                 snippet: str | None, size: str) -> str | None:
    """AI caption for a shared file/APK. None -> caller uses fallback."""
    prompt = f"""You write catchy captions for a Telegram channel that shares Android/PC apps and tools.

Raw filename: {raw_name}
Clean app name: {app_name} {version or ""}
Info from the web: {snippet or "not available"}
File size: {size}

Write ONE caption, plain text, max 600 characters, exactly in this shape:
Line 1: a single fitting emoji, the app name and version only (no promo words).
Then a blank line, then "✨ Features:" followed by 3-5 short bullet lines, each starting with "• ".
Base the bullets on the web info and what the app is genuinely known for. If the raw filename suggests it is a modded/premium build you may mention unlocked features, no watermark, 4K export or that it is free - keep it believable.
No links, no @mentions, no hashtags, no quotes, no markdown. Caption only:"""
    text = _ask_gemini(prompt, max_tokens=400)
    if text and len(text) <= 900:
        return text
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
