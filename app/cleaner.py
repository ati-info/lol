"""Turn a messy forwarded filename into a clean app name + version.

Example:
    "Capcut pro 27.55v By @SomethingModder.apk"
        -> ("CapCut Pro", "27.55", ".apk")
"""
import os
import re

_VERSION_RE = re.compile(r"(?:^|[^\d.])(\d+(?:\.\d+){1,3})(?![\d.])")

_REMOVE_WORDS = {
    "by", "from", "join", "subscribe", "channel", "official", "original",
    "download", "free", "new", "latest", "update", "updated", "full",
    "version", "release", "cracked", "crack", "hack", "hacked", "v", "ver",
}

# Words we keep but normalize the casing of.
_SPECIAL_CASING = {
    "pro": "Pro", "mod": "Mod", "modded": "Mod", "premium": "Premium",
    "plus": "Plus", "lite": "Lite", "ai": "AI", "hd": "HD", "4k": "4K",
    "vpn": "VPN", "mobile": "Mobile",
    "capcut": "CapCut", "youtube": "YouTube", "tiktok": "TikTok",
    "whatsapp": "WhatsApp", "instagram": "Instagram", "spotify": "Spotify",
    "alight": "Alight", "kinemaster": "KineMaster", "picsart": "PicsArt",
    "pubg": "PUBG", "freefire": "Free Fire", "ff": "FF",
}


def split_filename(filename: str):
    """Return (clean_name, version_or_None, extension)."""
    if not filename:
        return "Unknown App", None, ""

    base, ext = os.path.splitext(filename)
    ext = ext.lower()

    # 1. remove urls, t.me links (even glued like "t.meXyz"), @mentions, emails
    base = re.sub(
        r"(https?://\S+|www\.\S+|(?:telegram\.me|t\.me)[\w./\-]*)",
        " ", base, flags=re.I,
    )
    base = re.sub(r"@[\w_]{2,}", " ", base)
    base = re.sub(r"[\w.+-]+@[\w-]+\.\w+", " ", base)
    # "... by ChannelName" promo tail
    base = re.sub(r"\bby\s+[\w.]{3,}", " ", base, flags=re.I)

    # 2. drop bracketed promo chunks like [Join @xyz]
    base = re.sub(r"[\[\(\{][^\]\)\}]*(@|join|http|t\.me)[^\]\)\}]*[\]\)\}]", " ", base, flags=re.I)
    base = re.sub(r"[\[\(\{\]\)\}]", " ", base)

    # 3. extract the version BEFORE dots get destroyed ("27.55v" / "v9.0.28")
    version = None
    m = _VERSION_RE.search(base)
    if m:
        version = m.group(1)
        base = base[: m.start(1)] + " " + base[m.end(1):]

    # 4. normalize separators & drop emojis/symbols (keep dots between digits)
    base = re.sub(r"[_\-\+]+", " ", base)
    base = re.sub(r"(?<!\d)\.(?!\d)", " ", base)
    base = re.sub(r"[^\w\s.]", " ", base, flags=re.UNICODE)

    # 5. filter promo words, normalize casing
    words = []
    for token in base.split():
        low = token.lower().strip()
        if not low or len(low) <= 1:
            continue
        if low in _REMOVE_WORDS:
            continue
        if re.fullmatch(r"\d{1,2}", low) and version:
            continue  # stray number fragments when a dotted version exists
        nice = _SPECIAL_CASING.get(low)
        if nice is not None:
            words.append(nice)
            continue
        words.append(token.capitalize() if low.isalpha() else token)

    name = " ".join(words).strip() or "Unknown App"
    # de-duplicate repeated tokens ("Pro Pro" -> "Pro")
    name = re.sub(r"\b(\w+)( \1\b)+", r"\1", name)
    return name, version, ext


def safe_filename(name: str, version, ext: str) -> str:
    flat = f"{name} {version or ''}".strip() or "file"
    flat = re.sub(r"[^\w.\- ]+", "", flat).strip().replace(" ", "_")
    return f"{flat}{ext}"
