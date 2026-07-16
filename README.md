# 🤖 FileCraft AI — Telegram File/APK Repost Bot

Forward ⏩ any file, APK or video to the bot — it removes the old caption,
@tags and promo links, figures out the **real app name + version**, searches
the web for info, downloads the app's picture, writes a fresh **AI caption**
and posts the clean result to your channel. 100% free to run.

```
 messy forward ──► bot ──► clean post
 ─────────────     │       ─────────────────────────────
 📄 Capcut pro     │       🖼️ [app icon]
 27.55v By         │       📄 CapCut_Pro_27.55.apk
 @SomeoneMod.apk   │       📱 CapCut Pro 27.55
 #mod #apk         │       ✨ Features:
 💯 t.me/spam      │       • Save videos in 4K
                   │       • Unlock 🔓 all effects
                   │       • No watermark
                   │       • Free 🆓
                   │       📦 Size: 90 MB
```

## ✨ Features

| Feature | How (free) |
|---|---|
| Caption / @tag / link removal | regex pipeline (`cleaner.py`) |
| Real app name + version detection | filename regex + **read from inside the APK** (androguard) |
| Web info about the app | DuckDuckGo search — no API key |
| App picture attached to post | DuckDuckGo image search, or the icon pulled out of the APK |
| AI captions with feature list | Google Gemini **free tier** (optional — template fallback without a key) |
| Channel auto-posting | set `CHANNEL_ID`, make bot admin |
| YouTube description generator | YouTube oEmbed (no key) + Gemini — great for your YT channel |
| Big file support | files > 20 MB are re-posted by `file_id` (no re-download needed) |
| "No internet" resilient | every web/AI call has a graceful fallback |
| Works without bot restarts | `/health` endpoint for UptimeRobot |

## 🧰 Commands

`/start` · `/help` · `/ping` · `/stats` · `/id`

## 🚀 Deploy on Render (free)

1. **Create the bot** — talk to [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token.
2. **(Optional) AI key** — <https://aistudio.google.com/apikey> → free key.
3. **Push this repo to GitHub**, then on [Render](https://dashboard.render.com):
   **New → Web Service → your repo**. Render reads `render.yaml` automatically
   (free plan, `pip install -r requirements.txt`, `python main.py`).
4. Add **Environment Variables**:

   | Key | Value |
   |---|---|
   | `BOT_TOKEN` | from BotFather (required) |
   | `GEMINI_API_KEY` | from AI Studio (optional) |
   | `CHANNEL_ID` | `@yourchannel` or `-100xxxxxxxxxx` (optional — without it, bot just replies to you) |
   | `CHANNEL_LINK` | `https://t.me/yourchannel` (optional) |

5. **Add the bot to your channel as admin** (if you use auto-posting).
6. Done — the webhook is set automatically from `RENDER_EXTERNAL_URL`.

> Channel id erkhum: forward any channel post to [@userinfobot](https://t.me/userinfobot) → it shows the `-100…` id.

## ⏱ Keep it awake — UptimeRobot (5 min)

Render free services sleep after ~15 min without traffic. Fix (free):

1. <https://uptimerobot.com> → sign up → **Add New Monitor**
2. Type: **HTTP(s)** — URL: `https://YOUR-APP.onrender.com/health`
3. Interval: **5 minutes** → Save.

Telegram usually delivers to a sleeping service anyway via webhook retries,
but the ping keeps everything instant.

## 💻 Run locally

```bash
cp .env.example .env     # fill BOT_TOKEN
pip install -r requirements.txt
python main.py           # polling mode, no public URL needed
```

## ⚠️ Limits (all free-plan limits, not code bugs)

- Official Bot API: download ≤ 20 MB (larger files are reposted by `file_id` — caption is cleaned, original filename kept), upload ≤ 50 MB.
- Need 2 GB renames? Self-host a [Bot API server](https://core.telegram.org/bots/api#using-a-local-bot-api-server) and point PTB at it later.
- Gemini free tier: ~15 req/min per model — fine for a channel bot.

## 💡 Extra free things you can add later

- **MongoDB Atlas free** stats/broadcast lists instead of in-memory counters
- `/broadcast` admin command, force-join check before posting
- **YouTube Data API free quota** for view counts in the description draft
- Scheduled daily "app of the day" post using PTB JobQueue
- Short-link free domain (e.g. is-a.dev) for prettier pings

## 🇧🇩 বাংলা কুইক স্টার্ট

1. BotFather থেকে bot বানিয়ে **token** নাও
2. AI Studio থেকে free **Gemini key** নাও (চাইলে — key ছাড়াও চলবে)
3. এই repo GitHub এ push করে **Render** এ deploy করো (free plan)
4. Environment এ `BOT_TOKEN`, `GEMINI_API_KEY`, `CHANNEL_ID` বসাও
5. Bot কে channel এ **admin** বানাও
6. **UptimeRobot** এ `https://your-app.onrender.com/health` — ৫ মিনিট interval
7. এবার যেকোনো file/APK forward করো — bot নিজে caption মুছে, নাম ঠিক করে, AI caption + app এর ছবিসহ post দিবে 🚀

## 📁 Structure

```
main.py            entry (polling locally / webhook on Render)
app/handlers.py    telegram logic
app/cleaner.py     filename + caption cleaning
app/ai.py          Gemini captions (with fallbacks)
app/search.py      DuckDuckGo info/image + YouTube oEmbed
app/apk.py         read name/version/icon from APK (androguard)
app/server.py      Flask: /, /health, /webhook/<token>
render.yaml        one-click Render blueprint
```
