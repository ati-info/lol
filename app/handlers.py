"""Telegram handlers - the heart of the bot.

IMPORTANT: no Telegram file is ever downloaded or re-uploaded.
Files are re-sent by their `file_id` (they stay on Telegram's servers),
we only replace the caption. Zero disk usage, tiny RAM footprint -
runs happily on Render's 512 MB free plan.
"""
import logging
import os
import time

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import ai, caption as caption_builder, cleaner, config, search
from .utils import (
    YOUTUBE_RE,
    clean_caption_text,
    first_sentence,
    human_size,
    looks_modded,
    trim,
)

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


def _fallback_features(desc: str | None, mod: bool) -> list[str]:
    feats = []
    if desc:
        feats.append(first_sentence(desc, 110))
    if mod:
        feats += ["Premium / paid features unlocked 🔓", "No ads 🚫"]
    feats.append("Free to use 🆓")
    return feats


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
        "2️⃣ Pick the clean app name + version\n"
        "3️⃣ Search the web for info about it\n"
        "4️⃣ Add a fresh AI caption with features\n"
        "5️⃣ Attach the app's picture and post it 🗃️\n\n"
        "📹 Send a YouTube link and I'll draft a description too.\n"
        "Type /help for details."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *How it works*\n\n"
        "• Forward a file ➜ I repost it (no download!) with a new "
        "AI caption + app icon. Old caption/tags are gone.\n"
        "• Forward a photo ➜ tags/links removed from caption.\n"
        "• Send a YouTube link ➜ ready-made description + hashtags.\n\n"
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


async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Check if authorized admin
    if config.ADMIN_IDS and user_id not in config.ADMIN_IDS:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
        
    from .userbot import init_login_session
    response = await init_login_session(update.effective_chat.id, user_id)
    await update.message.reply_text(response, parse_mode="Markdown")


# ------------------------------------------------------------------ files
def _file_parts(msg):
    """Return (telegram_file_obj, filename, size, ext) for docs/video/audio."""
    obj = msg.document or msg.video or msg.audio
    if not obj:
        return None
    fname = getattr(obj, "file_name", None) or f"file_{obj.file_unique_id}"
    if not getattr(obj, "file_name", None) and msg.video:
        fname += ".mp4"
    return obj, fname, getattr(obj, "file_size", 0), os.path.splitext(fname)[1].lower()


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    parts = _file_parts(msg)
    if not parts:
        return
    tg_file_obj, raw_name, fsize, _ext = parts
    _STATS["files"] += 1

    is_channel_post = msg.chat.type == "channel"
    status = None
    if not is_channel_post:
        status = await msg.reply_text("⏳ Processing…")

    try:
        # -- 1. clean app name + version from the filename --
        name, version, ext = cleaner.split_filename(raw_name)
        mod = looks_modded(raw_name)
        query = f"{name} {version or ''}".strip()

        # -- 2. web lookup: Play Store / iTunes / DuckDuckGo (all free) --
        #    tiny app icon only - the Telegram file itself is never touched
        info = search.lookup_app(query)
        name = info.get("name") or name  # prefer the official store name
        version = version or info.get("version")
        icon_bytes = info.get("icon")

        # -- 3. AI feature list (Gemini free tier), fallback without a key --
        features = ai.feature_bullets(
            raw_name=raw_name, app_name=name, version=version,
            snippet=info.get("desc"), mod=mod,
        ) or _fallback_features(info.get("desc"), mod)

        caption = caption_builder.build_caption(
            name=name, version=version, features=features,
            size=human_size(fsize), ext=ext, mod=mod,
            link=config.CHANNEL_LINK or None,
        )

        # -- 4. repost BY FILE_ID: no download, no upload, any file size --
        #    Telegram rule: photo + document CANNOT share one album, so the
        #    (photo + caption) and the file go as two separate messages.
        dest = _destination(update)
        photo_posted = False
        if icon_bytes:
            try:
                await context.bot.send_photo(
                    chat_id=dest,
                    photo=icon_bytes,
                    caption=trim(caption, 1024),
                    reply_markup=_channel_button(),
                )
                photo_posted = True
            except Exception as exc:
                log.warning("photo post failed (%s) -> doc-only fallback", exc)

        if photo_posted:
            mini_title = f"{name}{' v' + version if version else ''}"
            await context.bot.send_document(
                chat_id=dest,
                document=tg_file_obj.file_id,
                caption=f"📥 {trim(mini_title, 200)}  •  {human_size(fsize)}",
            )
        else:
            await context.bot.send_document(
                chat_id=dest,
                document=tg_file_obj.file_id,
                caption=trim(caption, 1024),
                reply_markup=_channel_button(),
            )

        if status:
            await status.edit_text(
                "✅ Posted to channel!" if config.CHANNEL_ID else "✅ Done — caption replaced!"
            )
    except Exception as exc:
        log.exception("file handling failed")
        if status:
            await status.edit_text(f"⚠️ Failed: {type(exc).__name__}. Try again.")


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
    user_id = update.effective_user.id

    # 1. Check if user is in ACTIVE_LOGINS session (Userbot config)
    from .userbot import ACTIVE_LOGINS, handle_login_input
    if user_id in ACTIVE_LOGINS:
        response = await handle_login_input(user_id, text)
        if response:
            await msg.reply_text(response, parse_mode="Markdown")
        return

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
    app.add_handler(CommandHandler("login", cmd_login))
    app.add_handler(
        MessageHandler(
            (filters.Document.ALL | filters.VIDEO | filters.AUDIO) & ~filters.ChatType.CHANNEL,
            handle_file
        )
    )
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.ChatType.CHANNEL, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.ChatType.CHANNEL, handle_text))
