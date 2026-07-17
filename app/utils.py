"""Small helpers shared across the bot."""
import re

# ---------------------------------------------------------------- caption cleaning
_URL_RE = re.compile(r"(https?://\S+|www\.\S+|t\.me/\S+|telegram\.me/\S+)", re.I)
_MENTION_RE = re.compile(r"@[\w_]{2,}")
_HASHTAG_RE = re.compile(r"#[\w\u0980-\u09FF]+")  # Latin + Bangla hashtags
_PROMO_LINE_RE = re.compile(
    r"(join|subscribe|channel|backup|support|group)[\s:]*(@|https?|t\.me)", re.I
)


def clean_caption_text(text: str) -> str:
    """Strip @mentions, links, hashtags and promo lines from an old caption."""
    if not text:
        return ""
    lines_out = []
    for line in text.splitlines():
        if _PROMO_LINE_RE.search(line) and len(line) < 120:
            continue  # pure promo line -> drop
        line = _URL_RE.sub("", line)
        line = _MENTION_RE.sub("", line)
        line = _HASHTAG_RE.sub("", line)
        line = re.sub(r"\s{2,}", " ", line).strip(" -\t")
        if line:
            lines_out.append(line)
    return "\n".join(lines_out).strip()


# ---------------------------------------------------------------- misc
def human_size(num_bytes) -> str:
    if not num_bytes:
        return "Unknown size"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def trim(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


YOUTUBE_RE = re.compile(
    r"(https?://)?(www\.|m\.)?(youtube\.com/(watch\?v=|shorts/|live/)|youtu\.be/)[\w\-?=&%]+",
    re.I,
)


# ---------------------------------------------------------------- fancy text
_BOLD = {}
for _i, _ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    _BOLD[_ch] = chr(0x1D5D4 + _i)
for _i, _ch in enumerate("abcdefghijklmnopqrstuvwxyz"):
    _BOLD[_ch] = chr(0x1D5EE + _i)
for _i, _ch in enumerate("0123456789"):
    _BOLD[_ch] = chr(0x1D7EC + _i)


def ubold(text: str) -> str:
    """'Mod Info' -> '𝗠𝗼𝗱 𝗜𝗻𝗳𝗼' (unicode mathematical bold)."""
    return "".join(_BOLD.get(c, c) for c in text)


_MOD_RE = re.compile(
    r"(mod|modded|premium|crack(ed)?|patched?|unlock(ed)?|vip|plus\+)", re.I
)


def looks_modded(filename: str) -> bool:
    """True if the raw filename hints at a mod/premium build."""
    return bool(_MOD_RE.search(filename or ""))


def first_sentence(text: str, limit: int = 260) -> str:
    """First sentence (or two, if very short) of a longer description."""
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text)
    out = parts[0] if parts else text
    if len(out) < 40 and len(parts) > 1:
        out = out + " " + parts[1]
    return trim(out, limit)
