"""Free web lookups - no API keys needed.

* DuckDuckGo text search  -> a 1-2 line description of the app
* DuckDuckGo image search -> the app's icon/picture to attach to the post

Everything is wrapped in try/except: if the network or the library fails,
the bot silently continues without web info ("no internet problem solved").
"""
import logging

import requests

from .utils import trim

log = logging.getLogger(__name__)

try:  # the package was renamed `ddgs`; support both
    from ddgs import DDGS  # type: ignore
except ImportError:  # pragma: no cover
    from duckduckgo_search import DDGS  # type: ignore


def app_info(query: str) -> str | None:
    """A short factual snippet about the app, or None."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"{query} app", max_results=3))
        for item in results:
            body = (item.get("body") or "").strip()
            if len(body) > 40:
                return trim(body, 320)
    except Exception as exc:
        log.warning("DDG text search failed: %s", exc)
    return None


def app_image_bytes(query: str, max_bytes: int = 2 * 1024 * 1024) -> bytes | None:
    """Download the app's icon/cover image from the web, or None.

    Only a tiny image (a few hundred KB tops) is fetched - never the
    Telegram file itself - so RAM stays flat on the Render free plan.
    """
    urls: list[str] = []
    try:
        with DDGS() as ddgs:
            results = list(ddgs.images(f"{query} app icon", max_results=5))
        urls = [r.get("image") for r in results if r.get("image")]
    except Exception as exc:
        log.warning("DDG image search failed: %s", exc)

    for url in urls:
        try:
            resp = requests.get(
                url,
                timeout=15,
                headers={"User-Agent": "Mozilla/5.0 (compatible; bot/1.0)"},
                stream=True,
            )
            ctype = resp.headers.get("Content-Type", "")
            if resp.status_code != 200 or not ctype.startswith("image"):
                continue
            # skip reading the body if the server says it's too big
            declared = int(resp.headers.get("Content-Length") or 0)
            if declared and declared > max_bytes:
                continue
            data = resp.content
            if 1024 < len(data) <= max_bytes:
                return data
        except Exception as exc:
            log.debug("image download failed (%s): %s", url, exc)
    return None


def youtube_oembed(url: str) -> dict | None:
    """YouTube title/channel without any API key (public oEmbed endpoint)."""
    try:
        resp = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "title": data.get("title", ""),
                "author": data.get("author_name", ""),
                "thumbnail": data.get("thumbnail_url", ""),
            }
    except Exception as exc:
        log.warning("YouTube oEmbed failed: %s", exc)
    return None
