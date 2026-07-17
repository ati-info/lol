import os
import json
import asyncio
import logging
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from . import config

log = logging.getLogger(__name__)

STATE_FILE = "userbot_state.json"
SESSION_NAME = "user_session"

# A dict to hold temporary login state per chat_id/user_id for bot-based login
ACTIVE_LOGINS = {}

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning("Could not read userbot state file: %s", e)
    
    # Fallback to config setting
    return {
        "last_checked_id": config.USERBOT_LAST_CHECKED_ID
    }

def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        log.error("Could not save userbot state file: %s", e)

def parse_chat_id(chat_input):
    if not chat_input:
        return None
    chat_input = str(chat_input).strip()
    try:
        if chat_input.startswith('-') or chat_input.isdigit():
            return int(chat_input)
    except ValueError:
        pass
    return chat_input

async def run_check_cycle(client):
    target = parse_chat_id(config.USERBOT_TARGET_CHANNEL)
    destination = parse_chat_id(config.USERBOT_DESTINATION)
    
    if not target or not destination:
        log.warning("Userbot: Target channel or destination is not set in config.")
        return

    state = load_state()
    last_checked_id = state.get("last_checked_id", 0)
    
    log.info("Userbot: Checking target channel %s starting from ID: %s", target, last_checked_id + 1)
    
    try:
        target_entity = await client.get_input_entity(target)
    except Exception as e:
        log.error("Userbot: Error accessing target channel '%s': %s", target, e)
        return
        
    try:
        destination_entity = await client.get_input_entity(destination)
    except Exception as e:
        log.error("Userbot: Error accessing destination '%s': %s", destination, e)
        return

    # Fetch the latest message ID in target channel
    latest_id = None
    try:
        async for msg in client.iter_messages(target_entity, limit=1):
            latest_id = msg.id
            break
    except Exception as e:
        log.error("Userbot: Error fetching latest message ID: %s", e)
        return

    if not latest_id:
        log.info("Userbot: Target channel is empty or no messages found.")
        return

    current_id = last_checked_id + 1
    if current_id > latest_id:
        log.info("Userbot: Already caught up. Target latest ID: %s, Current ID: %s", latest_id, current_id)
        return

    log.info("Userbot: Scanning message IDs from %s to %s...", current_id, latest_id)
    found_file = False
    
    while current_id <= latest_id:
        try:
            msg = await client.get_messages(target_entity, ids=current_id)
        except FloodWaitError as e:
            log.warning("Userbot: Flood wait required. Sleeping for %s seconds...", e.seconds)
            await asyncio.sleep(e.seconds)
            continue
        except Exception as e:
            log.error("Userbot: Error fetching message ID %s: %s", current_id, e)
            state["last_checked_id"] = current_id
            save_state(state)
            current_id += 1
            continue

        if not msg:
            # Message doesn't exist or is deleted, record progress and skip
            state["last_checked_id"] = current_id
            save_state(state)
            current_id += 1
            continue

        if msg.file:
            log.info("Userbot: Found file in message ID %s! Forwarding to %s...", current_id, destination)
            try:
                await client.forward_messages(destination_entity, msg)
                log.info("Userbot: Successfully forwarded message ID %s.", current_id)
                state["last_checked_id"] = current_id
                save_state(state)
                found_file = True
                break  # Stop checking this run, wait for next 5 minutes
            except Exception as e:
                log.error("Userbot: Failed to forward message ID %s: %s", current_id, e)
                state["last_checked_id"] = current_id
                save_state(state)
                break
        else:
            # Non-file message (like plain text), record progress and skip
            state["last_checked_id"] = current_id
            save_state(state)
            current_id += 1

    if not found_file:
        log.info("Userbot: Completed check. No new files found in this run.")

# Global reference to running background task so we don't start duplicate tasks
_userbot_task = None

async def start_userbot_loop():
    global _userbot_task
    
    if _userbot_task and not _userbot_task.done():
        log.info("Userbot: Background task is already running.")
        return

    if not config.USERBOT_API_ID or not config.USERBOT_API_HASH:
        log.info("Userbot: USERBOT_API_ID or USERBOT_API_HASH is not set. Userbot feature disabled.")
        return

    # Check if session string is configured
    if not config.USERBOT_SESSION_STRING and not os.path.exists(f"{SESSION_NAME}.session"):
        log.info("Userbot: No session string or session file found. Ready to use /login inside Telegram.")
        return

    def run():
        _userbot_task = asyncio.create_task(_userbot_loop_runner())
        
    run()

async def _userbot_loop_runner():
    from telethon.sessions import StringSession

    log.info("Userbot: Initializing personal account userbot...")
    client = None
    
    session_str = config.USERBOT_SESSION_STRING.strip() if config.USERBOT_SESSION_STRING else ""
    if session_str and len(session_str) > 10:
        try:
            from telethon.sessions import StringSession
            client = TelegramClient(StringSession(session_str), config.USERBOT_API_ID, config.USERBOT_API_HASH)
            log.info("Userbot: Successfully initialized String Session from environment variables.")
        except ValueError as e:
            log.warning("Userbot: USERBOT_SESSION_STRING in environment is invalid (%s). Falling back to file session.", e)
            client = None

    if not client:
        log.info("Userbot: Using file-based SQLite session (%s.session)...", SESSION_NAME)
        client = TelegramClient(SESSION_NAME, config.USERBOT_API_ID, config.USERBOT_API_HASH)
    
    try:
        await client.connect()
        authorized = await client.is_user_authorized()
        
        if not authorized:
            log.error("Userbot: Session is not authorized!")
            log.error("Please run /login inside Telegram or 'login_userbot.py' locally to authorize.")
            await client.disconnect()
            return
            
        log.info("Userbot: Successfully connected and authorized!")
        me = await client.get_me()
        log.info("Userbot: Running as %s (@%s)", me.first_name, me.username or "No Username")
        
        interval = config.USERBOT_CHECK_INTERVAL_SECONDS
        while True:
            try:
                await run_check_cycle(client)
            except Exception as e:
                log.exception("Userbot: Exception in check cycle: %s", e)
                
            log.info("Userbot: Sleeping for %s seconds (next check)...", interval)
            await asyncio.sleep(interval)
            
    except Exception as e:
        log.exception("Userbot: Failed to start: %s", e)
    finally:
        if client.is_connected():
            await client.disconnect()


# --- Chat-based Interactive Login Logic -----------------------------

async def init_login_session(chat_id, user_id):
    if not config.USERBOT_API_ID or not config.USERBOT_API_HASH:
        return (
            "❌ `USERBOT_API_ID` or `USERBOT_API_HASH` is not set in environment variables.\n\n"
            "Please configure them in your `.env` or Render Dashboard first!"
        )
        
    ACTIVE_LOGINS[user_id] = {
        "step": "waiting_phone",
        "client": None,
        "phone": None,
        "phone_code_hash": None
    }
    return (
        "📱 **Personal Account Login Initiated**\n\n"
        "Please send your Telegram phone number with country code (e.g., `+88017XXXXXXXX`):\n\n"
        "*(আপনার টেলিগ্রাম ফোন নম্বরটি কান্ট্রি কোডসহ দিন যেমন: `+88017XXXXXXXX`)*"
    )

async def handle_login_input(user_id, text):
    if user_id not in ACTIVE_LOGINS:
        return None
        
    session = ACTIVE_LOGINS[user_id]
    step = session["step"]
    
    if step == "waiting_phone":
        phone = text.strip().replace(" ", "")
        if not phone.startswith("+"):
            return "❌ Phone number must start with `+`. Please enter again (যেমন: `+88017XXXXXXXX`):"
            
        session["phone"] = phone
        
        from telethon.sessions import StringSession
        client = TelegramClient(StringSession(), config.USERBOT_API_ID, config.USERBOT_API_HASH)
        
        try:
            await client.connect()
            sent_code = await client.send_code_request(phone)
            
            session["client"] = client
            session["phone_code_hash"] = sent_code.phone_code_hash
            session["step"] = "waiting_otp"
            
            return (
                f"📩 **OTP sent to {phone}!**\n\n"
                "Please check your Telegram app (from official Telegram account) or SMS, and reply here with the **OTP code**:\n\n"
                "*(কোডটি লিখে এখানে রিপ্লাই দিন)*"
            )
        except Exception as e:
            if client.is_connected():
                await client.disconnect()
            ACTIVE_LOGINS.pop(user_id, None)
            return f"❌ Failed to send OTP: `{str(e)}`\n\nLogin process cancelled. Type /login to start again."
            
    elif step == "waiting_otp":
        otp = text.strip().replace(" ", "")
        client = session["client"]
        phone = session["phone"]
        phone_code_hash = session["phone_code_hash"]
        
        try:
            try:
                await client.sign_in(phone, otp, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                session["step"] = "waiting_password"
                return (
                    "🔒 **2-Step Verification (2FA) is enabled on your account!**\n\n"
                    "Please send your **2FA Password** (আপনার ২এফএ পাসওয়ার্ড লিখে রিপ্লাই দিন):"
                )
                
            return await finalize_login(user_id)
            
        except Exception as e:
            if client.is_connected():
                await client.disconnect()
            ACTIVE_LOGINS.pop(user_id, None)
            return f"❌ Login failed: `{str(e)}`\n\nLogin process cancelled. Type /login to start again."
            
    elif step == "waiting_password":
        password = text.strip()
        client = session["client"]
        
        try:
            await client.sign_in(password=password)
            return await finalize_login(user_id)
        except Exception as e:
            if client.is_connected():
                await client.disconnect()
            ACTIVE_LOGINS.pop(user_id, None)
            return f"❌ 2FA Password login failed: `{str(e)}`\n\nLogin process cancelled. Type /login to start again."

    return None

async def finalize_login(user_id):
    session = ACTIVE_LOGINS[user_id]
    client = session["client"]
    
    try:
        session_str = client.session.save()
        
        # Save session string dynamically
        config.USERBOT_SESSION_STRING = session_str
        
        # Write to .env permanently
        env_lines = []
        has_session_key = False
        if os.path.exists(".env"):
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip() and "=" in line and not line.startswith("#"):
                        key = line.split("=", 1)[0].strip()
                        if key == "USERBOT_SESSION_STRING":
                            env_lines.append(f"USERBOT_SESSION_STRING={session_str}\n")
                            has_session_key = True
                        else:
                            env_lines.append(line)
                    else:
                        env_lines.append(line)
            if not has_session_key:
                env_lines.append(f"USERBOT_SESSION_STRING={session_str}\n")
        else:
            env_lines.append(f"USERBOT_SESSION_STRING={session_str}\n")
            
        with open(".env", "w", encoding="utf-8") as f:
            f.writelines(env_lines)
            
        # Ensure state file exists
        if not os.path.exists(STATE_FILE):
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump({"last_checked_id": config.USERBOT_LAST_CHECKED_ID}, f, indent=4)
                
        # Start background task
        asyncio.create_task(_userbot_loop_runner())
        
        ACTIVE_LOGINS.pop(user_id, None)
        
        return (
            "🎉 **LOGIN SUCCESSFUL!**\n\n"
            "Your personal account userbot session is now successfully created!\n\n"
            f"🔑 **Your Session String:**\n`{session_str}`\n\n"
            "📌 **Next Steps:**\n"
            "1. Copy the session string above and save it securely.\n"
            "2. If hosting on **Render**, set an Environment Variable named `USERBOT_SESSION_STRING` with this value so it persists when Render restarts.\n"
            "3. 🤖 **The file forwarder is now running in the background!** It will scan files every 5 minutes."
        )
    except Exception as e:
        ACTIVE_LOGINS.pop(user_id, None)
        return f"❌ Failed to finalize login: `{str(e)}`"
