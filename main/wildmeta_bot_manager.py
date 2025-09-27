#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wildmeta Bot Manager - Main Entry Point
Manages both RSS and X feed bots with unified control, monitoring, and logging.

Usage:
    python wildmeta_bot_manager.py           # Run both bots
    python wildmeta_bot_manager.py --rss     # Run only RSS bot
    python wildmeta_bot_manager.py --x       # Run only X bot
    python wildmeta_bot_manager.py --status  # Check bot status
"""

import os
import sys
import asyncio
import signal
import logging
import argparse
import json
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor
import threading
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import both bot modules
try:
    import rss_macro_crypto_bot
    import wildmeta_x_feed_bot
except ImportError as e:
    print(f"Error importing bot modules: {e}")
    print("Make sure both bot files are in the same directory as this manager.")
    sys.exit(1)

# ---------- Configuration ----------
from dotenv import load_dotenv
load_dotenv()

# Logging configuration
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# ---------- Logging Setup ----------
class BotLogHandler(logging.Handler):
    """Custom log handler to track bot status and errors."""
    
    def __init__(self):
        super().__init__()
        self.rss_errors = []
        self.x_errors = []
        self.rss_last_activity = None
        self.x_last_activity = None
        
    def emit(self, record):
        # Track errors
        if record.levelno >= logging.ERROR:
            if "macro-crypto-bot" in record.name:
                self.rss_errors.append({
                    "time": datetime.now(timezone.utc).isoformat(),
                    "message": record.getMessage()
                })
                # Keep only last 10 errors
                self.rss_errors = self.rss_errors[-10:]
            elif "wildmeta-x-bot" in record.name:
                self.x_errors.append({
                    "time": datetime.now(timezone.utc).isoformat(),
                    "message": record.getMessage()
                })
                self.x_errors = self.x_errors[-10:]
        
        # Track activity
        if "cycle_done" in record.getMessage() or "cycle_complete" in record.getMessage():
            if "macro-crypto-bot" in record.name:
                self.rss_last_activity = datetime.now(timezone.utc)
            elif "wildmeta-x-bot" in record.name:
                self.x_last_activity = datetime.now(timezone.utc)

# Global log handler for monitoring
bot_log_handler = BotLogHandler()

def setup_logging(name: str, log_file: str) -> logging.Logger:
    """Set up logging for each bot with file and console output."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    logger.handlers = []
    
    # File handler
    file_handler = logging.FileHandler(LOG_DIR / log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # Console handler with color coding
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Add custom handler for monitoring
    logger.addHandler(bot_log_handler)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# ---------- Bot Manager Class ----------
class BotManager:
    """Manages multiple bot processes with monitoring and control."""
    
    def __init__(self):
        self.rss_task: Optional[asyncio.Task] = None
        self.x_task: Optional[asyncio.Task] = None
        self.shutdown_event = asyncio.Event()
        self.rss_enabled = True
        self.x_enabled = True
        self.start_time = datetime.now(timezone.utc)
        
        # Setup loggers
        self.rss_logger = setup_logging("macro-crypto-bot", "rss_bot.log")
        self.x_logger = setup_logging("wildmeta-x-bot", "x_bot.log")
        self.manager_logger = setup_logging("bot-manager", "manager.log")
        
    async def run_rss_bot(self):
        """Run the RSS bot in its own async context."""
        self.manager_logger.info("Starting RSS Macro/Crypto Bot...")
        try:
            # Monkey-patch the logger in the RSS bot module
            rss_macro_crypto_bot.log = self.rss_logger
            
            # Run the RSS bot
            await rss_macro_crypto_bot.run_loop()
        except asyncio.CancelledError:
            self.manager_logger.info("RSS bot cancelled")
            raise
        except Exception as e:
            self.manager_logger.error(f"RSS bot crashed: {e}")
            raise
            
    async def run_x_bot(self):
        """Run the X bot in its own async context."""
        self.manager_logger.info("Starting X Feed Bot...")
        try:
            # Monkey-patch the logger in the X bot module
            wildmeta_x_feed_bot.log = self.x_logger
            
            # Run the X bot
            await wildmeta_x_feed_bot.run_loop()
        except asyncio.CancelledError:
            self.manager_logger.info("X bot cancelled")
            raise
        except Exception as e:
            self.manager_logger.error(f"X bot crashed: {e}")
            raise
    
    async def health_monitor(self):
        """Monitor bot health and restart if needed."""
        while not self.shutdown_event.is_set():
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Check RSS bot
                if self.rss_enabled and self.rss_task:
                    if self.rss_task.done():
                        exception = self.rss_task.exception()
                        if exception:
                            self.manager_logger.error(f"RSS bot died with exception: {exception}")
                            self.manager_logger.info("Restarting RSS bot...")
                            self.rss_task = asyncio.create_task(self.run_rss_bot())
                
                # Check X bot
                if self.x_enabled and self.x_task:
                    if self.x_task.done():
                        exception = self.x_task.exception()
                        if exception:
                            self.manager_logger.error(f"X bot died with exception: {exception}")
                            self.manager_logger.info("Restarting X bot...")
                            self.x_task = asyncio.create_task(self.run_x_bot())
                            
            except Exception as e:
                self.manager_logger.error(f"Health monitor error: {e}")
                
    def get_status(self) -> Dict:
        """Get current status of all bots."""
        uptime = datetime.now(timezone.utc) - self.start_time
        
        status = {
            "manager": {
                "uptime": str(uptime).split('.')[0],
                "start_time": self.start_time.isoformat(),
            },
            "rss_bot": {
                "enabled": self.rss_enabled,
                "running": self.rss_task and not self.rss_task.done() if self.rss_task else False,
                "last_activity": bot_log_handler.rss_last_activity.isoformat() if bot_log_handler.rss_last_activity else None,
                "recent_errors": len(bot_log_handler.rss_errors),
                "database": os.path.exists("bot.db")
            },
            "x_bot": {
                "enabled": self.x_enabled,
                "running": self.x_task and not self.x_task.done() if self.x_task else False,
                "last_activity": bot_log_handler.x_last_activity.isoformat() if bot_log_handler.x_last_activity else None,
                "recent_errors": len(bot_log_handler.x_errors),
                "database": os.path.exists("x_bot.db")
            }
        }
        
        return status
    
    async def start(self, rss_only=False, x_only=False):
        """Start the bot manager and selected bots."""
        self.manager_logger.info("=" * 60)
        self.manager_logger.info("   Wildmeta Intelligence Suite - Bot Manager")
        self.manager_logger.info("=" * 60)
        
        # Determine which bots to run
        if rss_only:
            self.x_enabled = False
            self.manager_logger.info("Mode: RSS Bot Only")
        elif x_only:
            self.rss_enabled = False
            self.manager_logger.info("Mode: X Bot Only")
        else:
            self.manager_logger.info("Mode: Both Bots")
        
        # Start selected bots
        tasks = []
        
        if self.rss_enabled:
            self.rss_task = asyncio.create_task(self.run_rss_bot())
            tasks.append(self.rss_task)
            self.manager_logger.info("✓ RSS Macro/Crypto Bot scheduled")
        
        if self.x_enabled:
            self.x_task = asyncio.create_task(self.run_x_bot())
            tasks.append(self.x_task)
            self.manager_logger.info("✓ X Feed Bot scheduled")
        
        # Start health monitor
        monitor_task = asyncio.create_task(self.health_monitor())
        tasks.append(monitor_task)
        self.manager_logger.info("✓ Health monitor started")
        
        self.manager_logger.info("-" * 60)
        self.manager_logger.info("All systems operational. Press Ctrl+C to stop.")
        self.manager_logger.info(f"Logs directory: {LOG_DIR.absolute()}")
        self.manager_logger.info("-" * 60)
        
        # Wait for shutdown or task completion
        try:
            await self.shutdown_event.wait()
        except KeyboardInterrupt:
            self.manager_logger.info("\nShutdown signal received...")
        
        # Cancel all tasks
        self.manager_logger.info("Stopping all bots...")
        for task in tasks:
            if task and not task.done():
                task.cancel()
        
        # Wait for tasks to complete cancellation
        await asyncio.gather(*tasks, return_exceptions=True)
        
        self.manager_logger.info("All bots stopped successfully.")
        
    async def shutdown(self):
        """Trigger graceful shutdown."""
        self.shutdown_event.set()

# ---------- Signal Handlers ----------
manager_instance: Optional[BotManager] = None

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print("\n[Manager] Received shutdown signal...")
    if manager_instance:
        asyncio.create_task(manager_instance.shutdown())

# ---------- CLI Commands ----------
def check_status():
    """Check and display bot status."""
    print("\n" + "=" * 60)
    print("   Wildmeta Bot Status")
    print("=" * 60)
    
    # Check if manager is running by looking for lock file
    lock_file = Path(".manager.lock")
    if lock_file.exists():
        print("✓ Bot Manager: RUNNING")
    else:
        print("✗ Bot Manager: NOT RUNNING")
    
    # Check databases
    print("\nDatabases:")
    if Path("bot.db").exists():
        size = Path("bot.db").stat().st_size / 1024
        print(f"  ✓ RSS Bot DB: {size:.1f} KB")
    else:
        print("  ✗ RSS Bot DB: Not found")
    
    if Path("x_bot.db").exists():
        size = Path("x_bot.db").stat().st_size / 1024
        print(f"  ✓ X Bot DB: {size:.1f} KB")
    else:
        print("  ✗ X Bot DB: Not found")
    
    # Check log files
    print("\nLog Files:")
    if LOG_DIR.exists():
        for log_file in LOG_DIR.glob("*.log"):
            size = log_file.stat().st_size / 1024
            modified = datetime.fromtimestamp(log_file.stat().st_mtime)
            print(f"  • {log_file.name}: {size:.1f} KB (modified: {modified.strftime('%Y-%m-%d %H:%M')})")
    
    print("\n" + "=" * 60)

def display_help():
    """Display detailed help information."""
    help_text = """
╔══════════════════════════════════════════════════════════════╗
║           Wildmeta Intelligence Suite - Bot Manager          ║
╚══════════════════════════════════════════════════════════════╝

USAGE:
    python wildmeta_bot_manager.py [OPTIONS]

OPTIONS:
    (no options)    Run both RSS and X bots
    --rss          Run only the RSS Macro/Crypto bot
    --x            Run only the X Feed bot
    --status       Check current bot status
    --help         Display this help message

EXAMPLES:
    python wildmeta_bot_manager.py              # Run both bots
    python wildmeta_bot_manager.py --rss        # RSS bot only
    python wildmeta_bot_manager.py --x          # X bot only
    python wildmeta_bot_manager.py --status     # Check status

FEATURES:
    • Unified process management for both bots
    • Automatic restart on crashes
    • Centralized logging in logs/ directory
    • Health monitoring and status tracking
    • Graceful shutdown with Ctrl+C

LOG FILES:
    logs/manager.log    - Bot manager events
    logs/rss_bot.log   - RSS bot activity
    logs/x_bot.log     - X bot activity

MONITORING:
    The manager monitors both bots and will automatically restart
    them if they crash. All activity is logged to the logs/ folder.

STOPPING:
    Press Ctrl+C to gracefully stop all bots.
    """
    print(help_text)

# ---------- Main Entry Point ----------
async def main():
    """Main entry point for the bot manager."""
    global manager_instance
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Wildmeta Bot Manager - Manage RSS and X feed bots",
        add_help=False  # We'll handle help ourselves
    )
    parser.add_argument("--rss", action="store_true", help="Run only RSS bot")
    parser.add_argument("--x", action="store_true", help="Run only X bot")
    parser.add_argument("--status", action="store_true", help="Check bot status")
    parser.add_argument("--help", action="store_true", help="Show help message")
    
    args = parser.parse_args()
    
    # Handle help
    if args.help:
        display_help()
        return
    
    # Handle status check
    if args.status:
        check_status()
        return
    
    # Check for .env file
    if not Path(".env").exists():
        print("ERROR: .env file not found!")
        print("Please create a .env file with your bot configuration.")
        print("See config.template for an example.")
        sys.exit(1)
    
    # Create and configure manager
    manager_instance = BotManager()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, signal_handler)
    
    # Create lock file to indicate manager is running
    lock_file = Path(".manager.lock")
    lock_file.touch()
    
    try:
        # Start the manager
        await manager_instance.start(rss_only=args.rss, x_only=args.x)
    finally:
        # Clean up lock file
        if lock_file.exists():
            lock_file.unlink()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Manager] Shutdown complete.")
    except Exception as e:
        print(f"\n[Manager] Fatal error: {e}")
        sys.exit(1)
