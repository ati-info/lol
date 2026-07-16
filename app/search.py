"""Free web lookups - no API keys needed.

For an app name we try several free sources and merge what they know:

1. Google Play Store page   -> official name, description, icon (scraped)
2. Apple iTunes Search API  -> official name, version, description, artwork
3. DuckDuckGo text/images   -> fallback for apps that are not on stores
   (modded apks etc.)

Images are normalised to clean PNG with Pillow (Telegram can reject WebP),
so posts reliably come WITH a picture.
Everything is wrapped in try/except: if the network fails, the bot
continues without web info ("no internet problem solved").
"""
import html
import io
import logging
import re

import requests

from .utils import first_sentence, trim

log = logging.getLogger(__name__)

try:  # package was renamed `ddgs`; support both
    from ddgs import DDGS  # type: ignore
except ImportError:  # pragma: no cover
    from duckduckgo_search import DDGS  # type: ignore

try:
    from PIL import Image

    _HAS_PIL = True
except Exception:  # pragma: no cover - optional but recommended
    _HAS_PIL = False

_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def _get(url: str, **kw) -> requests.Response:
    kw.setdefault("timeout", 15)
    kw.setdefault("headers", _UA)
    return requests.get(url, **kw)


# ------------------------------------------------------------------ images
def _normalise_image(data: bytes) -> bytes | None:
    """Convert any downloaded image to a Telegram-friendly PNG."""
    if not _HAS_PIL:
        return data
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
        if im.mode != "RGB":  # RGBA/LA/P/webp -> put on white background
            im = im.convert("RGBA")
            bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
            im = Image.alpha_composite(bg, im).convert("RGB")
        im.thumbnail((512, 512))
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
        return buf.getvalue()
    except Exception as exc:
        log.debug("image normalise failed: %s", exc)
        return None


def _fetch_image(url: str, cap: int = 2 * 1024 * 1024) -> bytes | None:
    try:
        resp = _get(url, stream=True)
        if resp.status_code != 200:
            return None
        if not resp.headers.get("Content-Type", "").startswith("image"):
            return None
        declared = int(resp.headers.get("Content-Length") or 0)
        if declared and declared > cap:
            return None
        data = resp.content
        if not (1024 < len(data) <= cap):
            return None
        return _normalise_image(data)
    except Exception as exc:
        log.debug("image fetch failed (%s): %s", url, exc)
        return None


# ------------------------------------------------------------------ sources
def _meta(page_html: str, prop: str) -> str | None:
    for tag in re.findall(r"<meta\b[^>]*>", page_html):
        if (
            f'property="{prop}"' in tag
            or f'name="{prop}"' in tag
            or f"property='{prop}'" in tag
            or f"name='{prop}'" in tag
        ):
            m = re.search(r'content="([^"]*)"', tag) or re.search(r"content='([^']*)'", tag)
            if m:
                return html.unescape(m.group(1)).strip()
    return None


def _play_store(query: str) -> dict | None:
    """Scrape the app's Google Play page (no API key needed)."""
    try:
        search_url = (
            "https://play.google.com/store/search?q="
            + requests.utils.quote(query)
            + "&c=apps&hl=en&gl=US"
        )
        resp = _get(search_url)
        if resp.status_code != 200:
            return None
        m = re.search(r"/store/apps/details\?id=([\w.]+)", resp.text)
        if not m:
            return None
        page = _get(f"https://play.google.com/store/apps/details?id={m.group(1)}&hl=en&gl=US")
        if page.status_code != 200:
            return None

        out = {"name": None, "version": None, "desc": None, "icon_url": None}
        title = _meta(page.text, "og:title")
        if title:
            title = re.sub(r"\s*-\s*(Apps on )?Google Play.*$", "", title).strip()
            out["name"] = trim(title, 60) or None
        desc = _meta(page.text, "og:description")
        if desc:
            out["desc"] = first_sentence(desc, 260) or None
        icon = _meta(page.text, "og:image")
        if icon:
            if "play-lh" in icon and not re.search(r"=\w", icon.split("/")[-1]):
                icon += "=w512-h512"  # ask for a big icon
            out["icon_url"] = icon
        return out if any(out.values()) else None
    except Exception as exc:
        log.warning("play store lookup failed: %s", exc)
        return None


def _itunes(query: str) -> dict | None:
    """Apple's public Search API (free, no key) - official name/artwork."""
    try:
        resp = requests.get(
            "https://itunes.apple.com/search",
            params={"term": query, "entity": "software", "limit": 1, "country": "us"},
            headers=_UA,
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        results = resp.json().get("results") or []
        if not results:
            return None
        app = results[0]
        return {
            "name": trim(app.get("trackName") or "", 60) or None,
            "version": (app.get("version") or "").strip() or None,
            "desc": first_sentence(app.get("description") or "", 260) or None,
            "icon_url": app.get("artworkUrl512") or None,
        }
    except Exception as exc:
        log.warning("itunes lookup failed: %s", exc)
        return None


def _ddg_text(query: str) -> str | None:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"{query} app", max_results=3))
        for item in results:
            body = (item.get("body") or "").strip()
            if len(body) > 40:
                return trim(body, 300)
    except Exception as exc:
        log.warning("DDG text search failed: %s", exc)
    return None


def _ddg_image(query: str) -> bytes | None:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.images(f"{query} app icon", max_results=5))
        for item in results:
            url = item.get("image")
            if not url:
                continue
            data = _fetch_image(url)
            if data:
                return data
    except Exception as exc:
        log.warning("DDG image search failed: %s", exc)
    return None


# ------------------------------------------------------------------ combined
def lookup_app(query: str) -> dict:
    """Merge all free sources: {'name','version','desc','icon'} (any may be None)."""
    info = {"name": None, "version": None, "desc": None, "icon": None}

    ps = _play_store(query)
    if ps:
        info["name"] = ps.get("name")
        info["version"] = ps.get("version")
        info["desc"] = ps.get("desc")
        if ps.get("icon_url"):
            info["icon"] = _fetch_image(ps["icon_url"])

    it = _itunes(query)
    if it:
        info["name"] = info["name"] or it.get("name")
        info["version"] = info["version"] or it.get("version")
        info["desc"] = info["desc"] or it.get("desc")
        if info["icon"] is None and it.get("icon_url"):
            info["icon"] = _fetch_image(it["icon_url"])

    if info["desc"] is None:
        info["desc"] = _ddg_text(query)
    if info["icon"] is None:
        info["icon"] = _ddg_image(query)

    return info


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
