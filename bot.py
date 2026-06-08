import asyncio

import discord
from discord.ext import commands

from config import DISCORD_TOKEN
from database import init_db
from monitor import monitoring_loop

# ── Bot setup ────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = False  # disabled because no privileged intents in portal

bot = commands.Bot(command_prefix="!", intents=intents)

# List of cog modules to load
COGS = [
    "cogs.api_commands",
    "cogs.monitoring_commands",
    "cogs.settings_commands",
]


# ── Events ───────────────────────────────────────────────────

@bot.event
async def on_ready():
    """Fires once when the bot connects to Discord."""
    print(f"✅  Bot is online as {bot.user}")
    print(f"📡  Connected to {len(bot.guilds)} server(s)")

    # Initialise the database tables
    init_db()

    # Sync slash commands to Discord
    try:
        synced = await bot.tree.sync()
        print(f"🔄  Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"❌  Failed to sync commands: {e}")

    # Start the background monitoring loop
    if not monitoring_loop.is_running():
        monitoring_loop.start(bot)
        print("🔁  Monitoring loop started")

    print("─" * 45)
    print("   Ready!  Use /addapi in Discord to begin.")
    print("─" * 45)


# ── Main ─────────────────────────────────────────────────────

async def main():
    """Load cogs, then start the bot."""
    async with bot:
        for cog in COGS:
            try:
                await bot.load_extension(cog)
                print(f"📦  Loaded cog: {cog}")
            except Exception as e:
                print(f"❌  Failed to load {cog}: {e}")
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
