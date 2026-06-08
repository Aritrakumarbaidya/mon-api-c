import discord
from discord import app_commands
from discord.ext import commands

from database import (
    add_api,
    remove_api,
    get_all_apis,
    update_api_url,
    set_api_active,
)


class APICommands(commands.Cog):
    """Commands to add, remove, and manage monitored APIs."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /addapi ──────────────────────────────────────────────

    @app_commands.command(name="addapi", description="Add a new API to monitor")
    @app_commands.describe(name="A short unique name (e.g. weather-api)", url="The API endpoint URL")
    async def addapi(self, interaction: discord.Interaction, name: str, url: str):
        # Basic URL validation
        if not url.startswith(("http://", "https://")):
            embed = discord.Embed(
                title="❌  Invalid URL",
                description="URL must start with `http://` or `https://`.",
                colour=discord.Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        success = add_api(name, url, interaction.guild_id)
        if success:
            embed = discord.Embed(
                title="✅  API Added",
                colour=discord.Colour.green(),
            )
            embed.add_field(name="📛 Name", value=f"`{name.lower()}`", inline=True)
            embed.add_field(name="🔗 URL",  value=f"`{url}`",          inline=True)
            embed.add_field(name="⏱️ Interval", value="`5 min` (default)", inline=True)
            embed.set_footer(text="Use /createchannel to set up a dedicated alert channel")
        else:
            embed = discord.Embed(
                title="⚠️  Name Already Exists",
                description=f"An API named `{name.lower()}` is already being monitored.\n"
                            f"Use `/editapi` to change its URL or `/removeapi` to delete it.",
                colour=discord.Colour.orange(),
            )
        await interaction.response.send_message(embed=embed)

    # ── /removeapi ───────────────────────────────────────────

    @app_commands.command(name="removeapi", description="Remove an API from monitoring")
    @app_commands.describe(name="Name of the API to remove")
    async def removeapi(self, interaction: discord.Interaction, name: str):
        deleted = remove_api(name, interaction.guild_id)
        if deleted:
            embed = discord.Embed(
                title="🗑️  API Removed",
                description=f"`{name.lower()}` and all its logs have been deleted.",
                colour=discord.Colour.green(),
            )
        else:
            embed = discord.Embed(
                title="❌  Not Found",
                description=f"No API named `{name.lower()}` found in this server.",
                colour=discord.Colour.red(),
            )
        await interaction.response.send_message(embed=embed)

    # ── /listapis ────────────────────────────────────────────

    @app_commands.command(name="listapis", description="List all monitored APIs")
    async def listapis(self, interaction: discord.Interaction):
        apis = get_all_apis(interaction.guild_id)
        if not apis:
            embed = discord.Embed(
                title="📭  No APIs",
                description="No APIs are being monitored yet.\nUse `/addapi` to add one!",
                colour=discord.Colour.greyple(),
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(
            title="📋  Monitored APIs",
            colour=discord.Colour.blurple(),
        )

        for api in apis:
            status_icon = "🟢" if api["is_active"] else "⏸️"
            alerts_icon = "🔔" if api["alerts_enabled"] else "🔕"
            embed.add_field(
                name=f"{status_icon}  {api['name']}",
                value=(
                    f"🔗 `{api['url']}`\n"
                    f"⏱️ Every `{api['check_interval']} min`  {alerts_icon}"
                ),
                inline=False,
            )

        embed.set_footer(text=f"{len(apis)} API(s) registered")
        await interaction.response.send_message(embed=embed)

    # ── /editapi ─────────────────────────────────────────────

    @app_commands.command(name="editapi", description="Update the URL for an API")
    @app_commands.describe(name="API name", new_url="The new endpoint URL")
    async def editapi(self, interaction: discord.Interaction, name: str, new_url: str):
        if not new_url.startswith(("http://", "https://")):
            embed = discord.Embed(
                title="❌  Invalid URL",
                description="URL must start with `http://` or `https://`.",
                colour=discord.Colour.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        updated = update_api_url(name, new_url, interaction.guild_id)
        if updated:
            embed = discord.Embed(
                title="✏️  API Updated",
                description=f"`{name.lower()}` now points to:\n`{new_url}`",
                colour=discord.Colour.green(),
            )
        else:
            embed = discord.Embed(
                title="❌  Not Found",
                description=f"No API named `{name.lower()}` found in this server.",
                colour=discord.Colour.red(),
            )
        await interaction.response.send_message(embed=embed)

    # ── /pauseapi ────────────────────────────────────────────

    @app_commands.command(name="pauseapi", description="Pause monitoring for an API")
    @app_commands.describe(name="API name")
    async def pauseapi(self, interaction: discord.Interaction, name: str):
        updated = set_api_active(name, interaction.guild_id, active=False)
        if updated:
            embed = discord.Embed(
                title="⏸️  Monitoring Paused",
                description=f"`{name.lower()}` is now paused. Use `/resumeapi` to restart.",
                colour=discord.Colour.orange(),
            )
        else:
            embed = discord.Embed(
                title="❌  Not Found",
                description=f"No API named `{name.lower()}` found in this server.",
                colour=discord.Colour.red(),
            )
        await interaction.response.send_message(embed=embed)

    # ── /resumeapi ───────────────────────────────────────────

    @app_commands.command(name="resumeapi", description="Resume monitoring for an API")
    @app_commands.describe(name="API name")
    async def resumeapi(self, interaction: discord.Interaction, name: str):
        updated = set_api_active(name, interaction.guild_id, active=True)
        if updated:
            embed = discord.Embed(
                title="▶️  Monitoring Resumed",
                description=f"`{name.lower()}` is now being monitored again.",
                colour=discord.Colour.green(),
            )
        else:
            embed = discord.Embed(
                title="❌  Not Found",
                description=f"No API named `{name.lower()}` found in this server.",
                colour=discord.Colour.red(),
            )
        await interaction.response.send_message(embed=embed)


# ── Cog loader (required by discord.py) ─────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(APICommands(bot))
