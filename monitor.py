import asyncio
from datetime import datetime, timedelta

import aiohttp
import discord
from discord.ext import tasks

from database import (
    get_all_active_apis,
    get_channel_for_api,
    get_stats,
    insert_log,
    get_history,
)

# Track when each API was last checked  {api_id: datetime}
_last_checked: dict[int, datetime] = {}


# ── Single-API health check ─────────────────────────────────

async def check_api(session: aiohttp.ClientSession, api_row) -> dict:
    """Ping one API and persist the result.

    Returns a dict with: api_id, status_code, response_time, is_success,
    error_message, api_name, api_url.
    """
    url = api_row["url"]
    api_id = api_row["id"]

    try:
        start = asyncio.get_event_loop().time()
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            elapsed = asyncio.get_event_loop().time() - start
            status_code = resp.status
            is_success = 200 <= status_code < 400
            error_message = None if is_success else f"HTTP {status_code}: {resp.reason}"

    except asyncio.TimeoutError:
        elapsed = 0.0
        status_code = 0
        is_success = False
        error_message = "Request timed out after 10 seconds"

    except aiohttp.ClientConnectorError:
        elapsed = 0.0
        status_code = 0
        is_success = False
        error_message = "Connection refused or DNS failure"

    except Exception as exc:
        elapsed = 0.0
        status_code = 0
        is_success = False
        error_message = str(exc)

    # Persist
    await asyncio.to_thread(
        insert_log, api_id, status_code, elapsed, is_success, error_message
    )

    return {
        "api_id": api_id,
        "api_name": api_row["name"],
        "api_url": url,
        "status_code": status_code,
        "response_time": round(elapsed, 4),
        "is_success": is_success,
        "error_message": error_message,
    }


# ── Alert embed builder ─────────────────────────────────────

def build_alert_embed(result: dict) -> discord.Embed:
    """Build a rich embed for a DOWN / error alert."""
    embed = discord.Embed(
        title="🔴  API Alert — DOWN",
        colour=discord.Colour.red(),
        timestamp=datetime.now(),
    )
    embed.add_field(name="📛 API Name",      value=f"`{result['api_name']}`",           inline=True)
    embed.add_field(name="🔗 URL",           value=f"`{result['api_url']}`",            inline=True)
    embed.add_field(name="📡 Status Code",   value=f"`{result['status_code']}`",        inline=True)
    embed.add_field(name="⏱️ Response Time", value=f"`{result['response_time']:.4f}s`", inline=True)
    if result["error_message"]:
        embed.add_field(
            name="⚠️ Error",
            value=f"```{result['error_message']}```",
            inline=False,
        )
    embed.set_footer(text="API Monitoring Bot")
    return embed


def build_recovery_embed(result: dict) -> discord.Embed:
    """Build a rich embed for an UP-recovery alert."""
    embed = discord.Embed(
        title="🟢  API Recovered — UP",
        colour=discord.Colour.green(),
        timestamp=datetime.now(),
    )
    embed.add_field(name="📛 API Name",      value=f"`{result['api_name']}`",           inline=True)
    embed.add_field(name="🔗 URL",           value=f"`{result['api_url']}`",            inline=True)
    embed.add_field(name="📡 Status Code",   value=f"`{result['status_code']}`",        inline=True)
    embed.add_field(name="⏱️ Response Time", value=f"`{result['response_time']:.4f}s`", inline=True)
    embed.set_footer(text="API Monitoring Bot")
    return embed


# ── Background loop ─────────────────────────────────────────

@tasks.loop(seconds=60)
async def monitoring_loop(bot: discord.Client):
    """Runs every 60 s.  For each active API whose interval has elapsed,
    performs a health check and sends alerts when needed."""
    apis = await asyncio.to_thread(get_all_active_apis)
    if not apis:
        return

    now = datetime.now()

    async with aiohttp.ClientSession() as session:
        for api in apis:
            api_id = api["id"]
            interval = timedelta(minutes=api["check_interval"])

            # Skip if not yet due
            last = _last_checked.get(api_id)
            if last and (now - last) < interval:
                continue

            result = await check_api(session, api)
            _last_checked[api_id] = now

            status_label = "UP" if result["is_success"] else "DOWN"
            print(
                f"[{now.strftime('%H:%M:%S')}] "
                f"{result['api_name']}: {status_label}  |  "
                f"Code {result['status_code']}  |  "
                f"{result['response_time']}s"
            )

            # ── Alerting ─────────────────────────────────────
            if not api["alerts_enabled"]:
                continue

            channel_cfg = await asyncio.to_thread(get_channel_for_api, api_id)
            if not channel_cfg:
                continue
            channel = bot.get_channel(channel_cfg["channel_id"])
            if not channel:
                continue

            # Check previous log to detect state changes
            recent = await asyncio.to_thread(get_history, api_id, 2)
            was_up = True
            if len(recent) >= 2:
                was_up = bool(recent[1]["is_success"])

            if not result["is_success"] and was_up:
                # API is DOWN → send alert
                await channel.send(
                    content="🚨 **API Alert!** An issue has been detected:",
                    embed=build_alert_embed(result),
                )
            elif not was_up and result["is_success"]:
                # API just recovered → notify
                await channel.send(
                    content="✅ **API Recovered!** The API is back online:",
                    embed=build_recovery_embed(result),
                )
