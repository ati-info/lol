import os
import json
import asyncio
import logging
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from . import config

log = logging.getLogger(__name__)

STATE_FILE = "userbot_state.json"
SESSION_NAME = "user_session"

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

async def start_userbot_loop():
    if not config.USERBOT_API_ID or not config.USERBOT_API_HASH:
        log.info("Userbot: USERBOT_API_ID or USERBOT_API_HASH is not set. Userbot feature disabled.")
        return

    log.info("Userbot: Initializing personal account userbot...")
    client = TelegramClient(SESSION_NAME, config.USERBOT_API_ID, config.USERBOT_API_HASH)
    
    try:
        await client.connect()
        authorized = await client.is_user_authorized()
        
        if not authorized:
            log.error("Userbot: Session is not authorized!")
            log.error("Please run the interactive login script 'login_userbot.py' locally first to authorize the session.")
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
