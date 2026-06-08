from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from database import (
    get_api,
    get_latest_log,
    get_history,
    get_stats,
    get_uptime_percentage,
    get_channel_for_api,
)


class MonitoringCommands(commands.Cog):
    """Commands to view monitoring data."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /status ──────────────────────────────────────────────

    @app_commands.command(name="status", description="Show the current status of an API")
    @app_commands.describe(name="API name")
    async def status(self, interaction: discord.Interaction, name: str):
        api = get_api(name, interaction.guild_id)
        if not api:
            embed = discord.Embed(
                title="❌  Not Found",
                description=f"No API named `{name.lower()}` in this server.",
                colour=discord.Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        log = get_latest_log(api["id"])
        stats = get_stats(api["id"])
        uptime_pct, _, _ = get_uptime_percentage(api["id"])
        channel_cfg = get_channel_for_api(api["id"])

        # Determine state
        if not api["is_active"]:
            state = "⏸️ Paused"
            colour = discord.Colour.greyple()
        elif log and log["is_success"]:
            state = "🟢 UP"
            colour = discord.Colour.green()
        elif log:
            state = "🔴 DOWN"
            colour = discord.Colour.red()
        else:
            state = "⚪ No Data"
            colour = discord.Colour.light_grey()

        embed = discord.Embed(
            title=f"📊  Status — {api['name']}",
            colour=colour,
            timestamp=datetime.now(),
        )
        embed.add_field(name="📛 API Name",         value=f"`{api['name']}`",                    inline=True)
        embed.add_field(name="🔗 URL",              value=f"`{api['url']}`",                     inline=True)
        embed.add_field(name="🔄 Current State",    value=state,                                 inline=True)

        if log:
            embed.add_field(name="📡 Status Code",  value=f"`{log['status_code']}`",             inline=True)
            embed.add_field(name="⏱️ Response Time", value=f"`{log['response_time']:.4f}s`",     inline=True)
            ts = log["timestamp"][:19].replace("T", " ")
            embed.add_field(name="🕐 Last Checked",  value=f"`{ts}`",                           inline=True)
        else:
            embed.add_field(name="🕐 Last Checked",  value="`Never`",                           inline=True)

        embed.add_field(name="📈 Uptime (24h)",     value=f"`{uptime_pct}%`",                    inline=True)
        embed.add_field(name="🔢 Total Checks",     value=f"`{stats['total']}`",                 inline=True)
        embed.add_field(name="❌ Failures",          value=f"`{stats['failed']}`",                inline=True)

        embed.add_field(name="⏱️ Interval",         value=f"`{api['check_interval']} min`",      inline=True)
        embed.add_field(name="🔔 Alerts",           value="Enabled" if api["alerts_enabled"] else "Disabled", inline=True)

        alert_ch = f"<#{channel_cfg['channel_id']}>" if channel_cfg else "`None`"
        embed.add_field(name="📢 Alert Channel",    value=alert_ch,                              inline=True)

        if log and log["error_message"]:
            embed.add_field(name="⚠️ Last Error", value=f"```{log['error_message']}```", inline=False)

        embed.set_footer(text="API Monitoring Bot")
        await interaction.response.send_message(embed=embed)

    # ── /history ─────────────────────────────────────────────

    @app_commands.command(name="history", description="Show recent monitoring logs for an API")
    @app_commands.describe(name="API name")
    async def history(self, interaction: discord.Interaction, name: str):
        api = get_api(name, interaction.guild_id)
        if not api:
            embed = discord.Embed(
                title="❌  Not Found",
                description=f"No API named `{name.lower()}` in this server.",
                colour=discord.Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        rows = get_history(api["id"], limit=10)
        if not rows:
            embed = discord.Embed(
                title="📭  No History",
                description=f"No monitoring logs yet for `{name.lower()}`.\n"
                            "Logs appear after the first monitoring check.",
                colour=discord.Colour.greyple(),
            )
            await interaction.response.send_message(embed=embed)
            return

        emoji_map = {1: "🟢", 0: "🔴"}
        lines = []
        for r in rows:
            emoji = emoji_map.get(r["is_success"], "⚪")
            ts = r["timestamp"][:19].replace("T", " ")
            label = "UP" if r["is_success"] else "DOWN"
            lines.append(
                f"{emoji} `{ts}` | **{label}** | "
                f"Code `{r['status_code']}` | `{r['response_time']:.4f}s`"
            )

        embed = discord.Embed(
            title=f"📜  History — {api['name']}",
            description="\n".join(lines),
            colour=discord.Colour.blurple(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"Last {len(rows)} check(s)  •  API Monitoring Bot")
        await interaction.response.send_message(embed=embed)

    # ── /stats ───────────────────────────────────────────────

    @app_commands.command(name="stats", description="Show aggregate statistics for an API")
    @app_commands.describe(name="API name")
    async def stats(self, interaction: discord.Interaction, name: str):
        api = get_api(name, interaction.guild_id)
        if not api:
            embed = discord.Embed(
                title="❌  Not Found",
                description=f"No API named `{name.lower()}` in this server.",
                colour=discord.Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        s = get_stats(api["id"])

        if s["total"] == 0:
            embed = discord.Embed(
                title="📭  No Data",
                description=f"No checks recorded for `{name.lower()}` yet.",
                colour=discord.Colour.greyple(),
            )
            await interaction.response.send_message(embed=embed)
            return

        # Uptime bar
        bar_len = 20
        filled = int(bar_len * s["uptime_pct"] / 100)
        bar = "█" * filled + "░" * (bar_len - filled)

        embed = discord.Embed(
            title=f"📊  Stats — {api['name']}",
            colour=discord.Colour.blurple(),
            timestamp=datetime.now(),
        )
        embed.add_field(name="🔢 Total Checks",    value=f"`{s['total']}`",                  inline=True)
        embed.add_field(name="✅ Successful",       value=f"`{s['success']}`",                inline=True)
        embed.add_field(name="❌ Failed",            value=f"`{s['failed']}`",                 inline=True)
        embed.add_field(name="⏱️ Avg Response",     value=f"`{s['avg_response_time']:.4f}s`", inline=True)
        embed.add_field(name="📈 Uptime",           value=f"`{s['uptime_pct']}%`",            inline=True)
        embed.add_field(name="📊 Progress",         value=f"`[{bar}]`",                       inline=False)
        embed.set_footer(text="API Monitoring Bot")
        await interaction.response.send_message(embed=embed)


# ── Cog loader ───────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(MonitoringCommands(bot))
