# 🚀 Wildmeta Intelligence Suite

**A comprehensive financial intelligence system that monitors global macro/crypto news and social media, analyzes sentiment using advanced AI, and delivers curated insights to Telegram.**

## 🌟 Overview

The Wildmeta Intelligence Suite consists of two specialized bots that work together to provide real-time financial intelligence:

1. **RSS Macro/Crypto Bot** - Monitors 40+ financial news sources for macroeconomic and cryptocurrency content
2. **X Feed Bot** - Tracks @wildmetaHQ on X (Twitter) for social media updates

Both bots use sophisticated filtering, AI-powered sentiment analysis, and deliver formatted insights directly to your Telegram channels with rich previews and actionable intelligence.

## 🎯 How It Works

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   WILDMETA INTELLIGENCE SUITE                │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────┐        ┌──────────────────────┐   │
│  │   RSS MACRO/CRYPTO   │        │      X FEED BOT      │   │
│  │        BOT           │        │                      │   │
│  ├──────────────────────┤        ├──────────────────────┤   │
│  │                      │        │                      │   │
│  │  40+ News Sources:   │        │  X/Twitter Monitor: │   │
│  │  • Reuters           │        │  • @wildmetaHQ       │   │
│  │  • Bloomberg         │        │  • Real-time posts   │   │
│  │  • CoinTelegraph     │        │  • Engagement data   │   │
│  │  • Federal Reserve   │        │  • Link previews     │   │
│  │  • ECB, BIS, etc.    │        │                      │   │
│  └──────────┬───────────┘        └──────────┬───────────┘   │
│             │                                │               │
│             ▼                                ▼               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              CONTENT PROCESSING PIPELINE              │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │                                                       │   │
│  │  1. EXTRACTION: Full-text article extraction          │   │
│  │  2. FILTERING: Keyword matching (macro/crypto/HL)    │   │
│  │  3. SENTIMENT: AI ensemble analysis                  │   │
│  │  4. DEDUPLICATION: SQLite tracking                   │   │
│  │  5. FORMATTING: Rich HTML with insights              │   │
│  └──────────┬────────────────────────────────────────────┘   │
│             │                                                 │
│             ▼                                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           SENTIMENT ANALYSIS ENGINE (AI)             │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │                                                       │   │
│  │  • FinBERT: Financial domain-specific model          │   │
│  │  • RoBERTa: Social media sentiment                   │   │
│  │  • VADER: Rule-based fallback                        │   │
│  │  • Ensemble: Weighted combination with adjustments   │   │
│  └──────────┬────────────────────────────────────────────┘   │
│             │                                                 │
│             ▼                                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              TELEGRAM DELIVERY SYSTEM                │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │                                                       │   │
│  │  Chat: -1002918297497                                │   │
│  │  ├── Thread #5: Macro/Crypto News                    │   │
│  │  └── Thread #711: X/Twitter Updates                  │   │
│  │                                                       │   │
│  │  Features:                                            │   │
│  │  • Rich HTML formatting                              │   │
│  │  • Link previews/embeds                              │   │
│  │  • Sentiment badges & scores                         │   │
│  │  • Reading time & word count                         │   │
│  │  • Market impact insights                            │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Content Acquisition**
   - RSS bot polls 40+ feeds every 3 minutes
   - X bot checks @wildmetaHQ every 5 minutes
   - Both use async HTTP clients for efficient fetching

2. **Content Processing**
   - **Extraction**: Full article text using trafilatura/readability
   - **Filtering**: Regex-based keyword matching for relevance
   - **Analysis**: Multi-model sentiment analysis ensemble
   - **Enrichment**: Add metrics, timestamps, reading time

3. **Intelligence Delivery**
   - Format with HTML for rich Telegram messages
   - Include sentiment scores, keywords, and insights
   - Post to specific Telegram threads
   - Track in SQLite to prevent duplicates

## 📦 Project Structure

```
wildmeta/
├── main/                           # Main application directory
│   ├── rss_macro_crypto_bot.py    # RSS news aggregator bot (642 lines)
│   ├── wildmeta_x_feed_bot.py     # X/Twitter monitor bot (635 lines)
│   ├── bot.db                     # SQLite database for RSS bot
│   ├── x_bot.db                   # SQLite database for X bot (created on first run)
│   └── .env                       # Environment configuration (user-created)
├── config.template                # Template for environment variables
├── requirements.txt               # Python dependencies
├── README.md                      # This comprehensive documentation
├── Lib/                          # Python virtual environment libraries
├── Scripts/                      # Virtual environment scripts
└── pyvenv.cfg                    # Virtual environment configuration
```

## 🛠️ Installation & Setup

### Prerequisites

- Python 3.8 or higher
- Windows/Linux/macOS
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Telegram Group with topics enabled

### Step 1: Set Up Virtual Environment

```bash
cd wildmeta

# Create virtual environment (if not already created)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### Step 2: Install Dependencies

```bash
# Upgrade pip
pip install -U pip

# Install all dependencies
pip install feedparser httpx trafilatura readability-lxml beautifulsoup4 nltk transformers torch tenacity python-dateutil python-dotenv aiofiles

# Download NLTK data for sentiment analysis
python -c "import nltk; nltk.download('vader_lexicon')"
```

### Step 3: Configure Environment

Create `.env` file in the `main/` directory:

```bash
cd main
# Copy template and edit with your values
copy ..\config.template .env  # Windows
# or
cp ../config.template .env     # Linux/macOS
```

Edit `.env` with your configuration:

```env
# REQUIRED - Telegram Configuration
BOT_TOKEN=your_bot_token_here
CHAT_ID=-1002918297497

# RSS Bot Configuration
THREAD_ID=5                    # Thread for macro/crypto news
POLL_SECONDS=180              # Check feeds every 3 minutes
DB_PATH=./bot.db
REGION_TZ=Asia/Singapore
POST_ONLY_ON_STRONG_MATCH=false
MAX_AGE_DAYS=2

# X Bot Configuration  
X_THREAD_ID=711               # Thread for X posts
X_USERNAME=wildmetaHQ
X_POLL_SECONDS=300           # Check X every 5 minutes
X_DB_PATH=./x_bot.db
X_MAX_POSTS_PER_CYCLE=5
```

### Step 4: Get Telegram Credentials

1. **Create Bot Token:**
   - Message [@BotFather](https://t.me/botfather)
   - Send `/newbot` and follow instructions
   - Copy the token to your `.env`

2. **Get Chat ID:**
   - Add bot to your group
   - Send a test message
   - Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - Find `"chat":{"id":-1002918297497}` in response

3. **Get Thread IDs:**
   - Create topics in your Telegram group
   - Send messages to each topic
   - Check getUpdates response for `message_thread_id`

## 🚀 Running the Bots

### Option 1: Run Individually

```bash
cd wildmeta\main

# Run RSS Macro/Crypto Bot
python rss_macro_crypto_bot.py

# In another terminal, run X Feed Bot
python wildmeta_x_feed_bot.py
```

### Option 2: Run Both Together (Windows)

Create `start_bots.bat`:
```batch
@echo off
cd /d C:\Users\lowai\coding\wildmeta\main
start "RSS Bot" cmd /k "python rss_macro_crypto_bot.py"
start "X Bot" cmd /k "python wildmeta_x_feed_bot.py"
```

### Option 3: Run as Services (Production)

For production deployment, use process managers:
- **Windows**: Task Scheduler or NSSM
- **Linux**: systemd, supervisor, or pm2
- **Docker**: Create Dockerfile with both processes

## 📊 Features in Detail

### RSS Macro/Crypto Bot

#### News Sources (40+)
- **Macro/Economics**: Fed, ECB, BIS, OECD, World Bank, Reuters, Bloomberg, FT
- **Crypto**: CoinTelegraph, CoinDesk, Decrypt, The Block, Bitcoin Magazine
- **Analysis**: CEPR, Bruegel, Calculated Risk, Liberty Street Economics

#### Keyword Filtering
- **Macro Terms**: CPI, PCE, inflation, FOMC, Fed, yields, bonds, GDP, PMI, unemployment
- **Crypto Terms**: Bitcoin, Ethereum, DeFi, stablecoins, ETF, SEC, exchanges
- **Priority Terms**: Hyperliquid (special handling)

#### Sentiment Analysis
- **FinBERT**: Specialized for financial text (60% weight)
- **RoBERTa**: Social media sentiment (40% weight)  
- **VADER**: Fallback for short text or errors
- **Domain Adjustments**: Rate changes, ETF approvals affect scores

### X Feed Bot

#### Monitoring Capabilities
- Tracks @wildmetaHQ posts in real-time
- Fetches post content, timestamps, engagement metrics
- Uses Nitter instances for reliable scraping
- No API keys required

#### Telegram Integration
- Posts to dedicated thread (#711)
- Rich formatting with X branding
- Automatic link previews/embeds
- Engagement metrics (likes, retweets, replies)

## 📈 Message Examples

### RSS News Message
```
📰 Fed Signals Potential Rate Cut Amid Cooling Inflation
🗞️ Reuters Business News — 2024-01-15 14:30

🟢 Positive 7.85/10
Ensemble comp: 7.85/10
FinBERT: positive 8.20/10
RoBERTa: positive 7.50/10

🧾 The Federal Reserve indicated it may consider rate cuts...

#Macro #Fed #Inflation #RateCut

📊 reuters.com • ~3 min • 450 words
🔎 #Fed, #Inflation, #RateCut, #CPI
🎯 Easier policy; typically supportive for risk assets.

🔗 https://reuters.com/business/fed-signals-rate-cut
```

### X Post Message
```
𝕏 @wildmetaHQ
2024-01-15 14:30 UTC

Breaking: Major announcement about our new DeFi integration 
with @PartnerProtocol bringing enhanced liquidity solutions...

💬 15 • 🔁 42 • ❤️ 128

🔗 View on X
```

## 🔧 Configuration Options

### Filtering Modes

| Mode | Setting | Behavior |
|------|---------|----------|
| Standard | `POST_ONLY_ON_STRONG_MATCH=false` | Posts any macro OR crypto match |
| Strict | `POST_ONLY_ON_STRONG_MATCH=true` | Requires multiple keywords or cross-domain |
| Sentiment Override | Automatic | High-confidence sentiment overrides weak matches |

### Performance Tuning

| Parameter | Default | Range | Impact |
|-----------|---------|-------|---------|
| `POLL_SECONDS` | 180 | 60-600 | Feed check frequency |
| `X_POLL_SECONDS` | 300 | 180-900 | X check frequency |
| `MAX_AGE_DAYS` | 2 | 1-7 | Backfill limit |
| `X_MAX_POSTS_PER_CYCLE` | 5 | 1-20 | X posts per check |

## 🗄️ Database Management

### View Statistics

```bash
# RSS Bot statistics
sqlite3 main/bot.db "SELECT COUNT(*) as total_posts FROM seen;"
sqlite3 main/bot.db "SELECT feed, COUNT(*) as posts FROM seen GROUP BY feed ORDER BY posts DESC LIMIT 10;"

# X Bot statistics  
sqlite3 main/x_bot.db "SELECT COUNT(*) as total_posts FROM x_posts;"
sqlite3 main/x_bot.db "SELECT content, datetime(first_seen_ts, 'unixepoch') FROM x_posts ORDER BY first_seen_ts DESC LIMIT 5;"
```

### Reset Databases

```bash
# Reset RSS bot (removes all history)
rm main/bot.db

# Reset X bot
rm main/x_bot.db
```

## 📊 Monitoring & Logs

### Log Format
Both bots use structured JSON logging:

```json
{
  "event": "cycle_done",
  "posted": 5,
  "duration_s": 45.2,
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### Health Indicators
- **Healthy**: Regular "cycle_done" events
- **Warning**: Frequent rate limit messages
- **Error**: Feed fetch failures or model loading issues

## 🔒 Security & Privacy

- **Local Processing**: All analysis done locally, no external APIs
- **No Data Collection**: Only public RSS feeds and posts processed
- **Secure Storage**: SQLite databases stored locally
- **Token Security**: Bot tokens in `.env` file (never commit!)
- **Rate Limiting**: Respects all API rate limits

## 🚦 Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "Set BOT_TOKEN in environment" | Create `.env` file in `main/` directory |
| "Could not pre-load HF models" | Normal on first run, models download automatically |
| "Hit Telegram rate limit" | Bot handles automatically, increase poll intervals if frequent |
| "No posts fetched from @wildmetaHQ" | Check if Nitter instances are accessible |
| Database locked | Ensure only one instance per bot is running |

### Performance Optimization

1. **Reduce Memory Usage**: Set `MAX_POSTS_PER_CYCLE=3`
2. **Reduce API Calls**: Increase `POLL_SECONDS` and `X_POLL_SECONDS`
3. **Improve Latency**: Use `POST_ONLY_ON_STRONG_MATCH=true`
4. **Debug Issues**: Check logs for specific error messages

## 🎯 Use Cases

1. **Trading Intelligence**: Real-time macro/crypto news for trading decisions
2. **Market Research**: Automated collection of market sentiment
3. **Community Updates**: Keep groups informed of relevant news
4. **Sentiment Tracking**: Monitor market mood across sources
5. **Social Monitoring**: Track important X accounts for updates

## 🚀 Future Enhancements

- **Multi-account X monitoring**: Track multiple Twitter accounts
- **Custom keyword filters**: User-defined filtering rules
- **Web dashboard**: Real-time analytics and configuration
- **Alert system**: Critical news notifications
- **Historical analysis**: Sentiment trends over time
- **API endpoints**: REST API for external integrations

## 📝 License & Disclaimer

This project is for educational and personal use. Users must:
- Respect Terms of Service of RSS providers and social media platforms
- Use responsibly and ethically
- Not use for spam or harassment
- Comply with local regulations regarding data collection

## 🤝 Support

For issues or questions:
1. Check this README thoroughly
2. Review bot logs for specific errors
3. Verify all dependencies are installed
4. Ensure `.env` configuration is correct
5. Test with individual bots before running both

---

**Built with ❤️ for the Wildmeta community**

*Version 2.5 - Real-time Financial Intelligence*
