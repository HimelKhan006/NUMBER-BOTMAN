#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚡ NUMBER BOTMAN - Professional Multi-User Number Distribution Engine
======================================================================
- Single-Use Number Delivery (Numbers auto-removed on issue, 100% exclusive)
- Guaranteed '+' Prefix on all phone numbers
- Separated Main Management DB + Dedicated Country Databases
- Admin Bulk Number Upload & Bulk Removal via .txt Files
- Multi-User Session Isolation & Instant 10-Number Rotation
- 28-Hour Gist Persistent Cloud Storage & SQLite WAL Architecture
- Professional Admin Panel, Broadcast System & User Analytics
"""

import os
import sys
import subprocess

# ==========================================
# 1. Auto Dependency Installer
# ==========================================
def ensure_dependencies():
    required = [
        ("telegram", "python-telegram-bot>=21.0"),
        ("httpx",    "httpx>=0.27.0"),
        ("dotenv",   "python-dotenv>=1.0.0"),
    ]
    for module_name, package_spec in required:
        try:
            __import__(module_name)
        except ImportError:
            print(f"📦 Installing {package_spec}...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--no-warn-script-location", package_spec],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )

ensure_dependencies()

# ==========================================
# 2. Imports
# ==========================================
import re
import json
import html
import sqlite3
import logging
import asyncio
import argparse
from typing import Set, Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

import httpx
from telegram import (
    Update,
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeChat,
    MenuButtonCommands,
)
from telegram.constants import ParseMode
from telegram.error import RetryAfter, TimedOut, NetworkError, Conflict
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ==========================================
# 3. Configuration & Secrets
# ==========================================
def load_environment():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("\"'").strip()
                    if key and key not in os.environ:
                        os.environ[key] = val
        except Exception:
            pass

load_environment()

TELEGRAM_BOT_TOKEN     = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
STARTUP_TYPE           = os.getenv("STARTUP_TYPE", "workflow_dispatch").strip().lower()

_admin_raw    = os.getenv("ADMIN_USER_IDS", "").strip()
ADMIN_USER_IDS: List[int] = [int(u.strip()) for u in _admin_raw.split(",") if u.strip().isdigit()]

GIST_ID    = os.getenv("GIST_ID", os.getenv("GITHUB_GIST_ID", "")).strip()
GIST_TOKEN = os.getenv("GIST_TOKEN", os.getenv("GH_TOKEN", os.getenv("GITHUB_TOKEN", ""))).strip()

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
MAIN_DB_FILE    = os.getenv("DB_FILE", os.path.join(BASE_DIR, "bot4_database.db"))
STOCKS_DIR      = os.path.join(BASE_DIR, "country_stocks")
os.makedirs(STOCKS_DIR, exist_ok=True)

DATA_FILE = os.path.join(BASE_DIR, "bot_data.json")

# ==========================================
# 4. Logging
# ==========================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("NUMBER_BOTMAN")

def is_admin(user_id: int) -> bool:
    """Strict admin check — always requires explicit ADMIN_USER_IDS. Never grants access by default."""
    if not ADMIN_USER_IDS:
        return False  # No admins configured -> nobody is admin
    return user_id in ADMIN_USER_IDS

def is_user_authorized(user_id: int) -> bool:
    """Alias kept for compatibility — use is_admin() for all admin checks."""
    return is_admin(user_id)

# Country Flags mapping
COUNTRY_FLAGS = {
    "usa": "🇺🇸", "united states": "🇺🇸", "us": "🇺🇸",
    "uk": "🇬🇧", "united kingdom": "🇬🇧", "england": "🇬🇧", "great britain": "🇬🇧",
    "canada": "🇨🇦", "ca": "🇨🇦",
    "russia": "🇷🇺", "ru": "🇷🇺",
    "india": "🇮🇳", "in": "🇮🇳",
    "bangladesh": "🇧🇩", "bd": "🇧🇩",
    "pakistan": "🇵🇰", "pk": "🇵🇰",
    "germany": "🇩🇪", "de": "🇩🇪",
    "france": "🇫🇷", "fr": "🇫🇷",
    "italy": "🇮🇹", "it": "🇮🇹",
    "spain": "🇪🇸", "es": "🇪🇸",
    "brazil": "🇧🇷", "br": "🇧🇷",
    "australia": "🇦🇺", "au": "🇦🇺",
    "indonesia": "🇮🇩", "id": "🇮🇩",
    "nigeria": "🇳🇬", "ng": "🇳🇬",
    "netherlands": "🇳🇱", "nl": "🇳🇱",
    "sweden": "🇸🇪", "se": "🇸🇪",
    "poland": "🇵🇱", "pl": "🇵🇱",
    "turkey": "🇹🇷", "tr": "🇹🇷",
    "ukraine": "🇺🇦", "ua": "🇺🇦",
    "vietnam": "🇻🇳", "vn": "🇻🇳",
    "philippines": "🇵🇭", "ph": "🇵🇭",
    "egypt": "🇪🇬", "eg": "🇪🇬",
    "south africa": "🇿🇦", "za": "🇿🇦",
    "china": "🇨🇳", "cn": "🇨🇳",
    "japan": "🇯🇵", "jp": "🇯🇵",
}

def format_country_name(name: str) -> str:
    cleaned = name.strip()
    lower = cleaned.lower()
    for key, flag in COUNTRY_FLAGS.items():
        if key == lower or lower.startswith(key + " ") or lower.endswith(" " + key):
            if not any(char in cleaned for char in "🇦🇧🇨🇩🇪🇫🇬🇭🇮🇯🇰🇱🇲🇳🇴🇵🇶🇷🇸🇹🇺🇻🇼🇽🇾🇿"):
                return f"{flag} {cleaned}"
    return cleaned

def sanitize_phone_number(raw_num: str) -> Optional[str]:
    """Cleans phone numbers and guarantees leading '+' prefix."""
    s = raw_num.strip()
    if not s:
        return None
    digits = re.sub(r"[^\d]", "", s)
    if len(digits) < 5:
        return None
    return f"+{digits}"

# ==========================================
# 5. Database Engine (Main DB + Per-Country Stocks)
# ==========================================
def get_main_db():
    conn = sqlite3.connect(MAIN_DB_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn

def get_country_db(country_id: int):
    c_db_path = os.path.join(STOCKS_DIR, f"country_{country_id}.db")
    conn = sqlite3.connect(c_db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS available_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS used_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT NOT NULL,
            user_id INTEGER,
            delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    return conn

def init_db():
    with get_main_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS countries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                numbers_consumed INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Auto-migration if table was created previously with older schema
        try:
            conn.execute("ALTER TABLE users ADD COLUMN numbers_consumed INTEGER DEFAULT 0;")
        except Exception:
            pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS delivery_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                country_id INTEGER,
                number_count INTEGER,
                delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS linked_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT DEFAULT '',
                invite_link TEXT UNIQUE NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
    logger.info("📦 Main Management Database initialized at %s", MAIN_DB_FILE)

def register_user(user_id: int, username: str = "", first_name: str = ""):
    try:
        with get_main_db() as conn:
            conn.execute("""
                INSERT INTO users (user_id, username, first_name, numbers_consumed, joined_at, last_seen)
                VALUES (?, ?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_seen = CURRENT_TIMESTAMP;
            """, (user_id, username or "", first_name or ""))
            conn.commit()
    except Exception as e:
        logger.warning(f"Error registering user: {e}")

def get_all_user_ids() -> List[int]:
    with get_main_db() as conn:
        cur = conn.execute("SELECT user_id FROM users;")
        return [row["user_id"] for row in cur.fetchall()]

def get_or_create_country(country_name: str) -> int:
    formatted = format_country_name(country_name)
    with get_main_db() as conn:
        cur = conn.execute("SELECT id FROM countries WHERE LOWER(name) = LOWER(?);", (formatted,))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur = conn.execute("INSERT INTO countries (name) VALUES (?);", (formatted,))
        conn.commit()
        cid = cur.lastrowid
        # Initialize country DB
        get_country_db(cid).close()
        return cid

def get_all_countries_with_stock(only_active: bool = True) -> List[Dict[str, Any]]:
    results = []
    with get_main_db() as conn:
        cur = conn.execute("SELECT id, name FROM countries ORDER BY name ASC;")
        countries = cur.fetchall()

    for c in countries:
        cid = c["id"]
        cname = c["name"]
        try:
            with get_country_db(cid) as cconn:
                avail = cconn.execute("SELECT COUNT(*) FROM available_numbers;").fetchone()[0]
                used = cconn.execute("SELECT COUNT(*) FROM used_numbers;").fetchone()[0]
        except Exception:
            avail, used = 0, 0

        if only_active and avail == 0:
            continue

        results.append({
            "id": cid,
            "name": cname,
            "available": avail,
            "used": used,
            "total": avail + used,
        })
    return results

def add_numbers_to_country(country_id: int, numbers: List[str]) -> Tuple[int, int]:
    """Adds numbers with guaranteed '+' prefix to the isolated country database."""
    added = 0
    duplicates = 0
    with get_country_db(country_id) as conn:
        for raw in numbers:
            num = sanitize_phone_number(raw)
            if not num:
                continue
            try:
                conn.execute("INSERT INTO available_numbers (number) VALUES (?);", (num,))
                added += 1
            except sqlite3.IntegrityError:
                duplicates += 1
        conn.commit()
    return added, duplicates

def remove_numbers_from_country(country_id: int, numbers: List[str]) -> int:
    """Removes specific numbers from country stock via .txt list."""
    removed = 0
    with get_country_db(country_id) as conn:
        for raw in numbers:
            num = sanitize_phone_number(raw)
            if not num:
                continue
            cur = conn.execute("DELETE FROM available_numbers WHERE number = ?;", (num,))
            if cur.rowcount > 0:
                removed += cur.rowcount
        conn.commit()
    return removed

def consume_numbers_for_user(country_id: int, user_id: int, limit: int = 10) -> Tuple[List[str], int, str]:
    """
    Atomically retrieves 10 numbers for a user and REMOVES them from available stock.
    Guarantees no other user will EVER get these numbers again!
    """
    with get_main_db() as mconn:
        c_row = mconn.execute("SELECT name FROM countries WHERE id = ?;", (country_id,)).fetchone()
        country_name = c_row["name"] if c_row else "Unknown"

    with get_country_db(country_id) as cconn:
        cur = cconn.execute("""
            SELECT id, number FROM available_numbers
            ORDER BY id ASC
            LIMIT ?;
        """, (limit,))
        rows = cur.fetchall()

        if not rows:
            return [], 0, country_name

        numbers = [r["number"] for r in rows]
        ids = [r["id"] for r in rows]

        # Atomically remove from available stock & move to used archive
        cconn.execute(f"DELETE FROM available_numbers WHERE id IN ({','.join(['?']*len(ids))});", ids)
        for num in numbers:
            cconn.execute("INSERT INTO used_numbers (number, user_id) VALUES (?, ?);", (num, user_id))
        cconn.commit()

        # Get remaining available count
        remaining = cconn.execute("SELECT COUNT(*) FROM available_numbers;").fetchone()[0]

    # Update user consumption counter in main DB
    try:
        with get_main_db() as mconn:
            mconn.execute("""
                UPDATE users SET numbers_consumed = numbers_consumed + ?, last_seen = CURRENT_TIMESTAMP
                WHERE user_id = ?;
            """, (len(numbers), user_id))
            mconn.execute("""
                INSERT INTO delivery_log (user_id, country_id, number_count) VALUES (?, ?, ?);
            """, (user_id, country_id, len(numbers)))
            mconn.commit()
    except Exception as e:
        logger.warning(f"Error logging delivery: {e}")

    return numbers, remaining, country_name

def delete_country_and_stock(country_id: int) -> bool:
    try:
        with get_main_db() as conn:
            conn.execute("DELETE FROM countries WHERE id = ?;", (country_id,))
            conn.commit()
        # Delete country SQLite DB file
        c_db_path = os.path.join(STOCKS_DIR, f"country_{country_id}.db")
        if os.path.exists(c_db_path):
            os.remove(c_db_path)
        return True
    except Exception as e:
        logger.error(f"Error deleting country {country_id}: {e}")
        return False

def get_system_stats() -> Dict[str, Any]:
    with get_main_db() as mconn:
        total_users = mconn.execute("SELECT COUNT(*) FROM users;").fetchone()[0]
        total_consumed = mconn.execute("SELECT COALESCE(SUM(numbers_consumed), 0) FROM users;").fetchone()[0]

    all_countries = get_all_countries_with_stock(only_active=False)
    total_available = sum(c["available"] for c in all_countries)
    active_countries_count = sum(1 for c in all_countries if c["available"] > 0)

    return {
        "total_available": total_available,
        "total_consumed": total_consumed,
        "total_users": total_users,
        "total_countries": len(all_countries),
        "active_countries": active_countries_count,
    }

# ==========================================
# Group Management Functions
# ==========================================
def add_linked_group(title: str = "", invite_link: str = "") -> bool:
    try:
        clean_link = invite_link.strip()
        if not clean_link:
            return False
        if not clean_link.startswith("http://") and not clean_link.startswith("https://"):
            clean_link = "https://" + clean_link
        clean_title = (title or "Join OTP Group").strip()
        with get_main_db() as conn:
            conn.execute("""
                INSERT INTO linked_groups (title, invite_link)
                VALUES (?, ?)
                ON CONFLICT(invite_link) DO UPDATE SET
                    title = excluded.title;
            """, (clean_title, clean_link))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error adding linked group: {e}")
        return False

def remove_linked_group(group_id: int) -> bool:
    """Removes a linked group by its DB primary key id."""
    try:
        with get_main_db() as conn:
            conn.execute("DELETE FROM linked_groups WHERE id = ?;", (group_id,))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error removing linked group: {e}")
        return False

def set_primary_group(title: str = "", invite_link: str = "") -> bool:
    """Clears old links and sets the new primary OTP group link."""
    try:
        clean_link = invite_link.strip()
        if not clean_link:
            return False
        if not clean_link.startswith("http://") and not clean_link.startswith("https://"):
            clean_link = "https://" + clean_link
        clean_title = (title or "Join OTP Group").strip()
        with get_main_db() as conn:
            conn.execute("DELETE FROM linked_groups;")
            conn.execute("""
                INSERT INTO linked_groups (title, invite_link)
                VALUES (?, ?);
            """, (clean_title, clean_link))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error setting primary group: {e}")
        return False

def get_linked_groups() -> List[Dict[str, Any]]:
    try:
        with get_main_db() as conn:
            cur = conn.execute("SELECT id, title, invite_link, added_at FROM linked_groups ORDER BY id ASC;")
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching linked groups: {e}")
        return []

def get_top_users(limit: int = 10) -> List[Dict[str, Any]]:
    with get_main_db() as conn:
        cur = conn.execute("""
            SELECT user_id, username, first_name, numbers_consumed, last_seen
            FROM users
            ORDER BY numbers_consumed DESC, last_seen DESC
            LIMIT ?;
        """, (limit,))
        return [dict(row) for row in cur.fetchall()]

# ==========================================
# 6. Gist Persistent Storage Sync
# ==========================================
GIST_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

class GistStorage:
    def __init__(self, gist_id: str, token: str, filename: str = "number_botman_data.json",
                 description: str = "Number Botman — Persistent Cloud Backup"):
        self.gist_id = gist_id
        self.token = token
        self.filename = filename
        self.description = description
        self.bot_name = "NUMBER_BOTMAN"
        self.enabled = bool(token)
        self.api_url = f"https://api.github.com/gists/{gist_id}" if gist_id else ""

    def _auth_headers(self) -> Dict[str, str]:
        return {**GIST_HEADERS, "Authorization": f"Bearer {self.token}"}

    async def ensure_gist(self) -> bool:
        if not self.token:
            return False
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                res = await http.get("https://api.github.com/gists?per_page=100", headers=self._auth_headers())
                if res.is_success:
                    gists = res.json()
                    matching = [g for g in gists if self.filename in g.get("files", {})]
                    if matching:
                        primary = matching[0]
                        self.gist_id = primary.get("id", "")
                        self.api_url = f"https://api.github.com/gists/{self.gist_id}"
                        logger.info(f"☁️ Reusing existing GitHub Gist: {self.gist_id}")

                        for dup in matching[1:]:
                            dup_id = dup.get("id")
                            if dup_id and dup_id != self.gist_id:
                                try:
                                    del_res = await http.delete(f"https://api.github.com/gists/{dup_id}", headers=self._auth_headers())
                                    if del_res.status_code in (200, 204):
                                        logger.info(f"🗑️ Deleted duplicate Gist: {dup_id}")
                                except Exception:
                                    pass
                        return True

                res = await http.post(
                    "https://api.github.com/gists",
                    headers=self._auth_headers(),
                    json={
                        "description": self.description,
                        "public": False,
                        "files": {
                            self.filename: {
                                "content": json.dumps({"bot": self.bot_name, "countries": {}, "updated_at": datetime.now(timezone.utc).isoformat()}, indent=2)
                            }
                        }
                    }
                )
                if res.is_success:
                    self.gist_id = res.json().get("id", "")
                    self.api_url = f"https://api.github.com/gists/{self.gist_id}"
                    logger.info(f"☁️ Created new GitHub Gist: {self.gist_id}")
                    return True
        except Exception as e:
            logger.warning(f"Gist auto-discovery error: {e}")
        return False

    async def export_and_sync(self) -> bool:
        if not self.enabled or not self.api_url:
            return False
        try:
            countries_data = {}
            with get_main_db() as conn:
                cur = conn.execute("SELECT id, name FROM countries;")
                for c_row in cur.fetchall():
                    cid = c_row["id"]
                    cname = c_row["name"]
                    with get_country_db(cid) as cconn:
                        num_list = [r["number"] for r in cconn.execute("SELECT number FROM available_numbers;").fetchall()]
                        if num_list:
                            countries_data[cname] = num_list

            payload = {
                "description": self.description,
                "files": {
                    self.filename: {
                        "content": json.dumps({
                            "bot": self.bot_name,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                            "total_countries": len(countries_data),
                            "countries": countries_data,
                        }, indent=2)
                    }
                }
            }
            async with httpx.AsyncClient(timeout=15.0) as http:
                res = await http.patch(self.api_url, headers=self._auth_headers(), json=payload)
                if res.is_success:
                    logger.info("☁️ Database backed up to GitHub Gist.")
                    return True
        except Exception as e:
            logger.warning(f"Gist export error: {e}")
        return False

    async def restore_from_gist(self) -> bool:
        if not self.enabled or not self.api_url:
            return False
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                res = await http.get(self.api_url, headers=self._auth_headers())
                if res.is_success:
                    data = res.json()
                    files = data.get("files", {})
                    if self.filename in files:
                        content = files[self.filename].get("content", "{}")
                        parsed = json.loads(content)
                        countries_data = parsed.get("countries", {})
                        total_restored = 0
                        for cname, num_list in countries_data.items():
                            cid = get_or_create_country(cname)
                            added, _ = add_numbers_to_country(cid, num_list)
                            total_restored += added
                        logger.info(f"☁️ Restored {total_restored} numbers from GitHub Gist.")
                        return True
        except Exception as e:
            logger.warning(f"Gist restore error: {e}")
        return False

gist_storage = GistStorage(GIST_ID, GIST_TOKEN)

# Admin interactive state management
# admin_id -> {"numbers": List[str], "filename": str, "mode": "add"|"remove", "awaiting_country_name": bool, "awaiting_broadcast": bool}
ADMIN_STATES: Dict[int, Dict[str, Any]] = {}

# ==========================================
# 7. Network Engine (Retry & Flood Control)
# ==========================================
async def send_with_retry(bot: Bot, chat_id: int, text: str,
                          reply_markup: Optional[InlineKeyboardMarkup] = None,
                          max_retries: int = 3) -> bool:
    for attempt in range(1, max_retries + 1):
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
            return True
        except RetryAfter as e:
            logger.warning(f"Flood limit for {chat_id}. Sleeping {e.retry_after}s...")
            await asyncio.sleep(e.retry_after + 1.0)
        except (TimedOut, NetworkError) as e:
            logger.warning(f"Network error sending to {chat_id}: {e}. Retrying ({attempt}/{max_retries})...")
            await asyncio.sleep(2.0 * attempt)
        except Exception as e:
            logger.error(f"Telegram error delivering to {chat_id}: {e}")
            return False
    return False

# ==========================================
# 8. Startup Announcement System
# ==========================================
async def send_startup_announcement(application: Application):
    is_auto_restart = (STARTUP_TYPE == "schedule")
    if is_auto_restart:
        logger.info("ℹ️ Silent auto-refresh cycle active. No Telegram alert dispatched.")
        return

    stats = get_system_stats()
    admin_msg = (
        "🚀 <b>NUMBER BOTMAN ONLINE (Admin Alert)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "• <b>Status:</b> <code>Active & Serving Live Numbers ✅</code>\n"
        "• <b>Storage:</b> <code>Per-Country Database Active ☁️</code>\n"
        f"• <b>Active Stock:</b> <code>{stats['total_available']} Available Numbers</code>\n"
        f"• <b>Delivered Total:</b> <code>{stats['total_consumed']} Numbers Consumed</code>\n"
        f"• <b>Country Pools:</b> <code>{stats['active_countries']} Active Countries</code>\n"
        "🔔 <i>Single-use exclusive delivery & .txt management ready.</i>\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    for aid in ADMIN_USER_IDS:
        if aid:
            try:
                await send_with_retry(application.bot, aid, admin_msg)
                logger.info(f"✅ Startup alert sent to admin private chat {aid}")
            except Exception as e:
                logger.warning(f"Startup alert failed for admin {aid}: {e}")

# ==========================================
# 9. Keyboards & Views
# ==========================================
def get_main_menu_keyboard(user_id: int = 0) -> InlineKeyboardMarkup:
    """Builds the main menu keyboard. Admin panel button only shown to confirmed admins."""
    buttons = [
        [InlineKeyboardButton("📱 Get Number", callback_data="btn_get_number")],
        [InlineKeyboardButton("📊 Number Inventory", callback_data="btn_inventory"), InlineKeyboardButton("ℹ️ Help / Info", callback_data="btn_help")]
    ]
    if user_id and is_admin(user_id):
        buttons.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(buttons)

def get_countries_keyboard(page: int = 0, per_page: int = 8, is_admin_mode: bool = False) -> InlineKeyboardMarkup:
    countries = get_all_countries_with_stock(only_active=(not is_admin_mode))
    if not countries:
        if is_admin_mode:
            return InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Upload Numbers (.txt)", callback_data="admin_upload_prompt")],
                [InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_panel")]
            ])
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="btn_main_menu")]
        ])

    start = page * per_page
    end = start + per_page
    current_page_countries = countries[start:end]

    buttons = []
    row = []
    for c in current_page_countries:
        prefix = "adm_country_" if is_admin_mode else "c_"
        label = f"{c['name']} ({c['available']})"
        row.append(InlineKeyboardButton(label, callback_data=f"{prefix}{c['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ Previous", callback_data=f"page_{'adm_' if is_admin_mode else ''}{page-1}"))
    if end < len(countries):
        nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"page_{'adm_' if is_admin_mode else ''}{page+1}"))
    if nav_row:
        buttons.append(nav_row)

    back_cb = "admin_panel" if is_admin_mode else "btn_main_menu"
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=back_cb)])
    return InlineKeyboardMarkup(buttons)

def get_numbers_view_keyboard(country_id: int) -> InlineKeyboardMarkup:
    """Builds number result keyboard. Includes OTP group URL buttons at the bottom."""
    buttons = [
        [
            InlineKeyboardButton("🔄 Change Numbers", callback_data=f"change_num_{country_id}"),
            InlineKeyboardButton("🌍 Change Country", callback_data="btn_get_number")
        ],
    ]

    # Add linked OTP group URL buttons
    groups = get_linked_groups()
    for g in groups:
        link = g.get("invite_link", "").strip()
        title = g.get("title", "").strip() or f"OTP Group {g['id']}"
        if link:  # Only show if invite link is configured
            buttons.append([InlineKeyboardButton(f"💬 {title}", url=link)])

    buttons.append([InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")])
    return InlineKeyboardMarkup(buttons)

# ==========================================
# 10. Command Handlers
# ==========================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return

    register_user(user.id, user.username, user.first_name)

    welcome_text = (
        f"👋 <b>Welcome, {user.first_name}!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <b>NUMBER BOTMAN</b> provides fresh, exclusive phone numbers for all your OTP and verification needs.\n\n"
        f"✨ <b>Features:</b>\n"
        f"• 🔒 <b>100% Exclusive:</b> Numbers given to you are removed from stock and never given to anyone else.\n"
        f"• ➕ <b>International Format:</b> All numbers start with <code>+</code>.\n"
        f"• 🔄 <b>Change Numbers:</b> Tap to get 10 brand-new numbers instantly!\n"
        f"• 🌍 <b>Multiple Countries:</b> Choose from active global pools.\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👇 <i>Click below to get numbers:</i>"
    )
    keyboard = get_main_menu_keyboard(user.id)
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        # Silently ignore or send generic message — do not confirm admin exists
        await update.message.reply_text("⛔ <b>Access Restricted.</b> This command is not available.", parse_mode=ParseMode.HTML)
        return

    stats = get_system_stats()
    admin_text = (
        f"👑 <b>NUMBER BOTMAN — Admin Management Panel</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Real-time Live Inventory:</b>\n"
        f"• <b>Available in Stock:</b> <code>{stats['total_available']} numbers</code>\n"
        f"• <b>Delivered / Used:</b> <code>{stats['total_consumed']} numbers</code>\n"
        f"• <b>Active Countries:</b> <code>{stats['active_countries']} pools</code>\n"
        f"• <b>Registered Users:</b> <code>{stats['total_users']} users</code>\n"
        f"• <b>Cloud Storage:</b> <code>{'Connected ☁️' if gist_storage.enabled else 'Local SQLite'}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <i>Upload .txt to Add or Remove numbers in bulk:</i>"
    )
    groups = get_linked_groups()
    groups_count = len(groups)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Numbers (.txt)", callback_data="admin_upload_prompt"), InlineKeyboardButton("🗑️ Remove Numbers (.txt)", callback_data="admin_remove_prompt")],
        [InlineKeyboardButton("🌍 Manage Countries & Stock", callback_data="admin_manage_countries")],
        [InlineKeyboardButton("👥 User Analytics", callback_data="admin_users"), InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast_prompt")],
        [InlineKeyboardButton(f"💬 Linked OTP Groups ({groups_count})", callback_data="admin_linked_groups")],
        [InlineKeyboardButton("☁️ Sync Cloud Backup", callback_data="admin_sync_gist")],
        [InlineKeyboardButton("🏠 Exit Admin Panel", callback_data="btn_main_menu")]
    ])
    await update.message.reply_text(admin_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        return  # Silently ignore — do not leak admin existence

    msg_text = update.message.text.replace("/broadcast", "", 1).strip()
    if not msg_text:
        await update.message.reply_text(
            "⚠️ <b>Usage:</b> <code>/broadcast Your message here</code>\n"
            "Or use the <b>📢 Broadcast Message</b> button in `/admin`.",
            parse_mode=ParseMode.HTML
        )
        return

    await execute_broadcast(context.bot, update.message.chat_id, msg_text)

async def getnumber_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    register_user(user.id, user.username, user.first_name)
    countries = get_all_countries_with_stock(only_active=True)
    if not countries:
        await update.message.reply_text(
            "⚠️ <b>No numbers are currently available in stock.</b>\n"
            "Please check back soon or contact the admin.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")]
            ])
        )
        return

    await update.message.reply_text(
        "🌍 <b>Select a Country:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Choose the country you want numbers for:</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=get_countries_keyboard(page=0, per_page=8, is_admin_mode=False)
    )

async def inventory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    register_user(user.id, user.username, user.first_name)
    stats = get_system_stats()
    countries = get_all_countries_with_stock(only_active=True)
    c_lines = ""
    for c in countries[:10]:
        c_lines += f"• {c['name']}: <code>{c['available']} available</code>\n"
    if len(countries) > 10:
        c_lines += f"<i>...and {len(countries) - 10} more countries.</i>\n"

    if not c_lines:
        c_lines = "<i>No numbers available in stock right now.</i>\n"

    inv_text = (
        f"📊 <b>Live Number Inventory</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Available in Stock:</b> <code>{stats['total_available']} numbers</code>\n"
        f"• <b>Total Consumed:</b> <code>{stats['total_consumed']} numbers</code>\n"
        f"• <b>Active Countries:</b> <code>{stats['active_countries']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌍 <b>Available Pools:</b>\n"
        f"{c_lines}"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(
        inv_text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Get Numbers Now", callback_data="btn_get_number")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")]
        ])
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    register_user(user.id, user.username, user.first_name)
    help_text = (
        f"ℹ️ <b>How NUMBER BOTMAN Works:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"1️⃣ Use <code>/getnumber</code> or tap <b>'📱 Get Number'</b> to choose a country.\n"
        f"2️⃣ Select your country button.\n"
        f"3️⃣ Bot delivers <b>10 copyable numbers</b> (all starting with <code>+</code>).\n"
        f"4️⃣ Tap any number to copy it to clipboard.\n"
        f"5️⃣ Click <b>'🔄 Change Numbers'</b> to get 10 brand-new numbers!\n"
        f"6️⃣ Old numbers are removed from stock so no other user will receive them.\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <i>Fast, reliable, and available 24/7.</i>"
    )
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Get Number", callback_data="btn_get_number")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")]
        ])
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    stats = get_system_stats()
    stats_text = (
        f"📈 <b>NUMBER BOTMAN Live Statistics</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Available Stock:</b> <code>{stats['total_available']} numbers</code>\n"
        f"• <b>Total Consumed:</b> <code>{stats['total_consumed']} numbers</code>\n"
        f"• <b>Active Countries:</b> <code>{stats['active_countries']}</code>\n"
        f"• <b>Total Users:</b> <code>{stats['total_users']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)

async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        return  # Silently ignore
    ADMIN_STATES[user.id] = {"mode": "add"}
    await update.message.reply_text(
        "➕ <b>Add Numbers (.txt) File:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Please send a <b>.txt</b> file containing phone numbers to this chat.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
        ])
    )

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        return  # Silently ignore
    ADMIN_STATES[user.id] = {"mode": "remove"}
    await update.message.reply_text(
        "🗑️ <b>Remove Numbers (.txt) File:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Please send a <b>.txt</b> file containing phone numbers you want to delete from stock.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
        ])
    )

async def resolve_telegram_group_link(bot: Bot, input_text: str) -> tuple[str, str]:
    """
    Given an input string (e.g. 'https://t.me/KKH_OTP_GROUP' or '@KKH_OTP_GROUP' or 'My Group | https://t.me/...'),
    resolves the real chat title and permanent invite link via Telegram Bot API if possible.
    """
    parts = input_text.split("|", 1)
    if len(parts) == 2:
        title = parts[0].strip()
        link = parts[1].strip()
    else:
        title = ""
        link = input_text.strip()

    # Extract username if it's a public link like https://t.me/username
    clean_username = link
    for prefix in ["https://t.me/", "http://t.me/", "t.me/", "https://telegram.me/", "@"]:
        if clean_username.startswith(prefix):
            clean_username = clean_username[len(prefix):]
            break
    clean_username = clean_username.strip("/").strip()

    # If it's a plain username (no +), try to get official chat info from Telegram
    if clean_username and not clean_username.startswith("+"):
        try:
            chat = await bot.get_chat(f"@{clean_username}")
            if chat:
                if not title:
                    title = chat.title or "Join OTP Group"
                if chat.invite_link:
                    link = chat.invite_link
                else:
                    link = f"https://t.me/{clean_username}"
                return title, link
        except Exception as e:
            logger.warning(f"Could not resolve chat @{clean_username}: {e}")

    if not title:
        title = "Join OTP Group"
    if not link.startswith("http://") and not link.startswith("https://"):
        link = "https://" + link
    return title, link

async def addgroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        return  # Silently ignore

    text = update.message.text.replace("/addgroup", "", 1).strip()
    if not text:
        ADMIN_STATES[user.id] = {"awaiting_group_link": True}
        await update.message.reply_text(
            "➕ <b>Add Linked OTP Group:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Please send the group title and invite link, for example:\n"
            "<code>My OTP Group | https://t.me/yourgroup</code>\n\n"
            "<i>Or simply send just the Telegram link / username:</i>\n"
            "<code>https://t.me/yourgroup</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ])
        )
        return

    title, link = await resolve_telegram_group_link(context.bot, text)

    ok = add_linked_group(title=title, invite_link=link)
    if ok:
        await update.message.reply_text(
            f"✅ <b>OTP Group Linked Successfully!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏷️ <b>Title:</b> <code>{title}</code>\n"
            f"🔗 <b>Link:</b> <code>{link}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ <i>This group will now appear as a direct redirect button at the bottom of the numbers screen!</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 View Linked Groups", callback_data="admin_linked_groups")],
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ])
        )
    else:
        await update.message.reply_text("❌ <b>Failed to link group.</b>", parse_mode=ParseMode.HTML)

async def setgroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        return  # Silently ignore

    text = update.message.text.replace("/setgroup", "", 1).strip()
    if not text:
        ADMIN_STATES[user.id] = {"awaiting_set_group_link": True}
        await update.message.reply_text(
            "🔄 <b>Update / Replace OTP Group Link:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Send your group link or username to replace any old/expired links:\n\n"
            "<b>Format:</b>\n"
            "<code>Group Name | https://t.me/your_link</code>\n"
            "<i>Or simply send the link or username:</i>\n"
            "<code>https://t.me/your_otp_group</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ])
        )
        return

    title, link = await resolve_telegram_group_link(context.bot, text)

    ok = set_primary_group(title=title, invite_link=link)
    if ok:
        await update.message.reply_text(
            f"✅ <b>Primary OTP Group Link Updated!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏷️ <b>Title:</b> <code>{title}</code>\n"
            f"🔗 <b>Link:</b> <code>{link}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ <i>All old/expired links cleared. This new link is now active at the bottom of the numbers screen!</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 View Linked Groups", callback_data="admin_linked_groups")],
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ])
        )
    else:
        await update.message.reply_text("❌ <b>Failed to update group link.</b>", parse_mode=ParseMode.HTML)

async def execute_broadcast(bot: Bot, admin_chat_id: int, text: str):
    user_ids = get_all_user_ids()
    if not user_ids:
        await bot.send_message(admin_chat_id, "⚠️ No registered users found.", parse_mode=ParseMode.HTML)
        return

    status_msg = await bot.send_message(
        admin_chat_id,
        f"⏳ <b>Broadcasting to {len(user_ids)} users...</b>",
        parse_mode=ParseMode.HTML
    )

    success = 0
    failed = 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, text, parse_mode=ParseMode.HTML)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"📢 <b>Broadcast Complete!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>Sent Successfully:</b> <code>{success}</code>\n"
        f"❌ <b>Failed / Blocked:</b> <code>{failed}</code>\n"
        f"👥 <b>Total Users:</b> <code>{len(user_ids)}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode=ParseMode.HTML
    )

# ==========================================
# 11. Admin File (.txt) & Text Upload Handlers
# ==========================================
async def handle_document_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    doc = update.message.document
    if not user or not is_user_authorized(user.id) or not doc:
        return

    file_name = doc.file_name or "numbers.txt"
    if not file_name.lower().endswith(".txt"):
        await update.message.reply_text("⚠️ <b>Please upload a <code>.txt</code> file.</b>", parse_mode=ParseMode.HTML)
        return

    msg = await update.message.reply_text("⏳ <i>Downloading and parsing numbers file...</i>", parse_mode=ParseMode.HTML)

    try:
        file_obj = await context.bot.get_file(doc.file_id)
        file_bytes = await file_obj.download_as_bytearray()

        try:
            content = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content = file_bytes.decode("latin-1", errors="ignore")

        lines = content.splitlines()
        extracted_numbers = []
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            clean = sanitize_phone_number(line_str)
            if clean:
                extracted_numbers.append(clean)

        if not extracted_numbers:
            await msg.edit_text("❌ <b>No valid phone numbers found in this file.</b>", parse_mode=ParseMode.HTML)
            return

        # Check if admin previously selected "remove" mode
        prev_mode = ADMIN_STATES.get(user.id, {}).get("mode", "add")

        ADMIN_STATES[user.id] = {
            "numbers": extracted_numbers,
            "filename": file_name,
            "mode": prev_mode,
        }

        countries = get_all_countries_with_stock(only_active=False)
        buttons = []
        row = []
        for c in countries[:8]:
            row.append(InlineKeyboardButton(f"{c['name']}", callback_data=f"sel_upload_c_{c['id']}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        buttons.append([InlineKeyboardButton("➕ Type New Country Name", callback_data="prompt_new_country")])
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_upload")])

        action_label = "➕ ADD to" if prev_mode == "add" else "🗑️ REMOVE from"
        await msg.edit_text(
            f"📄 <b>File Parsed:</b> <code>{file_name}</code>\n"
            f"🔢 <b>Valid Numbers (with +):</b> <code>{len(extracted_numbers)}</code>\n"
            f"⚙️ <b>Action:</b> <code>{action_label} Stock</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌍 <b>Select Country:</b>\n"
            f"<i>Tap an existing country below or tap 'Type New Country Name':</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        logger.error(f"Error handling file upload: {e}")
        await msg.edit_text(f"❌ <b>Error processing file:</b> <code>{e}</code>", parse_mode=ParseMode.HTML)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    if not user or not is_user_authorized(user.id) or not text:
        return

    admin_state = ADMIN_STATES.get(user.id)
    if not admin_state:
        return

    if admin_state.get("awaiting_broadcast"):
        del ADMIN_STATES[user.id]
        await execute_broadcast(context.bot, update.message.chat_id, text)
        return

    if admin_state.get("awaiting_group_link"):
        del ADMIN_STATES[user.id]
        title, link = await resolve_telegram_group_link(context.bot, text)

        ok = add_linked_group(title=title, invite_link=link)
        if ok:
            await update.message.reply_text(
                f"✅ <b>OTP Group Linked Successfully!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🏷️ <b>Title:</b> <code>{title}</code>\n"
                f"🔗 <b>Link:</b> <code>{link}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"✨ <i>This group is now added as a direct redirect button at the bottom of the numbers screen!</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 View Linked Groups", callback_data="admin_linked_groups")],
                    [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
                ])
            )
        else:
            await update.message.reply_text(
                "❌ <b>Failed to save group.</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
                ])
            )
        return

    if admin_state.get("awaiting_set_group_link"):
        del ADMIN_STATES[user.id]
        title, link = await resolve_telegram_group_link(context.bot, text)

        ok = set_primary_group(title=title, invite_link=link)
        if ok:
            await update.message.reply_text(
                f"✅ <b>Primary OTP Group Link Updated!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🏷️ <b>Title:</b> <code>{title}</code>\n"
                f"🔗 <b>Link:</b> <code>{link}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"✨ <i>All previous/expired links removed. The new link is now active!</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 View Linked Groups", callback_data="admin_linked_groups")],
                    [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
                ])
            )
        else:
            await update.message.reply_text(
                "❌ <b>Failed to update group link.</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
                ])
            )
        return

    if admin_state.get("awaiting_country_name"):
        country_name = text
        numbers = admin_state["numbers"]
        filename = admin_state["filename"]
        mode = admin_state.get("mode", "add")

        cid = get_or_create_country(country_name)

        if mode == "remove":
            removed = remove_numbers_from_country(cid, numbers)
            del ADMIN_STATES[user.id]
            if gist_storage.enabled:
                asyncio.create_task(gist_storage.export_and_sync())

            all_c = get_all_countries_with_stock(only_active=False)
            c_info = next((x for x in all_c if x["id"] == cid), {})
            await update.message.reply_text(
                f"🗑️ <b>Removal Complete!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🌍 <b>Country:</b> <code>{c_info.get('name', country_name)}</code>\n"
                f"📄 <b>Source File:</b> <code>{filename}</code>\n"
                f"🗑️ <b>Removed Numbers:</b> <code>{removed}</code>\n"
                f"📊 <b>Remaining Stock:</b> <code>{c_info.get('available', 0)}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
                ])
            )
            return

        added, duplicates = add_numbers_to_country(cid, numbers)
        del ADMIN_STATES[user.id]

        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())

        all_c = get_all_countries_with_stock(only_active=False)
        c_info = next((x for x in all_c if x["id"] == cid), {})

        await update.message.reply_text(
            f"✅ <b>Upload Complete!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌍 <b>Country:</b> <code>{c_info.get('name', country_name)}</code>\n"
            f"📄 <b>Source File:</b> <code>{filename}</code>\n"
            f"📥 <b>Added Numbers:</b> <code>{added}</code>\n"
            f"⚠️ <b>Duplicates Skipped:</b> <code>{duplicates}</code>\n"
            f"📊 <b>Total Available:</b> <code>{c_info.get('available', added)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📱 Test Get Numbers", callback_data=f"c_{cid}")],
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ])
        )

# ==========================================
# 12. Callback Query Handler (Interactive Buttons)
# ==========================================
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = update.effective_user
    if not user:
        return

    user_admin = is_admin(user.id)
    register_user(user.id, user.username, user.first_name)

    # 1. Main Menu
    if data == "btn_main_menu":
        welcome_text = (
            f"👋 <b>Welcome, {user.first_name}!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 <b>NUMBER BOTMAN</b> provides fresh, exclusive phone numbers for all your OTP and verification needs.\n\n"
            f"✨ <b>Features:</b>\n"
            f"• 🔒 <b>100% Exclusive:</b> Numbers given to you are removed from stock and never given to anyone else.\n"
            f"• ➕ <b>International Format:</b> All numbers start with <code>+</code>.\n"
            f"• 🔄 <b>Change Numbers:</b> Tap to get 10 brand-new numbers instantly!\n"
            f"• 🌍 <b>Multiple Countries:</b> Choose from active global pools.\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👇 <i>Click below to get numbers:</i>"
        )
        await query.edit_message_text(
            welcome_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard(user.id)
        )

    # 2. Get Number -> Choose Country
    elif data == "btn_get_number" or (data.startswith("page_") and not data.startswith("page_adm_")):
        page = int(data.split("_")[1]) if data.startswith("page_") else 0
        countries = get_all_countries_with_stock(only_active=True)
        if not countries:
            await query.edit_message_text(
                "⚠️ <b>No numbers are currently available in stock.</b>\n\n"
                "Please check back soon or contact the admin to upload new numbers.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="btn_main_menu")]
                ])
            )
            return

        await query.edit_message_text(
            "🌍 <b>Select a Country:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Choose the country you want numbers for:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_countries_keyboard(page=page, per_page=8, is_admin_mode=False)
        )

    # 3. Selected Country / Change Numbers -> Consume & Deliver 10 Numbers
    elif data.startswith("c_") or data.startswith("change_num_"):
        country_id = int(data.split("_")[1]) if data.startswith("c_") else int(data.split("_")[2])

        numbers, remaining_count, country_name = consume_numbers_for_user(
            country_id=country_id,
            user_id=user.id,
            limit=10
        )

        if not numbers:
            await query.edit_message_text(
                f"⚠️ <b>No more numbers available in stock for {country_name}.</b>\n"
                f"All available numbers have been consumed. Please select another country.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌍 Choose Another Country", callback_data="btn_get_number")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")]
                ])
            )
            return

        # Auto-sync Gist after consumption
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())

        num_lines = []
        for idx, n in enumerate(numbers, 1):
            num_lines.append(f"  {idx}. <code>{n}</code>")
        numbers_formatted = "\n".join(num_lines)

        group_notice = ""
        groups = get_linked_groups()
        if groups:
            group_notice = "\n\n💬 <b>Need OTP codes? Click the group button below to get OTPs!</b>"

        response_text = (
            f"📱 <b>Your Exclusive Numbers — {country_name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{numbers_formatted}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔒 <i>These {len(numbers)} numbers are reserved for you and removed from stock.</i>\n"
            f"📊 <b>Remaining in Stock:</b> <code>{remaining_count}</code>\n"
            f"💡 <b>Tap any number above to copy it instantly!</b>"
            f"{group_notice}"
        )
        await query.edit_message_text(
            response_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_numbers_view_keyboard(country_id)
        )

    # 4. Inventory Overview
    elif data == "btn_inventory":
        stats = get_system_stats()
        countries = get_all_countries_with_stock(only_active=True)
        c_lines = ""
        for c in countries[:10]:
            c_lines += f"• {c['name']}: <code>{c['available']} available</code>\n"
        if len(countries) > 10:
            c_lines += f"<i>...and {len(countries) - 10} more countries.</i>\n"

        if not c_lines:
            c_lines = "<i>No numbers available in stock right now.</i>\n"

        inv_text = (
            f"📊 <b>Live Number Inventory</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Available in Stock:</b> <code>{stats['total_available']} numbers</code>\n"
            f"• <b>Total Consumed:</b> <code>{stats['total_consumed']} numbers</code>\n"
            f"• <b>Active Countries:</b> <code>{stats['active_countries']}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌍 <b>Available Pools:</b>\n"
            f"{c_lines}"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        await query.edit_message_text(
            inv_text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📱 Get Numbers Now", callback_data="btn_get_number")],
                [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="btn_main_menu")]
            ])
        )

    # 5. Help / Info
    elif data == "btn_help":
        help_text = (
            f"ℹ️ <b>How NUMBER BOTMAN Works:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"1️⃣ Click <b>'📱 Get Number'</b> to view available countries.\n"
            f"2️⃣ Select your country button.\n"
            f"3️⃣ Bot delivers <b>10 copyable numbers</b> (all formatted with <code>+</code>).\n"
            f"4️⃣ Tap any number to copy it to clipboard.\n"
            f"5️⃣ Click <b>'🔄 Change Numbers'</b> to get 10 brand-new numbers!\n"
            f"6️⃣ Old numbers are automatically removed from stock so no other user will receive them.\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <i>Fast, reliable, and available 24/7.</i>"
        )
        await query.edit_message_text(
            help_text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📱 Get Number", callback_data="btn_get_number")],
                [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="btn_main_menu")]
            ])
        )

    # 6. Admin Panel
    elif data == "admin_panel" and user_admin:
        stats = get_system_stats()
        groups = get_linked_groups()
        groups_count = len(groups)
        admin_text = (
            f"👑 <b>NUMBER BOTMAN — Admin Management Panel</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Real-time Live Inventory:</b>\n"
            f"• <b>Available in Stock:</b> <code>{stats['total_available']} numbers</code>\n"
            f"• <b>Delivered / Used:</b> <code>{stats['total_consumed']} numbers</code>\n"
            f"• <b>Active Countries:</b> <code>{stats['active_countries']} pools</code>\n"
            f"• <b>Registered Users:</b> <code>{stats['total_users']} users</code>\n"
            f"• <b>Linked OTP Groups:</b> <code>{groups_count} active</code>\n"
            f"• <b>Cloud Storage:</b> <code>{'Connected ☁️' if gist_storage.enabled else 'Local SQLite'}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <i>Upload .txt to Add or Remove numbers in bulk:</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Numbers (.txt)", callback_data="admin_upload_prompt"), InlineKeyboardButton("🗑️ Remove Numbers (.txt)", callback_data="admin_remove_prompt")],
            [InlineKeyboardButton("🌍 Manage Countries & Stock", callback_data="admin_manage_countries")],
            [InlineKeyboardButton("👥 User Analytics", callback_data="admin_users"), InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast_prompt")],
            [InlineKeyboardButton(f"💬 Linked OTP Groups ({groups_count})", callback_data="admin_linked_groups")],
            [InlineKeyboardButton("☁️ Sync Cloud Backup", callback_data="admin_sync_gist")],
            [InlineKeyboardButton("🏠 Exit Admin Panel", callback_data="btn_main_menu")]
        ])
        await query.edit_message_text(admin_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    # 7. Admin Add Numbers Prompt
    elif data == "admin_upload_prompt" and user_admin:
        ADMIN_STATES[user.id] = {"mode": "add"}
        await query.edit_message_text(
            "➕ <b>Add Numbers (.txt) File:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Please send a <b>.txt</b> file containing phone numbers (one number per line) directly to this chat.\n\n"
            "<b>Example:</b>\n"
            "<code>+12025550143\n12025550189\n+12025550192</code>\n\n"
            "<i>(All numbers will automatically be formatted with a leading <code>+</code>).</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_panel")]
            ])
        )

    # 8. Admin Remove Numbers Prompt
    elif data == "admin_remove_prompt" and user_admin:
        ADMIN_STATES[user.id] = {"mode": "remove"}
        await query.edit_message_text(
            "🗑️ <b>Remove Numbers (.txt) File:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Please send a <b>.txt</b> file containing phone numbers you want to <b>DELETE / REMOVE</b> from stock.\n\n"
            "<i>The bot will parse the numbers and remove them from the chosen country pool.</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_panel")]
            ])
        )

    # 9. Admin User Analytics
    elif data == "admin_users" and user_admin:
        stats = get_system_stats()
        top_users = get_top_users(limit=10)
        u_lines = ""
        for idx, u in enumerate(top_users, 1):
            name = u["first_name"] or u["username"] or str(u["user_id"])
            u_lines += f"{idx}. <b>{name}</b> (<code>{u['user_id']}</code>) — <code>{u['numbers_consumed']} consumed</code>\n"

        if not u_lines:
            u_lines = "<i>No active users yet.</i>\n"

        users_text = (
            f"👥 <b>User Analytics & Activity</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Total Registered Users:</b> <code>{stats['total_users']}</code>\n"
            f"• <b>Total Numbers Consumed:</b> <code>{stats['total_consumed']}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏆 <b>Top Active Users:</b>\n"
            f"{u_lines}"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        await query.edit_message_text(
            users_text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Broadcast to All Users", callback_data="admin_broadcast_prompt")],
                [InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_panel")]
            ])
        )

    # 10. Admin Broadcast Prompt
    elif data == "admin_broadcast_prompt" and user_admin:
        ADMIN_STATES[user.id] = {"awaiting_broadcast": True}
        await query.edit_message_text(
            "📢 <b>Broadcast Message to All Users:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Please type your broadcast announcement in this chat.\n\n"
            "<i>Formatting: Supports HTML tags like <code>&lt;b&gt;bold&lt;/b&gt;</code>, <code>&lt;code&gt;code&lt;/code&gt;</code>.</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel Broadcast", callback_data="cancel_broadcast")]
            ])
        )

    # 11. Cancel Broadcast
    elif data == "cancel_broadcast" and user_admin:
        if user.id in ADMIN_STATES:
            del ADMIN_STATES[user.id]
        await query.edit_message_text(
            "❌ <b>Broadcast cancelled.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ])
        )

    # 12. Admin Select Existing Country for Upload / Removal
    elif data.startswith("sel_upload_c_") and user_admin:
        cid = int(data.split("_")[3])
        pending = ADMIN_STATES.get(user.id)
        if not pending:
            await query.edit_message_text("⚠️ <b>Session expired. Please upload the .txt file again.</b>", parse_mode=ParseMode.HTML)
            return

        numbers = pending["numbers"]
        filename = pending["filename"]
        mode = pending.get("mode", "add")

        if mode == "remove":
            removed = remove_numbers_from_country(cid, numbers)
            del ADMIN_STATES[user.id]
            if gist_storage.enabled:
                asyncio.create_task(gist_storage.export_and_sync())

            all_c = get_all_countries_with_stock(only_active=False)
            c_info = next((x for x in all_c if x["id"] == cid), {})
            await query.edit_message_text(
                f"🗑️ <b>Removal Complete!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🌍 <b>Country:</b> <code>{c_info.get('name', 'Unknown')}</code>\n"
                f"📄 <b>Source File:</b> <code>{filename}</code>\n"
                f"🗑️ <b>Removed Numbers:</b> <code>{removed}</code>\n"
                f"📊 <b>Remaining Stock:</b> <code>{c_info.get('available', 0)}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
                ])
            )
            return

        added, duplicates = add_numbers_to_country(cid, numbers)
        del ADMIN_STATES[user.id]

        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())

        all_c = get_all_countries_with_stock(only_active=False)
        c_info = next((x for x in all_c if x["id"] == cid), {})

        await query.edit_message_text(
            f"✅ <b>Upload Complete!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌍 <b>Country:</b> <code>{c_info.get('name', 'Unknown')}</code>\n"
            f"📄 <b>Source File:</b> <code>{filename}</code>\n"
            f"📥 <b>Added Numbers (with +):</b> <code>{added}</code>\n"
            f"⚠️ <b>Duplicates Skipped:</b> <code>{duplicates}</code>\n"
            f"📊 <b>Total Available Stock:</b> <code>{c_info.get('available', added)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📱 Test Get Numbers", callback_data=f"c_{cid}")],
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ])
        )

    # 13. Admin Prompt Type New Country Name
    elif data == "prompt_new_country" and user_admin:
        pending = ADMIN_STATES.get(user.id)
        if not pending:
            await query.edit_message_text("⚠️ <b>Session expired. Please upload the .txt file again.</b>", parse_mode=ParseMode.HTML)
            return
        pending["awaiting_country_name"] = True
        await query.edit_message_text(
            f"✍️ <b>Please type the Country Name in chat:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Example:</i> <code>USA</code> or <code>United States 🇺🇸</code> or <code>India 🇮🇳</code>\n\n"
            f"All <b>{len(pending['numbers'])}</b> numbers will be processed for this country!",
            parse_mode=ParseMode.HTML
        )

    # 14. Admin Cancel Upload
    elif data == "cancel_upload" and user_admin:
        if user.id in ADMIN_STATES:
            del ADMIN_STATES[user.id]
        await query.edit_message_text("❌ <b>Action cancelled.</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
        ]))

    # 15. Admin Manage Countries
    elif (data == "admin_manage_countries" or data.startswith("page_adm_")) and user_admin:
        page = int(data.split("_")[2]) if data.startswith("page_adm_") else 0
        countries = get_all_countries_with_stock(only_active=False)
        if not countries:
            await query.edit_message_text(
                "🌍 <b>No countries created yet.</b>\nUpload a .txt file to create your first country pool!",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📤 Upload Numbers (.txt)", callback_data="admin_upload_prompt")],
                    [InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_panel")]
                ])
            )
            return

        await query.edit_message_text(
            "🌍 <b>Manage Countries & Stocks:</b>\n"
            "<i>Select a country to view details, stock, or delete:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_countries_keyboard(page=page, per_page=8, is_admin_mode=True)
        )

    # 16. Admin View Country Details
    elif data.startswith("adm_country_") and user_admin:
        cid = int(data.split("_")[2])
        all_c = get_all_countries_with_stock(only_active=False)
        c_info = next((x for x in all_c if x["id"] == cid), {})
        c_name = c_info.get("name", "Unknown")

        await query.edit_message_text(
            f"🌍 <b>Country:</b> <code>{c_name}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>Available in Stock:</b> <code>{c_info.get('available', 0)}</code>\n"
            f"🔒 <b>Delivered / Used:</b> <code>{c_info.get('used', 0)}</code>\n"
            f"📊 <b>Total Numbers Added:</b> <code>{c_info.get('total', 0)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ Delete Country & All Stock", callback_data=f"adm_del_confirm_{cid}")],
                [InlineKeyboardButton("🔙 Back to Countries", callback_data="admin_manage_countries")]
            ])
        )

    # 17. Admin Delete Country Confirmation
    elif data.startswith("adm_del_confirm_") and user_admin:
        cid = int(data.split("_")[3])
        all_c = get_all_countries_with_stock(only_active=False)
        c_name = next((x["name"] for x in all_c if x["id"] == cid), "Unknown")

        await query.edit_message_text(
            f"⚠️ <b>Are you sure you want to delete {c_name} and its stock database?</b>\n"
            f"<i>This action cannot be undone.</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"adm_del_do_{cid}")],
                [InlineKeyboardButton("❌ Cancel", callback_data=f"adm_country_{cid}")]
            ])
        )

    # 18. Admin Execute Delete
    elif data.startswith("adm_del_do_") and user_admin:
        cid = int(data.split("_")[3])
        delete_country_and_stock(cid)
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())
        await query.edit_message_text(
            "🗑️ <b>Country pool and database deleted successfully.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ])
        )

    # 19. Admin Sync Gist
    elif data == "admin_sync_gist" and user_admin:
        if not gist_storage.enabled:
            await query.edit_message_text(
                "⚠️ <b>GIST_TOKEN is not configured in .env or secrets.</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
                ])
            )
            return

        ok = await gist_storage.export_and_sync()
        status_msg = "✅ <b>Database backed up to GitHub Gist successfully!</b>" if ok else "❌ <b>Backup to Gist failed.</b> Check logs."
        await query.edit_message_text(
            status_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ])
        )

    # 20. Admin Manage Linked OTP Groups
    elif data == "admin_linked_groups" and user_admin:
        groups = get_linked_groups()
        groups_list_text = ""
        buttons = []
        if groups:
            for idx, g in enumerate(groups, 1):
                groups_list_text += f"<b>{idx}. {g['title']}</b>\n🔗 <code>{g['invite_link']}</code>\n\n"
                buttons.append([InlineKeyboardButton(f"🗑️ Delete: {g['title'][:20]}", callback_data=f"del_group_{g['id']}")])
        else:
            groups_list_text = "<i>No OTP groups linked yet. Click '🔄 Set Primary OTP Link' below to set one!</i>\n\n"

        text = (
            f"💬 <b>Linked OTP Groups Management</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"These group buttons appear at the bottom of the <b>Get Number</b> results screen so users can click and be redirected straight to your OTP group for codes.\n\n"
            f"{groups_list_text}"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>Tip: For private groups, make sure to generate a permanent link with 'No expiration' so users never see an 'Expired link' error!</i>"
        )
        buttons.append([InlineKeyboardButton("🔄 Set / Replace Primary Link", callback_data="prompt_set_group")])
        buttons.append([InlineKeyboardButton("➕ Add Additional Group", callback_data="prompt_add_group")])
        buttons.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

    # 21. Prompt Add OTP Group
    elif data == "prompt_add_group" and user_admin:
        ADMIN_STATES[user.id] = {"awaiting_group_link": True}
        text = (
            "➕ <b>Add Linked OTP Group:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Please send your group title and invite link in this chat.\n\n"
            "<b>Format:</b>\n"
            "<code>Group Name | https://t.me/your_otp_group</code>\n\n"
            "<i>Or simply send just the Telegram link:</i>\n"
            "<code>https://t.me/your_otp_group</code>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "👇 <i>Type and send the message below:</i>"
        )
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="admin_linked_groups")]
            ])
        )

    # 21b. Prompt Set / Replace Primary OTP Group
    elif data == "prompt_set_group" and user_admin:
        ADMIN_STATES[user.id] = {"awaiting_set_group_link": True}
        text = (
            "🔄 <b>Set / Replace Primary OTP Group Link:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "This will <b>clear any old/expired links</b> and set your new permanent link active.\n\n"
            "<b>Format:</b>\n"
            "<code>Group Name | https://t.me/your_permanent_group</code>\n\n"
            "<i>Or simply send just the Telegram link:</i>\n"
            "<code>https://t.me/your_otp_group</code>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <b>To prevent expired link error:</b>\n"
            "• <b>Public group:</b> Use <code>https://t.me/group_username</code>\n"
            "• <b>Private group:</b> Edit group > Invite links > Create Link > Set <b>No time limit</b> & <b>No user limit</b>!\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "👇 <i>Type and send your new link below:</i>"
        )
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="admin_linked_groups")]
            ])
        )

    # 22. Delete OTP Group
    elif data.startswith("del_group_") and user_admin:
        gid = int(data.split("_")[2])
        remove_linked_group(gid)
        groups = get_linked_groups()
        groups_list_text = ""
        buttons = []
        if groups:
            for idx, g in enumerate(groups, 1):
                groups_list_text += f"<b>{idx}. {g['title']}</b>\n🔗 <code>{g['invite_link']}</code>\n\n"
                buttons.append([InlineKeyboardButton(f"🗑️ Delete: {g['title'][:20]}", callback_data=f"del_group_{g['id']}")])
        else:
            groups_list_text = "<i>No OTP groups linked yet.</i>\n\n"

        text = (
            f"✅ <b>OTP Group Removed!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{groups_list_text}"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        buttons.append([InlineKeyboardButton("➕ Add OTP Group", callback_data="prompt_add_group")])
        buttons.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

# ==========================================
# 13. Diagnostics & Self-Test Engine
# ==========================================
async def run_diagnostics():
    print("=" * 60)
    print("  NUMBER BOTMAN — COMPLETE SYSTEM DIAGNOSTICS")
    print("=" * 60)
    print(f" Python Version : {sys.version.split()[0]}")
    print(f" Main DB Path   : {MAIN_DB_FILE}")
    print(f" Stocks DB Dir  : {STOCKS_DIR}")
    print(f" Admin IDs      : {ADMIN_USER_IDS or 'None (Open)'}")
    print(f" Gist Storage   : {'Enabled ☁️' if GIST_TOKEN else 'Disabled (Local only)'}")
    print("-" * 60)

    # Test 1: Telegram Bot Token
    if not TELEGRAM_BOT_TOKEN:
        print("❌ [FAIL] TELEGRAM_BOT_TOKEN is missing!")
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            res = await http.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe")
            if res.status_code == 200:
                bot_info = res.json().get("result", {})
                print(f"✅ [PASS] Telegram Bot connected: @{bot_info.get('username')} ({bot_info.get('first_name')})")
            else:
                print(f"❌ [FAIL] Invalid Telegram Bot Token! (HTTP {res.status_code})")
                return False
    except Exception as e:
        print(f"❌ [FAIL] Telegram connection error: {e}")
        return False

    # Test 2: Database Initialization
    try:
        init_db()
        stats = get_system_stats()
        print(f"✅ [PASS] Main Database active: {stats['total_available']} available, {stats['total_consumed']} consumed, {stats['total_users']} users")
    except Exception as e:
        print(f"❌ [FAIL] SQLite error: {e}")
        return False

    # Test 3: Gist Cloud Storage
    if GIST_TOKEN:
        try:
            ok = await gist_storage.ensure_gist()
            if ok:
                print(f"✅ [PASS] GitHub Gist Cloud Storage connected: {gist_storage.gist_id}")
            else:
                print("⚠️ [WARN] GitHub Gist connection failed.")
        except Exception as e:
            print(f"⚠️ [WARN] Gist test error: {e}")

    print("-" * 60)
    print("🎉 ALL CORE DIAGNOSTIC TESTS PASSED! System is 100% operational.")
    print("=" * 60)
    return True

# ==========================================
# 14. Main Application Entry Point
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="NUMBER BOTMAN")
    parser.add_argument("--test", "--diagnostics", action="store_true", help="Run system diagnostics and exit")
    args = parser.parse_args()

    if args.test:
        success = asyncio.run(run_diagnostics())
        sys.exit(0 if success else 1)

    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ CRITICAL: TELEGRAM_BOT_TOKEN is missing! Please configure .env or GitHub Secrets.")
        sys.exit(1)

    init_db()

    # Cloud Gist restore on startup
    if gist_storage.enabled:
        async def init_gist():
            await gist_storage.ensure_gist()
            await gist_storage.restore_from_gist()
        asyncio.run(init_gist())

    httpx_req = HTTPXRequest(
        connection_pool_size=16,
        connect_timeout=15.0,
        read_timeout=30.0,
        write_timeout=30.0,
    )
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).request(httpx_req).build()

    # Command & Message Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("getnumber", getnumber_command))
    app.add_handler(CommandHandler("inventory", inventory_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("upload", upload_command))
    app.add_handler(CommandHandler("remove", remove_command))
    app.add_handler(CommandHandler("addgroup", addgroup_command))
    app.add_handler(CommandHandler("setgroup", setgroup_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document_upload))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    async def setup_bot_commands(application: Application):
        try:
            # 1. Default user commands
            user_commands = [
                BotCommand("start", "🚀 Start bot & open main menu"),
                BotCommand("getnumber", "📱 Get 10 numbers by country"),
                BotCommand("inventory", "📊 View live number stock"),
                BotCommand("help", "ℹ️ How to use the bot"),
                BotCommand("stats", "📈 View live statistics"),
            ]
            await application.bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
            await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())

            # 2. Admin custom commands
            admin_commands = [
                BotCommand("start", "🚀 Main Menu"),
                BotCommand("getnumber", "📱 Get Numbers"),
                BotCommand("admin", "👑 Open Admin Management Panel"),
                BotCommand("upload", "➕ Add Numbers (.txt file)"),
                BotCommand("remove", "🗑️ Remove Numbers (.txt file)"),
                BotCommand("setgroup", "🔄 Set / Replace Primary OTP Group link"),
                BotCommand("addgroup", "💬 Link additional OTP Group"),
                BotCommand("broadcast", "📢 Broadcast message to all users"),
                BotCommand("stats", "📊 View live system statistics"),
                BotCommand("help", "ℹ️ How to use the bot"),
            ]
            for aid in ADMIN_USER_IDS:
                if aid:
                    try:
                        await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(aid))
                    except Exception:
                        pass
            logger.info("✅ Telegram Bot Command Menu & Menu Button configured.")
        except Exception as e:
            logger.warning(f"Could not configure Bot Command Menu: {e}")

    async def post_init(application: Application):
        await setup_bot_commands(application)
        await send_startup_announcement(application)

    app.post_init = post_init

    logger.info("🚀 NUMBER BOTMAN is running live in multi-user exclusive mode!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
