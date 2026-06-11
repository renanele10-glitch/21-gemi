"""
main.py — Bot Cassino
Variáveis obrigatórias: DISCORD_TOKEN, DATABASE_URL
"""
import asyncio, os, traceback
import discord
from discord.ext import commands

TOKEN  = os.environ["DISCORD_TOKEN"]
DB_URL = os.environ.get("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)

COGS = ["cogs.db", "cogs.fichas", "cogs.blackjack", "cogs.poker", "cogs.truco", "cogs.xadrez"]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
bot.db_url = DB_URL


@bot.event
async def on_ready():
    synced = await bot.tree.sync()
    print(f"✅ {bot.user} | {len(synced)} comandos sincronizados")


async def main():
    async with bot:
        for cog in COGS:
            try:
                await bot.load_extension(cog)
                print(f"  ✓ {cog}")
            except Exception as e:
                print(f"  ✗ {cog}: {e}")
                traceback.print_exc()
        await bot.start(TOKEN)


asyncio.run(main())
