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
import time
import argparse
from typing import Set, Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta

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
try:
    from telegram import CopyTextButton
except ImportError:
    CopyTextButton = None

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

    def _read_env_file(path: str):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
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

    cur_dir = os.path.dirname(os.path.abspath(__file__))
    _read_env_file(os.path.join(cur_dir, ".env"))

    # Also check sibling bot folders for linked OTP provider APIs
    parent_dir = os.path.dirname(cur_dir)
    _read_env_file(os.path.join(parent_dir, "1_THIRDWAVE_BOT", ".env"))
    _read_env_file(os.path.join(parent_dir, "2_OTPMAN_BOT", ".env"))
    _read_env_file(os.path.join(parent_dir, "3_OTPMAN2_BOT", ".env"))

load_environment()

TELEGRAM_BOT_TOKEN     = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
STARTUP_TYPE           = os.getenv("STARTUP_TYPE", "workflow_dispatch").strip().lower()

_admin_raw    = os.getenv("ADMIN_USER_IDS", "").strip()
ADMIN_USER_IDS: List[int] = [int(u.strip()) for u in _admin_raw.split(",") if u.strip().isdigit()]

GIST_ID    = os.getenv("GIST_ID", os.getenv("GITHUB_GIST_ID", "")).strip()
GIST_TOKEN = os.getenv("GIST_TOKEN", os.getenv("GH_TOKEN", os.getenv("GITHUB_TOKEN", ""))).strip()
_is_handover: bool = os.getenv("IS_HANDOVER", "false").strip().lower() in ("true", "1", "yes")
_handover_epoch: float = 0.0
bot_process_start_time: float = time.time()

# Linked OTP APIs for SMS Receiving
THIRDWAVE_API_KEY  = os.getenv("THIRDWAVE_API_KEY", "").strip()
THIRDWAVE_BASE_URL = os.getenv("THIRDWAVE_BASE_URL", "https://thirdwave.cc").rstrip("/")

OTPMAN_API_KEY     = os.getenv("OTPMAN_API_KEY", os.getenv("AUGESTEL_API_KEY", os.getenv("PANEL_API_KEY", ""))).strip()
OTPMAN_BASE_URL    = os.getenv("OTPMAN_BASE_URL", os.getenv("AUGESTEL_BASE_URL", "https://augestel.com")).rstrip("/")

OTPMAN2_API_KEY    = os.getenv("OTPMAN2_API_KEY", os.getenv("KSI_API_KEY", "")).strip()
OTPMAN2_BASE_URL   = os.getenv("OTPMAN2_BASE_URL", os.getenv("KSI_BASE_URL", "https://augestel.com")).rstrip("/")

USER_STATES: Dict[int, Dict[str, Any]] = {}

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
        try:
            conn.execute("ALTER TABLE users ADD COLUMN prefer_plus INTEGER DEFAULT 1;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0;")
        except Exception:
            pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_admins (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER DEFAULT 0,
                username TEXT,
                first_name TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS active_user_numbers (
                number TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                country_name TEXT,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_active_user_numbers_uid ON active_user_numbers(user_id);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_sms_deliveries (
                id TEXT PRIMARY KEY,
                number TEXT,
                user_id INTEGER,
                full_text TEXT,
                raw_json TEXT,
                delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_seen_sms_deliv ON seen_sms_deliveries(delivered_at);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_otps (
                id TEXT PRIMARY KEY,
                provider TEXT,
                country TEXT,
                number TEXT,
                otp_code TEXT,
                raw_message TEXT,
                user_id INTEGER,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_processed_otps_user ON processed_otps(user_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_processed_otps_time ON processed_otps(received_at);")

        try:
            conn.execute("ALTER TABLE seen_sms_deliveries ADD COLUMN full_text TEXT;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE seen_sms_deliveries ADD COLUMN raw_json TEXT;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE delivery_log ADD COLUMN is_secret INTEGER DEFAULT 0;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN user_quantity INTEGER DEFAULT 10;")
        except Exception:
            pass

        conn.commit()
    logger.info("📦 Main Management Database initialized at %s", MAIN_DB_FILE)
    load_consumed_cache()

def register_user(user_id: int, username: str = "", first_name: str = ""):
    try:
        with get_main_db() as conn:
            conn.execute("""
                INSERT INTO users (user_id, username, first_name, numbers_consumed, has_secret_access, prefer_plus, joined_at, last_seen)
                VALUES (?, ?, ?, 0, 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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
            SELECT user_id, username, first_name, numbers_consumed, has_secret_access, prefer_plus, is_admin, joined_at, last_seen
            FROM users WHERE user_id = ?;
        """, (user_id,)).fetchone()
        return dict(row) if row else None

# ==========================================
# Multi-Admin Engine & Number Format Preferences
# ==========================================
def is_admin(user_id: int) -> bool:
    """Strict admin check: checks environment ADMIN_USER_IDS, database bot_admins, and users.is_admin."""
    if not user_id:
        return False
    if ADMIN_USER_IDS and user_id in ADMIN_USER_IDS:
        return True
    try:
        with get_main_db() as conn:
            row = conn.execute("SELECT user_id FROM bot_admins WHERE user_id = ?;", (user_id,)).fetchone()
            if row:
                return True
            urow = conn.execute("SELECT is_admin FROM users WHERE user_id = ?;", (user_id,)).fetchone()
            if urow and urow["is_admin"]:
                return True
    except Exception:
        pass
    return False

def is_user_authorized(user_id: int) -> bool:
    return is_admin(user_id)

def get_all_admin_ids() -> List[int]:
    """Returns all unique admin user IDs from environment and database."""
    admins = set(ADMIN_USER_IDS)
    try:
        with get_main_db() as conn:
            for r in conn.execute("SELECT user_id FROM bot_admins;").fetchall():
                admins.add(r["user_id"])
            for r in conn.execute("SELECT user_id FROM users WHERE is_admin = 1;").fetchall():
                admins.add(r["user_id"])
    except Exception:
        pass
    return list(admins)

def get_all_admin_details() -> List[Dict[str, Any]]:
    """Returns detailed information for all administrators."""
    results = []
    seen = set()
    # 1. Environment Super Admins
    for aid in ADMIN_USER_IDS:
        seen.add(aid)
        u = get_user_details(aid)
        results.append({
            "user_id": aid,
            "username": u.get("username", "") if u else "",
            "first_name": u.get("first_name", "") if u else "Super Admin",
            "is_super": True,
            "added_by": 0,
        })
    # 2. Database Admins
    try:
        with get_main_db() as conn:
            rows = conn.execute("SELECT user_id, added_by, username, first_name FROM bot_admins;").fetchall()
            for r in rows:
                uid = r["user_id"]
                if uid not in seen:
                    seen.add(uid)
                    results.append({
                        "user_id": uid,
                        "username": r["username"] or "",
                        "first_name": r["first_name"] or "Admin",
                        "is_super": False,
                        "added_by": r["added_by"] or 0,
                    })
    except Exception:
        pass
    return results

def add_admin(user_id: int, added_by: int = 0, username: str = "", first_name: str = "") -> bool:
    """Adds a new admin to the database."""
    try:
        with get_main_db() as conn:
            conn.execute("""
                INSERT INTO bot_admins (user_id, added_by, username, first_name)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = CASE WHEN excluded.username != '' THEN excluded.username ELSE bot_admins.username END,
                    first_name = CASE WHEN excluded.first_name != '' THEN excluded.first_name ELSE bot_admins.first_name END;
            """, (user_id, added_by, username or "", first_name or ""))
            conn.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?;", (user_id,))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error adding admin {user_id}: {e}")
        return False

def remove_admin(user_id: int) -> bool:
    """Removes an admin from database (cannot remove env super admins)."""
    if ADMIN_USER_IDS and user_id in ADMIN_USER_IDS:
        return False
    try:
        with get_main_db() as conn:
            conn.execute("DELETE FROM bot_admins WHERE user_id = ?;", (user_id,))
            conn.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?;", (user_id,))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error removing admin {user_id}: {e}")
        return False

def get_user_plus_preference(user_id: int) -> bool:
    """Returns True if user prefers with '+', False if without '+' (default: True)."""
    if not user_id:
        return True
    try:
        with get_main_db() as conn:
            row = conn.execute("SELECT prefer_plus FROM users WHERE user_id = ?;", (user_id,)).fetchone()
            if row and row["prefer_plus"] is not None:
                return bool(row["prefer_plus"])
    except Exception:
        pass
    return True

def set_user_plus_preference(user_id: int, prefer_plus: bool) -> bool:
    """Saves user's preferred number format (with/without '+')."""
    if not user_id:
        return False
    val = 1 if prefer_plus else 0
    try:
        with get_main_db() as conn:
            conn.execute("UPDATE users SET prefer_plus = ? WHERE user_id = ?;", (val, user_id))
            conn.commit()
        return True
    except Exception as e:
        logger.warning(f"Error setting plus preference for {user_id}: {e}")
        return False

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

class UserDeletionResult(dict):
    """Detailed summary of a user permanent purge that evaluates to True if user was found/deleted."""
    def __bool__(self) -> bool:
        return bool(self.get("deleted_user", False)) or bool(self.get("user_existed", False))

def delete_user(user_id: int) -> UserDeletionResult:
    """Permanently purges a user and ALL their data across main DB, active numbers, OTP history, and country stocks."""
    result = UserDeletionResult({
        "user_id": user_id,
        "user_existed": False,
        "deleted_user": False,
        "deleted_active_numbers": 0,
        "deleted_processed_otps": 0,
        "deleted_sms_deliveries": 0,
        "deleted_delivery_logs": 0,
        "deleted_stock_logs": 0,
        "was_admin": False,
    })
    try:
        with get_main_db() as conn:
            u_check = conn.execute("SELECT 1 FROM users WHERE user_id = ? LIMIT 1;", (user_id,)).fetchone()
            if u_check:
                result["user_existed"] = True

            # 1. Clear active assigned numbers for this user
            cur = conn.execute("DELETE FROM active_user_numbers WHERE user_id = ?;", (user_id,))
            result["deleted_active_numbers"] = cur.rowcount

            # 2. Clear processed OTP history for this user
            try:
                cur = conn.execute("DELETE FROM processed_otps WHERE user_id = ?;", (user_id,))
                result["deleted_processed_otps"] = cur.rowcount
            except Exception:
                pass

            # 3. Clear seen SMS deliveries for this user
            try:
                cur = conn.execute("DELETE FROM seen_sms_deliveries WHERE user_id = ?;", (user_id,))
                result["deleted_sms_deliveries"] = cur.rowcount
            except Exception:
                pass

            # 4. Clear delivery log entries
            cur = conn.execute("DELETE FROM delivery_log WHERE user_id = ?;", (user_id,))
            result["deleted_delivery_logs"] = cur.rowcount

            # 5. Clear bot_admins if promoted
            cur = conn.execute("DELETE FROM bot_admins WHERE user_id = ?;", (user_id,))
            if cur.rowcount > 0:
                result["was_admin"] = True

            # 6. Delete user account record
            cur = conn.execute("DELETE FROM users WHERE user_id = ?;", (user_id,))
            result["deleted_user"] = (cur.rowcount > 0)

            conn.commit()

        # 7. Purge user records across all per-country stock databases
        if os.path.exists(STOCKS_DIR):
            for fname in os.listdir(STOCKS_DIR):
                if fname.startswith("country_") and fname.endswith(".db"):
                    c_path = os.path.join(STOCKS_DIR, fname)
                    try:
                        with sqlite3.connect(c_path, timeout=10.0) as cconn:
                            c_cur = cconn.execute("DELETE FROM used_numbers WHERE user_id = ?;", (user_id,))
                            result["deleted_stock_logs"] += max(0, c_cur.rowcount)
                            cconn.commit()
                    except Exception as ce:
                        logger.debug(f"Error purging user {user_id} in {fname}: {ce}")

        # 8. Purge in-memory state
        if user_id in ADMIN_USER_IDS:
            ADMIN_USER_IDS.discard(user_id)
            set_bot_setting("admin_ids", ",".join(map(str, sorted(ADMIN_USER_IDS))))
        ADMIN_STATES.pop(user_id, None)
        USER_STATES.pop(user_id, None)

        logger.info(f"🗑️ User {user_id} permanently purged: {dict(result)}")
        return result
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        return result

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

    register_active_assigned_numbers(numbers, user_id, country_name)

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
# OTP Group Link Configuration (Multi-Tier Persistence)
# ==========================================
def get_otp_group_link() -> str:
    # Tier 1: Check SQLite database
    try:
        with get_main_db() as conn:
            row = conn.execute("SELECT value FROM bot_settings WHERE key = 'otp_group_link';").fetchone()
            if row and row["value"]:
                val = str(row["value"]).strip()
                if val:
                    return val
    except Exception as e:
        logger.warning(f"Error reading otp_group_link from DB: {e}")

    # Tier 2: Check persistent backup text files on disk
    backup_files = [
        os.path.join(STOCKS_DIR, "otp_group_link.txt"),
        os.path.join(BASE_DIR, "otp_group_link.txt"),
    ]
    for b_path in backup_files:
        if os.path.isfile(b_path):
            try:
                with open(b_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().strip()
                if content:
                    # Self-heal SQLite database with recovered link
                    try:
                        with get_main_db() as conn:
                            conn.execute("""
                                INSERT INTO bot_settings (key, value)
                                VALUES ('otp_group_link', ?)
                                ON CONFLICT(key) DO UPDATE SET value = excluded.value;
                            """, (content,))
                            conn.commit()
                            conn.execute("PRAGMA wal_checkpoint(FULL);")
                    except Exception:
                        pass
                    return content
            except Exception as fe:
                logger.warning(f"Notice reading {b_path}: {fe}")

    # Tier 3: Environment variable fallback
    env_link = os.getenv("OTP_GROUP_LINK", "").strip()
    if env_link:
        try:
            with get_main_db() as conn:
                conn.execute("""
                    INSERT INTO bot_settings (key, value)
                    VALUES ('otp_group_link', ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value;
                """, (env_link,))
                conn.commit()
        except Exception:
            pass
        return env_link

    return ""

def set_otp_group_link(link: str) -> bool:
    clean_link = link.strip()
    if clean_link and not clean_link.startswith("http://") and not clean_link.startswith("https://"):
        clean_link = "https://" + clean_link

    success = False

    # 1. Save to SQLite database
    try:
        with get_main_db() as conn:
            conn.execute("""
                INSERT INTO bot_settings (key, value)
                VALUES ('otp_group_link', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value;
            """, (clean_link,))
            conn.commit()
            try:
                conn.execute("PRAGMA wal_checkpoint(FULL);")
            except Exception:
                pass
        success = True
    except Exception as e:
        logger.error(f"Error setting otp_group_link in DB: {e}")

    # 2. Save to persistent text files on disk
    backup_files = [
        os.path.join(STOCKS_DIR, "otp_group_link.txt"),
        os.path.join(BASE_DIR, "otp_group_link.txt"),
    ]
    for b_path in backup_files:
        try:
            with open(b_path, "w", encoding="utf-8") as f:
                f.write(clean_link)
            success = True
        except Exception as fe:
            logger.warning(f"Notice writing link file {b_path}: {fe}")

    # 3. Update memory/environment
    os.environ["OTP_GROUP_LINK"] = clean_link

    # 4. Trigger immediate cloud Gist backup if enabled
    try:
        if "gist_storage" in globals() and gist_storage and gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())
    except Exception:
        pass

    return success

DEFAULT_OTP_GROUP_NAME = "💬 Join Updates Channel"

def get_otp_group_name() -> str:
    # Tier 1: Check SQLite database
    try:
        with get_main_db() as conn:
            row = conn.execute("SELECT value FROM bot_settings WHERE key = 'otp_group_name';").fetchone()
            if row and row["value"]:
                val = str(row["value"]).strip()
                if val:
                    return val
    except Exception as e:
        logger.warning(f"Error reading otp_group_name from DB: {e}")

    # Tier 2: Check persistent backup text files on disk
    backup_files = [
        os.path.join(STOCKS_DIR, "otp_group_name.txt"),
        os.path.join(BASE_DIR, "otp_group_name.txt"),
    ]
    for b_path in backup_files:
        if os.path.isfile(b_path):
            try:
                with open(b_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().strip()
                if content:
                    return content
            except Exception:
                pass

    # Tier 3: Environment variable fallback
    env_name = os.getenv("OTP_GROUP_NAME", "").strip()
    if env_name:
        return env_name

    return DEFAULT_OTP_GROUP_NAME

def set_otp_group_name(name: str) -> bool:
    clean_name = name.strip() or DEFAULT_OTP_GROUP_NAME
    success = False

    # 1. Save to SQLite database
    try:
        with get_main_db() as conn:
            conn.execute("""
                INSERT INTO bot_settings (key, value)
                VALUES ('otp_group_name', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value;
            """, (clean_name,))
            conn.commit()
            try:
                conn.execute("PRAGMA wal_checkpoint(FULL);")
            except Exception:
                pass
        success = True
    except Exception as e:
        logger.error(f"Error setting otp_group_name in DB: {e}")

    # 2. Save to persistent text files on disk
    backup_files = [
        os.path.join(STOCKS_DIR, "otp_group_name.txt"),
        os.path.join(BASE_DIR, "otp_group_name.txt"),
    ]
    for b_path in backup_files:
        try:
            with open(b_path, "w", encoding="utf-8") as f:
                f.write(clean_name)
            success = True
        except Exception as fe:
            logger.warning(f"Notice writing name file {b_path}: {fe}")

    # 3. Update memory/environment
    os.environ["OTP_GROUP_NAME"] = clean_name

    # 4. Trigger immediate cloud Gist backup if enabled
    try:
        if "gist_storage" in globals() and gist_storage and gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())
    except Exception:
        pass

    return success

# ==========================================
# 5b. Dynamic Settings, Bot Name & Quantity Controls
# ==========================================
def get_bot_setting(key: str, default: str = "") -> str:
    try:
        with get_main_db() as conn:
            row = conn.execute("SELECT value FROM bot_settings WHERE key = ?;", (key,)).fetchone()
            if row and row["value"] is not None:
                return str(row["value"]).strip()
    except Exception as e:
        logger.debug(f"Error reading setting {key}: {e}")
    return default

def set_bot_setting(key: str, value: str) -> bool:
    try:
        with get_main_db() as conn:
            conn.execute("""
                INSERT INTO bot_settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value;
            """, (key, str(value).strip()))
            conn.commit()
            try:
                conn.execute("PRAGMA wal_checkpoint(FULL);")
            except Exception:
                pass
        return True
    except Exception as e:
        logger.warning(f"Error saving setting {key}: {e}")
        return False

DEFAULT_BOT_NAME = "NUMBER BOTMAN"

def get_bot_name() -> str:
    val = get_bot_setting("bot_name", DEFAULT_BOT_NAME)
    return val if val else DEFAULT_BOT_NAME

def set_bot_name(name: str) -> bool:
    clean = name.strip()[:64]
    if not clean or clean.lower() in ("default", "reset"):
        clean = DEFAULT_BOT_NAME
    return set_bot_setting("bot_name", clean)

def get_admin_fixed_quantity() -> Optional[int]:
    """Returns fixed quantity if set by admin (1-1000), else None (default mode where users pick 1-10)."""
    val = get_bot_setting("admin_fixed_quantity", "default").strip().lower()
    if val != "default" and val.isdigit():
        q = int(val)
        if 1 <= q <= 1000:
            return q
    return None

def set_admin_fixed_quantity(quantity_val: str) -> bool:
    """Sets admin fixed quantity ('default' or integer string '1'-'1000')."""
    clean = str(quantity_val).strip().lower()
    if clean == "default":
        return set_bot_setting("admin_fixed_quantity", "default")
    if clean.isdigit() and 1 <= int(clean) <= 1000:
        return set_bot_setting("admin_fixed_quantity", str(int(clean)))
    return False

def get_user_quantity_preference(user_id: int) -> int:
    """Returns user's preferred number quantity (1-10, default 10)."""
    if not user_id:
        return 10
    try:
        with get_main_db() as conn:
            row = conn.execute("SELECT user_quantity FROM users WHERE user_id = ?;", (user_id,)).fetchone()
            if row and row["user_quantity"] is not None:
                q = int(row["user_quantity"])
                if 1 <= q <= 10:
                    return q
    except Exception:
        pass
    return 10

def set_user_quantity_preference(user_id: int, qty: int) -> bool:
    """Saves user's preferred number quantity (clamped between 1 and 10)."""
    if not user_id:
        return False
    clamped = max(1, min(10, int(qty)))
    try:
        with get_main_db() as conn:
            conn.execute("UPDATE users SET user_quantity = ? WHERE user_id = ?;", (clamped, user_id))
            conn.commit()
        return True
    except Exception as e:
        logger.warning(f"Error saving user quantity for {user_id}: {e}")
        return False

def get_effective_quantity_for_user(user_id: int) -> Tuple[int, bool]:
    """
    Returns (effective_limit, is_admin_fixed).
    If admin fixed quantity is active (1-1000), returns (fixed_qty, True).
    Otherwise returns (user_qty, False) where user_qty is 1-10.
    """
    fixed = get_admin_fixed_quantity()
    if fixed is not None:
        return fixed, True
    user_pref = get_user_quantity_preference(user_id)
    return user_pref, False

def get_thirdwave_config() -> Tuple[str, str]:
    key = get_bot_setting("api_thirdwave_key", THIRDWAVE_API_KEY).strip()
    url = get_bot_setting("api_thirdwave_url", THIRDWAVE_BASE_URL).strip().rstrip("/")
    return key, url

def set_thirdwave_config(key: Optional[str] = None, url: Optional[str] = None) -> bool:
    if key is not None:
        set_bot_setting("api_thirdwave_key", key.strip())
    if url is not None:
        clean_url = url.strip().rstrip("/")
        if clean_url:
            set_bot_setting("api_thirdwave_url", clean_url)
    return True

def get_augestel_config() -> Tuple[str, str]:
    key = get_bot_setting("api_augestel_key", OTPMAN_API_KEY).strip()
    url = get_bot_setting("api_augestel_url", OTPMAN_BASE_URL).strip().rstrip("/")
    return key, url

def set_augestel_config(key: Optional[str] = None, url: Optional[str] = None) -> bool:
    if key is not None:
        set_bot_setting("api_augestel_key", key.strip())
    if url is not None:
        clean_url = url.strip().rstrip("/")
        if clean_url:
            set_bot_setting("api_augestel_url", clean_url)
    return True

def get_otpman2_config() -> Tuple[str, str]:
    key = get_bot_setting("api_otpman2_key", OTPMAN2_API_KEY).strip()
    url = get_bot_setting("api_otpman2_url", OTPMAN2_BASE_URL).strip().rstrip("/")
    return key, url

def set_otpman2_config(key: Optional[str] = None, url: Optional[str] = None) -> bool:
    if key is not None:
        set_bot_setting("api_otpman2_key", key.strip())
    if url is not None:
        clean_url = url.strip().rstrip("/")
        if clean_url:
            set_bot_setting("api_otpman2_url", clean_url)
    return True

# ==========================================
# 5c. Active Number Tracking & Direct SMS Delivery
# ==========================================
def normalize_phone_number(raw_num: str) -> str:
    """Normalizes phone number to digits only for uniform indexing."""
    if not raw_num:
        return ""
    return re.sub(r"\D", "", str(raw_num))

def register_active_assigned_numbers(numbers: List[str], user_id: int, country_name: str):
    """Indexes numbers delivered to a user in active_user_numbers table for O(1) SMS routing."""
    if not numbers or not user_id:
        return
    try:
        with get_main_db() as conn:
            for num in numbers:
                digits = normalize_phone_number(num)
                if digits:
                    conn.execute("""
                        INSERT INTO active_user_numbers (number, user_id, country_name, assigned_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(number) DO UPDATE SET user_id = excluded.user_id, country_name = excluded.country_name, assigned_at = CURRENT_TIMESTAMP;
                    """, (digits, user_id, country_name))
            conn.commit()
    except Exception as e:
        logger.warning(f"Error indexing active numbers for SMS: {e}")

def find_user_for_phone_number(raw_num: str) -> Optional[Dict[str, Any]]:
    """Checks if incoming SMS recipient number was issued to an active user."""
    digits = normalize_phone_number(raw_num)
    if not digits:
        return None
    try:
        with get_main_db() as conn:
            row = conn.execute("""
                SELECT user_id, country_name, assigned_at FROM active_user_numbers
                WHERE number = ? OR number = ?
                ORDER BY assigned_at DESC LIMIT 1;
            """, (digits, digits.lstrip("0"))).fetchone()
            if row:
                return {
                    "user_id": int(row["user_id"]),
                    "country_name": str(row["country_name"] or ""),
                    "assigned_at": str(row["assigned_at"] or "")
                }
    except Exception as e:
        logger.warning(f"Error looking up phone number {raw_num}: {e}")
    return None

# ==========================================
# 5d. Country ISO, Language & OTP Formatting
# ==========================================
COUNTRY_ISO_DATA: Dict[str, Tuple[str, str]] = {
    # Asia & Middle East
    "sri lanka": ("🇱🇰", "LK"), "lk": ("🇱🇰", "LK"),
    "indonesia": ("🇮🇩", "ID"), "id": ("🇮🇩", "ID"),
    "india":     ("🇮🇳", "IN"), "in": ("🇮🇳", "IN"),
    "bangladesh":("🇧🇩", "BD"), "bd": ("🇧🇩", "BD"),
    "pakistan":  ("🇵🇰", "PK"), "pk": ("🇵🇰", "PK"),
    "vietnam":   ("🇻🇳", "VN"), "vn": ("🇻🇳", "VN"),
    "philippines":("🇵🇭","PH"), "ph": ("🇵🇭", "PH"),
    "thailand":  ("🇹🇭", "TH"), "th": ("🇹🇭", "TH"),
    "malaysia":  ("🇲🇾", "MY"), "my": ("🇲🇾", "MY"),
    "cambodia":  ("🇰🇭", "KH"), "kh": ("🇰🇭", "KH"),
    "myanmar":   ("🇲🇲", "MM"), "mm": ("🇲🇲", "MM"),
    "nepal":     ("🇳🇵", "NP"), "np": ("🇳🇵", "NP"),
    "china":     ("🇨🇳", "CN"), "cn": ("🇨🇳", "CN"),
    "taiwan":    ("🇹🇼", "TW"), "tw": ("🇹🇼", "TW"),
    "japan":     ("🇯🇵", "JP"), "jp": ("🇯🇵", "JP"),
    "south korea":("🇰🇷","KR"), "kr": ("🇰🇷", "KR"),
    "singapore": ("🇸🇬", "SG"), "sg": ("🇸🇬", "SG"),
    "hong kong": ("🇭🇰", "HK"), "hk": ("🇭🇰", "HK"),
    "saudi arabia":("🇸🇦","SA"), "sa": ("🇸🇦", "SA"),
    "uae":       ("🇦🇪", "AE"), "ae": ("🇦🇪", "AE"),
    "turkey":    ("🇹🇷", "TR"), "tr": ("🇹🇷", "TR"),
    "israel":    ("🇮🇱", "IL"), "il": ("🇮🇱", "IL"),
    "iran":      ("🇮🇷", "IR"), "ir": ("🇮🇷", "IR"),
    "iraq":      ("🇮🇶", "IQ"), "iq": ("🇮🇶", "IQ"),
    "qatar":     ("🇶🇦", "QA"), "qa": ("🇶🇦", "QA"),
    "kuwait":    ("🇰🇼", "KW"), "kw": ("🇰🇼", "KW"),
    "oman":      ("🇴🇲", "OM"), "om": ("🇴🇲", "OM"),
    "jordan":    ("🇯🇴", "JO"), "jo": ("🇯🇴", "JO"),
    "lebanon":   ("🇱🇧", "LB"), "lb": ("🇱🇧", "LB"),
    "kazakhstan":("🇰🇿", "KZ"), "kz": ("🇰🇿", "KZ"),
    "uzbekistan":("🇺🇿", "UZ"), "uz": ("🇺🇿", "UZ"),
    # Europe
    "united kingdom":("🇬🇧","GB"), "uk": ("🇬🇧", "GB"), "gb": ("🇬🇧", "GB"),
    "germany":   ("🇩🇪", "DE"), "de": ("🇩🇪", "DE"),
    "france":    ("🇫🇷", "FR"), "fr": ("🇫🇷", "FR"),
    "italy":     ("🇮🇹", "IT"), "it": ("🇮🇹", "IT"),
    "spain":     ("🇪🇸", "ES"), "es": ("🇪🇸", "ES"),
    "netherlands":("🇳🇱","NL"), "nl": ("🇳🇱", "NL"),
    "poland":    ("🇵🇱", "PL"), "pl": ("🇵🇱", "PL"),
    "russia":    ("🇷🇺", "RU"), "ru": ("🇷🇺", "RU"),
    "ukraine":   ("🇺🇦", "UA"), "ua": ("🇺🇦", "UA"),
    "sweden":    ("🇸🇪", "SE"), "se": ("🇸🇪", "SE"),
    "norway":    ("🇳🇴", "NO"), "no": ("🇳🇴", "NO"),
    "denmark":   ("🇩🇰", "DK"), "dk": ("🇩🇰", "DK"),
    "finland":   ("🇫🇮", "FI"), "fi": ("🇫🇮", "FI"),
    "belgium":   ("🇧🇪", "BE"), "be": ("🇧🇪", "BE"),
    "switzerland":("🇨🇭","CH"), "ch": ("🇨🇭", "CH"),
    "austria":   ("🇦🇹", "AT"), "at": ("🇦🇹", "AT"),
    "portugal":  ("🇵🇹", "PT"), "pt": ("🇵🇹", "PT"),
    "greece":    ("🇬🇷", "GR"), "gr": ("🇬🇷", "GR"),
    "czech republic":("🇨🇿","CZ"), "cz": ("🇨🇿", "CZ"),
    "romania":   ("🇷🇴", "RO"), "ro": ("🇷🇴", "RO"),
    "hungary":   ("🇭🇺", "HU"), "hu": ("🇭🇺", "HU"),
    "ireland":   ("🇮🇪", "IE"), "ie": ("🇮🇪", "IE"),
    # Americas
    "united states":("🇺🇸","US"), "usa": ("🇺🇸", "US"), "us": ("🇺🇸", "US"),
    "canada":    ("🇨🇦", "CA"), "ca": ("🇨🇦", "CA"),
    "brazil":    ("🇧🇷", "BR"), "br": ("🇧🇷", "BR"),
    "mexico":    ("🇲🇽", "MX"), "mx": ("🇲🇽", "MX"),
    "argentina": ("🇦🇷", "AR"), "ar": ("🇦🇷", "AR"),
    "colombia":  ("🇨🇴", "CO"), "co": ("🇨🇴", "CO"),
    "chile":     ("🇨🇱", "CL"), "cl": ("🇨🇱", "CL"),
    "peru":      ("🇵🇪", "PE"), "pe": ("🇵🇪", "PE"),
    # Africa
    "nigeria":   ("🇳🇬", "NG"), "ng": ("🇳🇬", "NG"),
    "egypt":     ("🇪🇬", "EG"), "eg": ("🇪🇬", "EG"),
    "south africa":("🇿🇦","ZA"), "za": ("🇿🇦", "ZA"),
    "kenya":     ("🇰🇪", "KE"), "ke": ("🇰🇪", "KE"),
    "ghana":     ("🇬🇭", "GH"), "gh": ("🇬🇭", "GH"),
    "morocco":   ("🇲🇦", "MA"), "ma": ("🇲🇦", "MA"),
    # Oceania
    "australia": ("🇦🇺", "AU"), "au": ("🇦🇺", "AU"),
    "new zealand":("🇳🇿","NZ"), "nz": ("🇳🇿", "NZ"),
}

def extract_otp_code(text: str) -> Optional[str]:
    if not text:
        return None
    cleaned = text.replace("\u200b", "").replace("\xa0", " ").strip()
    kw_match = re.search(
        r"(?:code|otp|pin|passcode|secret|verif\w*|kod\w*|c[oó]digo|clave|is)[:\s\-]+([A-Za-z0-9\-]{3,10})\b",
        cleaned, re.IGNORECASE,
    )
    if kw_match:
        code = kw_match.group(1).strip().replace("-", "").replace("–", "")
        if any(c.isdigit() for c in code) and len(code) >= 3:
            return code
    hyphen_match = re.findall(r"\b\d{3}[-–]\d{3}\b|\b\d{3}[-–]\d{4}\b|\b\d{4}[-–]\d{4}\b", cleaned)
    if hyphen_match:
        return hyphen_match[0].replace("-", "").replace("–", "")
    digits_match = re.findall(r"\b[0-9]{4,8}\b", cleaned)
    if digits_match:
        for d in digits_match:
            if not (len(d) == 4 and d.startswith(("19", "20"))):
                return d
    return None

def detect_sms_language(text: str) -> Tuple[str, str]:
    if not text:
        return ("English", "EN")
    t = text.strip()
    if re.search(r"[\u0600-\u06FF]", t):
        return ("Arabic", "AR")
    if re.search(r"[\u0400-\u04FF]", t):
        return ("Russian", "RU")
    if re.search(r"[\u4E00-\u9FFF]", t):
        return ("Chinese", "ZH")
    if re.search(r"[\u3040-\u30FF]", t):
        return ("Japanese", "JA")
    if re.search(r"[\u0590-\u05FF]", t):
        return ("Hebrew", "HE")
    if re.search(r"[\u0E00-\u0E7F]", t):
        return ("Thai", "TH")
    if re.search(r"[\u0370-\u03FF]", t):
        return ("Greek", "EL")

    low = t.lower()
    if any(w in low for w in ["kodunuz", "doğrulama", "şifre", "giriş", "paylaşmayın", "onay"]):
        return ("Turkish", "TR")
    if any(w in low for w in ["mã", "xác minh", "mật khẩu", "không chia sẻ", "đăng nhập"]):
        return ("Vietnamese", "VI")
    if any(w in low for w in ["código", "codigo", "tu código", "no compartas", "iniciar sesión", "verificación", "clave"]):
        return ("Spanish", "ES")
    if any(w in low for w in ["seu código", "não compartilhe", "senha", "segurança", "verificação"]):
        return ("Portuguese", "PT")
    if any(w in low for w in ["votre code", "ne partagez", "mot de passe", "vérification", "connexion"]):
        return ("French", "FR")
    if any(w in low for w in ["dein code", "ihr code", "bestätigungscode", "verifizierung", "passwort", "nicht weitergeben"]):
        return ("German", "DE")
    if any(w in low for w in ["il tuo codice", "non condividere", "verifica", "accesso"]):
        return ("Italian", "IT")
    if any(w in low for w in ["kode verifikasi", "jangan berikan", "jangan bagikan", "rahasia", "masuk"]):
        return ("Indonesian", "ID")
    if any(w in low for w in ["twój kod", "hasło", "weryfikacyjny", "nie udostępniaj"]):
        return ("Polish", "PL")

    return ("English", "EN")

def get_country_info_from_item(item: Dict[str, Any], country_hint: str = "") -> Tuple[str, str, str]:
    """Returns (flag, country_name, iso)."""
    raw_c = str(country_hint or item.get("country") or item.get("country_code") or item.get("iso") or "").strip().lower()
    if raw_c in COUNTRY_ISO_DATA:
        flag, iso = COUNTRY_ISO_DATA[raw_c]
        cname = country_hint.title() if country_hint else raw_c.title()
        return flag, cname, iso
    for k, (f, i) in COUNTRY_ISO_DATA.items():
        if k in raw_c or raw_c.startswith(k):
            return f, k.title(), i
    for k, flag in COUNTRY_FLAGS.items():
        if k in raw_c:
            return flag, k.title(), k.upper()
    return "🌐", (country_hint or "Global").title(), "XX"

def format_user_otp_notification(item: Dict[str, Any], country_hint: str = "", force_full: Optional[bool] = None, sms_id: str = "") -> Tuple[str, Optional[str], Optional[InlineKeyboardMarkup]]:
    raw_number  = str(item.get("number") or item.get("phone") or item.get("destinationNumber") or item.get("dst") or "")
    formatted_number = sanitize_phone_number(raw_number) or raw_number
    source      = html.escape(str(item.get("source") or item.get("sender") or item.get("caller") or "SMS Service").strip())
    raw_message = str(item.get("message") or item.get("text") or item.get("body") or item.get("messageBody") or "")
    otp_code    = extract_otp_code(raw_message)

    flag, country_name, iso = get_country_info_from_item(item, country_hint=country_hint)
    lang_name, _ = detect_sms_language(raw_message)

    low_source = source.lower()
    low_msg = raw_message.lower()
    wa_keywords = ["whatsapp", "‏واتساب‏", "واتساب", "ватсап", "wa code", "wa.me"]
    is_wa = "whatsapp" in low_source or any(k in low_msg for k in wa_keywords)
    wa_tag = ""
    if is_wa:
        if "whatsapp" not in low_source:
            source = "WhatsApp"
        old_indicators = [
            "new device", "being registered", "dispositivo nuevo", "nuevo dispositivo",
            "novo aparelho", "novo dispositivo", "новом устройстве", "нового устройства",
            "perangkat baru", "neuem gerät", "neuen gerat", "nouvel appareil",
            "nuovo dispositivo", "yeni bir cihaz", "nowym urządzeniu", "nowe urządzenie",
            "جهاز جديد", "دستگاه جدید", "dispositif nouveau",
        ]
        is_old = any(ind in low_msg for ind in old_indicators)
        wa_tag = "OLD" if is_old else "NEW"

    DIVIDER = "━━━━━━━━━━━━━━━━━━━━"

    header = "⚡ <b>NEW SMS RECEIVED</b> ⚡"
    lines = [header, DIVIDER]

    clean_num_disp = str(formatted_number).strip().lstrip("+")
    final_num = f"+{clean_num_disp}" if clean_num_disp else ""

    if final_num:
        lines.append(f"• <b>Number:</b> {flag} <code>{html.escape(final_num)}</code>")
    else:
        lines.append(f"• <b>Country:</b> {flag} <code>{html.escape(country_name)} ({iso})</code>")

    if is_wa and wa_tag:
        lines.append(f"• <b>Service:</b> <code>{source}</code> <b>[{wa_tag}]</b>")
    else:
        lines.append(f"• <b>Service:</b> <code>{source}</code>")

    if final_num:
        lines.append(f"• <b>Country:</b> <code>{html.escape(country_name)} ({iso})</code>")
    lines.append(f"• <b>Language:</b> <code>{lang_name}</code>")

    sms_view_mode = get_bot_setting("sms_view_mode", "default")
    should_show_full = (force_full is True) or (force_full is None and sms_view_mode == "full")

    if should_show_full and raw_message:
        lines.append(DIVIDER)
        lines.append("📜 <b>Full Message:</b>")
        lines.append(f"<code>{html.escape(raw_message)}</code>")

    lines.append(DIVIDER)
    text = "\n".join(lines)

    buttons = []
    if otp_code:
        if CopyTextButton:
            buttons.append([InlineKeyboardButton(otp_code, copy_text=CopyTextButton(text=otp_code))])
        else:
            buttons.append([InlineKeyboardButton(f"📋 {otp_code}", callback_data=f"otp_copy_{otp_code}")])

    if sms_id:
        if should_show_full:
            if sms_view_mode == "default":
                buttons.append([InlineKeyboardButton("🔙 Collapse SMS", callback_data=f"collapse_sms_{sms_id}")])
        else:
            if sms_view_mode == "default":
                buttons.append([InlineKeyboardButton("📜 Full SMS", callback_data=f"view_full_sms_{sms_id}")])

    group_link = get_otp_group_link()
    if group_link:
        buttons.append([InlineKeyboardButton(get_otp_group_name(), url=group_link)])

    markup = InlineKeyboardMarkup(buttons) if buttons else None
    return text, otp_code, markup

# ==========================================
# 5e. Multi-Provider API Engine & Live Polling
# ==========================================
SEEN_SMS_CACHE: Set[str] = set()
SEEN_SMS_TIMESTAMPS: Dict[str, float] = {}

def is_sms_processed(sms_id: str) -> bool:
    if not sms_id:
        return False
    if sms_id in SEEN_SMS_CACHE:
        return True
    try:
        with get_main_db() as conn:
            row = conn.execute("SELECT 1 FROM seen_sms_deliveries WHERE id = ? LIMIT 1;", (sms_id,)).fetchone()
            if row:
                SEEN_SMS_CACHE.add(sms_id)
                SEEN_SMS_TIMESTAMPS[sms_id] = time.time()
                return True
    except Exception:
        pass
    return False

def mark_sms_processed(sms_id: str, number: str = "", user_id: int = 0, full_text: str = "", raw_json: str = ""):
    if not sms_id:
        return
    SEEN_SMS_CACHE.add(sms_id)
    SEEN_SMS_TIMESTAMPS[sms_id] = time.time()
    try:
        with get_main_db() as conn:
            conn.execute("""
                INSERT INTO seen_sms_deliveries (id, number, user_id, full_text, raw_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    number = excluded.number,
                    user_id = excluded.user_id,
                    full_text = CASE WHEN excluded.full_text != '' THEN excluded.full_text ELSE seen_sms_deliveries.full_text END,
                    raw_json = CASE WHEN excluded.raw_json != '' THEN excluded.raw_json ELSE seen_sms_deliveries.raw_json END;
            """, (sms_id, number, user_id, full_text, raw_json))
            conn.commit()
    except Exception as e:
        logger.debug(f"Error marking sms processed: {e}")

def record_processed_otp(
    sms_id: str,
    provider: str,
    country: str,
    number: str,
    otp_code: str,
    raw_message: str,
    user_id: int = 0
):
    """Persistently logs received OTP into processed_otps table like OTP bots."""
    if not sms_id:
        return
    try:
        with get_main_db() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO processed_otps
                    (id, provider, country, number, otp_code, raw_message, user_id, received_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """, (sms_id, provider, country, number, otp_code, raw_message, user_id))
            conn.commit()
    except Exception as e:
        logger.debug(f"DB save error for processed OTP: {e}")

def cleanup_28h_otp_records():
    """Purges OTP messages and seen deliveries older than 28 hours (like OTP bots)."""
    try:
        with get_main_db() as conn:
            c1 = conn.execute("DELETE FROM processed_otps WHERE received_at < datetime('now', '-28 hours');")
            c2 = conn.execute("DELETE FROM seen_sms_deliveries WHERE delivered_at < datetime('now', '-28 hours');")
            conn.commit()
            logger.info(f"🧹 Pruned 28h history: {c1.rowcount} OTP records, {c2.rowcount} SMS delivery records.")
    except Exception as e:
        logger.warning(f"Error running 28h OTP database cleanup: {e}")

async def periodic_db_cleanup_loop():
    """Periodic background maintenance loop running every 30m to enforce 28h retention like OTP bots."""
    while True:
        await asyncio.sleep(1800)  # every 30m
        try:
            cleanup_28h_otp_records()
            cutoff = time.time() - (28 * 3600)
            stale_keys = [k for k, v in SEEN_SMS_TIMESTAMPS.items() if v < cutoff]
            for k in stale_keys:
                SEEN_SMS_TIMESTAMPS.pop(k, None)
                SEEN_SMS_CACHE.discard(k)
        except Exception as e:
            logger.warning(f"Periodic 28h cleanup error: {e}")

async def ping_provider_test(key: str, url: str, provider: str) -> Tuple[bool, str]:
    """Instantly pings a provider endpoint to test authentication, reachability, and latency."""
    clean_key = (key or "").strip()
    clean_url = (url or "").rstrip("/")
    if not clean_key or not clean_url:
        return False, "❌ API Key or Base URL is missing."

    prov = provider.lower()
    endpoint = f"{clean_url}/api/v1/traffic" if prov in ("thirdwave", "tw") else f"{clean_url}/api/v1/iprn/messages"
    params = {"page": 1, "pageSize": 1} if prov in ("thirdwave", "tw") else {"per_page": 1}

    try:
        t0 = time.time()
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.get(
                endpoint,
                headers={"Authorization": f"Bearer {clean_key}", "Accept": "application/json"},
                params=params
            )
            elapsed = int((time.time() - t0) * 1000)
            if res.is_success:
                return True, f"✅ Connected successfully (HTTP 200 OK, {elapsed}ms)!"
            elif res.status_code in (401, 403):
                return False, f"❌ Unauthorized (HTTP {res.status_code}, {elapsed}ms) - Invalid API Key."
            elif res.status_code == 404:
                return False, f"❌ Not Found (HTTP 404, {elapsed}ms) - Invalid Base URL."
            else:
                return False, f"⚠️ HTTP {res.status_code} ({elapsed}ms): {res.text[:80]}"
    except httpx.ConnectTimeout:
        return False, "❌ Connection timed out after 8s."
    except httpx.ConnectError:
        return False, "❌ Failed to connect (hostname/network unreachable)."
    except Exception as e:
        return False, f"❌ Ping error: {type(e).__name__} ({e})"


async def fetch_thirdwave_incoming() -> List[Dict[str, Any]]:
    key, url = get_thirdwave_config()
    if not key:
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                f"{url}/api/v1/traffic",
                headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
                params={"page": 1, "pageSize": 50}
            )
            if res.is_success:
                data = res.json()
                rows = data.get("rows") if isinstance(data, dict) else (data if isinstance(data, list) else [])
                return [r for r in rows if isinstance(r, dict)]
    except Exception as e:
        logger.debug(f"Thirdwave fetch notice: {e}")
    return []

async def fetch_augestel_incoming() -> List[Dict[str, Any]]:
    key, url = get_augestel_config()
    if not key:
        return []
    try:
        start_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                f"{url}/api/v1/iprn/messages",
                headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
                params={"per_page": 100, "start_date": start_date}
            )
            if res.is_success:
                data = res.json()
                items = data.get("data") if isinstance(data, dict) and "data" in data else (
                    data.get("rows") if isinstance(data, dict) and "rows" in data else (
                        data if isinstance(data, list) else []
                    )
                )
                return [r for r in items if isinstance(r, dict)]
    except Exception as e:
        logger.debug(f"Augestel fetch notice: {e}")
    return []

async def fetch_otpman2_incoming() -> List[Dict[str, Any]]:
    key, url = get_otpman2_config()
    if not key:
        return []
    try:
        now = datetime.now(timezone.utc)
        start_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                f"{url}/api/v1/iprn/messages",
                headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
                params={"per_page": 100, "start_date": start_date}
            )
            if res.is_success:
                data = res.json()
                items = data.get("data") if isinstance(data, dict) and "data" in data else (
                    data.get("rows") if isinstance(data, dict) and "rows" in data else (
                        data if isinstance(data, list) else []
                    )
                )
                return [r for r in items if isinstance(r, dict)]
    except Exception as e:
        logger.debug(f"OTPMan2 fetch notice: {e}")
    return []

async def sms_polling_worker(application: Application):
    """
    Continuous background loop that polls all enabled OTP provider APIs,
    matches incoming SMS against active_user_numbers,
    and forwards OTP messages directly to the users who got those numbers.
    """
    logger.info("📡 Live Multi-API SMS Polling Engine started for Number Bot.")
    await asyncio.sleep(5.0)
    while True:
        try:
            if get_bot_setting("sms_receiving_enabled", "1") != "1":
                await asyncio.sleep(8.0)
                continue

            tw_key, _ = get_thirdwave_config()
            aug_key, _ = get_augestel_config()
            ksi_key, _ = get_otpman2_config()

            tasks = []
            if get_bot_setting("api_thirdwave_enabled", "1") == "1" and tw_key:
                tasks.append(("Thirdwave", fetch_thirdwave_incoming()))
            if get_bot_setting("api_augestel_enabled", "1") == "1" and aug_key:
                tasks.append(("Augestel", fetch_augestel_incoming()))
            if get_bot_setting("api_otpman2_enabled", "1") == "1" and ksi_key:
                tasks.append(("OTPMan2", fetch_otpman2_incoming()))

            for provider_name, coro in tasks:
                try:
                    items = await coro
                    for item in items:
                        sms_id = str(item.get("id") or item.get("message_id") or "")
                        if not sms_id:
                            sms_id = f"{item.get('number')}_{item.get('message')}_{item.get('received_at')}"
                        if is_sms_processed(sms_id):
                            continue

                        raw_msg = str(item.get("message") or item.get("text") or item.get("body") or item.get("messageBody") or "")
                        item_json = json.dumps(item)
                        raw_num = str(item.get("number") or item.get("phone") or item.get("destinationNumber") or item.get("dst") or "")
                        user_info = find_user_for_phone_number(raw_num)
                        if user_info:
                            user_id = user_info["user_id"]
                            c_hint  = user_info.get("country_name", "")
                            text, otp, markup = format_user_otp_notification(item, country_hint=c_hint, sms_id=sms_id)
                            sent = await send_with_retry(application.bot, user_id, text, reply_markup=markup)
                            if sent:
                                logger.info(f"📨 Live OTP forwarded to user {user_id} for number {raw_num} ({provider_name})")
                                mark_sms_processed(sms_id, number=raw_num, user_id=user_id, full_text=raw_msg, raw_json=item_json)
                                record_processed_otp(
                                    sms_id=sms_id,
                                    provider=provider_name,
                                    country=c_hint,
                                    number=raw_num,
                                    otp_code=otp or "",
                                    raw_message=raw_msg,
                                    user_id=user_id
                                )
                        else:
                            mark_sms_processed(sms_id, number=raw_num, user_id=0, full_text=raw_msg, raw_json=item_json)
                            record_processed_otp(
                                sms_id=sms_id,
                                provider=provider_name,
                                country="",
                                number=raw_num,
                                otp_code="",
                                raw_message=raw_msg,
                                user_id=0
                            )
                except Exception as pe:
                    logger.debug(f"Provider {provider_name} cycle notice: {pe}")

        except Exception as e:
            logger.warning(f"SMS Polling worker loop exception: {e}")

        await asyncio.sleep(6.0)

async def check_all_connected_apis_status() -> Dict[str, Any]:
    """Tests connection, latency, and operational health for all 3 linked OTP provider APIs."""
    results = {}

    # 1. Thirdwave
    tw_key, tw_url = get_thirdwave_config()
    tw_enabled = (get_bot_setting("api_thirdwave_enabled", "1") == "1")
    if not tw_key:
        results["thirdwave"] = {"status": "⚠️ Not Configured (API Key Missing)", "ok": False, "enabled": tw_enabled, "url": tw_url}
    elif not tw_enabled:
        results["thirdwave"] = {"status": "⏸️ Disabled by Admin", "ok": True, "enabled": False, "url": tw_url}
    else:
        try:
            t0 = time.time()
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.get(
                    f"{tw_url}/api/v1/traffic",
                    headers={"Authorization": f"Bearer {tw_key}", "Accept": "application/json"},
                    params={"page": 1, "pageSize": 1}
                )
                elapsed = int((time.time() - t0) * 1000)
                if res.is_success:
                    results["thirdwave"] = {"status": f"✅ Online (200 OK, {elapsed}ms)", "ok": True, "enabled": True, "url": tw_url, "key": f"••••{tw_key[-4:]}"}
                else:
                    results["thirdwave"] = {"status": f"❌ Error (HTTP {res.status_code}, {elapsed}ms)", "ok": False, "enabled": True, "url": tw_url}
        except Exception as e:
            results["thirdwave"] = {"status": f"❌ Offline ({type(e).__name__})", "ok": False, "enabled": True, "url": tw_url}

    # 2. Augestel / OTPMan
    aug_key, aug_url = get_augestel_config()
    aug_enabled = (get_bot_setting("api_augestel_enabled", "1") == "1")
    if not aug_key:
        results["augestel"] = {"status": "⚠️ Not Configured (API Key Missing)", "ok": False, "enabled": aug_enabled, "url": aug_url}
    elif not aug_enabled:
        results["augestel"] = {"status": "⏸️ Disabled by Admin", "ok": True, "enabled": False, "url": aug_url}
    else:
        try:
            t0 = time.time()
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.get(
                    f"{aug_url}/api/v1/iprn/messages",
                    headers={"Authorization": f"Bearer {aug_key}", "Accept": "application/json"},
                    params={"per_page": 1}
                )
                elapsed = int((time.time() - t0) * 1000)
                if res.is_success:
                    results["augestel"] = {"status": f"✅ Online (200 OK, {elapsed}ms)", "ok": True, "enabled": True, "url": aug_url, "key": f"••••{aug_key[-4:]}"}
                else:
                    results["augestel"] = {"status": f"❌ Error (HTTP {res.status_code}, {elapsed}ms)", "ok": False, "enabled": True, "url": aug_url}
        except Exception as e:
            results["augestel"] = {"status": f"❌ Offline ({type(e).__name__})", "ok": False, "enabled": True, "url": aug_url}

    # 3. KSI / OTPMan2
    ksi_key, ksi_url = get_otpman2_config()
    ksi_enabled = (get_bot_setting("api_otpman2_enabled", "1") == "1")
    if not ksi_key:
        results["otpman2"] = {"status": "⚠️ Not Configured (API Key Missing)", "ok": False, "enabled": ksi_enabled, "url": ksi_url}
    elif not ksi_enabled:
        results["otpman2"] = {"status": "⏸️ Disabled by Admin", "ok": True, "enabled": False, "url": ksi_url}
    else:
        try:
            t0 = time.time()
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.get(
                    f"{ksi_url}/api/v1/iprn/messages",
                    headers={"Authorization": f"Bearer {ksi_key}", "Accept": "application/json"},
                    params={"per_page": 1}
                )
                elapsed = int((time.time() - t0) * 1000)
                if res.is_success:
                    results["otpman2"] = {"status": f"✅ Online (200 OK, {elapsed}ms)", "ok": True, "enabled": True, "url": ksi_url, "key": f"••••{ksi_key[-4:]}"}
                else:
                    results["otpman2"] = {"status": f"❌ Error (HTTP {res.status_code}, {elapsed}ms)", "ok": False, "enabled": True, "url": ksi_url}
        except Exception as e:
            results["otpman2"] = {"status": f"❌ Offline ({type(e).__name__})", "ok": False, "enabled": True, "url": ksi_url}

    with get_main_db() as conn:
        active_numbers_count = conn.execute("SELECT COUNT(DISTINCT user_id) FROM active_user_numbers;").fetchone()[0]
        total_delivered_count = conn.execute("SELECT COUNT(*) FROM seen_sms_deliveries WHERE user_id > 0;").fetchone()[0]

    results["active_users"] = active_numbers_count
    results["total_delivered"] = total_delivered_count
    results["sms_forwarding"] = (get_bot_setting("sms_receiving_enabled", "1") == "1")
    results["view_mode"] = get_bot_setting("sms_view_mode", "default")
    return results

def format_api_status_report(status_data: Dict[str, Any]) -> str:
    tw  = status_data.get("thirdwave", {})
    aug = status_data.get("augestel", {})
    ksi = status_data.get("otpman2", {})

    mode = status_data.get("view_mode", "default")
    mode_label = "📜 Default (With Full SMS Button)" if mode == "default" else ("📄 Fixed Always Full" if mode == "full" else "📦 Fixed Short Only")
    master_sms = "✅ Active (Forwarding ON)" if status_data.get("sms_forwarding") else "❌ Disabled (Forwarding OFF)"

    return (
        "📡 <b>Connected OTP Bots & API Status</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🌐 <b>1. Thirdwave OTP API</b>\n"
        f"• <b>Status:</b> {tw.get('status', 'Unknown')}\n"
        f"• <b>Base URL:</b> <code>{tw.get('url', 'N/A')}</code>\n\n"
        "🌐 <b>2. Augestel / OTPMan API</b>\n"
        f"• <b>Status:</b> {aug.get('status', 'Unknown')}\n"
        f"• <b>Base URL:</b> <code>{aug.get('url', 'N/A')}</code>\n\n"
        "🌐 <b>3. KSI / OTPMan2 API</b>\n"
        f"• <b>Status:</b> {ksi.get('status', 'Unknown')}\n"
        f"• <b>Base URL:</b> <code>{ksi.get('url', 'N/A')}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📊 <b>SMS Forwarding Engine:</b>\n"
        f"• <b>Master Forwarder:</b> {master_sms}\n"
        f"• <b>Recipients Tracked:</b> <code>{status_data.get('active_users', 0)} active users</code>\n"
        f"• <b>Total SMS Delivered:</b> <code>{status_data.get('total_delivered', 0)} forwarded</code>\n"
        f"• <b>SMS View Format:</b> <code>{mode_label}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ <i>Tap 'Test & Ping APIs Now' to run a live connection check across all 3 providers.</i>"
    )

def get_admin_api_status_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Test & Ping APIs Now", callback_data="admin_otp_status_refresh")],
        [InlineKeyboardButton("⚙️ SMS Forwarding Controls", callback_data="admin_sms_menu")],
        [InlineKeyboardButton("👑 Back to Admin Panel", callback_data="admin_panel")]
    ])

# ==========================================
# 6. Gist Persistent Storage Sync
# ==========================================
GIST_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

class GistStorage:
    def __init__(self, gist_id: str, token: str, filename: str = "number_botman_data.json",
                 description: str = "Number Botman — Persistent Cloud Backup (Auto-Managed)"):
        self.gist_id = gist_id or get_bot_setting("gist_id", "")
        self.token = token
        self.filename = filename
        self.description = description
        self.bot_name = "NUMBER_BOTMAN"
        self.enabled = bool(token)
        self.api_url = f"https://api.github.com/gists/{self.gist_id}" if self.gist_id else ""

    def _auth_headers(self) -> Dict[str, str]:
        return {**GIST_HEADERS, "Authorization": f"Bearer {self.token}"}

    async def ensure_gist(self) -> bool:
        """Finds existing Gist matching filename, deletes any duplicate Gists, or creates a new one automatically."""
        if not self.token:
            return False
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                # 0. If gist_id is already set, verify it exists and is accessible
                if self.gist_id:
                    check_res = await http.get(f"https://api.github.com/gists/{self.gist_id}", headers=self._auth_headers())
                    if check_res.is_success:
                        self.api_url = f"https://api.github.com/gists/{self.gist_id}"
                        return True
                    elif check_res.status_code == 404:
                        logger.warning(f"Configured Gist ID {self.gist_id} not found on GitHub (404). Searching/creating new Gist...")
                        self.gist_id = ""
                        self.api_url = ""

                # 1. Search existing Gists matching filename to reuse and delete duplicate leftovers
                res = await http.get("https://api.github.com/gists?per_page=100", headers=self._auth_headers())
                if res.is_success:
                    gists = res.json()
                    matching = [g for g in gists if self.filename in g.get("files", {})]
                    if matching:
                        primary = matching[0]
                        self.gist_id = primary.get("id", "")
                        self.api_url = f"https://api.github.com/gists/{self.gist_id}"
                        set_bot_setting("gist_id", self.gist_id)
                        logger.info(f"☁️ Reusing existing GitHub Gist: {self.gist_id}")

                        # Automatically delete duplicate leftover Gists
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

                # 2. No matching Gist exists -> create a brand new private Gist
                res = await http.post(
                    "https://api.github.com/gists",
                    headers=self._auth_headers(),
                    json={
                        "description": self.description,
                        "public": False,
                        "files": {
                            self.filename: {
                                "content": json.dumps({
                                    "bot": self.bot_name,
                                    "countries": {},
                                    "users": [],
                                    "admins": [],
                                    "active_numbers": [],
                                    "seen_sms": {},
                                    "updated_at": datetime.now(timezone.utc).isoformat()
                                }, indent=2)
                            }
                        }
                    }
                )
                if res.is_success:
                    self.gist_id = res.json().get("id", "")
                    self.api_url = f"https://api.github.com/gists/{self.gist_id}"
                    set_bot_setting("gist_id", self.gist_id)
                    logger.info(f"☁️ Created new GitHub Gist automatically: {self.gist_id}")
                    return True
                else:
                    logger.warning(f"Gist auto-create failed (HTTP {res.status_code}): {res.text[:120]}")
        except Exception as e:
            logger.warning(f"Gist auto-discovery error: {e}")
        return False

    async def export_and_sync(self, is_handover: bool = False) -> bool:
        """Prunes 28h history and syncs full database, numbers, settings, and active users to GitHub Gist."""
        if not self.enabled:
            return False
        if not self.api_url:
            await self.ensure_gist()
        if not self.api_url:
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
                users_cur = conn.execute("SELECT user_id, username, first_name, numbers_consumed, has_secret_access, prefer_plus, is_admin, user_quantity, joined_at FROM users;")
                users_data = [dict(r) for r in users_cur.fetchall()]

                # Export dynamic database administrators
                admins_cur = conn.execute("SELECT user_id, added_by, username, first_name FROM bot_admins;")
                admins_data = [dict(r) for r in admins_cur.fetchall()]

                # Export bot_settings
                settings_cur = conn.execute("SELECT key, value FROM bot_settings;")
                settings_data = {r["key"]: r["value"] for r in settings_cur.fetchall()}

                # Export active numbers mapped to users
                active_cur = conn.execute("SELECT number, user_id, country_name, assigned_at FROM active_user_numbers;")
                active_data = [dict(r) for r in active_cur.fetchall()]

                current_group_link = get_otp_group_link()
                current_group_name = get_otp_group_name()

            # Prune seen SMS to 28 hours
            cutoff_28h = time.time() - (28 * 3600)
            cleaned_seen = {k: v for k, v in SEEN_SMS_TIMESTAMPS.items() if v >= cutoff_28h}

            payload = {
                "description": self.description,
                "files": {
                    self.filename: {
                        "content": json.dumps({
                            "bot": self.bot_name,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                            "bot_settings": settings_data,
                            "otp_group_link": current_group_link,
                            "otp_group_name": current_group_name,
                            "total_countries": len(countries_data),
                            "countries": countries_data,
                            "used_countries": used_data,
                            "users": users_data,
                            "admins": admins_data,
                            "active_numbers": active_data,
                            "seen_sms": cleaned_seen,
                            "handover": is_handover,
                            "handover_epoch": datetime.now(timezone.utc).timestamp() if is_handover else 0.0,
                        }, indent=2)
                    }
                }
            }
            async with httpx.AsyncClient(timeout=15.0) as http:
                res = await http.patch(self.api_url, headers=self._auth_headers(), json=payload)
                if res.status_code == 404:
                    logger.warning(f"Gist {self.gist_id} returned 404. Re-creating automatically...")
                    self.gist_id = ""
                    self.api_url = ""
                    if await self.ensure_gist() and self.api_url:
                        res = await http.patch(self.api_url, headers=self._auth_headers(), json=payload)

                if res.is_success:
                    logger.info(f"☁️ Database, Users, Admins & Numbers backed up to GitHub Gist (handover={is_handover}).")
                    return True
                else:
                    logger.warning(f"Gist patch status {res.status_code}: {res.text[:120]}")
        except Exception as e:
            logger.warning(f"Gist export error: {e}")
        return False

    async def restore_from_gist(self) -> bool:
        """Restores complete state, database tables, and settings from GitHub Gist."""
        if not self.enabled:
            return False
        if not self.api_url:
            await self.ensure_gist()
        if not self.api_url:
            return False
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                res = await http.get(self.api_url, headers=self._auth_headers())
                if res.status_code == 404:
                    logger.warning(f"Gist {self.gist_id} returned 404 on restore. Searching matching Gist...")
                    self.gist_id = ""
                    self.api_url = ""
                    if await self.ensure_gist() and self.api_url:
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
                        admins_data = parsed.get("admins", [])
                        active_data = parsed.get("active_numbers", [])
                        seen_data = parsed.get("seen_sms", {})

                        if parsed.get("handover"):
                            global _is_handover, _handover_epoch
                            _is_handover = True
                            _handover_epoch = float(parsed.get("handover_epoch") or 0.0)
                            logger.info(f"🔄 Zero-Restart Handover Detected from Gist (handover epoch {_handover_epoch:.0f}).")

                        # 0. Restore Bot Settings
                        saved_settings = parsed.get("bot_settings", {})
                        if isinstance(saved_settings, dict):
                            for sk, sv in saved_settings.items():
                                set_bot_setting(str(sk), str(sv))
                            logger.info(f"☁️ Restored {len(saved_settings)} bot settings from Gist.")

                        # 0b. Restore OTP Group Link & Button Name
                        saved_group = parsed.get("otp_group_link")
                        if saved_group:
                            set_otp_group_link(str(saved_group).strip())
                            logger.info(f"☁️ Restored persistent OTP Group Link from Gist: {saved_group}")

                        saved_name = parsed.get("otp_group_name")
                        if saved_name:
                            set_otp_group_name(str(saved_name).strip())
                            logger.info(f"☁️ Restored persistent OTP Group Name from Gist: {saved_name}")

                        # 1. Restore Users & Permissions
                        with get_main_db() as mconn:
                            for u in users_data:
                                uid = u.get("user_id")
                                if not uid:
                                    continue
                                mconn.execute("""
                                    INSERT INTO users (user_id, username, first_name, numbers_consumed, has_secret_access, prefer_plus, is_admin, user_quantity, joined_at, last_seen)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                                    ON CONFLICT(user_id) DO UPDATE SET
                                        username = CASE WHEN excluded.username != '' THEN excluded.username ELSE users.username END,
                                        first_name = CASE WHEN excluded.first_name != '' THEN excluded.first_name ELSE users.first_name END,
                                        numbers_consumed = max(users.numbers_consumed, excluded.numbers_consumed),
                                        has_secret_access = excluded.has_secret_access,
                                        prefer_plus = excluded.prefer_plus,
                                        is_admin = max(users.is_admin, excluded.is_admin),
                                        user_quantity = excluded.user_quantity;
                                """, (
                                    uid,
                                    u.get("username", ""),
                                    u.get("first_name", ""),
                                    u.get("numbers_consumed", 0),
                                    u.get("has_secret_access", 0),
                                    u.get("prefer_plus", 1),
                                    u.get("is_admin", 0),
                                    u.get("user_quantity", 10),
                                    u.get("joined_at", datetime.now(timezone.utc).isoformat())
                                ))

                            # Restore Dynamic Administrators
                            for a in admins_data:
                                aid = a.get("user_id")
                                if aid:
                                    mconn.execute("""
                                        INSERT INTO bot_admins (user_id, added_by, username, first_name)
                                        VALUES (?, ?, ?, ?)
                                        ON CONFLICT(user_id) DO UPDATE SET
                                            username = CASE WHEN excluded.username != '' THEN excluded.username ELSE bot_admins.username END,
                                            first_name = CASE WHEN excluded.first_name != '' THEN excluded.first_name ELSE bot_admins.first_name END;
                                    """, (aid, a.get("added_by", 0), a.get("username", ""), a.get("first_name", "")))
                                    mconn.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?;", (aid,))

                            # Restore Active User Numbers
                            if active_data:
                                for an in active_data:
                                    anum = an.get("number")
                                    auid = an.get("user_id")
                                    if anum and auid:
                                        mconn.execute("""
                                            INSERT OR IGNORE INTO active_user_numbers (number, user_id, country_name, assigned_at)
                                            VALUES (?, ?, ?, ?);
                                        """, (anum, auid, an.get("country_name", ""), an.get("assigned_at", datetime.now(timezone.utc).isoformat())))

                            mconn.commit()

                        # 2. Restore 28h Seen SMS Cache
                        if isinstance(seen_data, dict):
                            cutoff_28h = time.time() - (28 * 3600)
                            for sid, ts in seen_data.items():
                                try:
                                    if float(ts) >= cutoff_28h:
                                        SEEN_SMS_CACHE.add(str(sid))
                                        SEEN_SMS_TIMESTAMPS[str(sid)] = float(ts)
                                except Exception:
                                    pass

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
                            f"☁️ Restored {len(users_data)} users, {len(active_data)} active numbers, "
                            f"{total_std_restored} standard numbers, {total_sec_restored} secret numbers & {total_used_restored} archived used numbers from GitHub Gist."
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
    global _is_handover
    # Completely suppress restart notification on handover sessions or silent mode
    silent_env = os.getenv("SILENT_STARTUP", "").strip().lower() in ("true", "1", "yes")
    if _is_handover or silent_env:
        logger.info("🤫 Automated session handover continuation: restart notification suppressed (zero-restart mode).")
        return

    admin_alert_enabled = os.getenv("ADMIN_STARTUP_ALERT", "false").strip().lower() in ("true", "1", "yes")
    if not admin_alert_enabled and STARTUP_TYPE != "push":
        logger.info("ℹ️ NUMBER BOTMAN started in silent 24/7 background mode (no admin spam).")
        return

    stats = get_system_stats()
    group_link = get_otp_group_link()
    group_info = f"\n• <b>OTP Group:</b> <code>{group_link}</code>" if group_link else ""

    admin_msg = (
        "⚡ <b>NUMBER BOTMAN 24/7 ONLINE</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "• <b>Status:</b> <code>Online & Serving Live Numbers ✅</code>\n"
        "• <b>Engine:</b> <code>Zero-Restart Handover Engine 🔄</code>\n"
        "• <b>Storage:</b> <code>SQLite WAL + Gist Cloud Backup ☁️</code>\n"
        f"• <b>Standard Stock:</b> <code>{stats['total_std_available']} Numbers</code>\n"
        f"• <b>Secret Stock:</b> <code>{stats['total_sec_available']} Numbers 🔒</code>\n"
        f"• <b>Total Delivered:</b> <code>{stats['total_consumed']} Numbers</code>\n"
        f"• <b>Registered Users:</b> <code>{stats['total_users']} users</code>"
        f"{group_info}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👑 <i>Send /admin or /stats anytime to view live dashboard.</i>"
    )
    for aid in get_all_admin_ids():
        if aid:
            try:
                await send_with_retry(application.bot, aid, admin_msg)
                logger.info(f"✅ Initial alert sent to admin {aid}")
            except Exception as e:
                logger.warning(f"Initial alert failed for admin {aid}: {e}")

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

    # Quick toggle / status of user's preferred number format (with + or without +)
    if user_id:
        pref_plus = get_user_plus_preference(user_id)
        fmt_label = "⚙️ Format: With '+' (+123) (Tap to switch)" if pref_plus else "⚙️ Format: Without '+' (123) (Tap to switch)"
        buttons.append([InlineKeyboardButton(fmt_label, callback_data="btn_toggle_plus_pref")])

    buttons.append([
        InlineKeyboardButton("📊 Number Inventory", callback_data="btn_inventory"),
        InlineKeyboardButton("ℹ️ Help / Info", callback_data="btn_help")
    ])

    group_link = get_otp_group_link()
    if group_link:
        buttons.append([InlineKeyboardButton(get_otp_group_name(), url=group_link)])

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

def get_numbers_view_keyboard(country_id: int, is_secret: bool = False, with_plus: bool = True, quantity: int = 10, is_fixed: bool = False) -> InlineKeyboardMarkup:
    """Builds number result keyboard with dynamic '+' toggle button, quantity selector, and OTP Group."""
    change_cb = f"sec_change_num_{country_id}" if is_secret else f"change_num_{country_id}"
    country_cb = "btn_get_secret_number" if is_secret else "btn_get_number"
    sec_tag = "sec" if is_secret else "std"

    if with_plus:
        toggle_btn = InlineKeyboardButton("➖ Remove '+' Prefix", callback_data=f"toggle_plus_0_{country_id}_{sec_tag}")
    else:
        toggle_btn = InlineKeyboardButton("➕ Add '+' Prefix", callback_data=f"toggle_plus_1_{country_id}_{sec_tag}")

    btn_rows = [[toggle_btn]]

    # If quantity is not fixed globally by admin, give user the button to change quantity (1-10)
    if not is_fixed:
        qty_btn = InlineKeyboardButton(f"🔢 Quantity: {quantity} (Change 1-10)", callback_data=f"user_qty_menu_{country_id}_{sec_tag}")
        btn_rows.append([qty_btn])

    btn_rows.append([
        InlineKeyboardButton(f"🔄 Get {quantity} More Numbers", callback_data=change_cb),
        InlineKeyboardButton("🌍 Change Country", callback_data=country_cb)
    ])

    group_link = get_otp_group_link()
    if group_link:
        btn_rows.append([InlineKeyboardButton(get_otp_group_name(), url=group_link)])

    btn_rows.append([InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")])
    return InlineKeyboardMarkup(btn_rows)

def get_user_quantity_keyboard(country_id: int, is_secret: bool = False) -> InlineKeyboardMarkup:
    sec_tag = "sec" if is_secret else "std"
    row1 = [InlineKeyboardButton(str(i), callback_data=f"user_set_qty_{country_id}_{sec_tag}_{i}") for i in range(1, 6)]
    row2 = [InlineKeyboardButton(str(i), callback_data=f"user_set_qty_{country_id}_{sec_tag}_{i}") for i in range(6, 11)]
    back_cb = f"sec_change_num_{country_id}" if is_secret else f"change_num_{country_id}"
    return InlineKeyboardMarkup([
        row1,
        row2,
        [InlineKeyboardButton("🔙 Back to Numbers", callback_data=back_cb)]
    ])

def get_admin_quantity_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Reset to Default (User Choice 1-10)", callback_data="admin_set_qty_default")],
        [
            InlineKeyboardButton("Fixed: 1", callback_data="admin_set_qty_fixed_1"),
            InlineKeyboardButton("Fixed: 2", callback_data="admin_set_qty_fixed_2"),
            InlineKeyboardButton("Fixed: 5", callback_data="admin_set_qty_fixed_5"),
            InlineKeyboardButton("Fixed: 10", callback_data="admin_set_qty_fixed_10"),
        ],
        [InlineKeyboardButton("✏️ Type Custom Quantity (1–1000)", callback_data="admin_set_qty_prompt")],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]
    ])

def get_admin_sms_keyboard() -> InlineKeyboardMarkup:
    sms_on = (get_bot_setting("sms_receiving_enabled", "1") == "1")
    tw_on  = (get_bot_setting("api_thirdwave_enabled", "1") == "1")
    aug_on = (get_bot_setting("api_augestel_enabled", "1") == "1")
    ksi_on = (get_bot_setting("api_otpman2_enabled", "1") == "1")
    view_mode = get_bot_setting("sms_view_mode", "default")
    if view_mode == "default":
        fmt_label = "📜 View Mode: Default (Expand Button)"
    elif view_mode == "full":
        fmt_label = "📄 View Mode: Fixed Always Full"
    else:
        fmt_label = "📦 View Mode: Fixed Short Only"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔔 Master Forwarding: {'✅ ON' if sms_on else '❌ OFF'}", callback_data="admin_toggle_sms_master")],
        [InlineKeyboardButton(fmt_label, callback_data="admin_cycle_sms_mode")],
        [InlineKeyboardButton("⚙️ Setup Websites & API Keys", callback_data="admin_setup_apis_menu")],
        [InlineKeyboardButton("📡 Check Connected APIs Status", callback_data="admin_otp_status")],
        [InlineKeyboardButton(f"🌐 Thirdwave API: {'✅ Active' if tw_on else '❌ OFF'}", callback_data="admin_toggle_api_thirdwave")],
        [InlineKeyboardButton(f"🌐 Augestel API: {'✅ Active' if aug_on else '❌ OFF'}", callback_data="admin_toggle_api_augestel")],
        [InlineKeyboardButton(f"🌐 KSI / OTPMan2 API: {'✅ Active' if ksi_on else '❌ OFF'}", callback_data="admin_toggle_api_otpman2")],
        [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]
    ])

def get_admin_setup_apis_keyboard() -> InlineKeyboardMarkup:
    tw_key, tw_url = get_thirdwave_config()
    aug_key, aug_url = get_augestel_config()
    ksi_key, ksi_url = get_otpman2_config()

    tw_mask = f"••••{tw_key[-4:]}" if tw_key else "Not Set ❌"
    aug_mask = f"••••{aug_key[-4:]}" if aug_key else "Not Set ❌"
    ksi_mask = f"••••{ksi_key[-4:]}" if ksi_key else "Not Set ❌"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🌐 1. Thirdwave ({tw_mask})", callback_data="admin_setup_tw_prompt")],
        [InlineKeyboardButton(f"🌐 2. Augestel ({aug_mask})", callback_data="admin_setup_aug_prompt")],
        [InlineKeyboardButton(f"🌐 3. KSI / OTPMan2 ({ksi_mask})", callback_data="admin_setup_ksi_prompt")],
        [InlineKeyboardButton("📡 Ping & Verify Connections", callback_data="admin_otp_status")],
        [InlineKeyboardButton("🔙 Back to SMS Controls", callback_data="admin_sms_menu")]
    ])

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
                limit, is_fixed = get_effective_quantity_for_user(user.id)
                numbers, remaining, cname = consume_numbers_for_user(cid, user.id, limit=limit, is_secret=False)
                if numbers:
                    pref_plus = get_user_plus_preference(user.id)
                    num_lines = [f"  {idx}. <code>{n if pref_plus else n.lstrip('+')}</code>" for idx, n in enumerate(numbers, 1)]
                    msg = (
                        f"📱 <b>Your Exclusive Numbers — {cname}</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"⚡ <i>Tap any number below to copy it:</i>\n\n"
                        + "\n".join(num_lines) + "\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 <b>Remaining in Stock:</b> <code>{remaining} numbers</code>\n"
                        f"🔒 <i>All {len(numbers)} numbers are reserved for you and removed from stock.</i>"
                    )
                    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=get_numbers_view_keyboard(cid, is_secret=False, with_plus=pref_plus, quantity=limit, is_fixed=is_fixed))
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
        curr_name = get_otp_group_name()
        curr_msg = f"• <b>Current Link:</b> <code>{curr}</code>\n• <b>Button Name:</b> <code>{curr_name}</code>\n\n" if curr else ""
        await update.message.reply_text(
            f"🔗 <b>Set OTP Group Link & Button Name:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{curr_msg}"
            f"Please send your link OR <code>Button Name | Link</code> in chat:\n"
            f"• Example 1: <code>https://t.me/your_otp_group</code>\n"
            f"• Example 2: <code>💬 Join VIP Channel | https://t.me/your_otp_group</code>\n\n"
            f"<i>(Users will see a '{curr_name}' button on their number delivery screen).</i>\n"
            f"<i>(Use /setgroupname &lt;name&gt; to change only the button name).</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]
            ])
        )
        return

    if "|" in text:
        parts = text.split("|", 1)
        name_part = parts[0].strip()
        link_part = parts[1].strip()
        if name_part:
            set_otp_group_name(name_part)
        text = link_part

    ok = set_otp_group_link(text)
    if ok:
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())
        await update.message.reply_text(
            f"✅ <b>OTP Group Link & Button Updated!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <b>Link:</b> <code>{get_otp_group_link()}</code>\n"
            f"🏷️ <b>Button Name:</b> <code>{get_otp_group_name()}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ])
        )
    else:
        await update.message.reply_text("❌ <b>Failed to update group link.</b>", parse_mode=ParseMode.HTML)

async def setgroupname_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    raw_text = update.message.text
    text = re.sub(r"^/(setgroupname|setbtnname)", "", raw_text, flags=re.IGNORECASE).strip()
    if not text:
        ADMIN_STATES[user.id] = {"awaiting_otp_group_name": True}
        curr_name = get_otp_group_name()
        await update.message.reply_text(
            f"🏷️ <b>Set OTP Group Button Name:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Current Name:</b> <code>{curr_name}</code>\n\n"
            f"Please send the desired button label in chat:\n"
            f"e.g. <code>💬 Join VIP Channel</code> or <code>📢 Official OTP Group</code>\n\n"
            f"<i>(Send <code>default</code> to reset to '{DEFAULT_OTP_GROUP_NAME}')</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]
            ])
        )
        return

    if text.lower() == "default":
        text = DEFAULT_OTP_GROUP_NAME

    ok = set_otp_group_name(text)
    if ok:
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())
        await update.message.reply_text(
            f"✅ <b>OTP Group Button Name Updated!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏷️ <b>Button Name:</b> <code>{get_otp_group_name()}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ])
        )
    else:
        await update.message.reply_text("❌ <b>Failed to update button name.</b>", parse_mode=ParseMode.HTML)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("⛔ <b>Access Restricted.</b> This command is not available.", parse_mode=ParseMode.HTML)
        return

    stats = get_system_stats()

    uptime_secs = int(time.time() - bot_process_start_time)
    hours, rem = divmod(uptime_secs, 3600)
    mins, secs = divmod(rem, 60)
    uptime_str = f"{hours}h {mins}m {secs}s" if hours else f"{mins}m {secs}s"

    session_timeout = int(os.getenv("SESSION_TIMEOUT", "0"))
    if session_timeout > 0:
        handover_secs = max(0, session_timeout - uptime_secs)
        h_hours, h_rem = divmod(handover_secs, 3600)
        h_mins, _ = divmod(h_rem, 60)
        handover_info = f"<code>{h_hours}h {h_mins}m remaining</code> (Auto-Sync 🔄)"
    else:
        handover_info = "<code>Always-Online (Continuous)</code>"

    current_bot_name = get_bot_name()
    fixed_qty = get_admin_fixed_quantity()
    qty_label = f"Fixed ({fixed_qty})" if fixed_qty else "Default (1–10)"
    sms_on = (get_bot_setting("sms_receiving_enabled", "1") == "1")

    admin_text = (
        f"👑 <b>{current_bot_name} — Admin Dashboard</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Engine Status:</b> <code>100% Online & Delivering ✅</code>\n"
        f"• <b>Bot Display Name:</b> <code>{current_bot_name}</code> (/setname)\n"
        f"• <b>Quantity Mode:</b> <code>{qty_label}</code> (/setquantity)\n"
        f"• <b>SMS Forwarding:</b> <code>{'✅ Active' if sms_on else '❌ Disabled'}</code>\n"
        f"• <b>Handover Mode:</b> <code>Zero-Restart Handover Active 🔄</code>\n"
        f"• <b>Session Uptime:</b> <code>{uptime_str}</code>\n"
        f"• <b>Next Handover:</b> {handover_info}\n"
        f"• <b>Cloud Storage:</b> <code>{'Connected ☁️' if gist_storage.enabled else 'Local SQLite'}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Real-time Live Inventory:</b>\n"
        f"• <b>Standard Available:</b> <code>{stats['total_std_available']} numbers</code>\n"
        f"• <b>Secret Available:</b> <code>{stats['total_sec_available']} numbers 🔒</code>\n"
        f"• <b>Total Consumed:</b> <code>{stats['total_consumed']} numbers</code>\n"
        f"• <b>Active Countries:</b> <code>{stats['active_countries']} pools</code>\n"
        f"• <b>Total Users:</b> <code>{stats['total_users']} users</code>\n"
        f"• <b>Secret Whitelisted:</b> <code>{stats['total_secret_users']} users</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <i>Configure number quantity, linked OTP APIs, and bot display name below:</i>"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Numbers (.txt)", callback_data="admin_upload_prompt"), InlineKeyboardButton("📁 Uploaded Pools & Stock", callback_data="admin_uploaded_files")],
        [InlineKeyboardButton(f"🔢 Quantity: {fixed_qty if fixed_qty else '1–10'}", callback_data="admin_qty_menu"), InlineKeyboardButton(f"📡 SMS Controls: {'ON' if sms_on else 'OFF'}", callback_data="admin_sms_menu")],
        [InlineKeyboardButton("📡 Connected OTP Bots Status", callback_data="admin_otp_status"), InlineKeyboardButton("✏️ Change Bot Name", callback_data="admin_set_name_prompt")],
        [InlineKeyboardButton("👥 User Management & Permissions", callback_data="admin_users"), InlineKeyboardButton("🗑️ Remove Numbers / Files", callback_data="admin_remove_files_menu")],
        [InlineKeyboardButton("👑 Admin Management", callback_data="admin_manage_admins"), InlineKeyboardButton("⚡ Live Bot Status", callback_data="admin_live_status")],
        [InlineKeyboardButton("🔗 Set OTP Group Link", callback_data="admin_set_group_prompt"), InlineKeyboardButton("🏷️ Set Button Name", callback_data="admin_set_group_name_prompt")],
        [InlineKeyboardButton("☁️ Sync Cloud Backup", callback_data="admin_sync_gist"), InlineKeyboardButton("🏠 Exit Admin Panel", callback_data="btn_main_menu")]
    ])
    await update.message.reply_text(admin_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

async def setname_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("⛔ <b>Access Restricted.</b> Admins only.", parse_mode=ParseMode.HTML)
        return

    new_name = " ".join(context.args).strip() if context.args else ""
    if not new_name:
        await update.message.reply_text(
            "✏️ <b>Change Bot Name:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Usage: <code>/setname Your New Bot Name</code>\n"
            "To reset to default: <code>/resetname</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/setname Number Hub VIP</code>",
            parse_mode=ParseMode.HTML
        )
        return

    if len(new_name) > 64:
        await update.message.reply_text("❌ Name must be 64 characters or fewer.", parse_mode=ParseMode.HTML)
        return

    try:
        await context.bot.set_my_name(name=new_name)
    except Exception as e:
        logger.warning(f"Could not set Telegram bot name: {e}")

    set_bot_name(new_name)
    if gist_storage.enabled:
        asyncio.create_task(gist_storage.export_and_sync())

    await update.message.reply_text(
        f"✅ <b>Bot Name Successfully Updated!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>New Name:</b> <code>{html.escape(new_name)}</code>\n"
        f"• <b>Telegram API:</b> <code>Applied Officially ✅</code>\n"
        f"• <b>Database:</b> <code>Saved & Synced 🔒</code>",
        parse_mode=ParseMode.HTML
    )

async def resetname_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("⛔ <b>Access Restricted.</b> Admins only.", parse_mode=ParseMode.HTML)
        return

    try:
        await context.bot.set_my_name(name=DEFAULT_BOT_NAME)
    except Exception as e:
        logger.warning(f"Could not reset Telegram bot name: {e}")

    set_bot_name(DEFAULT_BOT_NAME)
    if gist_storage.enabled:
        asyncio.create_task(gist_storage.export_and_sync())

    await update.message.reply_text(
        f"✅ <b>Bot Name Reset to Default!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Active Name:</b> <code>{DEFAULT_BOT_NAME}</code>\n"
        f"• <b>Database:</b> <code>Reset & Synced 🔒</code>",
        parse_mode=ParseMode.HTML
    )

async def setquantity_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("⛔ <b>Access Restricted.</b> Admins only.", parse_mode=ParseMode.HTML)
        return

    arg = context.args[0].strip().lower() if context.args else ""
    if not arg:
        current_fixed = get_admin_fixed_quantity()
        curr_str = f"Fixed to {current_fixed} numbers" if current_fixed else "Default (Users choose 1–10)"
        await update.message.reply_text(
            f"⚙️ <b>Number Quantity Distribution Control:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Current Setting:</b> <code>{curr_str}</code>\n\n"
            f"<b>Usage:</b>\n"
            f"• <code>/setquantity &lt;1-1000&gt;</code> — Fix quantity for all users (e.g. <code>/setquantity 2</code>)\n"
            f"• <code>/setquantity default</code> — Reset to default mode (users select 1–10)",
            parse_mode=ParseMode.HTML
        )
        return

    if arg == "default":
        set_admin_fixed_quantity("default")
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())
        await update.message.reply_text(
            "✅ <b>Quantity Mode Reset to Default!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Users can now select or type their desired quantity between <b>1 and 10</b>.",
            parse_mode=ParseMode.HTML
        )
        return

    if arg.isdigit() and 1 <= int(arg) <= 1000:
        val = int(arg)
        set_admin_fixed_quantity(str(val))
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())
        await update.message.reply_text(
            f"✅ <b>Fixed Quantity Applied Globally!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Fixed Count:</b> <code>{val} numbers</code>\n"
            f"• <b>Rule:</b> All users will now receive exactly <code>{val}</code> numbers when choosing a country.",
            parse_mode=ParseMode.HTML
        )
        return

    await update.message.reply_text("❌ Quantity must be between <code>1</code> and <code>1000</code>, or <code>default</code>.", parse_mode=ParseMode.HTML)

async def user_quantity_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    register_user(user.id, user.username, user.first_name)

    fixed = get_admin_fixed_quantity()
    if fixed is not None:
        await update.message.reply_text(
            f"ℹ️ <b>Quantity is currently fixed by Admin.</b>\n"
            f"All requests will automatically receive <b>{fixed} numbers</b>.",
            parse_mode=ParseMode.HTML
        )
        return

    arg = context.args[0].strip() if context.args else ""
    if not arg or not arg.isdigit() or not (1 <= int(arg) <= 10):
        curr = get_user_quantity_preference(user.id)
        await update.message.reply_text(
            f"🔢 <b>Set Desired Number Quantity:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Your Current Setting:</b> <code>{curr} numbers</code>\n\n"
            f"<b>Usage:</b>\n"
            f"<code>/quantity &lt;1-10&gt;</code> or <code>/qty &lt;1-10&gt;</code>\n\n"
            f"<b>Example:</b>\n"
            f"<code>/qty 2</code> (Receive 2 numbers at once)\n"
            f"<code>/qty 5</code> (Receive 5 numbers at once)",
            parse_mode=ParseMode.HTML
        )
        return

    val = int(arg)
    set_user_quantity_preference(user.id, val)
    await update.message.reply_text(
        f"✅ <b>Number Quantity Updated!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"You will now receive <b>{val} numbers</b> per request.\n"
        f"Use <code>/getnumber</code> to choose a country!",
        parse_mode=ParseMode.HTML
    )

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

async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    args = update.message.text.replace("/addadmin", "", 1).strip()
    if not args or not args.isdigit():
        await update.message.reply_text(
            "Usage: <code>/addadmin &lt;user_id&gt;</code>\n"
            "Example: <code>/addadmin 123456789</code>",
            parse_mode=ParseMode.HTML
        )
        return

    target_id = int(args)
    target_user = get_user_details(target_id)
    uname = target_user.get("username", "") if target_user else ""
    fname = target_user.get("first_name", "") if target_user else ""

    ok = add_admin(target_id, added_by=user.id, username=uname, first_name=fname)
    if ok:
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())
        u_disp = f"@{uname}" if uname else (fname or str(target_id))
        await update.message.reply_text(
            f"✅ <b>Administrator Promoted!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>User:</b> <code>{u_disp}</code> (<code>{target_id}</code>)\n"
            f"👑 <b>Role:</b> <code>Full Administrator</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin Management", callback_data="admin_manage_admins")],
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ])
        )
    else:
        await update.message.reply_text("❌ Failed to promote user to Administrator.", parse_mode=ParseMode.HTML)

async def removeadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    args = update.message.text.replace("/removeadmin", "", 1).strip()
    if not args or not args.isdigit():
        await update.message.reply_text(
            "Usage: <code>/removeadmin &lt;user_id&gt;</code>\n"
            "Example: <code>/removeadmin 123456789</code>",
            parse_mode=ParseMode.HTML
        )
        return

    target_id = int(args)
    ok = remove_admin(target_id)
    if ok:
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())
        await update.message.reply_text(
            f"✅ <b>Administrator Removed!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>User ID:</b> <code>{target_id}</code>\n"
            f"❌ <b>Status:</b> <code>Admin privileges revoked</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin Management", callback_data="admin_manage_admins")],
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ])
        )
    else:
        await update.message.reply_text(
            f"❌ Could not remove {target_id}. Super Admins in .env cannot be removed via Telegram.",
            parse_mode=ParseMode.HTML
        )

async def admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    admins = get_all_admin_details()
    admin_lines = []
    for a in admins:
        role = "👑 <b>Super Admin</b> (Env)" if a["is_super"] else "🛡️ <b>Admin</b> (Added via Bot)"
        u_tag = f"@{a['username']}" if a["username"] else a["first_name"]
        admin_lines.append(f"• <code>{a['user_id']}</code> — {u_tag} [{role}]")

    admins_formatted = "\n".join(admin_lines) if admin_lines else "<i>No administrators found.</i>"
    text = (
        f"👑 <b>Active Administrators List</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{admins_formatted}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>Use /addadmin &lt;id&gt; to add or /removeadmin &lt;id&gt; to remove.</i>"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Admin", callback_data="admin_add_admin_prompt")],
        [InlineKeyboardButton("🗑️ Remove Admin", callback_data="admin_remove_admin_menu")],
        [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias for /grantsecret — grants access to secret numbers pool."""
    await grantsecret_command(update, context)

async def removeuser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Permanently purges a user and all their records from the bot, main DB, country stocks, and Gist."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ <b>Usage:</b> <code>/removeuser <user_id></code>\n\n"
            "This will permanently delete the user, their active assigned numbers, delivery logs, OTP history, and country stock logs.",
            parse_mode=ParseMode.HTML
        )
        return

    target_str = context.args[0].strip()
    if not target_str.isdigit():
        await update.message.reply_text("❌ <b>Error:</b> Please provide a valid numeric User ID.", parse_mode=ParseMode.HTML)
        return

    target_id = int(target_str)
    u = get_user_details(target_id)
    uname = f"@{u['username']}" if u and u.get("username") else (u.get("first_name") if u else str(target_id))

    res = delete_user(target_id)
    if res and gist_storage.enabled:
        asyncio.create_task(gist_storage.export_and_sync())

    if res:
        text = (
            f"✅ <b>User Permanently Purged from Bot & Databases</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>Target User ID:</b> <code>{target_id}</code> ({uname})\n"
            f"👤 <b>Account Record:</b> <code>Permanently Deleted 🗑️</code>\n"
            f"📱 <b>Active Numbers Cleared:</b> <code>{res['deleted_active_numbers']}</code>\n"
            f"📨 <b>OTP Messages Cleared:</b> <code>{res['deleted_processed_otps'] + res['deleted_sms_deliveries']}</code>\n"
            f"📜 <b>Delivery Logs Cleared:</b> <code>{res['deleted_delivery_logs']}</code>\n"
            f"📦 <b>Country Stock Records Purged:</b> <code>{res['deleted_stock_logs']}</code>\n"
            f"☁️ <b>Cloud Sync:</b> <code>Committed to Gist ☁️</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ <i>All traces of user {target_id} have been completely removed.</i>"
        )
    else:
        text = f"❌ <b>Notice:</b> User ID <code>{target_id}</code> was not found in the database."

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 User Management", callback_data="admin_users")],
        [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

async def seturl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View or update base URL for connected OTP providers.
    Usage:
      /seturl (shows current URLs)
      /seturl <thirdwave|augestel|ksi> <base_url>
      /seturl <base_url> (defaults to Thirdwave)
    """
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    tw_key, tw_url = get_thirdwave_config()
    aug_key, aug_url = get_augestel_config()
    ksi_key, ksi_url = get_otpman2_config()

    if not context.args:
        text = (
            f"🌐 <b>Connected Provider Base URLs</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"1️⃣ <b>Thirdwave:</b>\n<code>{html.escape(tw_url)}</code>\n\n"
            f"2️⃣ <b>Augestel / OTPMan:</b>\n<code>{html.escape(aug_url)}</code>\n\n"
            f"3️⃣ <b>KSI / OTPMan2:</b>\n<code>{html.escape(ksi_url)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <b>To update a URL, use:</b>\n"
            f"<code>/seturl thirdwave &lt;new_url&gt;</code>\n"
            f"<code>/seturl augestel &lt;new_url&gt;</code>\n"
            f"<code>/seturl ksi &lt;new_url&gt;</code>\n\n"
            f"<i>Or use the interactive buttons in the Admin Panel!</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ Setup Websites & API Keys", callback_data="admin_setup_apis_menu")],
            [InlineKeyboardButton("📡 Ping & Verify Connections", callback_data="admin_otp_status")],
            [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
        ])
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        return

    args = context.args
    provider_arg = args[0].lower()

    if provider_arg in ("thirdwave", "tw", "1"):
        if len(args) < 2:
            await update.message.reply_text("⚠️ <b>Usage:</b> <code>/seturl thirdwave https://domain.com</code>", parse_mode=ParseMode.HTML)
            return
        new_url = args[1].strip()
        set_thirdwave_config(tw_key, new_url)
        target_name = "Thirdwave"
        prov_key = "thirdwave"
        active_key = tw_key
    elif provider_arg in ("augestel", "aug", "otpman", "2"):
        if len(args) < 2:
            await update.message.reply_text("⚠️ <b>Usage:</b> <code>/seturl augestel https://domain.com</code>", parse_mode=ParseMode.HTML)
            return
        new_url = args[1].strip()
        set_augestel_config(aug_key, new_url)
        target_name = "Augestel / OTPMan"
        prov_key = "augestel"
        active_key = aug_key
    elif provider_arg in ("ksi", "otpman2", "3"):
        if len(args) < 2:
            await update.message.reply_text("⚠️ <b>Usage:</b> <code>/seturl ksi https://domain.com</code>", parse_mode=ParseMode.HTML)
            return
        new_url = args[1].strip()
        set_otpman2_config(ksi_key, new_url)
        target_name = "KSI / OTPMan2"
        prov_key = "otpman2"
        active_key = ksi_key
    else:
        new_url = args[0].strip()
        set_thirdwave_config(tw_key, new_url)
        target_name = "Thirdwave"
        prov_key = "thirdwave"
        active_key = tw_key

    if gist_storage.enabled:
        asyncio.create_task(gist_storage.export_and_sync())

    ping_ok, ping_msg = await ping_provider_test(active_key, new_url, prov_key)

    resp_text = (
        f"✅ <b>{target_name} Base URL Updated!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 <b>New URL:</b> <code>{html.escape(new_url)}</code>\n"
        f"📡 <b>Live Ping Status:</b> {ping_msg}\n"
        f"💾 <b>Persistence:</b> Saved to DB & Cloud Gist\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Setup Websites & API Keys", callback_data="admin_setup_apis_menu")],
        [InlineKeyboardButton("📡 Check Connected APIs Status", callback_data="admin_otp_status")],
        [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
    ])
    await update.message.reply_text(resp_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

async def setthirdwave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Configure Thirdwave API Key and optional URL."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    full_arg = " ".join(context.args).strip()
    tw_key, tw_url = get_thirdwave_config()
    if not full_arg:
        mask = f"••••{tw_key[-4:]}" if tw_key else "Not Configured ❌"
        await update.message.reply_text(
            f"🌐 <b>Thirdwave IPRN API Configuration</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔑 <b>Current API Key:</b> <code>{mask}</code>\n"
            f"🌐 <b>Current Base URL:</b> <code>{html.escape(tw_url)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <b>To update, send:</b>\n"
            f"<code>/setthirdwave &lt;api_key&gt;</code>\n"
            f"<i>Or with URL:</i>\n"
            f"<code>/setthirdwave &lt;api_key&gt; | https://domain.com</code>",
            parse_mode=ParseMode.HTML
        )
        return

    if "|" in full_arg:
        parts = [p.strip() for p in full_arg.split("|", 1)]
        new_key = parts[0]
        new_url = parts[1] if parts[1] else tw_url
    else:
        parts = full_arg.split(None, 1)
        new_key = parts[0]
        new_url = parts[1].strip() if len(parts) > 1 and parts[1].startswith("http") else tw_url

    set_thirdwave_config(new_key, new_url)
    if gist_storage.enabled:
        asyncio.create_task(gist_storage.export_and_sync())

    ping_ok, ping_msg = await ping_provider_test(new_key, new_url, "thirdwave")
    mask = f"••••{new_key[-4:]}" if new_key else "None"

    await update.message.reply_text(
        f"✅ <b>Thirdwave Configuration Saved!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔑 <b>API Key:</b> <code>{mask}</code>\n"
        f"🌐 <b>Base URL:</b> <code>{html.escape(new_url)}</code>\n"
        f"📡 <b>Live Ping Test:</b> {ping_msg}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💾 <i>Saved secretly to database and synced to cloud backup.</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ Setup Websites & API Keys", callback_data="admin_setup_apis_menu")],
            [InlineKeyboardButton("📡 Check Connected APIs", callback_data="admin_otp_status")],
            [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
        ])
    )

async def setaugestel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Configure Augestel / OTPMan API Key and optional URL."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    full_arg = " ".join(context.args).strip()
    aug_key, aug_url = get_augestel_config()
    if not full_arg:
        mask = f"••••{aug_key[-4:]}" if aug_key else "Not Configured ❌"
        await update.message.reply_text(
            f"🌐 <b>Augestel / OTPMan API Configuration</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔑 <b>Current API Key:</b> <code>{mask}</code>\n"
            f"🌐 <b>Current Base URL:</b> <code>{html.escape(aug_url)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <b>To update, send:</b>\n"
            f"<code>/setaugestel &lt;api_key&gt;</code>\n"
            f"<i>Or with URL:</i>\n"
            f"<code>/setaugestel &lt;api_key&gt; | https://domain.com</code>",
            parse_mode=ParseMode.HTML
        )
        return

    if "|" in full_arg:
        parts = [p.strip() for p in full_arg.split("|", 1)]
        new_key = parts[0]
        new_url = parts[1] if parts[1] else aug_url
    else:
        parts = full_arg.split(None, 1)
        new_key = parts[0]
        new_url = parts[1].strip() if len(parts) > 1 and parts[1].startswith("http") else aug_url

    set_augestel_config(new_key, new_url)
    if gist_storage.enabled:
        asyncio.create_task(gist_storage.export_and_sync())

    ping_ok, ping_msg = await ping_provider_test(new_key, new_url, "augestel")
    mask = f"••••{new_key[-4:]}" if new_key else "None"

    await update.message.reply_text(
        f"✅ <b>Augestel Configuration Saved!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔑 <b>API Key:</b> <code>{mask}</code>\n"
        f"🌐 <b>Base URL:</b> <code>{html.escape(new_url)}</code>\n"
        f"📡 <b>Live Ping Test:</b> {ping_msg}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💾 <i>Saved secretly to database and synced to cloud backup.</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ Setup Websites & API Keys", callback_data="admin_setup_apis_menu")],
            [InlineKeyboardButton("📡 Check Connected APIs", callback_data="admin_otp_status")],
            [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
        ])
    )

async def setotpman2_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Configure KSI / OTPMan2 API Key and optional URL."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    full_arg = " ".join(context.args).strip()
    ksi_key, ksi_url = get_otpman2_config()
    if not full_arg:
        mask = f"••••{ksi_key[-4:]}" if ksi_key else "Not Configured ❌"
        await update.message.reply_text(
            f"🌐 <b>KSI / OTPMan2 API Configuration</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔑 <b>Current API Key:</b> <code>{mask}</code>\n"
            f"🌐 <b>Current Base URL:</b> <code>{html.escape(ksi_url)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <b>To update, send:</b>\n"
            f"<code>/setotpman2 &lt;api_key&gt;</code>\n"
            f"<i>Or with URL:</i>\n"
            f"<code>/setotpman2 &lt;api_key&gt; | https://domain.com</code>",
            parse_mode=ParseMode.HTML
        )
        return

    if "|" in full_arg:
        parts = [p.strip() for p in full_arg.split("|", 1)]
        new_key = parts[0]
        new_url = parts[1] if parts[1] else ksi_url
    else:
        parts = full_arg.split(None, 1)
        new_key = parts[0]
        new_url = parts[1].strip() if len(parts) > 1 and parts[1].startswith("http") else ksi_url

    set_otpman2_config(new_key, new_url)
    if gist_storage.enabled:
        asyncio.create_task(gist_storage.export_and_sync())

    ping_ok, ping_msg = await ping_provider_test(new_key, new_url, "otpman2")
    mask = f"••••{new_key[-4:]}" if new_key else "None"

    await update.message.reply_text(
        f"✅ <b>KSI / OTPMan2 Configuration Saved!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔑 <b>API Key:</b> <code>{mask}</code>\n"
        f"🌐 <b>Base URL:</b> <code>{html.escape(new_url)}</code>\n"
        f"📡 <b>Live Ping Test:</b> {ping_msg}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💾 <i>Saved secretly to database and synced to cloud backup.</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ Setup Websites & API Keys", callback_data="admin_setup_apis_menu")],
            [InlineKeyboardButton("📡 Check Connected APIs", callback_data="admin_otp_status")],
            [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
        ])
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    stats = get_system_stats()
    uptime_secs = int(time.time() - bot_process_start_time)
    hours, remainder = divmod(uptime_secs, 3600)
    mins, secs = divmod(remainder, 60)
    uptime_str = f"{hours}h {mins}m {secs}s" if hours else f"{mins}m {secs}s"

    session_timeout = int(os.getenv("SESSION_TIMEOUT", "0"))
    if session_timeout > 0:
        handover_secs = max(0, session_timeout - uptime_secs)
        h_hours, h_rem = divmod(handover_secs, 3600)
        h_mins, _ = divmod(h_rem, 60)
        handover_info = f"<code>{h_hours}h {h_mins}m remaining</code> (Zero-Restart 🔄)"
    else:
        handover_info = "<code>Always-Online (Continuous)</code>"

    admins = get_all_admin_ids()
    text = (
        f"⚡ <b>NUMBER BOTMAN — Live Engine Status</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>Engine:</b> <code>Zero-Restart Handover Engine 🔄</code>\n"
        f"• <b>Session Limit:</b> <code>5h 25min (19,500s)</code>\n"
        f"• <b>Session Uptime:</b> <code>{uptime_str}</code>\n"
        f"• <b>Next Handover:</b> {handover_info}\n"
        f"• <b>Cloud Storage:</b> <code>{'Connected to GitHub Gist ☁️' if gist_storage.enabled else 'Local SQLite'}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Inventory & Operations:</b>\n"
        f"• <b>Standard Numbers:</b> <code>{stats['total_std_available']} in stock</code>\n"
        f"• <b>Secret Numbers:</b> <code>{stats['total_sec_available']} in stock 🔒</code>\n"
        f"• <b>Delivered Numbers:</b> <code>{stats['total_consumed']} total</code>\n"
        f"• <b>Active Pools:</b> <code>{stats['active_countries']} countries</code>\n"
        f"• <b>Total Users:</b> <code>{stats['total_users']}</code>\n"
        f"• <b>Administrators:</b> <code>{len(admins)} active</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")]
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
    text = update.message.text.strip() if (update.message and update.message.text) else ""
    if not user or not text:
        return

    # 1. Check if user is setting their quantity
    user_state = USER_STATES.get(user.id)
    if user_state and user_state.get("awaiting_user_quantity"):
        del USER_STATES[user.id]
        if text.isdigit() and 1 <= int(text) <= 10:
            q = int(text)
            set_user_quantity_preference(user.id, q)
            await update.message.reply_text(
                f"✅ <b>Number Quantity Set to {q}!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"You will now receive <b>{q} numbers</b> per request.\n"
                f"Use <code>/getnumber</code> to request numbers!",
                parse_mode=ParseMode.HTML
            )
            return
        else:
            await update.message.reply_text("❌ Please enter a valid number between <b>1 and 10</b>.", parse_mode=ParseMode.HTML)
            return

    if not is_user_authorized(user.id):
        return

    admin_state = ADMIN_STATES.get(user.id)
    if not admin_state:
        return

    if admin_state.get("awaiting_bot_name"):
        del ADMIN_STATES[user.id]
        new_name = text if text.lower() != "default" else DEFAULT_BOT_NAME
        try:
            await context.bot.set_my_name(name=new_name)
        except Exception as e:
            logger.warning(f"Could not set Telegram bot name: {e}")
        set_bot_name(new_name)
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())
        await update.message.reply_text(
            f"✅ <b>Bot Display Name Saved!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 <b>Active Name:</b> <code>{html.escape(new_name)}</code>\n"
            f"• <b>Telegram API:</b> <code>Applied Officially ✅</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ])
        )
        return

    if admin_state.get("awaiting_fixed_quantity"):
        del ADMIN_STATES[user.id]
        if text.lower() == "default":
            set_admin_fixed_quantity("default")
            if gist_storage.enabled:
                asyncio.create_task(gist_storage.export_and_sync())
            await update.message.reply_text(
                "✅ <b>Quantity Mode Reset to Default!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Users can now select or type their desired quantity between <b>1 and 10</b>.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
                ])
            )
            return
        elif text.isdigit() and 1 <= int(text) <= 1000:
            val = int(text)
            set_admin_fixed_quantity(str(val))
            if gist_storage.enabled:
                asyncio.create_task(gist_storage.export_and_sync())
            await update.message.reply_text(
                f"✅ <b>Fixed Quantity Applied Globally!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Fixed Count:</b> <code>{val} numbers</code>\n"
                f"• <b>Rule:</b> All users will receive exactly <code>{val}</code> numbers automatically.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
                ])
            )
            return
        else:
            await update.message.reply_text(
                "❌ Quantity must be between <code>1</code> and <code>1000</code>, or send <code>default</code>.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
                ])
            )
            return

    if admin_state.get("awaiting_otp_group_name"):
        del ADMIN_STATES[user.id]
        new_name = text if text.lower() != "default" else DEFAULT_OTP_GROUP_NAME
        ok = set_otp_group_name(new_name)
        if ok:
            if gist_storage.enabled:
                asyncio.create_task(gist_storage.export_and_sync())
            await update.message.reply_text(
                f"✅ <b>OTP Group Button Name Saved!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🏷️ <b>Button Name:</b> <code>{get_otp_group_name()}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
                ])
            )
        else:
            await update.message.reply_text("❌ Failed to save button name.", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ]))
        return

    if admin_state.get("awaiting_otp_group_link"):
        del ADMIN_STATES[user.id]
        if "|" in text:
            parts = text.split("|", 1)
            name_part = parts[0].strip()
            link_part = parts[1].strip()
            if name_part:
                set_otp_group_name(name_part)
            text = link_part
        ok = set_otp_group_link(text)
        if ok:
            if gist_storage.enabled:
                asyncio.create_task(gist_storage.export_and_sync())
            await update.message.reply_text(
                f"✅ <b>OTP Group Link & Button Saved!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔗 <b>Link:</b> <code>{get_otp_group_link()}</code>\n"
                f"🏷️ <b>Button Name:</b> <code>{get_otp_group_name()}</code>\n"
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

    if admin_state.get("awaiting_add_admin"):
        del ADMIN_STATES[user.id]
        clean_id = re.sub(r"\D", "", text)
        if not clean_id:
            await update.message.reply_text(
                "❌ <b>Invalid User ID.</b> Please send numeric digits only (e.g. <code>6798979733</code>).",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Try Again", callback_data="admin_add_admin_prompt")],
                    [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
                ])
            )
            return

        target_id = int(clean_id)
        target_user = get_user_details(target_id)
        uname = target_user.get("username", "") if target_user else ""
        fname = target_user.get("first_name", "") if target_user else ""

        ok = add_admin(target_id, added_by=user.id, username=uname, first_name=fname)
        if ok:
            if gist_storage.enabled:
                asyncio.create_task(gist_storage.export_and_sync())
            u_disp = f"@{uname}" if uname else (fname or str(target_id))
            await update.message.reply_text(
                f"✅ <b>Administrator Promoted Successfully!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>User:</b> <code>{u_disp}</code> (<code>{target_id}</code>)\n"
                f"👑 <b>Role:</b> <code>Full Administrator</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>This user now has access to the Admin Dashboard and all admin controls.</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👑 Admin Management", callback_data="admin_manage_admins")],
                    [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
                ])
            )
        else:
            await update.message.reply_text("❌ Failed to add administrator.", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ]))
        return

    if admin_state.get("awaiting_tw_setup"):
        del ADMIN_STATES[user.id]
        if text.strip().lower() == "cancel":
            await update.message.reply_text("❌ Setup cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Setup Menu", callback_data="admin_setup_apis_menu")]]))
            return

        tw_key, tw_url = get_thirdwave_config()
        if "|" in text:
            parts = [p.strip() for p in text.split("|", 1)]
            new_key = parts[0]
            new_url = parts[1] if parts[1] else tw_url
        else:
            parts = text.split(None, 1)
            new_key = parts[0]
            new_url = parts[1].strip() if len(parts) > 1 and parts[1].startswith("http") else tw_url

        set_thirdwave_config(new_key, new_url)
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())

        ping_ok, ping_msg = await ping_provider_test(new_key, new_url, "thirdwave")
        mask = f"••••{new_key[-4:]}" if new_key else "None"

        await update.message.reply_text(
            f"✅ <b>Thirdwave Credentials Configured!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔑 <b>API Key:</b> <code>{mask}</code>\n"
            f"🌐 <b>Base URL:</b> <code>{html.escape(new_url)}</code>\n"
            f"📡 <b>Live Ping Test:</b> {ping_msg}\n"
            f"💾 <b>Cloud Backup:</b> Synchronized secretly with Gist ☁️\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Setup Websites & API Keys", callback_data="admin_setup_apis_menu")],
                [InlineKeyboardButton("📡 Check Connected APIs Status", callback_data="admin_otp_status")],
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ])
        )
        return

    if admin_state.get("awaiting_aug_setup"):
        del ADMIN_STATES[user.id]
        if text.strip().lower() == "cancel":
            await update.message.reply_text("❌ Setup cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Setup Menu", callback_data="admin_setup_apis_menu")]]))
            return

        aug_key, aug_url = get_augestel_config()
        if "|" in text:
            parts = [p.strip() for p in text.split("|", 1)]
            new_key = parts[0]
            new_url = parts[1] if parts[1] else aug_url
        else:
            parts = text.split(None, 1)
            new_key = parts[0]
            new_url = parts[1].strip() if len(parts) > 1 and parts[1].startswith("http") else aug_url

        set_augestel_config(new_key, new_url)
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())

        ping_ok, ping_msg = await ping_provider_test(new_key, new_url, "augestel")
        mask = f"••••{new_key[-4:]}" if new_key else "None"

        await update.message.reply_text(
            f"✅ <b>Augestel / OTPMan Credentials Configured!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔑 <b>API Key:</b> <code>{mask}</code>\n"
            f"🌐 <b>Base URL:</b> <code>{html.escape(new_url)}</code>\n"
            f"📡 <b>Live Ping Test:</b> {ping_msg}\n"
            f"💾 <b>Cloud Backup:</b> Synchronized secretly with Gist ☁️\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Setup Websites & API Keys", callback_data="admin_setup_apis_menu")],
                [InlineKeyboardButton("📡 Check Connected APIs Status", callback_data="admin_otp_status")],
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
            ])
        )
        return

    if admin_state.get("awaiting_ksi_setup"):
        del ADMIN_STATES[user.id]
        if text.strip().lower() == "cancel":
            await update.message.reply_text("❌ Setup cancelled.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Setup Menu", callback_data="admin_setup_apis_menu")]]))
            return

        ksi_key, ksi_url = get_otpman2_config()
        if "|" in text:
            parts = [p.strip() for p in text.split("|", 1)]
            new_key = parts[0]
            new_url = parts[1] if parts[1] else ksi_url
        else:
            parts = text.split(None, 1)
            new_key = parts[0]
            new_url = parts[1].strip() if len(parts) > 1 and parts[1].startswith("http") else ksi_url

        set_otpman2_config(new_key, new_url)
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())

        ping_ok, ping_msg = await ping_provider_test(new_key, new_url, "otpman2")
        mask = f"••••{new_key[-4:]}" if new_key else "None"

        await update.message.reply_text(
            f"✅ <b>KSI / OTPMan2 Credentials Configured!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔑 <b>API Key:</b> <code>{mask}</code>\n"
            f"🌐 <b>Base URL:</b> <code>{html.escape(new_url)}</code>\n"
            f"📡 <b>Live Ping Test:</b> {ping_msg}\n"
            f"💾 <b>Cloud Backup:</b> Synchronized secretly with Gist ☁️\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Setup Websites & API Keys", callback_data="admin_setup_apis_menu")],
                [InlineKeyboardButton("📡 Check Connected APIs Status", callback_data="admin_otp_status")],
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
        limit, is_fixed = get_effective_quantity_for_user(user.id)

        numbers, remaining_count, country_name = consume_numbers_for_user(
            country_id=country_id,
            user_id=user.id,
            limit=limit,
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

        pref_plus = get_user_plus_preference(user.id)
        num_lines = [f"  {idx}. <code>{n if pref_plus else n.lstrip('+')}</code>" for idx, n in enumerate(numbers, 1)]
        numbers_formatted = "\n".join(num_lines)

        group_link = get_otp_group_link()
        group_notice = f"\n\n💬 <b>Need incoming messages? Click '{get_otp_group_name()}' below!</b>" if group_link else ""

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
            reply_markup=get_numbers_view_keyboard(country_id, is_secret=False, with_plus=pref_plus, quantity=limit, is_fixed=is_fixed)
        )

    # 3b. Deliver Secret Numbers
    elif data.startswith("sec_c_") or data.startswith("sec_change_num_"):
        if not user_has_secret_access(user.id):
            await query.answer("⛔ Access Denied! Secret numbers are restricted.", show_alert=True)
            return

        country_id = int(data.split("_")[2]) if data.startswith("sec_c_") else int(data.split("_")[3])
        limit, is_fixed = get_effective_quantity_for_user(user.id)

        numbers, remaining_count, country_name = consume_numbers_for_user(
            country_id=country_id,
            user_id=user.id,
            limit=limit,
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

        pref_plus = get_user_plus_preference(user.id)
        num_lines = [f"  {idx}. <code>{n if pref_plus else n.lstrip('+')}</code>" for idx, n in enumerate(numbers, 1)]
        numbers_formatted = "\n".join(num_lines)

        group_link = get_otp_group_link()
        group_notice = f"\n\n💬 <b>Need incoming messages? Click '{get_otp_group_name()}' below!</b>" if group_link else ""

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
            reply_markup=get_numbers_view_keyboard(country_id, is_secret=True, with_plus=pref_plus, quantity=limit, is_fixed=is_fixed)
        )

    # 3c. Interactive Instant '+' Toggle for Delivered Numbers
    elif data.startswith("toggle_plus_"):
        # data format: toggle_plus_<target_fmt: 0 or 1>_<country_id>_<sec or std>
        parts = data.split("_")
        target_plus = (parts[2] == "1")
        country_id = int(parts[3])
        is_secret = (parts[4] == "sec")

        # Update user's persistent preference
        set_user_plus_preference(user.id, target_plus)
        limit, is_fixed = get_effective_quantity_for_user(user.id)

        current_text = query.message.text_html or query.message.text or ""

        if target_plus:
            # Restore '+' prefix to all numbers
            def _add_plus(m):
                content = m.group(1).strip()
                digits = re.sub(r"\D", "", content)
                if len(digits) >= 5 and not content.startswith("+"):
                    return f"<code>+{content}</code>"
                return m.group(0)
            new_text = re.sub(r"<code>([^<]+)</code>", _add_plus, current_text)
            alert_msg = "➕ Added '+' prefix to all numbers!"
        else:
            # Remove '+' prefix from all numbers
            def _remove_plus(m):
                content = m.group(1).strip()
                if content.startswith("+"):
                    return f"<code>{content[1:]}</code>"
                return m.group(0)
            new_text = re.sub(r"<code>([^<]+)</code>", _remove_plus, current_text)
            alert_msg = "➖ Removed '+' prefix from all numbers!"

        await query.answer(alert_msg)
        try:
            await query.edit_message_text(
                new_text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_numbers_view_keyboard(country_id, is_secret=is_secret, with_plus=target_plus, quantity=limit, is_fixed=is_fixed)
            )
        except Exception as e:
            logger.debug(f"Toggle plus message update notice: {e}")

    # 3d. User Quantity Selection Menu
    elif data.startswith("user_qty_menu_"):
        parts = data.split("_")
        country_id = int(parts[3])
        is_secret = (parts[4] == "sec")
        await query.edit_message_text(
            "🔢 <b>Choose Number Quantity (1–10):</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Select how many numbers you would like to receive at once:</i>\n"
            "<i>(You can also type /quantity &lt;1-10&gt; in chat)</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_user_quantity_keyboard(country_id, is_secret=is_secret)
        )

    # 3e. User Set Quantity & Deliver
    elif data.startswith("user_set_qty_"):
        parts = data.split("_")
        country_id = int(parts[3])
        is_secret = (parts[4] == "sec")
        chosen_qty = int(parts[5])
        set_user_quantity_preference(user.id, chosen_qty)

        numbers, remaining_count, country_name = consume_numbers_for_user(
            country_id=country_id,
            user_id=user.id,
            limit=chosen_qty,
            is_secret=is_secret
        )

        if not numbers:
            back_cb = "btn_get_secret_number" if is_secret else "btn_get_number"
            await query.edit_message_text(
                f"⚠️ <b>No more numbers available in stock for {country_name}.</b>\n"
                f"All available numbers have been consumed. Please select another country.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌍 Choose Another Country", callback_data=back_cb)],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")]
                ])
            )
            return

        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())

        pref_plus = get_user_plus_preference(user.id)
        num_lines = [f"  {idx}. <code>{n if pref_plus else n.lstrip('+')}</code>" for idx, n in enumerate(numbers, 1)]
        numbers_formatted = "\n".join(num_lines)

        group_link = get_otp_group_link()
        group_notice = f"\n\n💬 <b>Need incoming messages? Click '{get_otp_group_name()}' below!</b>" if group_link else ""

        title_prefix = "🔒 <b>Your SECRET Numbers" if is_secret else "📱 <b>Your Exclusive Numbers"
        response_text = (
            f"{title_prefix} — {country_name}</b>\n"
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
            reply_markup=get_numbers_view_keyboard(country_id, is_secret=is_secret, with_plus=pref_plus, quantity=chosen_qty, is_fixed=False)
        )

    # 3f. Expand Full Received SMS Text
    elif data.startswith("view_full_sms_"):
        sms_id = data.replace("view_full_sms_", "", 1)
        with get_main_db() as conn:
            row = conn.execute("SELECT number, full_text, raw_json FROM seen_sms_deliveries WHERE id = ? LIMIT 1;", (sms_id,)).fetchone()
        if not row or not row["full_text"]:
            await query.answer("ℹ️ Full message details are no longer cached.", show_alert=True)
            return

        raw_msg = row["full_text"]
        try:
            item = json.loads(row["raw_json"]) if row["raw_json"] else {"number": row["number"], "message": raw_msg}
        except Exception:
            item = {"number": row["number"], "message": raw_msg}

        text, otp, markup = format_user_otp_notification(item, force_full=True, sms_id=sms_id)
        try:
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        except Exception as e:
            logger.debug(f"Error expanding full SMS: {e}")
        await query.answer("📜 Full SMS revealed!")

    # 3g. Collapse Full Received SMS Text
    elif data.startswith("collapse_sms_"):
        sms_id = data.replace("collapse_sms_", "", 1)
        with get_main_db() as conn:
            row = conn.execute("SELECT number, full_text, raw_json FROM seen_sms_deliveries WHERE id = ? LIMIT 1;", (sms_id,)).fetchone()
        if not row:
            await query.answer()
            return

        raw_msg = row["full_text"] or ""
        try:
            item = json.loads(row["raw_json"]) if row["raw_json"] else {"number": row["number"], "message": raw_msg}
        except Exception:
            item = {"number": row["number"], "message": raw_msg}

        text, otp, markup = format_user_otp_notification(item, force_full=False, sms_id=sms_id)
        try:
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        except Exception as e:
            logger.debug(f"Error collapsing SMS: {e}")
        await query.answer("📦 SMS collapsed!")

    # 3d. Main Menu Preference Switcher
    elif data == "btn_toggle_plus_pref":
        curr = get_user_plus_preference(user.id)
        new_val = not curr
        set_user_plus_preference(user.id, new_val)
        status_str = "WITH '+' prefix (e.g. +1234567890)" if new_val else "WITHOUT '+' prefix (e.g. 1234567890)"
        await query.answer(f"✅ Number format set to: {status_str}", show_alert=True)
        keyboard = get_main_menu_keyboard(user.id)
        try:
            await query.edit_message_reply_markup(reply_markup=keyboard)
        except Exception:
            pass

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
        curr_name = get_otp_group_name()
        curr_msg = f"• <b>Current Link:</b> <code>{curr}</code>\n• <b>Button Name:</b> <code>{curr_name}</code>\n\n" if curr else ""
        await query.edit_message_text(
            f"🔗 <b>Set / Update OTP Group Link & Name:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{curr_msg}"
            f"Please send your link OR <code>Button Name | Link</code> in chat:\n"
            f"• Example 1: <code>https://t.me/your_otp_group</code>\n"
            f"• Example 2: <code>💬 Join VIP Channel | https://t.me/your_otp_group</code>\n\n"
            f"<i>(Users will see a '{curr_name}' button on their number delivery screen).</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏷️ Set Button Name Only", callback_data="admin_set_group_name_prompt")],
                [InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]
            ])
        )

    # Admin Set OTP Group Name Prompt
    elif data == "admin_set_group_name_prompt" and user_admin:
        ADMIN_STATES[user.id] = {"awaiting_otp_group_name": True}
        curr_name = get_otp_group_name()
        await query.edit_message_text(
            f"🏷️ <b>Set OTP Group Button Name:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Current Button Name:</b> <code>{curr_name}</code>\n\n"
            f"Please send the desired button label in chat:\n"
            f"e.g. <code>💬 Join VIP Channel</code> or <code>📢 Official OTP Group</code>\n\n"
            f"<i>(Send <code>default</code> to reset to '{DEFAULT_OTP_GROUP_NAME}')</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]
            ])
        )

    # 6. Admin Panel
    elif data == "admin_panel" and user_admin:
        stats = get_system_stats()
        current_bot_name = get_bot_name()
        fixed_qty = get_admin_fixed_quantity()
        qty_label = f"Fixed ({fixed_qty})" if fixed_qty else "Default (1–10)"
        sms_on = (get_bot_setting("sms_receiving_enabled", "1") == "1")
        view_mode = get_bot_setting("sms_view_mode", "default")
        mode_label = "Default (Button 📜)" if view_mode == "default" else ("Fixed Full 📄" if view_mode == "full" else "Short 📦")
        curr_link = get_otp_group_link()
        curr_name = get_otp_group_name()
        link_display = f"<code>{curr_link}</code>" if curr_link else "<i>Not Set</i>"
        admin_text = (
            f"👑 <b>{current_bot_name} — Admin Dashboard</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Bot Display Name:</b> <code>{current_bot_name}</code> (/setname)\n"
            f"• <b>Quantity Mode:</b> <code>{qty_label}</code> (/setquantity)\n"
            f"• <b>SMS Forwarding:</b> <code>{'✅ Active' if sms_on else '❌ Disabled'}</code>\n"
            f"• <b>SMS View Format:</b> <code>{mode_label}</code>\n"
            f"• <b>Cloud Storage:</b> <code>{'Connected ☁️' if gist_storage.enabled else 'Local SQLite'}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Real-time Live Inventory:</b>\n"
            f"• <b>Standard Available:</b> <code>{stats['total_std_available']} numbers</code>\n"
            f"• <b>Secret Available:</b> <code>{stats['total_sec_available']} numbers 🔒</code>\n"
            f"• <b>Total Consumed:</b> <code>{stats['total_consumed']} numbers</code>\n"
            f"• <b>Active Countries:</b> <code>{stats['active_countries']} pools</code>\n"
            f"• <b>Registered Users:</b> <code>{stats['total_users']} users</code>\n"
            f"• <b>Secret Whitelisted:</b> <code>{stats['total_secret_users']} users</code>\n"
            f"• <b>OTP Group Link:</b> {link_display}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <i>Configure number quantities, linked OTP APIs, and bot display name below:</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Numbers (.txt)", callback_data="admin_upload_prompt"), InlineKeyboardButton("📁 Uploaded Pools & Stock", callback_data="admin_uploaded_files")],
            [InlineKeyboardButton(f"🔢 Quantity: {fixed_qty if fixed_qty else '1–10'}", callback_data="admin_qty_menu"), InlineKeyboardButton(f"📡 SMS Controls: {'ON' if sms_on else 'OFF'}", callback_data="admin_sms_menu")],
            [InlineKeyboardButton("📡 Connected OTP Bots Status", callback_data="admin_otp_status"), InlineKeyboardButton("✏️ Change Bot Name", callback_data="admin_set_name_prompt")],
            [InlineKeyboardButton("👥 User Management & Permissions", callback_data="admin_users"), InlineKeyboardButton("🗑️ Remove Numbers / Files", callback_data="admin_remove_files_menu")],
            [InlineKeyboardButton("👑 Admin Management", callback_data="admin_manage_admins"), InlineKeyboardButton("⚡ Live Bot Status", callback_data="admin_live_status")],
            [InlineKeyboardButton("🔗 Set OTP Group Link", callback_data="admin_set_group_prompt"), InlineKeyboardButton("🏷️ Set Button Name", callback_data="admin_set_group_name_prompt")],
            [InlineKeyboardButton("☁️ Sync Cloud Backup", callback_data="admin_sync_gist"), InlineKeyboardButton("🏠 Exit Admin Panel", callback_data="btn_main_menu")]
        ])
        await query.edit_message_text(admin_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    # 6-a. Bot Display Name Prompt
    elif data == "admin_set_name_prompt" and user_admin:
        ADMIN_STATES[user.id] = {"awaiting_bot_name": True}
        curr = get_bot_name()
        await query.edit_message_text(
            f"✏️ <b>Change Bot Display Name</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Current Name:</b> <code>{curr}</code>\n\n"
            f"Please send the new bot display name (1–64 characters) in chat.\n"
            f"It will be updated on the Telegram Bot API and saved across reboots.\n\n"
            f"💡 <i>Tip: Send <code>reset</code> or <code>default</code> to restore the default name.</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]
            ])
        )

    # 6-b. Admin Quantity Management Menu
    elif data == "admin_qty_menu" and user_admin:
        fixed_qty = get_admin_fixed_quantity()
        status_str = f"Fixed ({fixed_qty} numbers per issue)" if fixed_qty else "Default (User Choice 1–10)"
        await query.edit_message_text(
            f"🔢 <b>Number Distribution Quantity Control</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Current Policy:</b> <code>{status_str}</code>\n\n"
            f"<b>How this works:</b>\n"
            f"• <b>Fixed Quantity:</b> Users will directly receive this exact amount of numbers (1–1000) with no prompt.\n"
            f"• <b>Default Mode:</b> Users can select or type their desired quantity between 1 and 10.\n\n"
            f"Select a preset below or type a custom quantity (1–1000):",
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_quantity_keyboard()
        )

    elif data == "admin_set_qty_default" and user_admin:
        set_admin_fixed_quantity("default")
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())
        await query.answer("🔄 Number quantity reset to Default (User choice 1–10)!", show_alert=True)
        await query.edit_message_text(
            "🔢 <b>Number Distribution Quantity Control</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "• <b>Current Policy:</b> <code>Default (User Choice 1–10) ✅</code>\n\n"
            "Users can now select or type their desired quantity (1–10).",
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_quantity_keyboard()
        )

    elif data.startswith("admin_set_qty_fixed_") and user_admin:
        val = int(data.replace("admin_set_qty_fixed_", ""))
        set_admin_fixed_quantity(val)
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())
        await query.answer(f"✅ Fixed quantity set to {val} numbers!", show_alert=True)
        await query.edit_message_text(
            f"🔢 <b>Number Distribution Quantity Control</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Current Policy:</b> <code>Fixed ({val} numbers) ✅</code>\n\n"
            f"All users will now receive exactly {val} number(s) on every request without being prompted.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_quantity_keyboard()
        )

    elif data == "admin_set_qty_prompt" and user_admin:
        ADMIN_STATES[user.id] = {"awaiting_fixed_quantity": True}
        await query.edit_message_text(
            "✏️ <b>Set Custom Fixed Number Quantity (1–1000)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Send an integer between <b>1 and 1000</b> in chat to fix the quantity globally.\n\n"
            "💡 <i>Or send <code>default</code> to restore user choice (1–10).</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="admin_qty_menu")]
            ])
        )

    # 6-c. SMS Controls & Linked Provider APIs
    elif data == "admin_sms_menu" and user_admin:
        sms_on = (get_bot_setting("sms_receiving_enabled", "1") == "1")
        view_mode = get_bot_setting("sms_view_mode", "default")
        mode_label = "Default (Button 📜)" if view_mode == "default" else ("Fixed Always Full 📄" if view_mode == "full" else "Fixed Short Only 📦")
        await query.edit_message_text(
            f"📡 <b>SMS Forwarding & Linked OTP APIs</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Master SMS Receiving:</b> <code>{'✅ Active (ON)' if sms_on else '❌ Disabled (OFF)'}</code>\n"
            f"• <b>SMS View Format:</b> <code>{mode_label}</code>\n\n"
            f"<b>How this works:</b>\n"
            f"When a user gets numbers from this bot, incoming OTP messages on those numbers are fetched from your linked OTP bots/APIs and forwarded directly to the user.\n\n"
            f"Toggle the master switch, view format, or individual APIs below:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_sms_keyboard()
        )

    elif data == "admin_toggle_sms_master" and user_admin:
        curr = (get_bot_setting("sms_receiving_enabled", "1") == "1")
        new_val = "0" if curr else "1"
        set_bot_setting("sms_receiving_enabled", new_val)
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())
        await query.answer(f"Master SMS Forwarding {'ENABLED ✅' if new_val == '1' else 'DISABLED ❌'}", show_alert=True)
        try:
            await query.edit_message_reply_markup(reply_markup=get_admin_sms_keyboard())
        except Exception:
            pass

    elif data == "admin_cycle_sms_mode" and user_admin:
        curr = get_bot_setting("sms_view_mode", "default")
        modes = ["default", "full", "short"]
        next_idx = (modes.index(curr) + 1) % len(modes) if curr in modes else 0
        new_mode = modes[next_idx]
        set_bot_setting("sms_view_mode", new_mode)
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())
        mode_label = "Default (Expand Button 📜)" if new_mode == "default" else ("Fixed Always Full 📄" if new_mode == "full" else "Fixed Short Only 📦")
        await query.answer(f"SMS View Format: {mode_label}", show_alert=True)
        try:
            await query.edit_message_reply_markup(reply_markup=get_admin_sms_keyboard())
        except Exception:
            pass

    elif data == "admin_toggle_api_thirdwave" and user_admin:
        curr = (get_bot_setting("api_thirdwave_enabled", "1") == "1")
        new_val = "0" if curr else "1"
        set_bot_setting("api_thirdwave_enabled", new_val)
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())
        await query.answer(f"Thirdwave API {'ENABLED ✅' if new_val == '1' else 'DISABLED ❌'}", show_alert=True)
        try:
            await query.edit_message_reply_markup(reply_markup=get_admin_sms_keyboard())
        except Exception:
            pass

    elif data == "admin_toggle_api_augestel" and user_admin:
        curr = (get_bot_setting("api_augestel_enabled", "1") == "1")
        new_val = "0" if curr else "1"
        set_bot_setting("api_augestel_enabled", new_val)
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())
        await query.answer(f"Augestel API {'ENABLED ✅' if new_val == '1' else 'DISABLED ❌'}", show_alert=True)
        try:
            await query.edit_message_reply_markup(reply_markup=get_admin_sms_keyboard())
        except Exception:
            pass

    elif data == "admin_toggle_api_otpman2" and user_admin:
        curr = (get_bot_setting("api_otpman2_enabled", "1") == "1")
        new_val = "0" if curr else "1"
        set_bot_setting("api_otpman2_enabled", new_val)
        if gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())
        await query.answer(f"KSI / OTPMan2 API {'ENABLED ✅' if new_val == '1' else 'DISABLED ❌'}", show_alert=True)
        try:
            await query.edit_message_reply_markup(reply_markup=get_admin_sms_keyboard())
        except Exception:
            pass

    # 6-e. Setup Websites & API Keys Menu
    elif data == "admin_setup_apis_menu" and user_admin:
        tw_key, tw_url = get_thirdwave_config()
        aug_key, aug_url = get_augestel_config()
        ksi_key, ksi_url = get_otpman2_config()

        tw_status = f"✅ Configured (••••{tw_key[-4:]})" if tw_key else "❌ Missing Key"
        aug_status = f"✅ Configured (••••{aug_key[-4:]})" if aug_key else "❌ Missing Key"
        ksi_status = f"✅ Configured (••••{ksi_key[-4:]})" if ksi_key else "❌ Missing Key"

        text = (
            f"⚙️ <b>Setup OTP Websites & API Keys</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Configure and connect the 3 OTP provider bots/APIs for live SMS receiving:\n\n"
            f"1️⃣ <b>Thirdwave:</b>\n"
            f"• Key: <code>{tw_status}</code>\n"
            f"• URL: <code>{html.escape(tw_url)}</code>\n\n"
            f"2️⃣ <b>Augestel / OTPMan:</b>\n"
            f"• Key: <code>{aug_status}</code>\n"
            f"• URL: <code>{html.escape(aug_url)}</code>\n\n"
            f"3️⃣ <b>KSI / OTPMan2:</b>\n"
            f"• Key: <code>{ksi_status}</code>\n"
            f"• URL: <code>{html.escape(ksi_url)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Click a provider below to input your API Key and URL:</i>"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=get_admin_setup_apis_keyboard())

    elif data == "admin_setup_tw_prompt" and user_admin:
        ADMIN_STATES[user.id] = {"awaiting_tw_setup": True}
        tw_key, tw_url = get_thirdwave_config()
        mask = f"••••{tw_key[-4:]}" if tw_key else "None"
        text = (
            f"🌐 <b>Setup Thirdwave IPRN API</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Current Key:</b> <code>{mask}</code>\n"
            f"• <b>Current URL:</b> <code>{html.escape(tw_url)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Send your new <b>Thirdwave API Key</b> by typing it in this chat.\n\n"
            f"💡 <i>To set both Key and URL together, use:</i>\n"
            f"<code>&lt;api_key&gt; | https://your-domain.com</code>\n\n"
            f"<i>Send <code>CANCEL</code> to abort.</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Setup Menu", callback_data="admin_setup_apis_menu")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    elif data == "admin_setup_aug_prompt" and user_admin:
        ADMIN_STATES[user.id] = {"awaiting_aug_setup": True}
        aug_key, aug_url = get_augestel_config()
        mask = f"••••{aug_key[-4:]}" if aug_key else "None"
        text = (
            f"🌐 <b>Setup Augestel / OTPMan API</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Current Key:</b> <code>{mask}</code>\n"
            f"• <b>Current URL:</b> <code>{html.escape(aug_url)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Send your new <b>Augestel API Key</b> by typing it in this chat.\n\n"
            f"💡 <i>To set both Key and URL together, use:</i>\n"
            f"<code>&lt;api_key&gt; | https://your-domain.com</code>\n\n"
            f"<i>Send <code>CANCEL</code> to abort.</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Setup Menu", callback_data="admin_setup_apis_menu")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    elif data == "admin_setup_ksi_prompt" and user_admin:
        ADMIN_STATES[user.id] = {"awaiting_ksi_setup": True}
        ksi_key, ksi_url = get_otpman2_config()
        mask = f"••••{ksi_key[-4:]}" if ksi_key else "None"
        text = (
            f"🌐 <b>Setup KSI / OTPMan2 API</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Current Key:</b> <code>{mask}</code>\n"
            f"• <b>Current URL:</b> <code>{html.escape(ksi_url)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Send your new <b>KSI / OTPMan2 API Key</b> by typing it in this chat.\n\n"
            f"💡 <i>To set both Key and URL together, use:</i>\n"
            f"<code>&lt;api_key&gt; | https://your-domain.com</code>\n\n"
            f"<i>Send <code>CANCEL</code> to abort.</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Setup Menu", callback_data="admin_setup_apis_menu")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


    # 6-d. Connected OTP Bots Status Diagnostic Check
    elif (data == "admin_otp_status" or data == "admin_otp_status_refresh") and user_admin:
        await query.answer("⏳ Pinging connected OTP APIs...")
        status_data = await check_all_connected_apis_status()
        report_text = format_api_status_report(status_data)
        try:
            await query.edit_message_text(
                report_text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_admin_api_status_keyboard()
            )
        except Exception as e:
            logger.debug(f"API status edit notice: {e}")

    # 6a. Admin Management Submenu
    elif data == "admin_manage_admins" and user_admin:
        admins = get_all_admin_details()
        admin_lines = []
        for a in admins:
            role = "👑 <b>Super Admin</b> (Env)" if a["is_super"] else "🛡️ <b>Admin</b> (Added via Bot)"
            u_tag = f"@{a['username']}" if a["username"] else a["first_name"]
            admin_lines.append(f"• <code>{a['user_id']}</code> — {u_tag} [{role}]")

        admins_formatted = "\n".join(admin_lines) if admin_lines else "<i>No administrators found.</i>"
        text = (
            f"👑 <b>Administrator Management</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Active Administrators:</b>\n"
            f"{admins_formatted}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>All administrators have full access to /admin, stock uploads, and bot management.</i>\n"
            f"<i>Super Admins are defined in GitHub Secrets / .env and cannot be removed via Telegram.</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add New Admin", callback_data="admin_add_admin_prompt")],
            [InlineKeyboardButton("🗑️ Remove Admin", callback_data="admin_remove_admin_menu")],
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    elif data == "admin_add_admin_prompt" and user_admin:
        ADMIN_STATES[user.id] = {"awaiting_add_admin": True}
        text = (
            "➕ <b>Add New Administrator</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Send the **Telegram User ID** (numbers only) of the user you wish to promote to Admin.\n\n"
            "💡 <i>Tip: The user can check their ID via @userinfobot or you can look them up via /users.</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="admin_manage_admins")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    elif data == "admin_remove_admin_menu" and user_admin:
        admins = get_all_admin_details()
        removable = [a for a in admins if not a["is_super"]]
        if not removable:
            await query.answer("ℹ️ No removable database admins found. Super Admins (from .env) cannot be removed via Telegram.", show_alert=True)
            return

        buttons = []
        for a in removable:
            u_tag = f"@{a['username']}" if a["username"] else a["first_name"]
            buttons.append([InlineKeyboardButton(f"🗑️ Remove {u_tag} ({a['user_id']})", callback_data=f"admin_rm_admin_{a['user_id']}")])

        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_manage_admins")])
        text = (
            "🗑️ <b>Remove Administrator</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Tap an admin below to revoke their administrative privileges:"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("admin_rm_admin_") and user_admin:
        target_id = int(data.split("_")[3])
        ok = remove_admin(target_id)
        if ok:
            if gist_storage.enabled:
                asyncio.create_task(gist_storage.export_and_sync())
            await query.answer(f"✅ Admin privileges revoked for {target_id}!", show_alert=True)
        else:
            await query.answer(f"❌ Could not remove {target_id}.", show_alert=True)

        admins = get_all_admin_details()
        admin_lines = []
        for a in admins:
            role = "👑 <b>Super Admin</b> (Env)" if a["is_super"] else "🛡️ <b>Admin</b> (Added via Bot)"
            u_tag = f"@{a['username']}" if a["username"] else a["first_name"]
            admin_lines.append(f"• <code>{a['user_id']}</code> — {u_tag} [{role}]")

        admins_formatted = "\n".join(admin_lines) if admin_lines else "<i>No administrators found.</i>"
        text = (
            f"👑 <b>Administrator Management</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Active Administrators:</b>\n"
            f"{admins_formatted}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>All administrators have full access to /admin, stock uploads, and bot management.</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add New Admin", callback_data="admin_add_admin_prompt")],
            [InlineKeyboardButton("🗑️ Remove Admin", callback_data="admin_remove_admin_menu")],
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    elif data == "admin_live_status" and user_admin:
        stats = get_system_stats()
        uptime_secs = int(time.time() - bot_process_start_time)
        hours, remainder = divmod(uptime_secs, 3600)
        mins, secs = divmod(remainder, 60)
        uptime_str = f"{hours}h {mins}m {secs}s" if hours else f"{mins}m {secs}s"

        session_timeout = int(os.getenv("SESSION_TIMEOUT", "0"))
        if session_timeout > 0:
            handover_secs = max(0, session_timeout - uptime_secs)
            h_hours, h_rem = divmod(handover_secs, 3600)
            h_mins, _ = divmod(h_rem, 60)
            handover_info = f"<code>{h_hours}h {h_mins}m remaining</code> (Zero-Restart 🔄)"
        else:
            handover_info = "<code>Always-Online (Continuous)</code>"

        admins = get_all_admin_ids()
        text = (
            f"⚡ <b>NUMBER BOTMAN — Live Engine Status</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• <b>Engine:</b> <code>Zero-Restart Handover Engine 🔄</code>\n"
            f"• <b>Session Limit:</b> <code>5h 25min (19,500s)</code>\n"
            f"• <b>Session Uptime:</b> <code>{uptime_str}</code>\n"
            f"• <b>Next Handover:</b> {handover_info}\n"
            f"• <b>Cloud Storage:</b> <code>{'Connected to GitHub Gist ☁️' if gist_storage.enabled else 'Local SQLite'}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Inventory & Operations:</b>\n"
            f"• <b>Standard Numbers:</b> <code>{stats['total_std_available']} in stock</code>\n"
            f"• <b>Secret Numbers:</b> <code>{stats['total_sec_available']} in stock 🔒</code>\n"
            f"• <b>Delivered Numbers:</b> <code>{stats['total_consumed']} total</code>\n"
            f"• <b>Active Pools:</b> <code>{stats['active_countries']} countries</code>\n"
            f"• <b>Total Users:</b> <code>{stats['total_users']}</code>\n"
            f"• <b>Administrators:</b> <code>{len(admins)} active</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh Status", callback_data="admin_live_status")],
            [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

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
            [InlineKeyboardButton("🗑️ Remove User", callback_data=f"u_del_confirm_{target_id}")],
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
            [InlineKeyboardButton("🗑️ Remove User", callback_data=f"u_del_confirm_{target_id}")],
            [InlineKeyboardButton("👥 Back to Users List", callback_data="admin_users")],
            [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
        ])
        await query.edit_message_text(profile_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    # 9d. Confirm User Removal
    elif data.startswith("u_del_confirm_") and user_admin:
        target_id = int(data.split("_")[3])
        u = get_user_details(target_id)
        if not u:
            await query.answer("⚠️ User not found.", show_alert=True)
            return
        uname = f"@{u['username']}" if u.get("username") else (u.get("first_name") or "Unknown")
        confirm_text = (
            f"⚠️ <b>Confirm User Removal</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>User ID:</b> <code>{u['user_id']}</code>\n"
            f"📛 <b>Name:</b> <code>{u.get('first_name') or 'N/A'}</code>\n"
            f"🔗 <b>Username:</b> {uname}\n"
            f"🔢 <b>Numbers Consumed:</b> <code>{u.get('numbers_consumed', 0)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🗑️ <b>This will permanently delete this user and their delivery log from the database.</b>\n"
            f"<i>This action cannot be undone!</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Remove User", callback_data=f"u_del_do_{target_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"u_inspect_{target_id}")]
        ])
        await query.edit_message_text(confirm_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    # 9e. Execute User Removal
    elif data.startswith("u_del_do_") and user_admin:
        target_id = int(data.split("_")[3])
        u = get_user_details(target_id)
        uname = f"@{u['username']}" if u and u.get("username") else (u.get("first_name") if u else str(target_id))
        consumed = u.get("numbers_consumed", 0) if u else 0

        res = delete_user(target_id)
        if res and gist_storage.enabled:
            asyncio.create_task(gist_storage.export_and_sync())

        if res:
            await query.answer("🗑️ User permanently purged!", show_alert=True)
            result_text = (
                f"✅ <b>User Permanently Purged from Bot & Databases</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🆔 <b>Target User ID:</b> <code>{target_id}</code>\n"
                f"📛 <b>Name:</b> <code>{uname}</code>\n"
                f"👤 <b>Account Record:</b> <code>Permanently Deleted 🗑️</code>\n"
                f"📱 <b>Active Numbers Cleared:</b> <code>{res['deleted_active_numbers']}</code>\n"
                f"📨 <b>OTP Messages Cleared:</b> <code>{res['deleted_processed_otps'] + res['deleted_sms_deliveries']}</code>\n"
                f"📜 <b>Delivery Logs Cleared:</b> <code>{res['deleted_delivery_logs']}</code>\n"
                f"📦 <b>Country Stock Records Purged:</b> <code>{res['deleted_stock_logs']}</code>\n"
                f"☁️ <b>Cloud Sync:</b> <code>Purged from Gist ☁️</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🗑️ <i>All user data and database entries have been permanently removed.</i>"
            )
        else:
            await query.answer("❌ User not found or already removed.", show_alert=True)
            result_text = (
                f"⚠️ <b>User Not Found</b>\n"
                f"<i>User ID <code>{target_id}</code> was not found in the database.</i>"
            )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 Back to Users List", callback_data="admin_users")],
            [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")]
        ])
        await query.edit_message_text(result_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

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
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("admins", admins_command))
    app.add_handler(CommandHandler("addadmin", addadmin_command))
    app.add_handler(CommandHandler("removeadmin", removeadmin_command))
    app.add_handler(CommandHandler("adduser", adduser_command))
    app.add_handler(CommandHandler("removeuser", removeuser_command))
    app.add_handler(CommandHandler("setgroup", setgroup_command))
    app.add_handler(CommandHandler("setgroupname", setgroupname_command))
    app.add_handler(CommandHandler("setbtnname", setgroupname_command))
    app.add_handler(CommandHandler("grantsecret", grantsecret_command))
    app.add_handler(CommandHandler("revokesecret", revokesecret_command))
    app.add_handler(CommandHandler("user", user_lookup_command))
    app.add_handler(CommandHandler("users", admin_command))
    app.add_handler(CommandHandler("setname", setname_command))
    app.add_handler(CommandHandler("resetname", resetname_command))
    app.add_handler(CommandHandler("quantity", user_quantity_command))
    app.add_handler(CommandHandler("qty", user_quantity_command))
    app.add_handler(CommandHandler("setquantity", setquantity_command))
    app.add_handler(CommandHandler("setqty", setquantity_command))
    app.add_handler(CommandHandler("seturl", seturl_command))
    app.add_handler(CommandHandler("setthirdwave", setthirdwave_command))
    app.add_handler(CommandHandler("settw", setthirdwave_command))
    app.add_handler(CommandHandler("setaugestel", setaugestel_command))
    app.add_handler(CommandHandler("setaug", setaugestel_command))
    app.add_handler(CommandHandler("setotpman", setaugestel_command))
    app.add_handler(CommandHandler("setotpman2", setotpman2_command))
    app.add_handler(CommandHandler("setksi", setotpman2_command))

    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document_upload))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    async def setup_bot_commands(application: Application):
        try:
            # 1. Default user commands
            user_commands = [
                BotCommand("start", "🚀 Start bot & open main menu"),
                BotCommand("getnumber", "📱 Get numbers by country"),
                BotCommand("quantity", "🔢 Set quantity preference (1–10)"),
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
                BotCommand("status", "⚡ Live Zero-Restart Status"),
                BotCommand("admin", "👑 Open Admin Management Panel"),
                BotCommand("setquantity", "🔢 Set fixed quantity (1–1000)"),
                BotCommand("seturl", "🌐 View / Update Provider URLs"),
                BotCommand("setthirdwave", "🔑 Set Thirdwave Key / URL"),
                BotCommand("setaugestel", "🔑 Set Augestel Key / URL"),
                BotCommand("setotpman2", "🔑 Set KSI/OTPMan2 Key / URL"),
                BotCommand("setname", "✏️ Change bot display name"),
                BotCommand("resetname", "🔄 Reset bot display name"),
                BotCommand("admins", "👥 View Active Administrators"),
                BotCommand("addadmin", "➕ Promote user to Admin"),
                BotCommand("removeadmin", "🗑️ Demote Admin to user"),
                BotCommand("removeuser", "🗑️ Permanently purge user"),
                BotCommand("grantsecret", "🔓 Grant Secret Access to user"),
                BotCommand("revokesecret", "🔒 Revoke Secret Access from user"),
                BotCommand("setgroup", "🔗 Set OTP Group link & name"),
                BotCommand("setgroupname", "🏷️ Set OTP Group button label"),
                BotCommand("user", "👤 Lookup user details & usage"),
                BotCommand("stats", "📊 View live system statistics"),
                BotCommand("help", "ℹ️ How to use the bot"),
            ]
            for aid in get_all_admin_ids():
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
        logger.info(f"⏱️ Zero-restart handover timer armed: {duration_seconds}s ({duration_seconds/3600:.1f}h).")
        sleep_before = max(0, duration_seconds - 60)
        await asyncio.sleep(sleep_before)
        logger.info("⏱️ Approaching handover window (60s remaining). Performing pre-handover state freeze...")
        try:
            with get_main_db() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            if os.path.exists(STOCKS_DIR):
                for f in os.listdir(STOCKS_DIR):
                    if f.endswith(".db"):
                        try:
                            with sqlite3.connect(os.path.join(STOCKS_DIR, f)) as cconn:
                                cconn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                        except Exception:
                            pass
        except Exception as e:
            logger.warning(f"DB checkpoint notice: {e}")

        if gist_storage.enabled:
            try:
                await gist_storage.export_and_sync(is_handover=True)
                logger.info("☁️ Pre-handover Gist backup completed successfully.")
            except Exception as e:
                logger.warning(f"Pre-handover Gist backup warning: {e}")
        logger.info("✅ Pre-handover state snapshot saved. Exiting cleanly for next runner switch (exit 0)...")
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

        # Launch Live Multi-API SMS Polling Engine
        asyncio.create_task(sms_polling_worker(application))

        # Launch 28h Database Retention Maintenance Loop
        asyncio.create_task(periodic_db_cleanup_loop())

        is_cloud = bool(STARTUP_TYPE or os.getenv("GITHUB_ACTIONS"))
        session_timeout = int(os.getenv("SESSION_TIMEOUT", "0"))
        if session_timeout > 0:
            asyncio.create_task(auto_session_handover(application, session_timeout))

    app.post_init = post_init

    def start_health_server():
        port_str = os.getenv("PORT")
        if not port_str:
            return
        try:
            from http.server import HTTPServer, BaseHTTPRequestHandler
            import threading

            class HealthHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200)
                    self.send_header("Content-type", "text/plain")
                    self.end_headers()
                    self.wfile.write(b"OK")

                def log_message(self, format, *args):
                    return

            port = int(port_str)
            server = HTTPServer(("0.0.0.0", port), HealthHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            logger.info(f"🌐 Cloud health check server active on port {port}")
        except Exception as e:
            logger.warning(f"Cloud health server notice: {e}")

    start_health_server()

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
