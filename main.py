"""Entry point.

Two modes, chosen automatically:

* WEBHOOK_URL / RENDER_EXTERNAL_URL set (Render deploy) -> Flask receives
  Telegram updates + UptimeRobot pings on $PORT.
* Not set (local testing) -> long polling, Flask still serves /health.

Run:  python main.py
"""
import asyncio
import logging
import threading

from telegram.ext import Application
from waitress import serve

from app import config, handlers, server

logging.basicConfig(
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("main")


async def _run_ptb(application: Application, ready: threading.Event) -> None:
    await application.initialize()
    await application.start()

    if config.WEBHOOK_URL:
        url = f"{config.WEBHOOK_URL}/webhook/{config.BOT_TOKEN}"
        await application.bot.set_webhook(url=url, drop_pending_updates=True)
        log.info("Webhook mode -> %s", url)
    else:
        await application.updater.start_polling(drop_pending_updates=True)
        log.info("Polling mode (local) started")

    ready.set()
    await asyncio.Event().wait()  # run forever


def _start_bot_thread() -> tuple[Application, asyncio.AbstractEventLoop, threading.Event]:
    loop = asyncio.new_event_loop()
    application = Application.builder().token(config.BOT_TOKEN).build()
    handlers.register(application)
    ready = threading.Event()

    def _runner():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_run_ptb(application, ready))

    threading.Thread(target=_runner, name="ptb-loop", daemon=True).start()
    ready.wait(timeout=60)
    return application, loop


def main() -> None:
    application, loop = _start_bot_thread()
    server.wire(application, loop)
    log.info("HTTP server listening on 0.0.0.0:%s", config.PORT)
    serve(server.flask_app, host="0.0.0.0", port=config.PORT, threads=8)


if __name__ == "__main__":
    main()
