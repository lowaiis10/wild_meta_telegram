#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wildmeta X (Twitter) → Telegram Bot
Fetches latest posts from @wildmetaHQ and posts them to Telegram with embeds.

Setup:
  pip install httpx beautifulsoup4 python-dotenv tenacity aiofiles
  
.env additions:
  BOT_TOKEN=xxxxxxxx:yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
  CHAT_ID=-1002918297497
  X_THREAD_ID=711
  X_POLL_SECONDS=300
  X_DB_PATH=./x_bot.db
  X_USERNAME=wildmetaHQ
  X_MAX_POSTS_PER_CYCLE=5
"""

from __future__ import annotations
import os, time, json, sqlite3, asyncio, hashlib, logging, html, re
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple
from urllib.parse import urlparse, quote

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv

# ---------- Configuration ----------
load_dotenv()

# Telegram configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "-1002918297497")
X_THREAD_ID = os.getenv("X_THREAD_ID", "711")  # X posts topic
POLL_SECONDS = int(os.getenv("X_POLL_SECONDS", "300"))  # 5 minutes default
DB_PATH = os.getenv("X_DB_PATH", "./x_bot.db")

# X/Twitter configuration
X_USERNAME = os.getenv("X_USERNAME", "wildmetaHQ")
MAX_POSTS_PER_CYCLE = int(os.getenv("X_MAX_POSTS_PER_CYCLE", "5"))
TIMEOUT = 30.0

if not BOT_TOKEN:
    raise SystemExit("Set BOT_TOKEN in your environment (.env).")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("wildmeta-x-bot")

# ---------- Database ----------
def init_db(path: str) -> None:
    """Initialize SQLite database for tracking seen X posts."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS x_posts (
      post_id TEXT PRIMARY KEY,
      username TEXT NOT NULL,
      content TEXT,
      posted_at INTEGER,
      first_seen_ts INTEGER NOT NULL,
      telegram_msg_id INTEGER
    );
    CREATE INDEX IF NOT EXISTS idx_username ON x_posts(username);
    CREATE INDEX IF NOT EXISTS idx_posted_at ON x_posts(posted_at);
    """)
    conn.commit()
    conn.close()

def seen_before(path: str, post_id: str) -> bool:
    """Check if we've seen this X post before."""
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM x_posts WHERE post_id=? LIMIT 1", (post_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None

def mark_seen(path: str, post_id: str, username: str, 
              content: str, posted_at: Optional[int], 
              telegram_msg_id: Optional[int] = None) -> None:
    """Mark an X post as seen and store its details."""
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute(
        """INSERT OR REPLACE INTO x_posts
           (post_id, username, content, posted_at, first_seen_ts, telegram_msg_id) 
           VALUES (?,?,?,?,?,?)""",
        (post_id, username, content, posted_at, int(time.time()), telegram_msg_id)
    )
    conn.commit()
    conn.close()

# ---------- X/Twitter Scraping ----------
class XPost:
    """Represents an X/Twitter post."""
    def __init__(self, post_id: str, username: str, content: str, 
                 timestamp: Optional[datetime] = None, 
                 images: List[str] = None, 
                 quoted_tweet: Optional[Dict] = None,
                 metrics: Optional[Dict] = None):
        self.post_id = post_id
        self.username = username
        self.content = content
        self.timestamp = timestamp
        self.images = images or []
        self.quoted_tweet = quoted_tweet
        self.metrics = metrics or {}
        self.url = f"https://x.com/{username}/status/{post_id}"

async def fetch_x_posts_nitter(client: httpx.AsyncClient, username: str) -> List[XPost]:
    """
    Fetch X posts using Nitter instances (privacy-focused Twitter frontend).
    Falls back through multiple instances if needed.
    """
    nitter_instances = [
        "https://nitter.privacydev.net",
        "https://nitter.poast.org", 
        "https://nitter.cz",
        "https://nitter.net",
    ]
    
    posts = []
    
    for instance in nitter_instances:
        try:
            url = f"{instance}/{username}"
            log.info(f"Trying Nitter instance: {url}")
            
            response = await client.get(
                url,
                timeout=TIMEOUT,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            
            if response.status_code != 200:
                log.warning(f"Instance {instance} returned status {response.status_code}")
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Parse Nitter timeline posts
            timeline_items = soup.select('.timeline-item')
            
            for item in timeline_items[:MAX_POSTS_PER_CYCLE]:
                try:
                    # Extract post ID from link
                    post_link = item.select_one('.tweet-link')
                    if not post_link:
                        continue
                        
                    post_url = post_link.get('href', '')
                    post_id_match = re.search(r'/status/(\d+)', post_url)
                    if not post_id_match:
                        continue
                        
                    post_id = post_id_match.group(1)
                    
                    # Extract content
                    content_elem = item.select_one('.tweet-content')
                    content = content_elem.get_text(strip=True) if content_elem else ""
                    
                    # Extract timestamp
                    timestamp = None
                    time_elem = item.select_one('.tweet-date a')
                    if time_elem and time_elem.get('title'):
                        try:
                            timestamp = datetime.strptime(
                                time_elem['title'], 
                                "%b %d, %Y · %I:%M %p %Z"
                            ).replace(tzinfo=timezone.utc)
                        except:
                            pass
                    
                    # Extract images
                    images = []
                    for img in item.select('.attachment-image img'):
                        img_src = img.get('src', '')
                        if img_src:
                            # Convert nitter image URL to Twitter image URL
                            if '/pic/' in img_src:
                                images.append(img_src)
                    
                    # Extract metrics
                    metrics = {}
                    stats = item.select('.tweet-stat')
                    for stat in stats:
                        icon = stat.select_one('.icon-container')
                        value = stat.select_one('.tweet-stat-value')
                        if icon and value:
                            if 'icon-comment' in str(icon):
                                metrics['replies'] = value.get_text(strip=True)
                            elif 'icon-retweet' in str(icon):
                                metrics['retweets'] = value.get_text(strip=True)
                            elif 'icon-heart' in str(icon):
                                metrics['likes'] = value.get_text(strip=True)
                    
                    posts.append(XPost(
                        post_id=post_id,
                        username=username,
                        content=content,
                        timestamp=timestamp,
                        images=images,
                        metrics=metrics
                    ))
                    
                except Exception as e:
                    log.warning(f"Error parsing post item: {e}")
                    continue
            
            if posts:
                log.info(f"Successfully fetched {len(posts)} posts from {instance}")
                return posts
                
        except Exception as e:
            log.warning(f"Failed to fetch from {instance}: {e}")
            continue
    
    return posts

async def fetch_x_posts_api(client: httpx.AsyncClient, username: str) -> List[XPost]:
    """
    Alternative: Fetch posts using unofficial X/Twitter API endpoints.
    This method may require additional headers or tokens.
    """
    posts = []
    
    try:
        # Try to get posts via X's web API (may require auth)
        url = f"https://x.com/{username}"
        
        response = await client.get(
            url,
            timeout=TIMEOUT,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
        )
        
        if response.status_code != 200:
            log.warning(f"X.com returned status {response.status_code}")
            return posts
        
        # Parse the HTML to extract initial data
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for React data in script tags
        for script in soup.find_all('script'):
            if script.string and 'window.__INITIAL_STATE__' in script.string:
                # Extract and parse the JSON data
                # This is a simplified approach - actual implementation would need proper parsing
                pass
        
        # Fallback to basic HTML scraping
        articles = soup.find_all('article', {'data-testid': 'tweet'})
        
        for article in articles[:MAX_POSTS_PER_CYCLE]:
            try:
                # Extract post URL and ID
                links = article.find_all('a', href=True)
                post_id = None
                for link in links:
                    href = link['href']
                    if '/status/' in href:
                        post_id = href.split('/status/')[-1].split('?')[0]
                        break
                
                if not post_id:
                    continue
                
                # Extract text content
                text_elem = article.find('div', {'data-testid': 'tweetText'})
                content = text_elem.get_text(strip=True) if text_elem else ""
                
                posts.append(XPost(
                    post_id=post_id,
                    username=username,
                    content=content,
                    timestamp=None,
                    images=[],
                    metrics={}
                ))
                
            except Exception as e:
                log.warning(f"Error parsing article: {e}")
                continue
                
    except Exception as e:
        log.warning(f"Failed to fetch from x.com directly: {e}")
    
    return posts

async def fetch_x_posts(client: httpx.AsyncClient, username: str) -> List[XPost]:
    """
    Main function to fetch X posts, trying multiple methods.
    """
    # Try Nitter first (more reliable, no auth needed)
    posts = await fetch_x_posts_nitter(client, username)
    
    # If Nitter fails, try direct X.com scraping
    if not posts:
        log.info("Nitter failed, trying direct X.com scraping...")
        posts = await fetch_x_posts_api(client, username)
    
    return posts

# ---------- Telegram Formatting ----------
def format_x_post_message(post: XPost) -> str:
    """
    Format an X post for Telegram with rich formatting.
    """
    # Escape HTML special characters
    def h(text: str) -> str:
        return html.escape(text or "", quote=False)
    
    # Format timestamp
    time_str = ""
    if post.timestamp:
        time_str = post.timestamp.strftime("%Y-%m-%d %H:%M UTC")
    
    # Build message parts
    lines = []
    
    # Header with X logo and username
    lines.append(f"<b>𝕏 @{h(post.username)}</b>")
    if time_str:
        lines.append(f"<i>{h(time_str)}</i>")
    lines.append("")  # Empty line
    
    # Post content
    if post.content:
        # Convert @mentions to links
        content = h(post.content)
        content = re.sub(
            r'@(\w+)', 
            r'<a href="https://x.com/\1">@\1</a>', 
            content
        )
        # Convert hashtags to links
        content = re.sub(
            r'#(\w+)', 
            r'<a href="https://x.com/hashtag/\1">#\1</a>', 
            content
        )
        lines.append(content)
        lines.append("")  # Empty line
    
    # Metrics if available
    if post.metrics:
        metrics_parts = []
        if 'replies' in post.metrics:
            metrics_parts.append(f"💬 {post.metrics['replies']}")
        if 'retweets' in post.metrics:
            metrics_parts.append(f"🔁 {post.metrics['retweets']}")
        if 'likes' in post.metrics:
            metrics_parts.append(f"❤️ {post.metrics['likes']}")
        
        if metrics_parts:
            lines.append(" • ".join(metrics_parts))
            lines.append("")  # Empty line
    
    # Add link to original post
    lines.append(f"🔗 <a href=\"{h(post.url)}\">View on X</a>")
    
    return "\n".join(lines)

# ---------- Telegram API ----------
async def tg_send_message(client: httpx.AsyncClient, text: str, 
                          disable_preview: bool = False) -> Optional[int]:
    """
    Send a message to Telegram and return the message ID.
    """
    payload = {
        "chat_id": CHAT_ID,
        "message_thread_id": int(X_THREAD_ID),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": disable_preview,
    }
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            response = await client.post(
                f"{TELEGRAM_API}/sendMessage",
                json=payload,
                timeout=TIMEOUT
            )
            
            if response.status_code == 429:
                # Rate limited
                retry_after = 5
                try:
                    data = response.json()
                    retry_after = data.get("parameters", {}).get("retry_after", 5)
                except:
                    pass
                
                log.info(f"Hit Telegram rate limit, waiting {retry_after}s...")
                await asyncio.sleep(retry_after)
                retry_count += 1
                continue
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("ok"):
                return data.get("result", {}).get("message_id")
            else:
                log.warning(f"Telegram API error: {data}")
                return None
                
        except Exception as e:
            log.error(f"Failed to send message: {e}")
            retry_count += 1
            if retry_count < max_retries:
                await asyncio.sleep(2 ** retry_count)
    
    return None

async def tg_send_with_preview(client: httpx.AsyncClient, post: XPost) -> Optional[int]:
    """
    Send an X post to Telegram with link preview (embed).
    """
    # Format the message
    message = format_x_post_message(post)
    
    # Send with preview enabled (disable_web_page_preview=False)
    msg_id = await tg_send_message(client, message, disable_preview=False)
    
    return msg_id

# ---------- Main Processing Loop ----------
async def process_x_feed(client: httpx.AsyncClient) -> int:
    """
    Fetch and process X posts from the configured username.
    Returns the number of posts sent to Telegram.
    """
    posted_count = 0
    
    try:
        # Fetch latest posts
        posts = await fetch_x_posts(client, X_USERNAME)
        
        if not posts:
            log.info(f"No posts fetched from @{X_USERNAME}")
            return 0
        
        log.info(f"Fetched {len(posts)} posts from @{X_USERNAME}")
        
        # Process posts (newest first)
        for post in posts:
            try:
                # Check if we've seen this post before
                if seen_before(DB_PATH, post.post_id):
                    log.debug(f"Already seen post {post.post_id}")
                    continue
                
                # Send to Telegram
                log.info(f"Sending post {post.post_id} to Telegram...")
                msg_id = await tg_send_with_preview(client, post)
                
                if msg_id:
                    # Mark as seen with Telegram message ID
                    mark_seen(
                        DB_PATH,
                        post.post_id,
                        post.username,
                        post.content,
                        int(post.timestamp.timestamp()) if post.timestamp else None,
                        msg_id
                    )
                    posted_count += 1
                    log.info(f"Successfully posted {post.post_id} (Telegram msg: {msg_id})")
                    
                    # Rate limit ourselves
                    await asyncio.sleep(1)
                else:
                    log.warning(f"Failed to send post {post.post_id}")
                    # Still mark as seen to avoid retry loops
                    mark_seen(
                        DB_PATH,
                        post.post_id,
                        post.username,
                        post.content,
                        int(post.timestamp.timestamp()) if post.timestamp else None,
                        None
                    )
                    
            except Exception as e:
                log.error(f"Error processing post {post.post_id}: {e}")
                continue
                
    except Exception as e:
        log.error(f"Error in process_x_feed: {e}")
    
    return posted_count

async def run_loop():
    """
    Main bot loop - polls X feed and posts to Telegram.
    """
    # Initialize database
    init_db(DB_PATH)
    
    log.info(f"Starting Wildmeta X Bot")
    log.info(f"Username: @{X_USERNAME}")
    log.info(f"Chat ID: {CHAT_ID}, Thread ID: {X_THREAD_ID}")
    log.info(f"Poll interval: {POLL_SECONDS}s")
    log.info(f"Max posts per cycle: {MAX_POSTS_PER_CYCLE}")
    
    async with httpx.AsyncClient(
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        },
        follow_redirects=True,
    ) as client:
        # Initial run
        try:
            count = await process_x_feed(client)
            if count > 0:
                log.info(f"Initial run: posted {count} new posts")
        except Exception as e:
            log.error(f"Error in initial run: {e}")
        
        # Main loop
        while True:
            try:
                # Wait for next poll
                await asyncio.sleep(POLL_SECONDS)
                
                # Process feed
                start_time = time.time()
                count = await process_x_feed(client)
                duration = time.time() - start_time
                
                log.info(json.dumps({
                    "event": "cycle_complete",
                    "posted": count,
                    "duration_s": round(duration, 2),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }))
                
            except KeyboardInterrupt:
                log.info("Received interrupt signal, shutting down...")
                break
            except Exception as e:
                log.error(f"Error in main loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying

def main():
    """
    Entry point for the bot.
    """
    try:
        asyncio.run(run_loop())
    except KeyboardInterrupt:
        log.info("Bot stopped by user.")
    except Exception as e:
        log.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    main()
