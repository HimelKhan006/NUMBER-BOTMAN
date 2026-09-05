# 🤖 NUMBER-BOTMAN — 24/7 Hosting & Setup Guide

Standalone, high-performance Telegram bot that manages and distributes single-use numbers (Standard & Secret pools), tracks user consumption, and syncs live state with **persistent SQLite databases (`bot4_database.db` & `country_stocks/`)** and **cloud memory via GitHub Gist**.

---

## 📁 Files in This Folder

| File | Description |
| :--- | :--- |
| `bot.py` | Self-contained single script (exclusive number delivery, secret access whitelist, admin UI) |
| `.github/workflows/run_bot.yml` | 24/7 GitHub Actions always-online runner — restarts once daily at **00:00 UTC** |
| `PUSH_TO_GITHUB.bat` | 1-Click push script for PC (pushes ONLY bot.py + workflow to GitHub) |
| `START_BOT.bat` | Run bot locally with auto-restart on crash |
| `TEST_BOT.bat` | Run complete connection & system diagnostics |
| `.env` | Local environment variables & secrets |
| `.env.example` | Template for environment variables |

---

## 🔑 GitHub Secrets Configuration (For 24/7 Server Hosting)

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
> - The bot automatically searches for its existing Gist (`number_botman_backup.json`), reuses it, and syncs all user accounts and number stocks.
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

## ⏰ 24-Hour Restart Schedule

This bot runs on a **single 24-hour scheduled cycle** — it restarts once every day at **00:00 UTC** automatically.

| Schedule | Time | Description |
| :--- | :--- | :--- |
| Daily Restart | `00:00 UTC` | Bot automatically restarts once per day |
| Uptime | ~24 hours | Full continuous uptime between restarts |
| Alert | Admin DM only | 🔄 Restart notification sent privately to admin |

> ✅ **No spam to groups.** All restart notifications go **only** to the Admin's private Telegram DM.

---

## 👑 Admin Commands Reference

> All admin commands are available via `/admin` panel or as direct commands.

| Command | Description |
| :--- | :--- |
| `/admin` | Open admin control panel |
| `/upload` | Upload a **Standard** numbers `.txt` file (visible to all users) |
| `/secretupload` | Upload a **Secret** numbers `.txt` file (hidden — admin only delivery) |
| `/setgroup` | Set the OTP Linked Group ID for forwarding numbers |
| `/adduser <id>` | Grant a user access to receive numbers |
| `/removeuser <id>` | Revoke a user's access |
| `/stats` | View bot usage statistics |

### How to Upload a Numbers File

1. Send `/upload` (standard) or `/secretupload` (secret) to the bot.
2. The bot will prompt you to send a `.txt` file.
3. Send the `.txt` file — one number per line.
4. The bot automatically imports all numbers into the correct pool.

> 🔒 **Secret numbers** are delivered only to whitelisted users. Regular users never see secret stock.

---

## 🔔 Delivery & Notification Flow

| Event | Destination | Description |
| :--- | :--- | :--- |
| **Number Request** | Requesting User (DM) | Exclusive single-use number delivered privately |
| **Secret Number Request** | Whitelisted User (DM) | Secret pool number delivered privately |
| **Bot Restart (Daily 00:00 UTC)** | Admin Private DM Only | 🔄 Restart alert with status & cycle info |
| **Manual Bot Boot** | Admin Private DM Only | 🔄 Online alert with status & platform name |
