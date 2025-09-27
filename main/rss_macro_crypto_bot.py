#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSS → Telegram (Macro/Crypto + Hyperliquid priority) with hardened networking, rate-limit handling,
initial backfill cap, rich sentiment, and clean one-newline formatting.

Setup:
  pip install -U pip
  pip install feedparser httpx trafilatura readability-lxml beautifulsoup4 nltk transformers torch tenacity python-dateutil python-dotenv
  python -c "import nltk; nltk.download('vader_lexicon')"

.env (example):
  BOT_TOKEN=xxxxxxxx:yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
  CHAT_ID=-1002918297497
  THREAD_ID=5
  POLL_SECONDS=180
  DB_PATH=./bot.db
  REGION_TZ=Asia/Singapore
  POST_ONLY_ON_STRONG_MATCH=false
  MAX_AGE_DAYS=2
"""

from __future__ import annotations
import os, time, json, re, sqlite3, asyncio, hashlib, logging, html, math
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from urllib.parse import urlparse

import feedparser
import httpx
import trafilatura
from bs4 import BeautifulSoup
from readability import Document
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dateutil import parser as dtparse
from dotenv import load_dotenv

# Sentiment libs (HF + VADER fallback)
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

# ---------- Config ----------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")                  # e.g. -1002918297497
THREAD_ID = os.getenv("THREAD_ID")              # optional topic id, e.g. "5"
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "180"))
DB_PATH = os.getenv("DB_PATH", "./bot.db")
REGION_TZ = os.getenv("REGION_TZ", "Asia/Singapore")
POST_ONLY_ON_STRONG_MATCH = os.getenv("POST_ONLY_ON_STRONG_MATCH", "false").lower() == "true"
MAX_AGE_DAYS = int(os.getenv("MAX_AGE_DAYS", "2"))   # cap backfill
TIMEOUT = 20.0

if not BOT_TOKEN or not CHAT_ID:
    raise SystemExit("Set BOT_TOKEN and CHAT_ID in your environment (.env).")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("macro-crypto-bot")

# ---------- Feeds (dead/blocked removed; reliable adds) ----------
FEEDS: List[str] = [
    # 📈 Macro / Markets — originals
    "https://cepr.org/rss/vox-content",
    "https://www.bruegel.org/rss.xml",
    "https://ritholtz.com/feed/",
    "https://billmitchell.org/blog/?feed=rss2",
    "https://eyeonhousing.org/category/macroeconomics/feed/",
    "https://feeds.feedburner.com/espeak",
    "https://alephblog.com/category/macroeconomics/feed/",
    "https://libertystreeteconomics.newyorkfed.org/feed/",
    "https://bankunderground.co.uk/feed/",
    "https://www.bis.org/rss/research.xml",
    "https://econbrowser.com/feed",
    "https://calculatedriskblog.com/feeds/posts/default?alt=rss",

    # 📈 Macro / Markets — new adds
    "https://www.ft.com/rss/markets",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/news/economy",
    "https://feeds.bloomberg.com/economics/news.rss",
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "https://feeds.a.dj.com/rss/RSSWSJD.xml",
    "https://www.oecd.org/newsroom/index.rss",
    "https://blogs.worldbank.org/feed",
    "https://www.ecb.europa.eu/rss/press.html",
    "https://www.bis.org/list/press_releases_rss.xml",

    # ₿ Crypto — originals
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss",
    "https://cryptoslate.com/feed/",
    "https://decrypt.co/feed",
    "https://bitcoinmagazine.com/feed",
    "https://cryptonews.com/news/feed/",
    "https://smartliquidity.info/feed/",
    "https://www.fxempire.com/api/v1/en/articles/rss/news",

    # ₿ Crypto — new adds
    "https://www.theblock.co/rss",
    "https://cryptobriefing.com/feed/",
    "https://coinjournal.net/feed/",
    "https://www.btc-echo.de/feed/",
    "https://www.newsbtc.com/feed/",
    "https://ambcrypto.com/feed/",
    "https://www.cryptoglobe.com/latest/feed/",
    "https://beincrypto.com/feed/",
    "https://www.cryptonewsz.com/feed/",

    # 🌍 Extra Global Finance / Geopolitics
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://www.theguardian.com/business/economics/rss",
    "https://asiatimes.com/category/business/feed/",
]

# ---------- Keyword filtering ----------
MACRO_TERMS = [
    r"\bcpi\b", r"\bpce\b", r"\binflation\b", r"\bdeflation\b",
    r"\bfomc\b", r"rate hike", r"rate cut", r"\bfed\b", r"\becb\b", r"\bboj\b", r"\bpboc\b",
    r"\btreasury\b", r"\byield(s)?\b", r"\bbond(s)?\b", r"\bgdp\b", r"\bpmi\b",
    r"\bunemployment\b", r"\bjobs?\b", r"\bnonfarm\b", r"\bmanufacturing\b", r"\bservices\b",
    r"\bqe\b", r"\bqt\b", r"\brecession\b", r"soft landing", r"stagflation",
]
CRYPTO_TERMS = [
    r"\bbitcoin\b", r"\bbtc\b", r"\beth(ereum)?\b", r"\bsol(ana)?\b",
    r"layer ?2", r"\brollup(s)?\b", r"\bdefi\b", r"\bstablecoin(s)?\b",
    r"\betf\b", r"\bsec\b", r"\bregulation\b", r"\bexchange(s)?\b", r"\bcex\b", r"\bdex\b",
    r"\bbinance\b", r"\bcoinbase\b", r"\bstaking\b", r"\brestaking\b", r"\bairdrops?\b",
    r"\bperpetual(s)?\b", r"\bonchain\b", r"\btoken(s)?\b", r"\bnft(s)?\b",
]
HYPERLIQUID_TERMS = [r"\bhyper ?liquid\b", r"\bhyperliquid\b", r"\bhl perps?\b", r"hyperliquid exchange"]

MACRO_REGEX = re.compile("|".join(MACRO_TERMS), re.IGNORECASE)
CRYPTO_REGEX = re.compile("|".join(CRYPTO_TERMS), re.IGNORECASE)
HYPER_REGEX = re.compile("|".join(HYPERLIQUID_TERMS), re.IGNORECASE)

DISPLAY_KEYWORDS = [
    ("cpi", r"\bcpi\b"), ("pce", r"\bpce\b"), ("inflation", r"\binflation\b"), ("deflation", r"\bdeflation\b"),
    ("FOMC", r"\bfomc\b"), ("rate hike", r"rate hike"), ("rate cut", r"rate cut"), ("Fed", r"\bfed\b"),
    ("ECB", r"\becb\b"), ("BOJ", r"\bboj\b"), ("PBOC", r"\bpboc\b"),
    ("yields", r"\byield(s)?\b"), ("bonds", r"\bbond(s)?\b"),
    ("GDP", r"\bgdp\b"), ("PMI", r"\bpmi\b"), ("jobs", r"\bjobs?\b"), ("unemployment", r"\bunemployment\b"),
    ("QE", r"\bqe\b"), ("QT", r"\bqt\b"), ("recession", r"\brecession\b"),
    ("Bitcoin", r"\bbitcoin\b|\bbtc\b"), ("Ethereum", r"\beth(ereum)?\b"),
    ("Solana", r"\bsol(ana)?\b"), ("ETF", r"\betf\b"), ("SEC", r"\bsec\b"),
    ("stablecoin", r"\bstablecoin(s)?\b"), ("DeFi", r"\bdefi\b"),
    ("exchange", r"\bexchange(s)?\b|\bcex\b|\bdex\b"),
    ("staking", r"\bstaking\b|\brestaking\b"), ("perpetuals", r"\bperpetual(s)?\b"),
    ("token", r"\btoken(s)?\b"), ("NFT", r"\bnft(s)?\b"),
    ("Hyperliquid", r"\bhyper ?liquid\b|\bhyperliquid\b|\bhl perps?\b"),
]
DISPLAY_KEYWORDS_COMPILED = [(name, re.compile(pat, re.IGNORECASE)) for name, pat in DISPLAY_KEYWORDS]

# ---------- Storage ----------
def init_db(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS seen (
      feed TEXT NOT NULL,
      entry_key TEXT NOT NULL,
      published_ts INTEGER,
      first_seen_ts INTEGER NOT NULL,
      PRIMARY KEY(feed, entry_key)
    );
    """)
    conn.commit()
    conn.close()

def seen_before(path: str, feed: str, key: str) -> bool:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM seen WHERE feed=? AND entry_key=? LIMIT 1", (feed, key))
    row = cur.fetchone()
    conn.close()
    return row is not None

def mark_seen(path: str, feed: str, key: str, published_ts: Optional[int]) -> None:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO seen(feed, entry_key, published_ts, first_seen_ts) VALUES (?,?,?,?)",
        (feed, key, published_ts, int(time.time()))
    )
    conn.commit()
    conn.close()

# ---------- Utilities ----------
def to_unix_ts(dt_str: Optional[str]) -> Optional[int]:
    if not dt_str:
        return None
    try:
        d = dtparse.parse(dt_str)
        if not d.tzinfo:
            d = d.replace(tzinfo=timezone.utc)
        return int(d.timestamp())
    except Exception:
        return None

def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()

def entry_key(entry) -> str:
    for k in ("id", "guid"):
        v = getattr(entry, k, None) or (entry.get(k) if isinstance(entry, dict) else None)
        if v:
            return str(v)
    if hasattr(entry, "link") and entry.link:
        return entry.link
    title = getattr(entry, "title", "") or ""
    pub = getattr(entry, "published", "") or ""
    return sha256(f"{title}|{pub}")

def first_nonempty(*vals) -> str:
    for v in vals:
        if v:
            return v
    return ""

def clip(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    return s[:n].rstrip() + "…"

def h(x: str) -> str:
    return html.escape(x or "", quote=False)

def host_of(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""

def read_time_minutes(text: str, wpm: int = 220) -> int:
    words = max(1, len(text.split()))
    return max(1, int(math.ceil(words / wpm)))

def pick_keywords(text: str, limit: int = 6) -> List[str]:
    text = text or ""
    seen = []
    for name, pat in DISPLAY_KEYWORDS_COMPILED:
        if pat.search(text):
            if name not in seen:
                seen.append(name)
        if len(seen) >= limit:
            break
    return seen

def why_it_matters(text: str) -> Optional[str]:
    t = (text or "").lower()
    rules = [
        (("rate hike", "hawkish"), "Tighter policy; typically risk-off for duration-sensitive assets."),
        (("rate cut", "dovish"), "Easier policy; typically supportive for risk assets and liquidity."),
        (("etf approval", "spot etf", "etf launch"), "Mainstream access → potential inflows and volatility."),
        (("liquidity crunch", "funding stress", "bank run"), "Funding stress; spillovers to broader markets possible."),
        (("regulation", "sec charges", "lawsuit"), "Regulatory overhang; headline risk for tokens/exchanges."),
        (("inflation cools", "disinflation"), "Cooling prices; supports rate-cut odds and risk appetite."),
        (("inflation surges", "reacceleration"), "Hot inflation; pressures yields and weighs on risk assets."),
    ]
    for keys, msg in rules:
        if any(k in t for k in keys):
            return msg
    return None

def too_old(pub_ts: Optional[int]) -> bool:
    if not pub_ts:
        return False
    return (time.time() - pub_ts) > MAX_AGE_DAYS * 86400

# ---------- Extraction ----------
async def fetch_text(client: httpx.AsyncClient, url: str) -> Optional[str]:
    if not url:
        return None
    try:
        r = await client.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        return r.text
    except Exception:
        return None

def extract_fulltext(html_text: Optional[str], url: str) -> Optional[str]:
    if not html_text:
        return None
    # Try trafilatura
    try:
        txt = trafilatura.extract(html_text, url=url, include_comments=False, include_tables=False)
        if txt and len(txt.strip()) > 200:
            return txt.strip()
    except Exception:
        pass
    # Fallback readability
    try:
        doc = Document(html_text)
        content_html = doc.summary(html_partial=True)
        soup = BeautifulSoup(content_html, "lxml")
        text = soup.get_text(separator=" ", strip=True)
        if text and len(text) > 200:
            return text
    except Exception:
        pass
    # Fallback plain soup
    try:
        soup = BeautifulSoup(html_text, "lxml")
        text = soup.get_text(separator=" ", strip=True)
        if text and len(text) > 200:
            return text
    except Exception:
        pass
    return None

# ---------- Filtering ----------
def matches_filters(title: str, summary: str, body: str) -> Tuple[bool, bool, bool]:
    text = " ".join([title or "", summary or "", body or ""])

    hyper = bool(HYPER_REGEX.search(text))
    macro_hits = MACRO_REGEX.findall(text)
    crypto_hits = CRYPTO_REGEX.findall(text)

    macro = bool(macro_hits)
    crypto = bool(crypto_hits)

    if hyper:
        return True, True, True

    if POST_ONLY_ON_STRONG_MATCH:
        # strong if both families present OR any one family has 2+ keyword hits
        strong = (macro and crypto) or (len(macro_hits) >= 2) or (len(crypto_hits) >= 2)
        return strong, macro, crypto

    return (macro or crypto), macro, crypto

# ---------- Sentiment ----------
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download("vader_lexicon")
VADER = SentimentIntensityAnalyzer()

_finbert = None
_rob = None

def load_hf_models():
    """Lazy load HF models once."""
    global _finbert, _rob
    if _finbert is None or _rob is None:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
        finbert_name = "ProsusAI/finbert"
        tok_f = AutoTokenizer.from_pretrained(finbert_name)
        mod_f = AutoModelForSequenceClassification.from_pretrained(finbert_name)
        _finbert = pipeline("sentiment-analysis", model=mod_f, tokenizer=tok_f, truncation=True)
        rob_name = "cardiffnlp/twitter-roberta-base-sentiment-latest"
        tok_r = AutoTokenizer.from_pretrained(rob_name)
        mod_r = AutoModelForSequenceClassification.from_pretrained(rob_name)
        _rob = pipeline("sentiment-analysis", model=mod_r, tokenizer=tok_r, truncation=True)

def map_finbert(label: str) -> str:
    l = label.lower()
    if "pos" in l: return "pos"
    if "neg" in l: return "neg"
    return "neu"

def map_roberta(label: str) -> str:
    l = label.lower()
    if "pos" in l or "2" in l: return "pos"
    if "neu" in l or "1" in l: return "neu"
    return "neg"

def human_label(l: str) -> str:
    return {"pos":"🟢 Positive","neu":"⚪ Neutral","neg":"🔴 Negative"}.get(l, "⚪ Neutral")

def sentiment_ensemble(text: str) -> dict:
    """
    Returns:
    {
      "label": "pos|neu|neg",
      "score": float 0..1,          # ensemble confidence (mapped from compound)
      "compound": float -1..1,      # ensemble signed score
      "finbert": {"label": "...", "score": 0..1} | None,
      "roberta": {"label": "...", "score": 0..1} | None,
      "vader": {"compound": -1..1} | None
    }
    """
    text = (text or "").strip()
    if len(text) < 16:
        v = VADER.polarity_scores(text)
        comp = v["compound"]
        label = "pos" if comp >= 0.3 else "neg" if comp <= -0.3 else "neu"
        return {"label": label, "score": (comp + 1) / 2, "compound": comp,
                "finbert": None, "roberta": None, "vader": {"compound": comp}}

    try:
        load_hf_models()
        t = text[:1200]
        f = _finbert(t)[0]
        r = _rob(t)[0]

        def as_num_fin(lab: str) -> int:
            m = map_finbert(lab); return 1 if m=="pos" else -1 if m=="neg" else 0
        def as_num_rob(lab: str) -> int:
            m = map_roberta(lab); return 1 if m=="pos" else -1 if m=="neg" else 0

        lf, sf = map_finbert(f["label"]), float(f.get("score", 0.5))
        lr, sr = map_roberta(r["label"]), float(r.get("score", 0.5))
        nf, nr = as_num_fin(lf), as_num_rob(lr)

        wf, wr = 0.6 * sf, 0.4 * sr
        denom = max(1e-6, wf + wr)
        comp = (nf * wf + nr * wr) / denom

        lower = t.lower()
        if "rate hike" in lower or "hawkish" in lower or "liquidity crunch" in lower:
            comp -= 0.05
        if "etf approval" in lower or "rate cut" in lower or "dovish" in lower:
            comp += 0.05
        comp = max(-1.0, min(1.0, comp))

        label = "pos" if comp >= 0.25 else "neg" if comp <= -0.25 else "neu"
        return {"label": label, "score": (comp + 1) / 2.0, "compound": comp,
                "finbert": {"label": lf, "score": sf},
                "roberta": {"label": lr, "score": sr},
                "vader": None}
    except Exception as e:
        log.warning(f"HF sentiment failed, falling back to VADER: {e}")
        v = VADER.polarity_scores(text)
        comp = v["compound"]
        label = "pos" if comp >= 0.3 else "neg" if comp <= -0.3 else "neu"
        return {"label": label, "score": (comp + 1) / 2.0, "compound": comp,
                "finbert": None, "roberta": None, "vader": {"compound": comp}}

# ---------- Telegram ----------
async def tg_send(client: httpx.AsyncClient, text: str) -> None:
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": False,
        "parse_mode": "HTML",
    }
    if THREAD_ID:
        payload["message_thread_id"] = int(THREAD_ID)

    while True:
        r = await client.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=TIMEOUT)
        if r.status_code != 429:
            r.raise_for_status()
            data = r.json()
            if not data.get("ok"):
                log.warning(f"Telegram API error: {data}")
            return
        # Respect Telegram flood control
        retry_after = 3
        try:
            retry_after = int(r.headers.get("Retry-After") or r.json().get("parameters", {}).get("retry_after", 3))
        except Exception:
            pass
        log.info(f"Hit Telegram rate limit; sleeping {retry_after}s")
        await asyncio.sleep(retry_after)

# ---- Formatting (single newline separators) ----
def _to10(x: float) -> float:
    return x * 10

def format_sentiment_block(s: dict) -> str:
    badge = human_label(s["label"])
    ens_score10 = _to10(s["score"])
    comp10 = _to10((s["compound"] + 1) / 2.0)  # map -1..1 → 0..1 → /10
    lines = [
        f"{badge} <b>{ens_score10:.2f}/10</b>",
        f"<code>Ensemble comp: {comp10:.2f}/10</code>",
    ]
    if s.get("finbert"):
        lines.append(f"<code>FinBERT: {html.escape(s['finbert']['label'])} {_to10(s['finbert']['score']):.2f}/10</code>")
    if s.get("roberta"):
        lines.append(f"<code>RoBERTa: {html.escape(s['roberta']['label'])} {_to10(s['roberta']['score']):.2f}/10</code>")
    if s.get("vader"):
        lines.append(f"<code>VADER: comp {_to10((s['vader']['compound'] + 1) / 2.0):.2f}/10</code>")
    return "\n".join(lines)

def format_insights_block(url: str, body: str, title: str, summary: str) -> str:
    txt = " ".join([title or "", summary or "", body or ""]).strip()
    kw = pick_keywords(txt, limit=6)
    read_mins = read_time_minutes(body or summary or title)
    wc = len((body or summary or title).split())
    host = host_of(url)
    parts = [f"📊 <i>{host}</i> • ~{read_mins} min • {wc} words"]
    if kw:
        parts.append("🔎 " + ", ".join(f"#{k.replace(' ','')}" for k in kw))
    w = why_it_matters(txt)
    if w:
        parts.append("🎯 " + h(w))
    return "\n".join(parts)

def format_message(feed_title: str, title: str, url: str, summary: str,
                   sent: dict, hyper: bool, pub_ts: Optional[int],
                   tags: Optional[list[str]] = None, body: str = "") -> str:
    date_str = ""
    if pub_ts:
        try:
            date_str = datetime.fromtimestamp(pub_ts).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass

    tag_list = tags or []
    if hyper and "Hyperliquid" not in tag_list:
        tag_list.append("Hyperliquid")
    tags_line = " ".join(f"#{t.replace(' ','')}" for t in tag_list) if tag_list else ""

    header = f"<b>📰 {h(title)}</b>\n🗞️ {h(feed_title)}" + (f" — {h(date_str)}" if date_str else "")
    senti = format_sentiment_block(sent)
    insights = format_insights_block(url, body, title, summary)

    lines = [header, senti, f"🧾 {h(clip(summary, 400))}"]
    if tags_line:
        lines.append(tags_line)
    lines.append(insights)
    if url:
        lines.append(f"🔗 <a href=\"{h(url)}\">{h(url)}</a>")
    return "\n".join(lines)

# ---------- Feed processing ----------
async def process_feed(client_http: httpx.AsyncClient, feed_url: str) -> int:
    posted = 0
    try:
        r = await client_http.get(feed_url, timeout=TIMEOUT)
        r.raise_for_status()
        parsed = feedparser.parse(r.content)
    except Exception as e:
        log.warning(f"Feed fetch failed {feed_url}: {e}")
        return 0

    feed_title = (parsed.feed.get("title") if parsed.get("feed") else None) or feed_url
    entries = parsed.entries or []
    for entry in entries:
        try:
            key = entry_key(entry)
            if seen_before(DB_PATH, feed_url, key):
                continue

            link = getattr(entry, "link", "") or ""
            title = getattr(entry, "title", "") or ""
            summary = first_nonempty(getattr(entry, "summary", ""), getattr(entry, "description", ""))
            pub_ts = to_unix_ts(getattr(entry, "published", None))
            if too_old(pub_ts):
                mark_seen(DB_PATH, feed_url, key, pub_ts)
                continue

            html_text = await fetch_text(client_http, link)
            body = extract_fulltext(html_text, link) or ""

            include, macro, crypto = matches_filters(title, summary, body)
            hyper = bool(HYPER_REGEX.search(" ".join([title, summary, body])))

            if not include and POST_ONLY_ON_STRONG_MATCH:
                tmp_text = (title + "\n" + summary + "\n" + body)[:1200]
                tmp_sent = sentiment_ensemble(tmp_text)
                if (macro or crypto) and (tmp_sent["score"] >= 0.8 or tmp_sent["score"] <= 0.2):
                    include = True

            if not include:
                log.info(json.dumps({
                    "event": "skip_item",
                    "reason": "filter_not_matched",
                    "feed": feed_url,
                    "title": title[:160]
                }))
                mark_seen(DB_PATH, feed_url, key, pub_ts)
                continue

            # Sentiment (full)
            raw_for_sent = (title + "\n" + summary + "\n" + body)[:1600]
            sent = sentiment_ensemble(raw_for_sent)

            # Tags
            tags = []
            if macro: tags.append("Macro")
            if crypto: tags.append("Crypto")

            msg = format_message(
                feed_title=feed_title,
                title=title,
                url=link,
                summary=first_nonempty(body, summary, title),
                sent=sent,
                hyper=hyper,
                pub_ts=pub_ts,
                tags=tags,
                body=body,
            )

            await tg_send(client_http, msg)
            posted += 1
            mark_seen(DB_PATH, feed_url, key, pub_ts)
            await asyncio.sleep(0.6)  # throttle Telegram to avoid 429
        except Exception as e:
            log.exception(f"Entry error {feed_url}: {e}")
            await asyncio.sleep(0.5)
    return posted

async def run_loop():
    init_db(DB_PATH)
    log.info(f"Starting. Feeds: {len(FEEDS)} | poll every {POLL_SECONDS}s | chat={CHAT_ID} topic={THREAD_ID or '-'}")
    async with httpx.AsyncClient(
        headers={"User-Agent": "WildmetaMacroCryptoBot/2.5"},
        follow_redirects=True,  # important for 301/302/308
    ) as client:
        # Warm HF models (optional)
        try:
            load_hf_models()
            log.info("Loaded HF sentiment models.")
        except Exception as e:
            log.warning(f"Could not pre-load HF models (will fallback if needed): {e}")

        # initial pass
        for feed in FEEDS:
            try:
                cnt = await process_feed(client, feed)
                if cnt:
                    log.info(f"Posted {cnt} from {feed}")
            except Exception as e:
                log.warning(f"Feed pass failed {feed}: {e}")

        # loop forever
        while True:
            start = time.time()
            total = 0
            for feed in FEEDS:
                total += await process_feed(client, feed)
            dur = time.time() - start
            log.info(json.dumps({"event":"cycle_done","posted":total,"duration_s":round(dur,2)}))
            await asyncio.sleep(POLL_SECONDS)

def main():
    try:
        asyncio.run(run_loop())
    except KeyboardInterrupt:
        log.info("Bye.")

if __name__ == "__main__":
    main()
