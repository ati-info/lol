"""Tiny Flask server.

* `GET /` and `GET /health`  -> liveness endpoints (UptimeRobot pings these)
* `POST /webhook/<token>`    -> Telegram webhook receiver (used on Render)

The Telegram application itself runs on an asyncio loop in a background
thread; incoming webhook updates are handed to it thread-safely.
"""
import asyncio
import logging
import time

from flask import Flask, request

_started = time.time()
log = logging.getLogger(__name__)

flask_app = Flask(__name__)
_ptb_app = None
_loop: asyncio.AbstractEventLoop | None = None


def wire(ptb_app, loop: asyncio.AbstractEventLoop) -> None:
    global _ptb_app, _loop
    _ptb_app, _loop = ptb_app, loop


@flask_app.get("/")
def index():
    return "🤖 Bot is alive and kicking!", 200


@flask_app.get("/health")
def health():
    return {
        "status": "ok",
        "uptime_seconds": int(time.time() - _started),
        "bot_ready": _ptb_app is not None,
    }, 200


@flask_app.post("/webhook/<token>")
def webhook(token: str):
    from . import config  # late import to avoid cycles

    if token != config.BOT_TOKEN:
        return "forbidden", 403
    if _ptb_app is None or _loop is None:
        return "starting", 200

    from telegram import Update

    try:
        update = Update.de_json(request.get_json(force=True), _ptb_app.bot)
        future = asyncio.run_coroutine_threadsafe(
            _ptb_app.process_update(update), _loop
        )
        future.result(timeout=15)
    except Exception as exc:
        log.exception("webhook processing failed: %s", exc)
    return "ok", 200
