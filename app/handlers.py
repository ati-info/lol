"""Telegram handlers - the heart of the bot."""
import logging
import os
import tempfile
import time

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    InputMediaDocument,
    InputMediaPhoto,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import ai, apk, cleaner, config, search
from .utils import YOUTUBE_RE, clean_caption_text, human_size, trim

log = logging.getLogger(__name__)

_STARTED_AT = time.time()
_STATS = {"files": 0, "photos": 0, "youtube": 0}


# ------------------------------------------------------------------ helpers
def _channel_button() -> InlineKeyboardMarkup | None:
    if not config.CHANNEL_LINK:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("📢 Join Our Channel", url=config.CHANNEL_LINK)]]
    )


def _destination(update: Update):
    """Post to the configured channel if set, otherwise reply to sender."""
    if config.CHANNEL_ID:
        return config.CHANNEL_ID
    return update.effective_chat.id


def _fallback_caption(name: str, version: str | None, size: str, snippet: str | None) -> str:
    title = f"📱 {name} {version or ''}".strip()
    lines = [title, ""]
    if snippet:
        lines += [f"ℹ️ {trim(snippet, 220)}", ""]
    lines.append("🆓 Free Download")
    lines.append(f"📦 Size: {size}")
    return "\n".join(lines).strip()


def _age() -> str:
    secs = int(time.time() - _STARTED_AT)
    h, secs = divmod(secs, 3600)
    m, s = divmod(secs, 60)
    return f"{h}h {m}m {s}s"


# ------------------------------------------------------------------ commands
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"🤖 *{config.BOT_NAME}*\n\n"
        "Forward ⏩ any file / APK / video / photo to me.\n\n"
        "I will:\n"
        "1️⃣ Remove the old caption, @tags & links\n"
        "2️⃣ Read the real app name + version\n"
        "3️⃣ Search the web for info about it\n"
        "4️⃣ Generate a fresh AI caption with features\n"
        "5️⃣ Attach the app's picture and post it 🗃️\n\n"
        "📹 Send a YouTube link and I'll draft a description too.\n"
        "Type /help for details."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *How it works*\n\n"
        "• Forward a file ➜ I repost it cleaned + AI caption + app icon.\n"
        "• Forward a photo ➜ tags/links removed from caption.\n"
        "• Send a YouTube link ➜ ready-made title/description/hashtags.\n\n"
        "Commands:\n"
        "/start – welcome\n"
        "/ping – check if I'm alive\n"
        "/stats – usage stats\n"
        "/id – your chat id",
        parse_mode="Markdown",
    )


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🏓 Pong! Uptime: {_age()}")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 *Stats*\n"
        f"• Files processed: {_STATS['files']}\n"
        f"• Photos cleaned: {_STATS['photos']}\n"
        f"• YouTube drafts: {_STATS['youtube']}\n"
        f"• Uptime: {_age()}",
        parse_mode="Markdown",
    )


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Chat ID: `{update.effective_chat.id}`\n"
        f"Your ID: `{update.effective_user.id}`",
        parse_mode="Markdown",
    )


# ------------------------------------------------------------------ files
def _file_parts(msg):
    """Return (telegram_file_obj, filename, size, mime, ext) for docs/video/audio."""
    obj = msg.document or msg.video or msg.audio
    if not obj:
        return None
    fname = getattr(obj, "file_name", None) or f"file_{obj.file_unique_id}"
    mime = getattr(obj, "mime_type", "") or ""
    if not getattr(obj, "file_name", None) and msg.video:
        fname += ".mp4"
    return obj, fname, getattr(obj, "file_size", 0), mime, os.path.splitext(fname)[1].lower()


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    parts = _file_parts(msg)
    if not parts:
        return
    tg_file_obj, raw_name, fsize, mime, ext = parts
    _STATS["files"] += 1

    is_channel_post = msg.chat.type == "channel"
    status = None
    if not is_channel_post:
        status = await msg.reply_text("⏳ Processing your file…")

    local_path = None
    tmpdir = tempfile.mkdtemp(prefix="fc_")
    try:
        name, version, _ = cleaner.split_filename(raw_name)
        icon_bytes = None

        # -- 1. small APKs: download once, read REAL name/version/icon --
        if ext == ".apk" and fsize and fsize <= config.MAX_RENAME_BYTES:
            try:
                local_path = os.path.join(tmpdir, raw_name)
                tg_file = await tg_file_obj.get_file()
                await tg_file.download_to_drive(local_path)
                meta = apk.parse_apk(local_path)
                if meta:
                    name = meta.get("label") or name
                    version = meta.get("version") or version
                    icon_bytes = meta.get("icon_bytes")
            except Exception as exc:
                log.warning("apk download/parse failed: %s", exc)
                local_path = None
        elif fsize and fsize <= config.MAX_RENAME_BYTES:
            # non-apk but renameable: download so we can re-upload with clean name
            try:
                local_path = os.path.join(tmpdir, raw_name)
                tg_file = await tg_file_obj.get_file()
                await tg_file.download_to_drive(local_path)
            except Exception as exc:
                log.warning("download failed: %s", exc)
                local_path = None

        query = f"{name} {version or ''}".strip()

        # -- 2. web info + picture (free DuckDuckGo, no keys) --
        snippet = search.app_info(query)
        if icon_bytes is None:
            icon_bytes = search.app_image_bytes(query)

        # -- 3. AI caption (Gemini free tier), fallback to template --
        size_txt = human_size(fsize)
        caption = ai.file_caption(
            raw_name=raw_name, app_name=name, version=version,
            snippet=snippet, size=size_txt,
        ) or _fallback_caption(name, version, size_txt, snippet)
        if config.CHANNEL_LINK and len(caption) < 880:
            caption += f"\n\n🔗 {config.CHANNEL_LINK}"

        # -- 4. deliver --
        dest = _destination(update)
        if local_path:  # re-upload with the CLEAN filename
            new_fname = cleaner.safe_filename(name, version, ext)
            file_payload = InputFile(open(local_path, "rb"), filename=new_fname)
        else:  # too big to re-download: reuse Telegram's copy via file_id
            file_payload = tg_file_obj.file_id

        if icon_bytes:
            media = [
                InputMediaPhoto(media=icon_bytes, caption=trim(caption, 1024)),
                InputMediaDocument(media=file_payload),
            ]
            await context.bot.send_media_group(chat_id=dest, media=media)
        else:
            await context.bot.send_document(
                chat_id=dest,
                document=file_payload,
                caption=trim(caption, 1024),
                reply_markup=_channel_button(),
            )

        if status:
            await status.edit_text(
                "✅ Posted!" if config.CHANNEL_ID else "✅ Done — cleaned & regenerated!"
            )
    except Exception as exc:
        log.exception("file handling failed")
        if status:
            await status.edit_text(f"⚠️ Failed: {type(exc).__name__}. Try again.")
    finally:
        try:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


# ------------------------------------------------------------------ photos
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg.photo:
        return
    _STATS["photos"] += 1
    cleaned = clean_caption_text(msg.caption or "")
    dest = _destination(update)
    await context.bot.send_photo(
        chat_id=dest,
        photo=msg.photo[-1].file_id,
        caption=trim(cleaned, 1024) if cleaned else None,
        reply_markup=_channel_button() if cleaned else None,
    )
    if msg.chat.type != "channel":
        await msg.reply_text("✅ Caption cleaned & posted!")


# ------------------------------------------------------------------ text / youtube
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    text = msg.text or ""
    yt = YOUTUBE_RE.search(text)
    if not yt:
        await msg.reply_text(
            "⏩ Forward any file/APK to clean & repost it, "
            "or send a YouTube link for an AI description. See /help"
        )
        return

    _STATS["youtube"] += 1
    url = yt.group(0)
    status = await msg.reply_text("🔍 Fetching video info…")
    info = search.youtube_oembed(url)
    if not info:
        await status.edit_text("⚠️ Couldn't fetch video info. Check the link.")
        return

    desc = ai.youtube_description(title=info["title"], channel=info["author"]) or (
        f"{info['title']}\n\n🔔 Subscribe for more!\n\n#{info['author'].replace(' ', '')}"
    )
    caption = f"🎬 {trim(info['title'], 120)}\n📺 {info['author']}\n🔗 {url}"
    if info.get("thumbnail"):
        await status.delete()
        await msg.reply_photo(photo=info["thumbnail"], caption=caption)
    else:
        await status.edit_text(caption)
    await msg.reply_text(f"📝 AI Description (copy-paste ready):\n\n{desc}")


# ------------------------------------------------------------------ wiring
def register(app: Application) -> None:
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(
        MessageHandler(filters.Document.ALL | filters.VIDEO | filters.AUDIO, handle_file)
    )
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
