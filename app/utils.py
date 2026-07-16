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
