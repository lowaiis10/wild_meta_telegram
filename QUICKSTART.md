# 🚀 Wildmeta Intelligence Suite - Quick Start Guide

Get up and running in 5 minutes!

## 📋 Prerequisites Check

- [ ] Python 3.8+ installed
- [ ] Telegram bot token ready
- [ ] Telegram group with topics enabled

## ⚡ Fast Setup (Windows)

### 1️⃣ Install Dependencies (2 minutes)

```bash
cd C:\Users\lowai\coding\wildmeta

# Activate virtual environment
venv\Scripts\activate

# Install everything
pip install feedparser httpx trafilatura readability-lxml beautifulsoup4 nltk transformers torch tenacity python-dateutil python-dotenv aiofiles

# Download sentiment model data
python -c "import nltk; nltk.download('vader_lexicon')"
```

### 2️⃣ Configure Environment (1 minute)

Create `C:\Users\lowai\coding\wildmeta\main\.env`:

```env
# REQUIRED
BOT_TOKEN=YOUR_BOT_TOKEN_HERE
CHAT_ID=-1002918297497

# RSS Bot
THREAD_ID=5
POLL_SECONDS=180

# X Bot
X_THREAD_ID=711
X_USERNAME=wildmetaHQ
X_POLL_SECONDS=300
```

### 3️⃣ Start Both Bots (1 minute)

```bash
cd C:\Users\lowai\coding\wildmeta\main

# Option A: Use the launcher script
start_bots.bat

# Option B: Run manually
python rss_macro_crypto_bot.py
python wildmeta_x_feed_bot.py
```

## ✅ Verify It's Working

You should see:
1. **RSS Bot**: `Starting. Feeds: 40 | poll every 180s`
2. **X Bot**: `Starting Wildmeta X Bot`
3. **Telegram**: Messages appearing in your group

## 🎯 What Happens Next?

- **RSS Bot** checks 40+ news sources every 3 minutes
- **X Bot** monitors @wildmetaHQ every 5 minutes
- Both post to your Telegram group with:
  - AI sentiment analysis (Positive/Neutral/Negative)
  - Keywords and hashtags
  - Reading time estimates
  - Market impact insights
  - Link previews

## 🔧 Quick Fixes

| Problem | Solution |
|---------|----------|
| "BOT_TOKEN not set" | Check `.env` file exists in `main/` folder |
| No messages appearing | Verify bot is admin in Telegram group |
| Rate limit errors | Normal - bots handle automatically |

## 📊 Monitor Status

Check if working:
```bash
# See RSS bot database
sqlite3 main\bot.db "SELECT COUNT(*) FROM seen;"

# See X bot database  
sqlite3 main\x_bot.db "SELECT COUNT(*) FROM x_posts;"
```

---

**That's it! Your financial intelligence system is now running!** 🎉

For detailed configuration and features, see the full [README.md](README.md)
