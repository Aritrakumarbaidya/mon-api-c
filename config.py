# ============================================================
# config.py — Load settings from .env (never hardcode secrets)
# ============================================================
import os
import sys
from dotenv import load_dotenv

# Load the .env file from the project root
load_dotenv()

# ── Required secrets ─────────────────────────────────────────
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN or DISCORD_TOKEN == "YOUR_DISCORD_BOT_TOKEN_HERE":
    print("❌  ERROR: Set your DISCORD_TOKEN in the .env file.")
    sys.exit(1)

# ── Database path ────────────────────────────────────────────
DATABASE_PATH = os.getenv("DATABASE_PATH", "monitoring.db")
