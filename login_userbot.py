import os
import sys
import asyncio
from telethon import TelegramClient

ENV_FILE = ".env"
STATE_FILE = "userbot_state.json"

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    banner = """
============================================================
           USERBOT INTERACTIVE LOGIN & SETUP
============================================================
* This script will help you log into your personal account
  and generate a highly portable 'USERBOT_SESSION_STRING'.
* This session string is perfect for hosting on Render free
  plan, as it doesn't get deleted when Render restarts!
============================================================
"""
    print(banner)

def load_env():
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    parts = line.split("=", 1)
                    key = parts[0].strip()
                    val = parts[1].strip()
                    # Strip quotes if any
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    env[key] = val
    return env

def save_env(env_data):
    # Read existing file to preserve comments if possible, or just overwrite with fresh list
    lines = []
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    lines.append(line)
                    continue
                if "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    if key in env_data:
                        lines.append(f"{key}={env_data[key]}\n")
                        del env_data[key]
                    else:
                        lines.append(line)
                else:
                    lines.append(line)
                    
    # Append any remaining keys
    for key, val in env_data.items():
        lines.append(f"{key}={val}\n")
        
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)

async def main():
    clear_screen()
    print_banner()
    
    # 1. Load or initialize .env
    if not os.path.exists(ENV_FILE):
        if os.path.exists(".env.example"):
            print("[+] .env file not found. Copying from .env.example...")
            try:
                with open(".env.example", "r", encoding="utf-8") as src:
                    content = src.read()
                with open(ENV_FILE, "w", encoding="utf-8") as dest:
                    dest.write(content)
            except Exception as e:
                print(f"[-] Error copying .env.example: {e}")
        else:
            print("[+] Creating a new .env file...")
            with open(ENV_FILE, "w", encoding="utf-8") as f:
                f.write("# Environment Configuration\n")
                
    env = load_env()
    
    # 2. Collect configurations if missing
    print("\n--- ENTER CREDENTIALS (তথ্যসমূহ প্রবেশ করান) ---")
    
    api_id_str = env.get("USERBOT_API_ID", "").strip()
    if not api_id_str:
        api_id_str = input("Enter USERBOT_API_ID (from my.telegram.org): ").strip()
        while not api_id_str.isdigit():
            print("Invalid API ID. It must be a number.")
            api_id_str = input("Enter USERBOT_API_ID: ").strip()
        env["USERBOT_API_ID"] = api_id_str
        
    api_hash = env.get("USERBOT_API_HASH", "").strip()
    if not api_hash:
        api_hash = input("Enter USERBOT_API_HASH (from my.telegram.org): ").strip()
        while not api_hash:
            print("API Hash cannot be empty.")
            api_hash = input("Enter USERBOT_API_HASH: ").strip()
        env["USERBOT_API_HASH"] = api_hash
        
    phone = env.get("USERBOT_PHONE", "").strip()
    if not phone:
        phone = input("Enter your personal phone number with country code (e.g., +88017XXXXXXXX): ").strip()
        while not phone.startswith("+"):
            print("Phone number must start with '+' (e.g. +880...)")
            phone = input("Enter Phone Number: ").strip()
        env["USERBOT_PHONE"] = phone

    target_channel = env.get("USERBOT_TARGET_CHANNEL", "").strip()
    if not target_channel:
        target_channel = input("Enter Target Channel Username/ID (e.g. @target_channel): ").strip()
        while not target_channel:
            print("Target channel cannot be empty.")
            target_channel = input("Enter Target Channel Username/ID: ").strip()
        env["USERBOT_TARGET_CHANNEL"] = target_channel

    destination = env.get("USERBOT_DESTINATION", "").strip()
    if not destination:
        destination = input("Enter Destination (Usually your Bot's username, e.g. @FileCraftAIBot): ").strip()
        while not destination:
            print("Destination cannot be empty.")
            destination = input("Enter Destination: ").strip()
        env["USERBOT_DESTINATION"] = destination

    last_id_str = env.get("USERBOT_LAST_CHECKED_ID", "").strip()
    if not last_id_str:
        last_id_str = input("Enter Starting Message ID (default: 1): ").strip()
        if not last_id_str.isdigit():
            last_id_str = "0"
        else:
            # We save starting_id - 1 so we start checking from starting_id
            last_id_str = str(max(0, int(last_id_str) - 1))
        env["USERBOT_LAST_CHECKED_ID"] = last_id_str

    bot_token = env.get("BOT_TOKEN", "").strip()
    if not bot_token:
        bot_token = input("Enter BOT_TOKEN (from @BotFather) [Optional for userbot login, but needed for main bot]: ").strip()
        if bot_token:
            env["BOT_TOKEN"] = bot_token

    # Save gathered config to .env
    save_env(env)
    print("\n[✓] Environment variables saved successfully in .env!")
    
    # 3. Create or update userbot_state.json
    import json
    state = {"last_checked_id": int(env.get("USERBOT_LAST_CHECKED_ID", "0"))}
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)
    print("[✓] Initial state saved to userbot_state.json!")
    
    # 4. Authenticate using Telethon client with StringSession
    print("\n[+] Starting Telethon Client. Please watch the terminal for OTP code/2FA Password prompts.")
    api_id = int(env["USERBOT_API_ID"])
    api_hash = env["USERBOT_API_HASH"]
    phone_number = env["USERBOT_PHONE"]
    
    from telethon.sessions import StringSession
    
    # Use StringSession so we get a single, portable string that works on Render free tier!
    client = TelegramClient(StringSession(), api_id, api_hash)
    
    try:
        await client.start(phone=phone_number)
        print("\n[✓] CONGRATULATIONS! LOGIN SUCCESSFUL!")
        me = await client.get_me()
        print(f"Logged in as: {me.first_name} (@{me.username or 'No Username'})")
        
        # Save session string
        session_str = client.session.save()
        env["USERBOT_SESSION_STRING"] = session_str
        save_env(env)
        
        print("\n=============================================================")
        print("⚡ YOUR STRING SESSION GENERATED SUCCESSFULLY!")
        print("=============================================================")
        print(f"\n{session_str}\n")
        print("=============================================================")
        print("\nWhat this means:")
        print("1. The session string has been automatically saved in your '.env' file as 'USERBOT_SESSION_STRING'.")
        print("2. When hosting on Render, copy the entire string above and set it as an Environment Variable named 'USERBOT_SESSION_STRING'.")
        print("3. This allows you to host the bot on Render Free tier without committing any '.session' files to Git! (Render restarts won't log you out)")
        print("4. When you run 'python main.py', the userbot will run in the background seamlessly!")
        
    except Exception as e:
        print(f"\n[-] Authentication or connection failed: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Session login cancelled.")
