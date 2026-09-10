# 🤖 NUMBER-BOTMAN — 24/7 Hosting & Setup Guide

Standalone, high-performance Telegram bot that manages and distributes single-use numbers (Standard & Secret pools), tracks user consumption, and syncs live state with **persistent SQLite databases (`bot4_database.db` & `country_stocks/`)** and **cloud memory via GitHub Gist**.

---

## 📁 Files in This Folder

| File | Description |
| :--- | :--- |
| `bot.py` | Self-contained single script (exclusive number delivery, secret access whitelist, admin UI, '+' toggle) |
| `.github/workflows/run_bot.yml` | 24/7 GitHub Actions always-online runner (zero-restart handover engine) |
| `PUSH_TO_GITHUB.bat` | 1-Click push script for PC (pushes ONLY bot.py + workflow to GitHub) |
| `START_BOT.bat` | Run bot locally with auto-restart on crash |
| `TEST_BOT.bat` | Run complete connection & system diagnostics |
| `.env` | Local environment variables & secrets |
| `.env.example` | Template for environment variables |

---

## 🔐 GitHub Secrets Configuration (For 24/7 Server Hosting)

Repository: 👉 **[https://github.com/HimelKhan006/NUMBER-BOTMAN](https://github.com/HimelKhan006/NUMBER-BOTMAN)**

Go to: **Settings ➔ Secrets and variables ➔ Actions ➔ New repository secret**

### Required Secrets

| Secret Name | Example Value | Description |
| :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | `8753777447:AAGQSD6...` | Telegram Bot token from [@BotFather](https://t.me/BotFather) |
| `ADMIN_USER_IDS` | `6798979733` | Telegram Admin User ID (for `/admin` & secret access controls) |
| `GIST_TOKEN` | `ghp_yourPersonalAccessToken...` | GitHub Token with `gist` scope *(powers cloud persistence)* |

---

## ☁️ How to Generate `GIST_TOKEN` (1-Minute Guide)

1. Open GitHub: **[https://github.com/settings/tokens/new](https://github.com/settings/tokens/new)**
2. Set **Note:** `NUMBER_BOT_STORAGE`
3. Set **Expiration:** `No expiration` (or desired timeframe)
4. Under **Select scopes**, check only: ✅ **`gist`** (Create gists)
5. Scroll to the bottom and click **Generate token**.
6. Copy the token and save it as the **`GIST_TOKEN`** secret in your GitHub repository!

> 💡 **Automatic Gist Management:**
>
> - The bot automatically searches for its existing Gist (`number_botman_backup.json`), reuses it, and syncs all user accounts, administrators, and number stocks.
> - Pushing code updates never deletes or resets your database or stock memory!

---

## 📱 Mobile Phone Setup & Upload Guide (No PC Required)

You can upload bot files, configure secrets, and start the 24/7 bot directly from your **mobile phone browser**:

### 1. How to Upload and Edit bot.py from Mobile

1. Open your repository on mobile: **[https://github.com/HimelKhan006/NUMBER-BOTMAN](https://github.com/HimelKhan006/NUMBER-BOTMAN)**
2. Tap on **`bot.py`**.
3. Tap the **✏️ (Pencil icon)** at the top right of the file.
4. Select all text, delete, and paste your updated `bot.py` code.
5. Scroll to the bottom and tap **`Commit changes...`** ➔ **`Commit changes`**.

### 2. How to Add GitHub Secrets from Mobile

1. In your repository, tap **`Settings`** (if hidden, enable "Desktop site" in your mobile browser menu).
2. Tap **`Secrets and variables`** ➔ **`Actions`**.
3. Tap the green **`New repository secret`** button.
4. Enter `TELEGRAM_BOT_TOKEN`, `ADMIN_USER_IDS`, and `GIST_TOKEN`.

### 3. How to Start the Bot from Mobile

1. In your repository, tap the **`Actions`** tab.
2. Tap **`NUMBER-BOTMAN 24/7 Runner`** on the left menu.
3. Tap the **`Run workflow`** dropdown ➔ Tap the green **`Run workflow`** button.
4. The bot will start immediately in the cloud and run 24/7! 🟢

---

## 💻 Running & Deploying from PC

- **1-Click Push from PC:** Double-click `PUSH_TO_GITHUB.bat`
- **Run Diagnostics Locally:** Double-click `TEST_BOT.bat`
- **Start Bot Locally:** Double-click `START_BOT.bat`

---

## 👑 Admin & Multi-Admin Commands Reference

> All admin commands are available via the `/admin` interactive panel or as direct commands.
> Any admin added via `/addadmin` receives full access to these tools.

| Command | Description |
| :--- | :--- |
| `/admin` | Open admin control panel (stock, users, admins, status) |
| `/admins` | View list of all active Super Admins and Bot Admins |
| `/addadmin <id>` | Promote a Telegram user to Administrator |
| `/removeadmin <id>` | Demote a Bot Admin back to regular user |
| `/status` | View live zero-restart engine uptime and stock overview |
| `/adduser <id>` | Grant a user access to the Secret Numbers Pool |
| `/removeuser <id>` | Revoke a user's access from the Secret Numbers Pool |
| `/setgroup` | Set the OTP Linked Group ID for forwarding numbers |
| `/stats` | View bot usage statistics |
| `/user <id>` | Lookup detailed profile and usage for any user |

---

## 📱 Interactive '+' Number Formatting (Professional Bot Feature)

When users or admins request numbers, they can toggle the `+` prefix dynamically:

- **Instant 1-Click Toggle:** Every delivered numbers message includes a `[ ➖ Remove '+' Prefix ]` / `[ ➕ Add '+' Prefix ]` button. Tapping it switches all numbers in the message instantly without consuming new stock.
- **Persistent Format Preference:** Tapping the button or clicking `[ ⚙️ Format ]` in the Main Menu saves the user's preferred format to SQLite & GitHub Gist. All future number requests will automatically arrive in their desired format.

### How to Upload a Numbers File

1. Send `/upload` (standard) or `/secretupload` (secret) to the bot, or use the `/admin` menu.
2. The bot will prompt you to send a `.txt` file.
3. Send the `.txt` file — one number per line.
4. The bot automatically imports all numbers into the correct pool and syncs to GitHub Gist.

> 🔒 **Secret numbers** are delivered only to whitelisted users. Regular users never see secret stock.

---

## ⚡ Zero-Restart Engine (5h 25min Auto-Handover)

This bot uses a **professional zero-restart handover system** — it never shows restart messages and keeps user stock, allocations, and database synchronized across sessions via GitHub Gist.

| Stage | What Happens |
| :--- | :--- |
| **Session Running** | Bot serves users 24/7 with real-time stock allocation |
| **60s Before Timeout** | Bot backs up full SQLite database and state to GitHub Gist with `handover=true` |
| **Clean Exit** | Bot exits with code 0 — workflow immediately triggers next session |
| **New Session Starts** | Bot reads Gist, restores full database & state, silently continues — zero messages |

> ✅ **No restart messages.** Admin is never spammed during routine handovers.
> ✅ **No data loss.** Full database state is synchronized to GitHub Gist before handover.

### Session Schedule

| Setting | Value | Description |
| :--- | :--- | :--- |
| Session Length | 5h 25min (19,500s) | Each runner session before handover |
| Handover Time | ~1–3 min | Gap between session end and new session start |
| Backup Cron | Every 6h | Failsafe if self-trigger ever fails |

---

## 🔔 Delivery & Notification Flow

| Event | Destination | Description |
| :--- | :--- | :--- |
| **Number Request** | Requesting User (DM) | Exclusive single-use number delivered privately (with dynamic `+` toggle) |
| **Secret Number Request** | Whitelisted User (DM) | Secret pool number delivered privately (with dynamic `+` toggle) |
| **Routine Handover (every 5h 25min)** | *Silent — no message* | 🤫 Zero-restart engine handles silently |
| **Initial Deployment / Push** | Admin Private DM Only | 🔔 One-time online alert sent only when ADMIN_STARTUP_ALERT=true |
