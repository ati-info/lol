"""Environment configuration for the bot.

Every setting comes from an environment variable so nothing secret ever
lives inside the repository. See `.env.example` for a ready template.
"""
import os


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}\n"
            "Set it in Render dashboard / .env file and redeploy."
        )
    return value


# --- Required ---------------------------------------------------------
BOT_TOKEN: str = _require("BOT_TOKEN")

# --- Optional ---------------------------------------------------------
# Google AI Studio key (free tier): https://aistudio.google.com/apikey
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
# Model preference, tried in order. flash-lite is the cheapest free-tier one.
GEMINI_MODELS = [
    m.strip()
    for m in os.getenv(
        "GEMINI_MODELS", "gemini-2.5-flash-lite,gemini-2.0-flash-lite,gemini-2.0-flash"
    ).split(",")
    if m.strip()
]

# Channel where finished posts are published. @username or numeric -100... id.
# Leave empty to simply reply in the same chat instead.
CHANNEL_ID: str = os.getenv("CHANNEL_ID", "").strip()
if CHANNEL_ID.lstrip("-").isdigit():
    CHANNEL_ID = int(CHANNEL_ID)

# Public link used on the "Join Channel" button / caption footer.
CHANNEL_LINK: str = os.getenv("CHANNEL_LINK", "").strip()

# Comma separated admin user ids (for /stats etc.)
ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x
}

# Webhook mode is used automatically on Render (RENDER_EXTERNAL_URL exists).
WEBHOOK_URL: str = (os.getenv("WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
PORT: int = int(os.getenv("PORT", "8080"))

# Bot display name used in messages.
BOT_NAME: str = os.getenv("BOT_NAME", "FileCraft AI")

# --- Userbot Settings (Optional) --------------------------------------
USERBOT_API_ID: int = int(os.getenv("USERBOT_API_ID", "0").strip() or 0)
USERBOT_API_HASH: str = os.getenv("USERBOT_API_HASH", "").strip()
USERBOT_PHONE: str = os.getenv("USERBOT_PHONE", "").strip()
USERBOT_TARGET_CHANNEL: str = os.getenv("USERBOT_TARGET_CHANNEL", "").strip()
USERBOT_DESTINATION: str = os.getenv("USERBOT_DESTINATION", "").strip()
USERBOT_LAST_CHECKED_ID: int = int(os.getenv("USERBOT_LAST_CHECKED_ID", "0").strip() or 0)
USERBOT_CHECK_INTERVAL_SECONDS: int = int(os.getenv("USERBOT_CHECK_INTERVAL_SECONDS", "300").strip() or 300)

