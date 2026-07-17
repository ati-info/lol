import os
import sys
import json
import asyncio
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError

CONFIG_FILE = 'config.json'
SESSION_NAME = 'user_session'

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading config: {e}")
            return {}
    return {}

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving config: {e}")

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

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    banner = """
============================================================
              TELEGRAM FILE FORWARDER BOT
============================================================
* Personal Account Session base automatic forwarder.
* checks target channel message by message.
* Skips text/empty messages, forwards files only.
* runs continuously every 5 minutes.
============================================================
"""
    print(banner)

async def check_and_forward(client, config):
    target = parse_chat_id(config.get('target_channel'))
    destination = parse_chat_id(config.get('destination_chat'))
    last_checked_id = config.get('last_checked_id', 0)
    
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking messages starting from ID: {last_checked_id + 1}...")
    
    try:
        # Get target channel entity
        target_entity = await client.get_input_entity(target)
    except Exception as e:
        print(f"Error accessing target channel '{target}': {e}")
        print("Please ensure that target channel is public or your account is joined/member of it.")
        return
        
    try:
        # Get destination channel/group entity
        destination_entity = await client.get_input_entity(destination)
    except Exception as e:
        print(f"Error accessing destination chat '{destination}': {e}")
        print("Please ensure destination chat/channel username or ID is correct and accessible.")
        return

    # Get the latest message ID of target channel
    latest_id = None
    try:
        async for msg in client.iter_messages(target_entity, limit=1):
            latest_id = msg.id
            break
    except Exception as e:
        print(f"Error fetching latest message from target: {e}")
        return

    if not latest_id:
        print("No messages found in target channel (it might be empty).")
        return

    current_id = last_checked_id + 1
    if current_id > latest_id:
        print(f"Already caught up with the latest message ID {latest_id}. No new messages.")
        return

    print(f"Target channel latest message ID: {latest_id}. Scanning IDs from {current_id} to {latest_id}...")
    
    found_file = False
    
    while current_id <= latest_id:
        # Flush line stdout update
        sys.stdout.write(f"\rScanning Message ID: {current_id} / {latest_id}")
        sys.stdout.flush()
        
        try:
            msg = await client.get_messages(target_entity, ids=current_id)
        except FloodWaitError as e:
            print(f"\nFloodWaitError! Must sleep for {e.seconds} seconds.")
            await asyncio.sleep(e.seconds)
            continue
        except Exception as e:
            # If a specific message fails, save and move on
            config['last_checked_id'] = current_id
            save_config(config)
            current_id += 1
            continue

        if not msg:
            # Message is deleted or doesn't exist
            config['last_checked_id'] = current_id
            save_config(config)
            current_id += 1
            continue

        # Check if the message contains only genuine files/APKs (excluding images, videos, audio, gif, text)
        is_genuine_file = False
        if msg.document and not msg.video and not msg.photo and not msg.audio and not msg.gif:
            mime = msg.document.mime_type or ""
            if not mime.startswith("image/") and not mime.startswith("video/") and not mime.startswith("audio/"):
                is_genuine_file = True

        if is_genuine_file:
            print(f"\n[+] Found genuine file (Document/APK) in message ID {current_id}! Forwarding to {destination}...")
            try:
                # Forward the message
                await client.forward_messages(destination_entity, msg)
                print(f"[✓] Successfully forwarded message ID {current_id}.")
                
                # Update config with the current message ID
                config['last_checked_id'] = current_id
                save_config(config)
                found_file = True
                break  # Stop searching for this run, wait for next 5-minute interval
            except Exception as e:
                print(f"\n[!] Error forwarding message ID {current_id}: {e}")
                # Save progress even on failure to avoid getting stuck on a restricted message
                config['last_checked_id'] = current_id
                save_config(config)
                break
        else:
            # No genuine file found (e.g., text, photo, video post), update config and move to next
            config['last_checked_id'] = current_id
            save_config(config)
            current_id += 1

    if not found_file:
        print("\nAll scanned messages checked, no files found in this run.")

async def setup_config():
    clear_screen()
    print_banner()
    print("--- CONFIGURATION SETUP (কনফিগারেশন সেটআপ) ---\n")
    
    print("To run this bot, you need a Telegram API ID and API Hash from https://my.telegram.org")
    print("(এই বটটি চালানোর জন্য আপনার https://my.telegram.org থেকে API ID এবং API Hash লাগবে)\n")
    
    api_id_str = input("Enter API ID (API ID দিন): ").strip()
    while not api_id_str.isdigit():
        print("Invalid API ID. It must be a number.")
        api_id_str = input("Enter API ID: ").strip()
    api_id = int(api_id_str)
        
    api_hash = input("Enter API Hash (API Hash দিন): ").strip()
    while not api_hash:
        print("API Hash cannot be empty.")
        api_hash = input("Enter API Hash: ").strip()

    phone = input("Enter Phone Number with country code (e.g. +88017XXXXXXXX) (কান্ট্রি কোডসহ ফোন নম্বর দিন): ").strip()
    while not phone.startswith('+'):
        print("Phone number must start with '+' (e.g. +880...)")
        phone = input("Enter Phone Number: ").strip()

    target_channel = input("Enter Target Channel Username/ID (টার্গেট চ্যানেল বা গ্রুপের ইউজারনেম/আইডি): ").strip()
    while not target_channel:
        print("Target channel cannot be empty.")
        target_channel = input("Enter Target Channel Username/ID: ").strip()

    destination_chat = input("Enter Destination Chat Username/ID (যেখানে ফরোয়ার্ড করতে চান সেই আইডি/ইউজারনেম): ").strip()
    while not destination_chat:
        print("Destination chat cannot be empty.")
        destination_chat = input("Enter Destination Chat Username/ID: ").strip()

    last_id_str = input("Enter starting message ID to check (e.g. 1 or 12) (শুরুর মেসেজ আইডি দিন, যেমন ১ বা ১২): ").strip()
    if not last_id_str.isdigit():
        last_checked_id = 0
    else:
        last_checked_id = int(last_id_str) - 1  # we start checking from last_checked_id + 1

    config = {
        "api_id": api_id,
        "api_hash": api_hash,
        "phone": phone,
        "target_channel": target_channel,
        "destination_chat": destination_chat,
        "last_checked_id": last_checked_id,
        "check_interval_seconds": 300  # 5 minutes
    }
    
    save_config(config)
    print("\n[✓] Configuration saved successfully to config.json!")
    input("Press Enter to continue... (এন্টার চাপুন...)")
    return config

async def main():
    clear_screen()
    print_banner()
    
    config = load_config()
    
    if not config:
        print("No configuration file found. Let's create one!")
        config = await setup_config()
        
    while True:
        clear_screen()
        print_banner()
        print(f"Current Config (বর্তমান কনফিগারেশন):")
        print(f" - Phone (ফোন নম্বর): {config.get('phone')}")
        print(f" - Target (টার্গেট): {config.get('target_channel')}")
        print(f" - Destination (যেখানে ফরোয়ার্ড হবে): {config.get('destination_chat')}")
        print(f" - Last Checked Msg ID (সর্বশেষ চেক করা আইডি): {config.get('last_checked_id')}")
        print(f" - Interval (সময় ব্যবধান): {config.get('check_interval_seconds')} seconds (5 mins)")
        print("\nSelect an option (একটি অপশন সিলেক্ট করুন):")
        print("1. Start Forwarder Bot (বট চালু করুন)")
        print("2. Change Configuration (কনফিগারেশন পরিবর্তন করুন)")
        print("3. Reset Session & Log Out (সেশন ডিলেট ও লগ আউট করুন)")
        print("4. Exit (বেরিয়ে যান)")
        
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == '1':
            break
        elif choice == '2':
            config = await setup_config()
        elif choice == '3':
            if os.path.exists(f"{SESSION_NAME}.session"):
                try:
                    os.remove(f"{SESSION_NAME}.session")
                    print("\n[✓] Session file deleted successfully!")
                except Exception as e:
                    print(f"\n[!] Error deleting session file: {e}")
            else:
                print("\n[!] No active session file found.")
            if os.path.exists(CONFIG_FILE):
                try:
                    os.remove(CONFIG_FILE)
                    print("[✓] Config file deleted successfully!")
                except Exception as e:
                    print(f"[!] Error deleting config file: {e}")
            config = {}
            print("\nPlease restart the script to set up a new session.")
            input("Press Enter to exit...")
            return
        elif choice == '4':
            print("Exiting...")
            return
        else:
            print("Invalid option. Please enter 1, 2, 3, or 4.")
            await asyncio.sleep(2)

    api_id = config.get('api_id')
    api_hash = config.get('api_hash')
    phone = config.get('phone')
    
    print("\nInitializing Telegram client...")
    client = TelegramClient(SESSION_NAME, api_id, api_hash)
    
    try:
        # start method will prompt interactively for phone number, OTP, and 2FA password
        await client.start(phone=phone)
    except Exception as e:
        print(f"\n[!] Authentication failed: {e}")
        print("Please check your credentials or delete user_session.session and try again.")
        return

    print("\n[✓] Successfully authenticated & connected to Telegram!")
    me = await client.get_me()
    print(f"Logged in as: {me.first_name} (@{me.username or 'No Username'})")
    
    interval = config.get('check_interval_seconds', 300)
    print(f"\nForwarder started! Running every {interval // 60} minutes.")
    print("Press Ctrl+C to stop the bot safely.\n")
    
    try:
        while True:
            # Refresh config in case it was updated externally
            config = load_config()
            await check_and_forward(client, config)
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Waiting for next check in {interval // 60} minutes...")
            await asyncio.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopping forwarder bot safely. Goodbye!")
    finally:
        await client.disconnect()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExited.")
