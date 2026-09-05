#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚡ NUMBER BOTMAN - Professional Multi-User Number Distribution Engine
======================================================================
- Single-Use Number Delivery (Numbers auto-removed on issue, 100% exclusive)
- Guaranteed '+' Prefix on all phone numbers
- Separated Main Management DB + Dedicated Country Databases
- Standard Numbers + Secret Numbers Pool with Admin Access Whitelisting
- Admin Bulk Number Upload & Bulk Removal via .txt Files
- Comprehensive User Management, Profile Inspection & Real-time Consumption Tracking
- Multi-User Session Isolation & Instant 10-Number Rotation
- GitHub Gist Persistent Cloud Storage & SQLite WAL Architecture
- Clean, Minimalist & Professional Interface
"""

import os
import sys
import subprocess

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

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

# ==========================================
# 4. Logging & Helpers
# ==========================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("NUMBER_BOTMAN")

def is_admin(user_id: int) -> bool:
    """Strict admin check — always requires explicit ADMIN_USER_IDS."""
    if not ADMIN_USER_IDS:
        return False
    return user_id in ADMIN_USER_IDS

def is_user_authorized(user_id: int) -> bool:
    return is_admin(user_id)

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
            is_secret INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS used_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number TEXT NOT NULL,
            user_id INTEGER,
            is_secret INTEGER DEFAULT 0,
            delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # Auto-migrations for existing databases
    try:
        conn.execute("ALTER TABLE available_numbers ADD COLUMN is_secret INTEGER DEFAULT 0;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE used_numbers ADD COLUMN is_secret INTEGER DEFAULT 0;")
    except Exception:
        pass
    conn.commit()
    return conn

def init_db():
    with get_main_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
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
                has_secret_access INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Auto-migrations
        try:
            conn.execute("ALTER TABLE users ADD COLUMN numbers_consumed INTEGER DEFAULT 0;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN has_secret_access INTEGER DEFAULT 0;")
        except Exception:
            pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS delivery_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                country_id INTEGER,
                number_count INTEGER,
                is_secret INTEGER DEFAULT 0,
                delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        try:
            conn.execute("ALTER TABLE delivery_log ADD COLUMN is_secret INTEGER DEFAULT 0;")
        except Exception:
            pass

        conn.commit()
    logger.info("📦 Main Management Database initialized at %s", MAIN_DB_FILE)
    load_consumed_cache()

def register_user(user_id: int, username: str = "", first_name: str = ""):
    try:
        with get_main_db() as conn:
            conn.execute("""
                INSERT INTO users (user_id, username, first_name, numbers_consumed, has_secret_access, joined_at, last_seen)
                VALUES (?, ?, ?, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = CASE WHEN excluded.username != '' THEN excluded.username ELSE users.username END,
                    first_name = CASE WHEN excluded.first_name != '' THEN excluded.first_name ELSE users.first_name END,
                    last_seen = CURRENT_TIMESTAMP;
            """, (user_id, username or "", first_name or ""))
            conn.commit()
    except Exception as e:
        logger.warning(f"Error registering user: {e}")

def get_all_user_ids() -> List[int]:
    with get_main_db() as conn:
        cur = conn.execute("SELECT user_id FROM users;")
        return [row["user_id"] for row in cur.fetchall()]

def get_user_details(user_id: int) -> Optional[Dict[str, Any]]:
    with get_main_db() as conn:
        row = conn.execute("""
            SELECT user_id, username, first_name, numbers_consumed, has_secret_access, joined_at, last_seen
            FROM users WHERE user_id = ?;
        """, (user_id,)).fetchone()
        return dict(row) if row else None

def user_has_secret_access(user_id: int) -> bool:
    """Admins always have full secret access. Regular users need granted access."""
    if is_admin(user_id):
        return True
    try:
        with get_main_db() as conn:
            row = conn.execute("SELECT has_secret_access FROM users WHERE user_id = ?;", (user_id,)).fetchone()
            if row and row["has_secret_access"] == 1:
                return True
    except Exception as e:
        logger.warning(f"Error checking secret access for {user_id}: {e}")
    return False

def set_user_secret_access(user_id: int, granted: bool) -> bool:
    val = 1 if granted else 0
    try:
        with get_main_db() as conn:
            conn.execute("""
                INSERT INTO users (user_id, has_secret_access, last_seen)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    has_secret_access = excluded.has_secret_access,
                    last_seen = CURRENT_TIMESTAMP;
            """, (user_id, val))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error setting secret access for {user_id}: {e}")
        return False

def get_all_users_detailed(limit: int = 10, offset: int = 0, search: str = "") -> Tuple[List[Dict[str, Any]], int]:
    with get_main_db() as conn:
        if search:
            search_pattern = f"%{search.strip()}%"
            cur_count = conn.execute("""
                SELECT COUNT(*) FROM users
                WHERE CAST(user_id AS TEXT) LIKE ? OR username LIKE ? OR first_name LIKE ?;
            """, (search_pattern, search_pattern, search_pattern))
            total = cur_count.fetchone()[0]

            cur = conn.execute("""
                SELECT user_id, username, first_name, numbers_consumed, has_secret_access, joined_at, last_seen
                FROM users
                WHERE CAST(user_id AS TEXT) LIKE ? OR username LIKE ? OR first_name LIKE ?
                ORDER BY numbers_consumed DESC, last_seen DESC
                LIMIT ? OFFSET ?;
            """, (search_pattern, search_pattern, search_pattern, limit, offset))
            rows = [dict(r) for r in cur.fetchall()]
            return rows, total
        else:
            total = conn.execute("SELECT COUNT(*) FROM users;").fetchone()[0]
            cur = conn.execute("""
                SELECT user_id, username, first_name, numbers_consumed, has_secret_access, joined_at, last_seen
                FROM users
                ORDER BY numbers_consumed DESC, last_seen DESC
                LIMIT ? OFFSET ?;
            """, (limit, offset))
            rows = [dict(r) for r in cur.fetchall()]
            return rows, total

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
        get_country_db(cid).close()
        return cid

def get_all_countries_with_stock(only_active: bool = True, secret_mode: bool = False) -> List[Dict[str, Any]]:
    results = []
    with get_main_db() as conn:
        cur = conn.execute("SELECT id, name FROM countries ORDER BY name ASC;")
        countries = cur.fetchall()

    for c in countries:
        cid = c["id"]
        cname = c["name"]
        try:
            with get_country_db(cid) as cconn:
                avail_std = cconn.execute("SELECT COUNT(*) FROM available_numbers WHERE is_secret = 0;").fetchone()[0]
                avail_sec = cconn.execute("SELECT COUNT(*) FROM available_numbers WHERE is_secret = 1;").fetchone()[0]
                used_std  = cconn.execute("SELECT COUNT(*) FROM used_numbers WHERE is_secret = 0;").fetchone()[0]
                used_sec  = cconn.execute("SELECT COUNT(*) FROM used_numbers WHERE is_secret = 1;").fetchone()[0]
        except Exception:
            avail_std, avail_sec, used_std, used_sec = 0, 0, 0, 0

        target_avail = avail_sec if secret_mode else avail_std
        if only_active and target_avail == 0:
            continue

        results.append({
            "id": cid,
            "name": cname,
            "available": target_avail,
            "available_std": avail_std,
            "available_sec": avail_sec,
            "used_std": used_std,
            "used_sec": used_sec,
            "total_available": avail_std + avail_sec,
            "total_used": used_std + used_sec,
            "total": avail_std + avail_sec + used_std + used_sec,
        })
    return results

# ==========================================
# In-Memory Deduplication Cache
# ==========================================
CONSUMED_NUMBERS_CACHE: Set[str] = set()

def load_consumed_cache():
    """Preloads all delivered numbers into memory for instantaneous deduplication."""
    global CONSUMED_NUMBERS_CACHE
    total_loaded = 0
    try:
        with get_main_db() as conn:
            countries = conn.execute("SELECT id FROM countries;").fetchall()
        for c in countries:
            cid = c["id"]
            try:
                with get_country_db(cid) as cconn:
                    used = cconn.execute("SELECT number FROM used_numbers;").fetchall()
                    for r in used:
                        CONSUMED_NUMBERS_CACHE.add(r["number"])
                        total_loaded += 1
            except Exception:
                pass
        logger.info(f"🔒 Deduplication Cache initialized with {total_loaded} previously delivered numbers.")
    except Exception as e:
        logger.warning(f"Could not load consumed cache: {e}")

def add_numbers_to_country(country_id: int, numbers: List[str], is_secret: bool = False) -> Tuple[int, int]:
    """
    Adds numbers with guaranteed '+' prefix to the isolated country database.
    Can be marked as standard (is_secret=0) or secret (is_secret=1).
    """
    added = 0
    duplicates = 0
    secret_val = 1 if is_secret else 0
    with get_country_db(country_id) as conn:
        for raw in numbers:
            num = sanitize_phone_number(raw)
            if not num:
                continue

            # Layer 1: In-memory instant check
            if num in CONSUMED_NUMBERS_CACHE:
                duplicates += 1
                continue

            # Layer 2: SQLite check in used_numbers archive
            already_used = conn.execute("SELECT 1 FROM used_numbers WHERE number = ? LIMIT 1;", (num,)).fetchone()
            if already_used:
                CONSUMED_NUMBERS_CACHE.add(num)
                duplicates += 1
                continue

            # Layer 3: SQLite UNIQUE constraint on available_numbers
            try:
                conn.execute("INSERT INTO available_numbers (number, is_secret) VALUES (?, ?);", (num, secret_val))
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

def consume_numbers_for_user(country_id: int, user_id: int, limit: int = 10, is_secret: bool = False) -> Tuple[List[str], int, str]:
    """
    Atomically retrieves numbers for a user and REMOVES them from available stock.
    Guarantees 100% exclusivity.
    """
    secret_val = 1 if is_secret else 0
    with get_main_db() as mconn:
        c_row = mconn.execute("SELECT name FROM countries WHERE id = ?;", (country_id,)).fetchone()
        country_name = c_row["name"] if c_row else "Unknown"

    with get_country_db(country_id) as cconn:
        cconn.execute("BEGIN IMMEDIATE;")
        cur = cconn.execute("""
            SELECT id, number FROM available_numbers
            WHERE is_secret = ?
            ORDER BY id ASC
            LIMIT ?;
        """, (secret_val, limit))
        rows = cur.fetchall()

        if not rows:
            cconn.commit()
            return [], 0, country_name

        numbers = [r["number"] for r in rows]
        ids = [r["id"] for r in rows]

        cconn.execute(f"DELETE FROM available_numbers WHERE id IN ({','.join(['?']*len(ids))});", ids)
        for num in numbers:
            cconn.execute("INSERT INTO used_numbers (number, user_id, is_secret) VALUES (?, ?, ?);", (num, user_id, secret_val))
            CONSUMED_NUMBERS_CACHE.add(num)
        cconn.commit()

        remaining = cconn.execute("SELECT COUNT(*) FROM available_numbers WHERE is_secret = ?;", (secret_val,)).fetchone()[0]

    try:
        with get_main_db() as mconn:
            mconn.execute("""
                UPDATE users SET numbers_consumed = numbers_consumed + ?, last_seen = CURRENT_TIMESTAMP
                WHERE user_id = ?;
            """, (len(numbers), user_id))
            mconn.execute("""
                INSERT INTO delivery_log (user_id, country_id, number_count, is_secret) VALUES (?, ?, ?, ?);
            """, (user_id, country_id, len(numbers), secret_val))
            mconn.commit()
    except Exception as e:
        logger.warning(f"Error logging delivery: {e}")

    return numbers, remaining, country_name

def delete_country_and_stock(country_id: int) -> bool:
    try:
        with get_main_db() as conn:
            conn.execute("DELETE FROM countries WHERE id = ?;", (country_id,))
            conn.commit()
        c_db_path = os.path.join(STOCKS_DIR, f"country_{country_id}.db")
        if os.path.exists(c_db_path):
            import gc
            gc.collect()
            try:
                os.remove(c_db_path)
            except Exception:
                try:
                    with sqlite3.connect(c_db_path) as cconn:
                        cconn.execute("DELETE FROM available_numbers;")
                        cconn.commit()
                except Exception:
                    pass
        return True
    except Exception as e:
        logger.error(f"Error deleting country {country_id}: {e}")
        return False

def get_system_stats() -> Dict[str, Any]:
    with get_main_db() as mconn:
        total_users = mconn.execute("SELECT COUNT(*) FROM users;").fetchone()[0]
        total_consumed = mconn.execute("SELECT COALESCE(SUM(numbers_consumed), 0) FROM users;").fetchone()[0]
        total_secret_users = mconn.execute("SELECT COUNT(*) FROM users WHERE has_secret_access = 1;").fetchone()[0]

    all_countries = get_all_countries_with_stock(only_active=False)
    total_std_avail = sum(c["available_std"] for c in all_countries)
    total_sec_avail = sum(c["available_sec"] for c in all_countries)
    active_countries_count = sum(1 for c in all_countries if (c["available_std"] + c["available_sec"]) > 0)

    return {
        "total_available": total_std_avail + total_sec_avail,
        "total_std_available": total_std_avail,
        "total_sec_available": total_sec_avail,
        "total_consumed": total_consumed,
        "total_users": total_users,
        "total_secret_users": total_secret_users,
        "total_countries": len(all_countries),
        "active_countries": active_countries_count,
    }



# ==========================================
# OTP Group Link Configuration
# ==========================================
def get_otp_group_link() -> str:
    try:
        with get_main_db() as conn:
            row = conn.execute("SELECT value FROM bot_settings WHERE key = 'otp_group_link';").fetchone()
            if row and row["value"]:
                return row["value"].strip()
    except Exception as e:
        logger.warning(f"Error fetching otp_group_link: {e}")
    return os.getenv("OTP_GROUP_LINK", "").strip()

def set_otp_group_link(link: str) -> bool:
    clean_link = link.strip()
    if clean_link and not clean_link.startswith("http://") and not clean_link.startswith("https://"):
        clean_link = "https://" + clean_link
    try:
        with get_main_db() as conn:
            conn.execute("""
                INSERT INTO bot_settings (key, value)
                VALUES ('otp_group_link', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value;
            """, (clean_link,))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error setting otp_group_link: {e}")
        return False

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
                                "content": json.dumps({"bot": self.bot_name, "countries": {}, "users": [], "updated_at": datetime.now(timezone.utc).isoformat()}, indent=2)
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
            used_data = {}
            with get_main_db() as conn:
                cur = conn.execute("SELECT id, name FROM countries;")
                for c_row in cur.fetchall():
                    cid = c_row["id"]
                    cname = c_row["name"]
                    with get_country_db(cid) as cconn:
                        std_list = [r["number"] for r in cconn.execute("SELECT number FROM available_numbers WHERE is_secret = 0;").fetchall()]
                        sec_list = [r["number"] for r in cconn.execute("SELECT number FROM available_numbers WHERE is_secret = 1;").fetchall()]
                        u_list   = [r["number"] for r in cconn.execute("SELECT number FROM used_numbers;").fetchall()]
                        if std_list or sec_list:
                            countries_data[cname] = {
                                "standard": std_list,
                                "secret": sec_list,
                            }
                        if u_list:
                            used_data[cname] = u_list

                # Export users
                users_cur = conn.execute("SELECT user_id, username, first_name, numbers_consumed, has_secret_access, joined_at FROM users;")
                users_data = [dict(r) for r in users_cur.fetchall()]



            payload = {
                "description": self.description,
                "files": {
                    self.filename: {
                        "content": json.dumps({
                            "bot": self.bot_name,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                            "total_countries": len(countries_data),
                            "countries": countries_data,
                            "used_countries": used_data,
                            "users": users_data,
                            
                        }, indent=2)
                    }
                }
            }
            async with httpx.AsyncClient(timeout=15.0) as http:
                res = await http.patch(self.api_url, headers=self._auth_headers(), json=payload)
                if res.is_success:
                    logger.info("☁️ Database, Users & Numbers backed up to GitHub Gist.")
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
                        used_data = parsed.get("used_countries", {})
                        users_data = parsed.get("users", [])
                        

                        # 0. Restore OTP Group Link
                        saved_group = parsed.get("otp_group_link")
                        if saved_group:
                            set_otp_group_link(saved_group)

                        # 1. Restore Users & Permissions
                        with get_main_db() as mconn:
                            for u in users_data:
                                uid = u.get("user_id")
                                if not uid:
                                    continue
                                mconn.execute("""
                                    INSERT INTO users (user_id, username, first_name, numbers_consumed, has_secret_access, joined_at, last_seen)
                                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                                    ON CONFLICT(user_id) DO UPDATE SET
                                        username = CASE WHEN excluded.username != '' THEN excluded.username ELSE users.username END,
                                        first_name = CASE WHEN excluded.first_name != '' THEN excluded.first_name ELSE users.first_name END,
                                        numbers_consumed = max(users.numbers_consumed, excluded.numbers_consumed),
                                        has_secret_access = excluded.has_secret_access;
                                """, (
                                    uid,
                                    u.get("username", ""),
                                    u.get("first_name", ""),
                                    u.get("numbers_consumed", 0),
                                    u.get("has_secret_access", 0),
                                    u.get("joined_at", datetime.now(timezone.utc).isoformat())
                                ))
                            mconn.commit()



                        # 3. Restore used numbers archive
                        total_used_restored = 0
                        for cname, u_list in used_data.items():
                            cid = get_or_create_country(cname)
                            with get_country_db(cid) as cconn:
                                for unum in u_list:
                                    s_num = sanitize_phone_number(unum)
                                    if s_num:
                                        CONSUMED_NUMBERS_CACHE.add(s_num)
                                        try:
                                            cconn.execute("INSERT OR IGNORE INTO used_numbers (number, user_id) VALUES (?, 0);", (s_num,))
                                            total_used_restored += 1
                                        except Exception:
                                            pass
                                cconn.commit()

                        # 4. Restore available numbers (Standard & Secret)
                        total_std_restored = 0
                        total_sec_restored = 0
                        for cname, c_stock in countries_data.items():
                            cid = get_or_create_country(cname)
                            if isinstance(c_stock, dict):
                                std_nums = c_stock.get("standard", [])
                                sec_nums = c_stock.get("secret", [])
                                if std_nums:
                                    added_std, _ = add_numbers_to_country(cid, std_nums, is_secret=False)
                                    total_std_restored += added_std
                                if sec_nums:
                                    added_sec, _ = add_numbers_to_country(cid, sec_nums, is_secret=True)
                                    total_sec_restored += added_sec
                            elif isinstance(c_stock, list):
                                added, _ = add_numbers_to_country(cid, c_stock, is_secret=False)
                                total_std_restored += added

                        logger.info(
                            f"☁️ Restored {len(users_data)} users, {total_std_restored} standard numbers, "
                            f"{total_sec_restored} secret numbers & {total_used_restored} archived used numbers from GitHub Gist."
                        )
                        return True
        except Exception as e:
            logger.warning(f"Gist restore error: {e}")
        return False

gist_storage = GistStorage(GIST_ID, GIST_TOKEN)

# Admin interactive state management
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
    is_auto_restart = (STARTUP_TYPE == "schedule" or os.getenv("SILENT_STARTUP") == "1")
    if is_auto_restart:
        logger.info("ℹ️ Routine 24-hour restart cycle. Silent startup (no admin notification spam).")
        return

    stats = get_system_stats()
    admin_msg = (
        "🚀 <b>NUMBER BOTMAN ONLINE</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "• <b>Status:</b> <code>Active & Serving Live Numbers ✅</code>\n"
        "• <b>Storage:</b> <code>SQLite WAL + Gist Cloud Backup ☁️</code>\n"
        f"• <b>Standard Stock:</b> <code>{stats['total_std_available']} Numbers</code>\n"
        f"• <b>Secret Stock:</b> <code>{stats['total_sec_available']} Numbers 🔒</code>\n"
        f"• <b>Total Delivered:</b> <code>{stats['total_consumed']} Numbers</code>\n"
        f"• <b>Registered Users:</b> <code>{stats['total_users']} users</code>\n"
        "🔔 <i>Single-use exclusive delivery & secret permission engine ready.</i>\n"
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
    """Builds the main menu keyboard with standard and secret number options."""
    buttons = [
        [InlineKeyboardButton("📱 Get Numbers", callback_data="btn_get_number")],
    ]

    # Display Secret Numbers button if admin or user has whitelisted secret access
    if user_id and user_has_secret_access(user_id):
        buttons.append([InlineKeyboardButton("🔒 Secret Numbers Pool", callback_data="btn_get_secret_number")])

    buttons.append([
        InlineKeyboardButton("📊 Number Inventory", callback_data="btn_inventory"),
        InlineKeyboardButton("ℹ️ Help / Info", callback_data="btn_help")
    ])

    if user_id and is_admin(user_id):
        buttons.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])

    return InlineKeyboardMarkup(buttons)

def get_countries_keyboard(page: int = 0, per_page: int = 8, is_admin_mode: bool = False, is_secret_mode: bool = False) -> InlineKeyboardMarkup:
    countries = get_all_countries_with_stock(only_active=(not is_admin_mode), secret_mode=is_secret_mode)
    if not countries:
        if is_admin_mode:
            return InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Upload Numbers (.txt)", callback_data="admin_upload_prompt")],
                [InlineKeyboardButton("🔒 Upload Secret Numbers (.txt)", callback_data="admin_upload_secret_prompt")],
                [InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_panel")]
            ])
        back_data = "btn_main_menu"
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data=back_data)]
        ])

    start = page * per_page
    end = start + per_page
    current_page_countries = countries[start:end]

    buttons = []
    row = []
    for c in current_page_countries:
        if is_admin_mode:
            prefix = "adm_country_"
            label = f"{c['name']} (S:{c['available_std']} | 🔒:{c['available_sec']})"
        elif is_secret_mode:
            prefix = "sec_c_"
            label = f"🔒 {c['name']} ({c['available']})"
        else:
            prefix = "c_"
            label = f"{c['name']} ({c['available']})"

        row.append(InlineKeyboardButton(label, callback_data=f"{prefix}{c['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    nav_row = []
    page_prefix = "page_adm_" if is_admin_mode else ("page_sec_" if is_secret_mode else "page_")
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ Previous", callback_data=f"{page_prefix}{page-1}"))
    if end < len(countries):
        nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"{page_prefix}{page+1}"))
    if nav_row:
        buttons.append(nav_row)

    back_cb = "admin_panel" if is_admin_mode else "btn_main_menu"
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=back_cb)])
    return InlineKeyboardMarkup(buttons)

def get_numbers_view_keyboard(country_id: int, is_secret: bool = False) -> InlineKeyboardMarkup:
    """Builds number result keyboard with optional Join OTP Group button."""
    change_cb = f"sec_change_num_{country_id}" if is_secret else f"change_num_{country_id}"
    country_cb = "btn_get_secret_number" if is_secret else "btn_get_number"

    buttons = [
        [
            InlineKeyboardButton("🔄 Get 10 More Numbers", callback_data=change_cb),
            InlineKeyboardButton("🌍 Change Country", callback_data=country_cb)
        ],
    ]

    group_link = get_otp_group_link()
    if group_link:
        buttons.append([InlineKeyboardButton("💬 Join OTP Group", url=group_link)])

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

    # Deep-link support
    if context.args:
        arg = context.args[0].strip()
        if arg == "getnumber":
            countries = get_all_countries_with_stock(only_active=True, secret_mode=False)
            if countries:
                await update.message.reply_text(
                    "🌍 <b>Select a Country:</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "<i>Choose the country you want numbers for:</i>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_countries_keyboard(page=0, per_page=8, is_admin_mode=False, is_secret_mode=False)
                )
                return
        elif arg == "secretnumbers" and user_has_secret_access(user.id):
            countries = get_all_countries_with_stock(only_active=True, secret_mode=True)
            if countries:
                await update.message.reply_text(
                    "🔒 <b>Secret Numbers Pool:</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "<i>Select a country to receive exclusive secret numbers:</i>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_countries_keyboard(page=0, per_page=8, is_admin_mode=False, is_secret_mode=True)
                )
                return
        elif arg.startswith("c_"):
            try:
                cid = int(arg.split("_")[1])
                numbers, remaining, cname = consume_numbers_for_user(cid, user.id, limit=10, is_secret=False)
                if numbers:
                    num_lines = [f"  {idx}. <code>{n}</code>" for idx, n in enumerate(numbers, 1)]
                    msg = (
                        f"📱 <b>Your Exclusive Numbers — {cname}</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"⚡ <i>Tap any number below to copy it:</i>\n\n"
                        + "\n".join(num_lines) + "\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 <b>Remaining in Stock:</b> <code>{remaining} numbers</code>\n"
                        f"🔒 <i>All {len(numbers)} numbers are reserved for you and removed from stock.</i>"
                    )
                    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=get_numbers_view_keyboard(cid, is_secret=False))
                    if gist_storage.enabled:
                        asyncio.create_task(gist_storage.export_and_sync())
                    return
            except Exception as e:
                logger.warning(f"Error handling start deep link {arg}: {e}")

    welcome_text = (
        f"👋 <b>Welcome, {user.first_name}!</b>\n\n"
        f"Select an option below to get numbers:"
    )
    keyboard = get_main_menu_keyboard(user.id)
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

async def setgroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    text = update.message.text.replace("/setgroup", "", 1).strip()
    if not text:
        ADMIN_STATES[user.id] = {"awaiting_otp_group_link": True}
        curr = get_otp_group_link()
        curr_msg = f"<b>Current Link:</b> <code>{curr}</code>\n\n" if curr else ""
        await update.message.reply_text(
            f"🔗 <b>Set OTP Group / Channel Link:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{curr_msg}"
            f"Please send your Telegram group link or username in chat:\n"
            f"<code>https://t.me/your_otp_group</code>\n\n"
            f"<i>(Users will see a direct '💬 Join OTP Group' button when receiving numbers).</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]
            ])
        )
        return

    ok = set_otp_group_link(text)
    if ok:
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())
        await update.message.reply_text(
            f"✅ <b>OTP Group Link Updated!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <b>Link:</b> <code>{get_otp_group_link()}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ])
        )
    else:
        await update.message.reply_text("❌ <b>Failed to update group link.</b>", parse_mode=ParseMode.HTML)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("⛔ <b>Access Restricted.</b> This command is not available.", parse_mode=ParseMode.HTML)
        return

    stats = get_system_stats()

    admin_text = (
        f"👑 <b>NUMBER BOTMAN — Admin Management Panel</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Real-time Live Inventory:</b>\n"
        f"• <b>Standard Available:</b> <code>{stats['total_std_available']} numbers</code>\n"
        f"• <b>Secret Available:</b> <code>{stats['total_sec_available']} numbers 🔒</code>\n"
        f"• <b>Total Consumed:</b> <code>{stats['total_consumed']} numbers</code>\n"
        f"• <b>Active Countries:</b> <code>{stats['active_countries']} pools</code>\n"
        f"• <b>Total Users:</b> <code>{stats['total_users']} users</code>\n"
        f"• <b>Secret Whitelisted:</b> <code>{stats['total_secret_users']} users</code>\n"
        f"• <b>Cloud Storage:</b> <code>{'Connected ☁️' if gist_storage.enabled else 'Local SQLite'}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <i>Easily upload .txt numbers for users or secret pools:</i>"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Numbers (.txt)", callback_data="admin_upload_prompt"), InlineKeyboardButton("📁 Uploaded Pools & Stock", callback_data="admin_uploaded_files")],
        [InlineKeyboardButton("👥 User Management & Permissions", callback_data="admin_users"), InlineKeyboardButton("🗑️ Remove Numbers / Files", callback_data="admin_remove_files_menu")],
        [InlineKeyboardButton("🔗 Set OTP Group Link", callback_data="admin_set_group_prompt"), InlineKeyboardButton("☁️ Sync Cloud Backup", callback_data="admin_sync_gist")],
        [InlineKeyboardButton("🏠 Exit Admin Panel", callback_data="btn_main_menu")]
    ])
    await update.message.reply_text(admin_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

async def getnumber_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    register_user(user.id, user.username, user.first_name)
    countries = get_all_countries_with_stock(only_active=True, secret_mode=False)
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
        reply_markup=get_countries_keyboard(page=0, per_page=8, is_admin_mode=False, is_secret_mode=False)
    )

async def secretnumbers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    register_user(user.id, user.username, user.first_name)

    if not user_has_secret_access(user.id):
        await update.message.reply_text(
            "⛔ <b>Access Restricted.</b>\n"
            "Secret numbers are reserved for authorized users only.\n"
            "Please contact the administrator to request access.",
            parse_mode=ParseMode.HTML
        )
        return

    countries = get_all_countries_with_stock(only_active=True, secret_mode=True)
    if not countries:
        await update.message.reply_text(
            "🔒 <b>Secret Numbers Pool</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "<i>No secret numbers currently available in stock.</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")]
            ])
        )
        return

    await update.message.reply_text(
        "🔒 <b>Secret Numbers Pool:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Select a country to receive exclusive secret numbers:</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=get_countries_keyboard(page=0, per_page=8, is_admin_mode=False, is_secret_mode=True)
    )

async def inventory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    register_user(user.id, user.username, user.first_name)
    stats = get_system_stats()
    countries = get_all_countries_with_stock(only_active=True, secret_mode=False)
    c_lines = ""
    for c in countries[:10]:
        c_lines += f"• {c['name']}: <code>{c['available']} available</code>\n"
    if len(countries) > 10:
        c_lines += f"<i>...and {len(countries) - 10} more countries.</i>\n"

    if not c_lines:
        c_lines = "<i>No numbers available in stock right now.</i>\n"

    secret_info = ""
    if user_has_secret_access(user.id):
        secret_info = f"• <b>Secret Stock Available:</b> <code>{stats['total_sec_available']} numbers 🔒</code>\n"

    inv_text = (
        f"📊 <b>Live Number Inventory</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Standard Available:</b> <code>{stats['total_std_available']} numbers</code>\n"
        f"{secret_info}"
        f"• <b>Total Consumed:</b> <code>{stats['total_consumed']} numbers</code>\n"
        f"• <b>Active Countries:</b> <code>{stats['active_countries']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌍 <b>Available Pools:</b>\n"
        f"{c_lines}"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    buttons = [
        [InlineKeyboardButton("📱 Get Numbers Now", callback_data="btn_get_number")],
    ]
    if user_has_secret_access(user.id):
        buttons.append([InlineKeyboardButton("🔒 Secret Numbers", callback_data="btn_get_secret_number")])
    buttons.append([InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")])

    await update.message.reply_text(inv_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    register_user(user.id, user.username, user.first_name)
    help_text = (
        f"ℹ️ <b>How NUMBER BOTMAN Works:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"1️⃣ Use <code>/getnumber</code> or tap <b>'📱 Get Numbers'</b> to choose a country.\n"
        f"2️⃣ Select your country button.\n"
        f"3️⃣ Bot delivers <b>10 copyable numbers</b> (all starting with <code>+</code>).\n"
        f"4️⃣ Tap any number to copy it to clipboard.\n"
        f"5️⃣ Click <b>'🔄 Get 10 More Numbers'</b> to rotate new numbers!\n"
        f"6️⃣ Numbers are exclusive and removed upon issue.\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <i>Fast, reliable, and available 24/7.</i>"
    )
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Get Numbers", callback_data="btn_get_number")],
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
        f"• <b>Standard Available Stock:</b> <code>{stats['total_std_available']} numbers</code>\n"
        f"• <b>Secret Available Stock:</b> <code>{stats['total_sec_available']} numbers 🔒</code>\n"
        f"• <b>Total Numbers Consumed:</b> <code>{stats['total_consumed']} numbers</code>\n"
        f"• <b>Active Countries:</b> <code>{stats['active_countries']}</code>\n"
        f"• <b>Total Users:</b> <code>{stats['total_users']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)

async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        return
    ADMIN_STATES[user.id] = {"mode": "add"}
    await update.message.reply_text(
        "➕ <b>Add Standard Numbers (.txt):</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Please send a <b>.txt</b> file containing phone numbers to this chat.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
        ])
    )

async def secretupload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        return
    ADMIN_STATES[user.id] = {"mode": "add_secret"}
    await update.message.reply_text(
        "🔒 <b>Add Secret Numbers (.txt):</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Please send a <b>.txt</b> file containing secret phone numbers to this chat.\n"
        "<i>These will only be accessible by Admin and Whitelisted users.</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
        ])
    )

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        return
    ADMIN_STATES[user.id] = {"mode": "remove"}
    await update.message.reply_text(
        "🗑️ <b>Remove Numbers (.txt):</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Please send a <b>.txt</b> file containing phone numbers you want to delete from stock.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
        ])
    )

# ── Admin User Management Commands ──
async def grantsecret_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    args = update.message.text.replace("/grantsecret", "", 1).strip()
    if not args or not args.isdigit():
        await update.message.reply_text(
            "Usage: <code>/grantsecret &lt;user_id&gt;</code>\n"
            "Example: <code>/grantsecret 123456789</code>",
            parse_mode=ParseMode.HTML
        )
        return

    target_id = int(args)
    set_user_secret_access(target_id, True)
    if gist_storage.enabled:
        asyncio.create_task(gist_storage.export_and_sync())

    u = get_user_details(target_id)
    uname = f"@{u['username']}" if u and u.get('username') else (u.get('first_name') if u else str(target_id))
    await update.message.reply_text(
        f"🔓 <b>Secret Numbers Access Granted!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User:</b> <code>{uname}</code> (<code>{target_id}</code>)\n"
        f"✅ <b>Status:</b> <code>Authorized to access Secret Numbers Pool</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 View User Details", callback_data=f"u_inspect_{target_id}")],
            [InlineKeyboardButton("👥 User Management", callback_data="admin_users")]
        ])
    )

async def revokesecret_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    args = update.message.text.replace("/revokesecret", "", 1).strip()
    if not args or not args.isdigit():
        await update.message.reply_text(
            "Usage: <code>/revokesecret &lt;user_id&gt;</code>\n"
            "Example: <code>/revokesecret 123456789</code>",
            parse_mode=ParseMode.HTML
        )
        return

    target_id = int(args)
    set_user_secret_access(target_id, False)
    if gist_storage.enabled:
        asyncio.create_task(gist_storage.export_and_sync())

    u = get_user_details(target_id)
    uname = f"@{u['username']}" if u and u.get('username') else (u.get('first_name') if u else str(target_id))
    await update.message.reply_text(
        f"🔒 <b>Secret Numbers Access Revoked!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User:</b> <code>{uname}</code> (<code>{target_id}</code>)\n"
        f"❌ <b>Status:</b> <code>Secret access removed</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 View User Details", callback_data=f"u_inspect_{target_id}")],
            [InlineKeyboardButton("👥 User Management", callback_data="admin_users")]
        ])
    )

async def user_lookup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    args = update.message.text.replace("/user", "", 1).strip()
    if not args or not args.isdigit():
        await update.message.reply_text(
            "Usage: <code>/user &lt;user_id&gt;</code>\n"
            "Example: <code>/user 123456789</code>",
            parse_mode=ParseMode.HTML
        )
        return

    target_id = int(args)
    u = get_user_details(target_id)
    if not u:
        await update.message.reply_text(f"⚠️ User <code>{target_id}</code> not found in database.", parse_mode=ParseMode.HTML)
        return

    secret_badge = "✅ Authorized" if u.get("has_secret_access") else "❌ Restricted"
    toggle_btn_text = "🔒 Revoke Secret Access" if u.get("has_secret_access") else "🔓 Grant Secret Access"

    text = (
        f"👤 <b>User Account Profile</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>User ID:</b> <code>{u['user_id']}</code>\n"
        f"📛 <b>First Name:</b> <code>{u.get('first_name') or 'N/A'}</code>\n"
        f"🔗 <b>Username:</b> @{u.get('username') or 'None'}\n"
        f"🔢 <b>Numbers Consumed:</b> <code>{u.get('numbers_consumed', 0)}</code>\n"
        f"🔒 <b>Secret Numbers Access:</b> <code>{secret_badge}</code>\n"
        f"📅 <b>Registered At:</b> <code>{u.get('joined_at', 'N/A')[:19]}</code>\n"
        f"⏱️ <b>Last Seen:</b> <code>{u.get('last_seen', 'N/A')[:19]}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_btn_text, callback_data=f"u_toggle_sec_{target_id}")],
        [InlineKeyboardButton("👥 Back to Users List", callback_data="admin_users")],
        [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

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
            file_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            file_text = file_bytes.decode("latin-1", errors="ignore")

        lines = file_text.splitlines()
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

        prev_mode = ADMIN_STATES.get(user.id, {}).get("mode", "add")

        ADMIN_STATES[user.id] = {
            "numbers": extracted_numbers,
            "filename": file_name,
            "mode": prev_mode,
        }

        if prev_mode == "remove":
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
            buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_upload")])

            await msg.edit_text(
                f"🗑️ <b>Remove Numbers from Pool:</b>\n"
                f"📄 <b>File:</b> <code>{file_name}</code>\n"
                f"🔢 <b>Numbers:</b> <code>{len(extracted_numbers)}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Select the country pool to remove these numbers from:",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return

        # Upload Flow: Step 1 Select Country
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

        await msg.edit_text(
            f"📄 <b>File Parsed Successfully!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 <b>Filename:</b> <code>{file_name}</code>\n"
            f"🔢 <b>Valid Numbers (with +):</b> <code>{len(extracted_numbers)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌍 <b>Step 1: Choose Country:</b>\n"
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

    if admin_state.get("awaiting_otp_group_link"):
        del ADMIN_STATES[user.id]
        ok = set_otp_group_link(text)
        if ok:
            if gist_storage.enabled:
                asyncio.create_task(gist_storage.export_and_sync())
            await update.message.reply_text(
                f"✅ <b>OTP Group Link Saved Successfully!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔗 <b>Link:</b> <code>{get_otp_group_link()}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
                ])
            )
        else:
            await update.message.reply_text("❌ Failed to save group link.", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ]))
        return

    if admin_state.get("awaiting_country_name"):
        country_name = text
        numbers = admin_state["numbers"]
        filename = admin_state["filename"]
        mode = admin_state.get("mode", "add")

        cid = get_or_create_country(country_name)
        admin_state["awaiting_country_name"] = False
        admin_state["country_id"] = cid
        admin_state["country_name"] = country_name

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
                f"🌍 <b>Country:</b> <code>{country_name}</code>\n"
                f"📄 <b>Source File:</b> <code>{filename}</code>\n"
                f"🗑️ <b>Removed Numbers:</b> <code>{removed}</code>\n"
                f"📊 <b>Remaining Stock:</b> <code>{c_info.get('total_available', 0)}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
                ])
            )
            return

        # Step 2: Choose Stock Pool (Standard or Secret)
        choice_text = (
            f"🌍 <b>Country:</b> <code>{country_name}</code>\n"
            f"📄 <b>File:</b> <code>{filename}</code> (<b>{len(numbers)}</b> numbers)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔒 <b>Step 2: Choose Destination Pool:</b>\n\n"
            f"• <b>Standard Stock:</b> Available for regular users when requesting numbers.\n"
            f"• <b>Secret Stock:</b> Hidden & reserved for Admin + Whitelisted users only.\n\n"
            f"<i>Where would you like to add these numbers?</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 Add to Standard Stock", callback_data=f"apply_stock_std_{cid}")],
            [InlineKeyboardButton("🔒 Add to Secret Stock", callback_data=f"apply_stock_sec_{cid}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_upload")]
        ])
        await update.message.reply_text(choice_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        return

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
            f"👋 <b>Welcome, {user.first_name}!</b>\n\n"
            f"Select an option below to get numbers:"
        )
        await query.edit_message_text(
            welcome_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard(user.id)
        )

    # 2. Get Standard Numbers -> Choose Country
    elif data == "btn_get_number" or data.startswith("page_std_") or (data.startswith("page_") and not data.startswith("page_adm_") and not data.startswith("page_sec_") and not data.startswith("page_users_") and not data.startswith("page_rmfiles_") and not data.startswith("page_upfiles_")):
        page = int(data.split("_")[-1]) if "_" in data and data.split("_")[-1].isdigit() else 0
        countries = get_all_countries_with_stock(only_active=True, secret_mode=False)
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
            reply_markup=get_countries_keyboard(page=page, per_page=8, is_admin_mode=False, is_secret_mode=False)
        )

    # 2b. Get Secret Numbers -> Choose Country
    elif data == "btn_get_secret_number" or data.startswith("page_sec_"):
        if not user_has_secret_access(user.id):
            await query.answer("⛔ Access Denied! Secret numbers are restricted to authorized users.", show_alert=True)
            return

        page = int(data.split("_")[-1]) if "_" in data and data.split("_")[-1].isdigit() else 0
        countries = get_all_countries_with_stock(only_active=True, secret_mode=True)
        if not countries:
            await query.edit_message_text(
                "🔒 <b>Secret Numbers Pool:</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "<i>No secret numbers are currently available in stock.</i>\n\n"
                "Please check back soon or contact admin.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="btn_main_menu")]
                ])
            )
            return

        await query.edit_message_text(
            "🔒 <b>Secret Numbers Pool — Select Country:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Exclusive numbers reserved for authorized accounts:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_countries_keyboard(page=page, per_page=8, is_admin_mode=False, is_secret_mode=True)
        )

    # 3. Deliver Standard Numbers
    elif (data.startswith("c_") and not data.startswith("change_num_") and not data.startswith("cancel_")) or data.startswith("change_num_"):
        country_id = int(data.split("_")[1]) if data.startswith("c_") else int(data.split("_")[2])

        numbers, remaining_count, country_name = consume_numbers_for_user(
            country_id=country_id,
            user_id=user.id,
            limit=10,
            is_secret=False
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

        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())

        num_lines = [f"  {idx}. <code>{n}</code>" for idx, n in enumerate(numbers, 1)]
        numbers_formatted = "\n".join(num_lines)

        group_link = get_otp_group_link()
        group_notice = "\n\n💬 <b>Need OTP codes? Click 'Join OTP Group' below!</b>" if group_link else ""

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
            reply_markup=get_numbers_view_keyboard(country_id, is_secret=False)
        )

    # 3b. Deliver Secret Numbers
    elif data.startswith("sec_c_") or data.startswith("sec_change_num_"):
        if not user_has_secret_access(user.id):
            await query.answer("⛔ Access Denied! Secret numbers are restricted.", show_alert=True)
            return

        country_id = int(data.split("_")[2]) if data.startswith("sec_c_") else int(data.split("_")[3])

        numbers, remaining_count, country_name = consume_numbers_for_user(
            country_id=country_id,
            user_id=user.id,
            limit=10,
            is_secret=True
        )

        if not numbers:
            await query.edit_message_text(
                f"⚠️ <b>No more secret numbers available for {country_name}.</b>\n"
                f"Please select another country from the Secret Pool.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔒 Choose Another Country", callback_data="btn_get_secret_number")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")]
                ])
            )
            return

        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())

        num_lines = [f"  {idx}. <code>{n}</code>" for idx, n in enumerate(numbers, 1)]
        numbers_formatted = "\n".join(num_lines)

        group_link = get_otp_group_link()
        group_notice = "\n\n💬 <b>Need OTP codes? Click 'Join OTP Group' below!</b>" if group_link else ""

        response_text = (
            f"🔒 <b>Your SECRET Numbers — {country_name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{numbers_formatted}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛡️ <i>Exclusive Secret Pool Numbers (100% single-user guaranteed).</i>\n"
            f"📊 <b>Remaining Secret Stock:</b> <code>{remaining_count}</code>\n"
            f"💡 <b>Tap any number to copy instantly!</b>"
            f"{group_notice}"
        )
        await query.edit_message_text(
            response_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_numbers_view_keyboard(country_id, is_secret=True)
        )

    # 4. Inventory Overview
    elif data == "btn_inventory":
        stats = get_system_stats()
        countries = get_all_countries_with_stock(only_active=True, secret_mode=False)
        c_lines = ""
        for c in countries[:10]:
            c_lines += f"• {c['name']}: <code>{c['available']} available</code>\n"
        if len(countries) > 10:
            c_lines += f"<i>...and {len(countries) - 10} more countries.</i>\n"

        if not c_lines:
            c_lines = "<i>No numbers available in stock right now.</i>\n"

        secret_info = ""
        if user_has_secret_access(user.id):
            secret_info = f"• <b>Secret Stock Available:</b> <code>{stats['total_sec_available']} numbers 🔒</code>\n"

        inv_text = (
            f"📊 <b>Live Number Inventory</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Standard Available:</b> <code>{stats['total_std_available']} numbers</code>\n"
            f"{secret_info}"
            f"• <b>Total Consumed:</b> <code>{stats['total_consumed']} numbers</code>\n"
            f"• <b>Active Countries:</b> <code>{stats['active_countries']}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌍 <b>Available Pools:</b>\n"
            f"{c_lines}"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        buttons = [
            [InlineKeyboardButton("📱 Get Numbers Now", callback_data="btn_get_number")],
        ]
        if user_has_secret_access(user.id):
            buttons.append([InlineKeyboardButton("🔒 Secret Numbers Pool", callback_data="btn_get_secret_number")])
        buttons.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="btn_main_menu")])

        await query.edit_message_text(inv_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

    # 5. Help / Info
    elif data == "btn_help":
        help_text = (
            f"ℹ️ <b>How NUMBER BOTMAN Works:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"1️⃣ Click <b>'📱 Get Numbers'</b> to view available countries.\n"
            f"2️⃣ Select your country button.\n"
            f"3️⃣ Bot delivers <b>10 copyable numbers</b> (formatted with <code>+</code>).\n"
            f"4️⃣ Tap any number to copy it to clipboard.\n"
            f"5️⃣ Click <b>'🔄 Get 10 More Numbers'</b> to rotate new numbers!\n"
            f"6️⃣ Numbers are exclusive and removed upon delivery.\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <i>Fast, reliable, and available 24/7.</i>"
        )
        await query.edit_message_text(
            help_text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📱 Get Numbers", callback_data="btn_get_number")],
                [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="btn_main_menu")]
            ])
        )

    # Admin Set OTP Group Prompt
    elif data == "admin_set_group_prompt" and user_admin:
        ADMIN_STATES[user.id] = {"awaiting_otp_group_link": True}
        curr = get_otp_group_link()
        curr_msg = f"<b>Current Link:</b> <code>{curr}</code>\n\n" if curr else ""
        await query.edit_message_text(
            f"🔗 <b>Set / Update OTP Group Link:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{curr_msg}"
            f"Please send your Telegram group link or username into this chat:\n"
            f"<code>https://t.me/your_otp_group</code>\n\n"
            f"<i>(Users will see a direct '💬 Join OTP Group' button when receiving numbers).</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]
            ])
        )

    # 6. Admin Panel
    elif data == "admin_panel" and user_admin:
        stats = get_system_stats()
        admin_text = (
            f"👑 <b>NUMBER BOTMAN — Admin Management Panel</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Real-time Live Inventory:</b>\n"
            f"• <b>Standard Available:</b> <code>{stats['total_std_available']} numbers</code>\n"
            f"• <b>Secret Available:</b> <code>{stats['total_sec_available']} numbers 🔒</code>\n"
            f"• <b>Total Delivered:</b> <code>{stats['total_consumed']} numbers</code>\n"
            f"• <b>Active Countries:</b> <code>{stats['active_countries']} pools</code>\n"
            f"• <b>Registered Users:</b> <code>{stats['total_users']} users</code>\n"
            f"• <b>Secret Whitelisted:</b> <code>{stats['total_secret_users']} users</code>\n"
            f"• <b>Cloud Storage:</b> <code>{'Connected ☁️' if gist_storage.enabled else 'Local SQLite'}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <i>Easily upload .txt numbers for users or secret pools:</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Numbers (.txt)", callback_data="admin_upload_prompt"), InlineKeyboardButton("📁 Uploaded Pools & Stock", callback_data="admin_uploaded_files")],
            [InlineKeyboardButton("👥 User Management & Permissions", callback_data="admin_users"), InlineKeyboardButton("🗑️ Remove Numbers / Files", callback_data="admin_remove_files_menu")],
            [InlineKeyboardButton("🔗 Set OTP Group Link", callback_data="admin_set_group_prompt"), InlineKeyboardButton("☁️ Sync Cloud Backup", callback_data="admin_sync_gist")],
            [InlineKeyboardButton("🏠 Exit Admin Panel", callback_data="btn_main_menu")]
        ])
        await query.edit_message_text(admin_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    # 6b. Admin View Uploaded Number Files & Stock Pools
    elif (data == "admin_uploaded_files" or data.startswith("page_upfiles_")) and user_admin:
        page = int(data.split("_")[2]) if data.startswith("page_upfiles_") else 0
        countries = get_all_countries_with_stock(only_active=False)
        stats = get_system_stats()

        if not countries:
            await query.edit_message_text(
                "📁 <b>Uploaded Number Files & Pools</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "<i>No country pools uploaded yet.</i>\n\n"
                "Upload your first file (.txt) to start serving numbers!",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Upload Numbers (.txt)", callback_data="admin_upload_prompt")],
                    [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]
                ])
            )
            return

        per_page = 6
        start = page * per_page
        end = start + per_page
        page_c = countries[start:end]

        lines = [
            "📁 <b>Uploaded Number Files & Stock Pools</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            f"📊 <b>Total Stock:</b> <code>{stats['total_available']} numbers</code> (Standard: <code>{stats['total_std_available']}</code> | Secret: <code>{stats['total_sec_available']} 🔒</code>)",
            f"👥 <b>Total Delivered:</b> <code>{stats['total_consumed']} numbers</code>",
            "━━━━━━━━━━━━━━━━━━━━"
        ]

        buttons = []
        for c in page_c:
            lines.append(
                f"🌍 <b>{c['name']}</b>\n"
                f"   • Standard Available: <code>{c['available_std']}</code>\n"
                f"   • Secret Available: <code>{c['available_sec']} 🔒</code>\n"
                f"   • Delivered: <code>{c['used_std'] + c['used_sec']}</code>\n"
            )
            buttons.append([InlineKeyboardButton(f"⚙️ Manage {c['name']}", callback_data=f"adm_country_{c['id']}")])

        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ Previous", callback_data=f"page_upfiles_{page-1}"))
        if end < len(countries):
            nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"page_upfiles_{page+1}"))
        if nav_row:
            buttons.append(nav_row)

        buttons.append([InlineKeyboardButton("➕ Add Numbers (.txt)", callback_data="admin_upload_prompt")])
        buttons.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")])

        await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

    # 6c. Admin Remove Files & Numbers Menu
    elif (data == "admin_remove_files_menu" or data.startswith("page_rmfiles_")) and user_admin:
        page = int(data.split("_")[2]) if data.startswith("page_rmfiles_") else 0
        countries = get_all_countries_with_stock(only_active=False)

        if not countries:
            await query.edit_message_text(
                "🗑️ <b>Remove Numbers & Files</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "<i>No country files or numbers available to remove.</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Upload Numbers (.txt)", callback_data="admin_upload_prompt")],
                    [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]
                ])
            )
            return

        per_page = 6
        start = page * per_page
        end = start + per_page
        page_c = countries[start:end]

        lines = [
            "🗑️ <b>Remove Numbers & Country Files</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            "⚡ <b>1-Click Removal:</b>",
            "<i>Click any country button below to delete all its numbers from stock instantly:</i>",
            "━━━━━━━━━━━━━━━━━━━━"
        ]

        buttons = []
        for c in page_c:
            buttons.append([InlineKeyboardButton(f"🗑️ Delete {c['name']} ({c['total_available']} nums)", callback_data=f"adm_quick_del_{c['id']}")])

        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ Previous", callback_data=f"page_rmfiles_{page-1}"))
        if end < len(countries):
            nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"page_rmfiles_{page+1}"))
        if nav_row:
            buttons.append(nav_row)

        buttons.append([InlineKeyboardButton("📄 Remove Specific Numbers (.txt)", callback_data="admin_remove_prompt")])
        buttons.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")] )
        await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

    # 6d. Quick Delete Confirmation
    elif data.startswith("adm_quick_del_") and not data.startswith("adm_quick_del_do_") and user_admin:
        cid = int(data.split("_")[3])
        all_c = get_all_countries_with_stock(only_active=False)
        c_info = next((x for x in all_c if x["id"] == cid), {})
        c_name = c_info.get("name", "Unknown")
        c_avail = c_info.get("total_available", 0)

        text = (
            f"⚠️ <b>Confirm Deletion — {c_name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Are you sure you want to remove <b>{c_name}</b> and delete all <b>{c_avail} numbers</b> from stock?\n\n"
            f"• <i>The country pool will be removed from stock immediately.</i>\n"
            f"• <i>Cloud Gist will synchronize automatically.</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"✅ Yes, Delete {c_name} Numbers", callback_data=f"adm_quick_del_do_{cid}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="admin_remove_files_menu")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    # 6e. Execute Quick Delete
    elif data.startswith("adm_quick_del_do_") and user_admin:
        cid = int(data.split("_")[4])
        all_c = get_all_countries_with_stock(only_active=False)
        c_info = next((x for x in all_c if x["id"] == cid), {})
        c_name = c_info.get("name", "Unknown")
        c_avail = c_info.get("total_available", 0)

        delete_country_and_stock(cid)
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())

        text = (
            f"✅ <b>Successfully Removed!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌍 <b>Country:</b> <code>{c_name}</code>\n"
            f"🗑️ <b>Deleted:</b> <code>{c_avail} numbers removed from stock</code>\n"
            f"☁️ <b>Cloud Status:</b> <code>Synchronized & Updated</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑️ Remove Another File", callback_data="admin_remove_files_menu")],
            [InlineKeyboardButton("📁 Uploaded Files", callback_data="admin_uploaded_files")],
            [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    # 7. Admin Add Numbers Prompt
    elif data == "admin_upload_prompt" and user_admin:
        ADMIN_STATES[user.id] = {"mode": "add"}
        await query.edit_message_text(
            "➕ <b>Add Numbers (.txt):</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Please send a <b>.txt</b> file containing phone numbers directly into this chat.\n\n"
            "<b>Format:</b> One phone number per line.\n"
            "<i>Example:</i>\n"
            "<code>+12025550143\n12025550189\n+12025550192</code>\n\n"
            "🔒 <i>You can assign numbers to <b>Standard Stock</b> (all users) or <b>Secret Stock</b> (whitelisted users only) in Step 2.</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_panel")]
            ])
        )

    # 7b. Admin Add Secret Numbers Prompt
    elif data == "admin_upload_secret_prompt" and user_admin:
        ADMIN_STATES[user.id] = {"mode": "add_secret"}
        await query.edit_message_text(
            "🔒 <b>Add Secret Numbers (.txt):</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Please send a <b>.txt</b> file containing phone numbers for the <b>Secret Numbers Pool</b>.\n\n"
            "• <i>These numbers will only be accessible by Admin and Whitelisted users!</i>\n"
            "• <i>Standard users cannot see or receive these numbers.</i>\n\n"
            "<b>Format:</b> One phone number per line.",
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

    # 9. Admin User Analytics & Management (Paginated User List)
    elif (data == "admin_users" or data.startswith("page_users_")) and user_admin:
        page = int(data.split("_")[2]) if data.startswith("page_users_") else 0
        per_page = 5
        offset = page * per_page
        users_list, total_users = get_all_users_detailed(limit=per_page, offset=offset)
        stats = get_system_stats()

        u_lines = []
        buttons = []

        if not users_list:
            u_lines.append("<i>No registered users found.</i>")
        else:
            for idx, u in enumerate(users_list, start=offset + 1):
                uname = f"@{u['username']}" if u.get("username") else (u.get("first_name") or "No name")
                sec_status = "🔓 Whitelisted" if u.get("has_secret_access") else "🔒 Restricted"
                u_lines.append(
                    f"{idx}. <b>{uname}</b>\n"
                    f"   🆔 <code>{u['user_id']}</code> | 🔢 Consumed: <code>{u['numbers_consumed']}</code>\n"
                    f"   🔒 Secret: <code>{sec_status}</code>\n"
                )
                buttons.append([InlineKeyboardButton(f"👤 Manage ID: {u['user_id']} ({uname[:12]})", callback_data=f"u_inspect_{u['user_id']}")])

        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ Previous", callback_data=f"page_users_{page-1}"))
        if offset + per_page < total_users:
            nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"page_users_{page+1}"))
        if nav_row:
            buttons.append(nav_row)

        buttons.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])

        users_text = (
            f"👥 <b>User Management & Access Control</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Total Users:</b> <code>{stats['total_users']}</code>\n"
            f"• <b>Total Numbers Consumed:</b> <code>{stats['total_consumed']}</code>\n"
            f"• <b>Secret Whitelisted Users:</b> <code>{stats['total_secret_users']}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            + "\n".join(u_lines) +
            f"\n━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>Tip: Click any user button above or use <code>/user &lt;id&gt;</code> to grant/revoke Secret Access!</i>"
        )
        await query.edit_message_text(users_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

    # 9b. User Inspection Profile & 1-Click Secret Access Toggle
    elif data.startswith("u_inspect_") and user_admin:
        target_id = int(data.split("_")[2])
        u = get_user_details(target_id)
        if not u:
            await query.answer("⚠️ User not found in database.", show_alert=True)
            return

        is_whitelisted = bool(u.get("has_secret_access"))
        secret_badge = "✅ Authorized (Whitelisted)" if is_whitelisted else "❌ Restricted"
        toggle_label = "🔒 Revoke Secret Access" if is_whitelisted else "🔓 Grant Secret Access"

        profile_text = (
            f"👤 <b>User Account Details</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>User Account ID:</b> <code>{u['user_id']}</code>\n"
            f"📛 <b>Name:</b> <code>{u.get('first_name') or 'N/A'}</code>\n"
            f"🔗 <b>Username:</b> @{u.get('username') or 'None'}\n"
            f"🔢 <b>Total Numbers Consumed:</b> <code>{u.get('numbers_consumed', 0)}</code> numbers\n"
            f"🔒 <b>Secret Numbers Access:</b> <code>{secret_badge}</code>\n"
            f"📅 <b>Joined Date:</b> <code>{u.get('joined_at', 'N/A')[:19]}</code>\n"
            f"⏱️ <b>Last Activity:</b> <code>{u.get('last_seen', 'N/A')[:19]}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <i>Click below to toggle Secret Numbers permission for this user:</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_label, callback_data=f"u_toggle_sec_{target_id}")],
            [InlineKeyboardButton("👥 Back to Users List", callback_data="admin_users")],
            [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
        ])
        await query.edit_message_text(profile_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    # 9c. Execute Toggle Secret Access
    elif data.startswith("u_toggle_sec_") and user_admin:
        target_id = int(data.split("_")[3])
        u = get_user_details(target_id)
        current_val = bool(u.get("has_secret_access")) if u else False
        new_val = not current_val

        set_user_secret_access(target_id, new_val)
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())

        u_updated = get_user_details(target_id)
        is_whitelisted = bool(u_updated.get("has_secret_access")) if u_updated else new_val
        secret_badge = "✅ Authorized (Whitelisted)" if is_whitelisted else "❌ Restricted"
        toggle_label = "🔒 Revoke Secret Access" if is_whitelisted else "🔓 Grant Secret Access"

        status_alert = "🔓 Secret Access Granted!" if new_val else "🔒 Secret Access Revoked!"
        await query.answer(status_alert, show_alert=True)

        profile_text = (
            f"👤 <b>User Account Details</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>User Account ID:</b> <code>{u_updated['user_id']}</code>\n"
            f"📛 <b>Name:</b> <code>{u_updated.get('first_name') or 'N/A'}</code>\n"
            f"🔗 <b>Username:</b> @{u_updated.get('username') or 'None'}\n"
            f"🔢 <b>Total Numbers Consumed:</b> <code>{u_updated.get('numbers_consumed', 0)}</code> numbers\n"
            f"🔒 <b>Secret Numbers Access:</b> <code>{secret_badge}</code>\n"
            f"📅 <b>Joined Date:</b> <code>{u_updated.get('joined_at', 'N/A')[:19]}</code>\n"
            f"⏱️ <b>Last Activity:</b> <code>{u_updated.get('last_seen', 'N/A')[:19]}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ <i>Permissions updated and saved to persistent database!</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_label, callback_data=f"u_toggle_sec_{target_id}")],
            [InlineKeyboardButton("👥 Back to Users List", callback_data="admin_users")],
            [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
        ])
        await query.edit_message_text(profile_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    # 12. Admin Select Existing Country for Upload / Removal
    elif data.startswith("sel_upload_c_") and user_admin:
        cid = int(data.split("_")[3])
        pending = ADMIN_STATES.get(user.id)
        if not pending or "numbers" not in pending:
            await query.edit_message_text("⚠️ <b>Upload session expired. Please upload your .txt file again.</b>", parse_mode=ParseMode.HTML)
            return

        mode = pending.get("mode", "add")
        numbers = pending["numbers"]
        filename = pending["filename"]

        all_c = get_all_countries_with_stock(only_active=False)
        c_info = next((x for x in all_c if x["id"] == cid), {})
        c_name = c_info.get("name", f"Country {cid}")

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
                f"🌍 <b>Country:</b> <code>{c_name}</code>\n"
                f"📄 <b>File:</b> <code>{filename}</code>\n"
                f"🗑️ <b>Removed Numbers:</b> <code>{removed}</code>\n"
                f"📊 <b>Remaining Stock:</b> <code>{c_info.get('total_available', 0)}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
                ])
            )
            return

        # Step 2: Choose Destination Pool (Standard or Secret)
        pending["country_id"] = cid
        pending["country_name"] = c_name

        text = (
            f"🌍 <b>Country Selected:</b> <code>{c_name}</code>\n"
            f"📄 <b>File:</b> <code>{filename}</code> (<b>{len(numbers)}</b> numbers)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔒 <b>Step 2: Choose Destination Pool:</b>\n\n"
            f"• <b>Standard:</b> Available for anyone requesting numbers.\n"
            f"• <b>Secret:</b> Hidden & reserved for Admin + Whitelisted users only.\n\n"
            f"<i>Where would you like to add these numbers?</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 Add to Standard Stock", callback_data=f"apply_stock_std_{cid}")],
            [InlineKeyboardButton("🔒 Add to Secret Stock", callback_data=f"apply_stock_sec_{cid}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_upload")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    # 12b. Execute Stock Application (Standard or Secret)
    elif (data.startswith("apply_stock_std_") or data.startswith("apply_stock_sec_")) and user_admin:
        is_secret = data.startswith("apply_stock_sec_")
        cid = int(data.split("_")[3])

        pending = ADMIN_STATES.get(user.id)
        if not pending or "numbers" not in pending:
            await query.edit_message_text("⚠️ <b>Upload session expired. Please upload your .txt file again.</b>", parse_mode=ParseMode.HTML)
            return

        numbers = pending["numbers"]
        filename = pending["filename"]
        c_name = pending.get("country_name", f"Country {cid}")

        added, duplicates = add_numbers_to_country(cid, numbers, is_secret=is_secret)
        del ADMIN_STATES[user.id]

        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())

        all_c = get_all_countries_with_stock(only_active=False)
        c_info = next((x for x in all_c if x["id"] == cid), {})
        pool_type = "🔒 Secret Stock" if is_secret else "Standard Stock"
        current_pool_avail = c_info.get("available_sec", added) if is_secret else c_info.get("available_std", added)

        text = (
            f"✅ <b>Upload Successful!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌍 <b>Country:</b> <code>{c_name}</code>\n"
            f"📂 <b>Destination:</b> <code>{pool_type}</code>\n"
            f"📄 <b>Source File:</b> <code>{filename}</code>\n"
            f"➕ <b>Added Numbers (with +):</b> <code>{added}</code>\n"
            f"⚠️ <b>Duplicates Skipped:</b> <code>{duplicates}</code>\n"
            f"📊 <b>Current Available in Pool:</b> <code>{current_pool_avail} numbers</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Upload Another File", callback_data="admin_upload_prompt")],
            [InlineKeyboardButton("📁 View Uploaded Pools", callback_data="admin_uploaded_files")],
            [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

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
                    [InlineKeyboardButton("➕ Upload Numbers (.txt)", callback_data="admin_upload_prompt")],
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
            f"📦 <b>Standard Stock:</b> <code>{c_info.get('available_std', 0)}</code>\n"
            f"🔒 <b>Secret Stock:</b> <code>{c_info.get('available_sec', 0)}</code>\n"
            f"📊 <b>Total Stock:</b> <code>{c_info.get('total_available', 0)}</code>\n"
            f"🔒 <b>Delivered / Used:</b> <code>{c_info.get('total_used', 0)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ 1-Click Delete File & Stock", callback_data=f"adm_quick_del_{cid}")],
                [InlineKeyboardButton("➕ Add Numbers (.txt)", callback_data="admin_upload_prompt")],
                [InlineKeyboardButton("📁 All Uploaded Files", callback_data="admin_uploaded_files")],
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
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
        status_msg = "✅ <b>Database and User permissions backed up to GitHub Gist!</b>" if ok else "❌ <b>Backup to Gist failed.</b> Check logs."
        await query.edit_message_text(
            status_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ])
        )

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

    # Test 2: Database Initialization & Migrations
    try:
        init_db()
        stats = get_system_stats()
        print(f"✅ [PASS] Main Database active: {stats['total_std_available']} standard, {stats['total_sec_available']} secret, {stats['total_consumed']} consumed, {stats['total_users']} users")
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
    app.add_handler(CommandHandler("secretnumbers", secretnumbers_command))
    app.add_handler(CommandHandler("inventory", inventory_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("setgroup", setgroup_command))
    app.add_handler(CommandHandler("upload", upload_command))
    app.add_handler(CommandHandler("secretupload", secretupload_command))
    app.add_handler(CommandHandler("remove", remove_command))
    app.add_handler(CommandHandler("grantsecret", grantsecret_command))
    app.add_handler(CommandHandler("revokesecret", revokesecret_command))
    app.add_handler(CommandHandler("user", user_lookup_command))
    app.add_handler(CommandHandler("users", admin_command))

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
                BotCommand("secretnumbers", "🔒 Secret Numbers Pool"),
                BotCommand("admin", "👑 Open Admin Management Panel"),
                BotCommand("upload", "➕ Add Standard Numbers (.txt)"),
                BotCommand("secretupload", "🔒 Add Secret Numbers (.txt)"),
                BotCommand("remove", "🗑️ Remove Numbers (.txt)"),
                BotCommand("grantsecret", "🔓 Grant Secret Access to user"),
                BotCommand("revokesecret", "🔒 Revoke Secret Access from user"),
                BotCommand("user", "👤 Lookup user details & usage"),
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

    async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
        err = context.error
        if isinstance(err, (NetworkError, TimedOut)):
            logger.warning(f"⚠️ Telegram network glitch (auto-recovering): {err}")
            return
        if isinstance(err, Conflict):
            logger.warning(f"⚠️ Telegram polling conflict (session handover in progress): {err}")
            return
        if isinstance(err, RetryAfter):
            logger.warning(f"⚠️ Telegram rate-limit (RetryAfter {err.retry_after}s): {err}")
            return
        logger.error(f"Unhandled error in update processing: {err}", exc_info=err)

    app.add_error_handler(global_error_handler)

    async def auto_session_handover(application: Application, duration_seconds: int):
        logger.info(f"⏱️ 24-hour scheduled restart timer armed: {duration_seconds}s ({duration_seconds/3600:.1f}h).")
        await asyncio.sleep(duration_seconds)
        logger.info("⏱️ 24-hour scheduled restart time reached. Initiating clean restart...")
        if gist_storage.enabled:
            try:
                await gist_storage.export_and_sync()
                logger.info("☁️ Pre-handover Gist backup completed successfully.")
            except Exception as e:
                logger.warning(f"Pre-handover Gist backup warning: {e}")
        try:
            application.stop_running()
        except Exception as e:
            logger.warning(f"Notice calling stop_running: {e}")

    async def post_init(application: Application):
        if gist_storage.enabled:
            try:
                await gist_storage.ensure_gist()
                await gist_storage.restore_from_gist()
            except Exception as e:
                logger.warning(f"Gist startup sync notice: {e}")
        await setup_bot_commands(application)
        await send_startup_announcement(application)

        is_cloud = bool(STARTUP_TYPE or os.getenv("GITHUB_ACTIONS"))
        session_timeout = int(os.getenv("SESSION_TIMEOUT", "86400"))
        if session_timeout > 0:
            asyncio.create_task(auto_session_handover(application, session_timeout))

    app.post_init = post_init

    logger.info("🚀 NUMBER BOTMAN is running live in multi-user exclusive mode!")
    app.run_polling(drop_pending_updates=False)

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped cleanly.")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"UNHANDLED EXCEPTION in bot main: {e}", exc_info=True)
        sys.exit(2)
