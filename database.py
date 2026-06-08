import sqlite3
from datetime import datetime, timedelta

from config import DATABASE_PATH


# ── Connection helper ────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """Return a connection with row-factory enabled."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row          # access columns by name
    conn.execute("PRAGMA foreign_keys = ON")  # enforce FK constraints
    return conn


# ── Schema initialisation ───────────────────────────────────

def init_db():
    """Create all tables if they don't already exist."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS apis (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            url             TEXT    NOT NULL,
            is_active       INTEGER NOT NULL DEFAULT 1,
            check_interval  INTEGER NOT NULL DEFAULT 5,
            alerts_enabled  INTEGER NOT NULL DEFAULT 1,
            guild_id        INTEGER NOT NULL,
            created_at      TEXT    NOT NULL,
            UNIQUE(name, guild_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS monitoring_logs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            api_id          INTEGER NOT NULL,
            timestamp       TEXT    NOT NULL,
            status_code     INTEGER NOT NULL,
            response_time   REAL    NOT NULL,
            is_success      INTEGER NOT NULL,
            error_message   TEXT,
            FOREIGN KEY (api_id) REFERENCES apis(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS channel_configs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            api_id          INTEGER NOT NULL UNIQUE,
            channel_id      INTEGER NOT NULL,
            guild_id        INTEGER NOT NULL,
            created_at      TEXT    NOT NULL,
            FOREIGN KEY (api_id) REFERENCES apis(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id        INTEGER NOT NULL,
            setting_key     TEXT    NOT NULL,
            setting_value   TEXT,
            UNIQUE(guild_id, setting_key)
        )
    """)

    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════
#  API CRUD
# ══════════════════════════════════════════════════════════════

def add_api(name: str, url: str, guild_id: int) -> bool:
    """Insert a new API.  Returns True on success, False if name exists."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO apis (name, url, guild_id, created_at) VALUES (?, ?, ?, ?)",
            (name.lower(), url, guild_id, datetime.now().isoformat()),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_api(name: str, guild_id: int) -> bool:
    """Delete an API and its logs / channel config (CASCADE).
    Returns True if a row was actually deleted."""
    conn = get_connection()
    cur = conn.execute(
        "DELETE FROM apis WHERE name = ? AND guild_id = ?",
        (name.lower(), guild_id),
    )
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def get_api(name: str, guild_id: int):
    """Return a single API row or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM apis WHERE name = ? AND guild_id = ?",
        (name.lower(), guild_id),
    ).fetchone()
    conn.close()
    return row


def get_all_apis(guild_id: int | None = None) -> list:
    """Return all APIs, optionally filtered by guild."""
    conn = get_connection()
    if guild_id is not None:
        rows = conn.execute(
            "SELECT * FROM apis WHERE guild_id = ? ORDER BY name", (guild_id,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM apis ORDER BY name").fetchall()
    conn.close()
    return rows


def get_all_active_apis() -> list:
    """Return every API where is_active = 1 (across all guilds)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM apis WHERE is_active = 1 ORDER BY id"
    ).fetchall()
    conn.close()
    return rows


def update_api_url(name: str, new_url: str, guild_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute(
        "UPDATE apis SET url = ? WHERE name = ? AND guild_id = ?",
        (new_url, name.lower(), guild_id),
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


def set_api_active(name: str, guild_id: int, active: bool) -> bool:
    conn = get_connection()
    cur = conn.execute(
        "UPDATE apis SET is_active = ? WHERE name = ? AND guild_id = ?",
        (1 if active else 0, name.lower(), guild_id),
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


def set_api_interval(name: str, guild_id: int, minutes: int) -> bool:
    conn = get_connection()
    cur = conn.execute(
        "UPDATE apis SET check_interval = ? WHERE name = ? AND guild_id = ?",
        (minutes, name.lower(), guild_id),
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


def set_api_alerts(name: str, guild_id: int, enabled: bool) -> bool:
    conn = get_connection()
    cur = conn.execute(
        "UPDATE apis SET alerts_enabled = ? WHERE name = ? AND guild_id = ?",
        (1 if enabled else 0, name.lower(), guild_id),
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


# ══════════════════════════════════════════════════════════════
#  MONITORING LOGS
# ══════════════════════════════════════════════════════════════

def insert_log(api_id: int, status_code: int, response_time: float,
               is_success: bool, error_message: str | None = None):
    conn = get_connection()
    conn.execute(
        """INSERT INTO monitoring_logs
           (api_id, timestamp, status_code, response_time, is_success, error_message)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (api_id, datetime.now().isoformat(), status_code,
         round(response_time, 4), 1 if is_success else 0, error_message),
    )
    conn.commit()
    conn.close()


def get_latest_log(api_id: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM monitoring_logs WHERE api_id = ? ORDER BY id DESC LIMIT 1",
        (api_id,),
    ).fetchone()
    conn.close()
    return row


def get_history(api_id: int, limit: int = 10) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM monitoring_logs WHERE api_id = ? ORDER BY id DESC LIMIT ?",
        (api_id, limit),
    ).fetchall()
    conn.close()
    return rows


def get_stats(api_id: int) -> dict:
    """Return aggregate statistics for an API.

    Returns dict with keys:
        total, success, failed, avg_response_time, uptime_pct
    """
    conn = get_connection()

    total = conn.execute(
        "SELECT COUNT(*) FROM monitoring_logs WHERE api_id = ?", (api_id,)
    ).fetchone()[0]

    success = conn.execute(
        "SELECT COUNT(*) FROM monitoring_logs WHERE api_id = ? AND is_success = 1",
        (api_id,),
    ).fetchone()[0]

    avg_rt = conn.execute(
        "SELECT AVG(response_time) FROM monitoring_logs WHERE api_id = ?",
        (api_id,),
    ).fetchone()[0]

    conn.close()

    failed = total - success
    uptime = round((success / total) * 100, 2) if total > 0 else 100.0
    avg_rt = round(avg_rt, 4) if avg_rt else 0.0

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "avg_response_time": avg_rt,
        "uptime_pct": uptime,
    }


def get_uptime_percentage(api_id: int, hours: int = 24) -> tuple:
    """Uptime % over the last *hours*.  Returns (pct, total, up_count)."""
    conn = get_connection()
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    rows = conn.execute(
        "SELECT is_success FROM monitoring_logs WHERE api_id = ? AND timestamp >= ?",
        (api_id, since),
    ).fetchall()
    conn.close()

    total = len(rows)
    if total == 0:
        return 100.0, 0, 0
    up = sum(1 for r in rows if r["is_success"])
    return round((up / total) * 100, 2), total, up


# ══════════════════════════════════════════════════════════════
#  CHANNEL CONFIGS
# ══════════════════════════════════════════════════════════════

def add_channel_config(api_id: int, channel_id: int, guild_id: int) -> bool:
    """Link a Discord channel to an API.  Replaces existing link."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO channel_configs
               (api_id, channel_id, guild_id, created_at)
               VALUES (?, ?, ?, ?)""",
            (api_id, channel_id, guild_id, datetime.now().isoformat()),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_channel_config(api_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute("DELETE FROM channel_configs WHERE api_id = ?", (api_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def get_channel_for_api(api_id: int):
    """Return the channel_configs row for an API (or None)."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM channel_configs WHERE api_id = ?", (api_id,)
    ).fetchone()
    conn.close()
    return row


# ══════════════════════════════════════════════════════════════
#  USER / GUILD SETTINGS
# ══════════════════════════════════════════════════════════════

def set_setting(guild_id: int, key: str, value: str):
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO user_settings (guild_id, setting_key, setting_value)
           VALUES (?, ?, ?)""",
        (guild_id, key, value),
    )
    conn.commit()
    conn.close()


def get_setting(guild_id: int, key: str, default: str | None = None):
    conn = get_connection()
    row = conn.execute(
        "SELECT setting_value FROM user_settings WHERE guild_id = ? AND setting_key = ?",
        (guild_id, key),
    ).fetchone()
    conn.close()
    return row["setting_value"] if row else default
