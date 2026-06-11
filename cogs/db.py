"""
cogs/db.py — Conexão com Postgres. Falha silenciosamente se não conectar.
"""
import asyncpg
import discord
from discord.ext import commands


class DB(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        url = self.bot.db_url
        if not url:
            print("[DB] ⚠️  Sem DATABASE_URL — fichas só em RAM.")
            self.bot.db = None
            return
        try:
            self.bot.db = await asyncpg.create_pool(url, min_size=1, max_size=5, timeout=10)
            async with self.bot.db.acquire() as c:
                await c.execute("""
                    CREATE TABLE IF NOT EXISTS fichas (
                        user_id      BIGINT PRIMARY KEY,
                        nome         TEXT    DEFAULT '',
                        saldo        INTEGER DEFAULT 1000,
                        vitorias     INTEGER DEFAULT 0,
                        derrotas     INTEGER DEFAULT 0,
                        ultimo_bonus TIMESTAMPTZ
                    );
                """)
            print("[DB] ✅ Postgres conectado.")
        except Exception as e:
            print(f"[DB] ⚠️  Falha ao conectar ({e}) — fichas só em RAM.")
            self.bot.db = None

    async def cog_unload(self):
        if self.bot.db:
            await self.bot.db.close()


async def setup(bot):
    await bot.add_cog(DB(bot))
