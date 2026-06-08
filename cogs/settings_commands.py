# ============================================================
# cogs/settings_commands.py — Configuration slash commands
# ============================================================
#  /createchannel  /setinterval  /enablealerts  /disablealerts
# ============================================================
import discord
from discord import app_commands
from discord.ext import commands

from database import (
    get_api,
    set_api_interval,
    set_api_alerts,
    add_channel_config,
)


class SettingsCommands(commands.Cog):
    """Commands to configure monitoring behaviour from Discord."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /createchannel ───────────────────────────────────────

    @app_commands.command(
        name="createchannel",
        description="Create a dedicated alert channel for an API",
    )
    @app_commands.describe(api_name="The API to create a channel for")
    async def createchannel(self, interaction: discord.Interaction, api_name: str):
        api = get_api(api_name, interaction.guild_id)
        if not api:
            embed = discord.Embed(
                title="❌  Not Found",
                description=f"No API named `{api_name.lower()}` in this server.",
                colour=discord.Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Defer because channel creation may take a moment
        await interaction.response.defer()

        guild = interaction.guild
        channel_name = f"{api_name.lower()}-monitor"

        # Check if a channel with that name already exists
        existing = discord.utils.get(guild.text_channels, name=channel_name)
        if existing:
            # Re-link it
            add_channel_config(api["id"], existing.id, guild.id)
            embed = discord.Embed(
                title="🔗  Channel Re-linked",
                description=f"Channel {existing.mention} already exists.\n"
                            f"Alerts for `{api_name.lower()}` will be sent there.",
                colour=discord.Colour.green(),
            )
            await interaction.followup.send(embed=embed)
            return

        # Create the channel with a helpful topic
        try:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    send_messages=False,        # read-only for members
                ),
                guild.me: discord.PermissionOverwrite(
                    send_messages=True,          # bot can post
                    embed_links=True,
                ),
            }

            new_channel = await guild.create_text_channel(
                name=channel_name,
                topic=f"🤖 Monitoring alerts for {api_name.lower()} — {api['url']}",
                overwrites=overwrites,
            )

            add_channel_config(api["id"], new_channel.id, guild.id)

            embed = discord.Embed(
                title="📢  Alert Channel Created",
                colour=discord.Colour.green(),
            )
            embed.add_field(name="📛 API",     value=f"`{api_name.lower()}`",  inline=True)
            embed.add_field(name="📺 Channel", value=new_channel.mention,      inline=True)
            embed.set_footer(text="Alerts and status updates will be posted here")
            await interaction.followup.send(embed=embed)

            # Send a welcome message in the new channel
            welcome = discord.Embed(
                title="👋  Monitoring Active",
                description=(
                    f"This channel will receive alerts for **{api_name.lower()}**.\n\n"
                    f"🔗 URL: `{api['url']}`\n"
                    f"⏱️ Interval: `{api['check_interval']} min`\n\n"
                    "I'll post here when the API goes **DOWN** or **recovers**."
                ),
                colour=discord.Colour.blurple(),
            )
            welcome.set_footer(text="API Monitoring Bot")
            await new_channel.send(embed=welcome)

        except discord.Forbidden:
            embed = discord.Embed(
                title="⛔  Missing Permissions",
                description="I don't have permission to create channels.\n"
                            "Please give me the **Manage Channels** permission.",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed)

    # ── /setinterval ─────────────────────────────────────────

    @app_commands.command(
        name="setinterval",
        description="Set the monitoring interval for an API",
    )
    @app_commands.describe(api_name="API name", minutes="Check every N minutes (1–60)")
    async def setinterval(self, interaction: discord.Interaction,
                          api_name: str, minutes: int):
        if minutes < 1 or minutes > 60:
            embed = discord.Embed(
                title="❌  Invalid Interval",
                description="Interval must be between **1** and **60** minutes.",
                colour=discord.Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        updated = set_api_interval(api_name, interaction.guild_id, minutes)
        if updated:
            embed = discord.Embed(
                title="⏱️  Interval Updated",
                description=f"`{api_name.lower()}` will now be checked every **{minutes} minute(s)**.",
                colour=discord.Colour.green(),
            )
        else:
            embed = discord.Embed(
                title="❌  Not Found",
                description=f"No API named `{api_name.lower()}` in this server.",
                colour=discord.Colour.red(),
            )
        await interaction.response.send_message(embed=embed)

    # ── /enablealerts ────────────────────────────────────────

    @app_commands.command(
        name="enablealerts",
        description="Enable alert notifications for an API",
    )
    @app_commands.describe(api_name="API name")
    async def enablealerts(self, interaction: discord.Interaction, api_name: str):
        updated = set_api_alerts(api_name, interaction.guild_id, enabled=True)
        if updated:
            embed = discord.Embed(
                title="🔔  Alerts Enabled",
                description=f"Alerts for `{api_name.lower()}` are now **ON**.\n"
                            "Make sure to `/createchannel` so alerts have somewhere to go!",
                colour=discord.Colour.green(),
            )
        else:
            embed = discord.Embed(
                title="❌  Not Found",
                description=f"No API named `{api_name.lower()}` in this server.",
                colour=discord.Colour.red(),
            )
        await interaction.response.send_message(embed=embed)

    # ── /disablealerts ───────────────────────────────────────

    @app_commands.command(
        name="disablealerts",
        description="Disable alert notifications for an API",
    )
    @app_commands.describe(api_name="API name")
    async def disablealerts(self, interaction: discord.Interaction, api_name: str):
        updated = set_api_alerts(api_name, interaction.guild_id, enabled=False)
        if updated:
            embed = discord.Embed(
                title="🔕  Alerts Disabled",
                description=f"Alerts for `{api_name.lower()}` are now **OFF**.\n"
                            "Monitoring will continue, but no messages will be sent.",
                colour=discord.Colour.orange(),
            )
        else:
            embed = discord.Embed(
                title="❌  Not Found",
                description=f"No API named `{api_name.lower()}` in this server.",
                colour=discord.Colour.red(),
            )
        await interaction.response.send_message(embed=embed)


# ── Cog loader ───────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(SettingsCommands(bot))
