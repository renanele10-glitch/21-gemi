"""
cogs/fichas.py — Fichas compartilhadas entre todos os jogos.
Comandos: /fichas /bonus /ranking /transferir

v3:
  - /fichas agora mostra W/L junto (unificado com /historico básico)
  - add_saldo é thread-safe via lock por user (evita race condition em double-spend)
  - users_em_jogo importável para proteção anti-spam cross-cog
"""
import discord, asyncio
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone, timedelta

SALDO_INICIAL  = 1_000
BONUS_VALOR    = 300
BONUS_COOLDOWN = timedelta(hours=20)

# Lock por user_id para operações de saldo (evita race condition)
_saldo_locks: dict[int, asyncio.Lock] = {}

def _lock(uid: int) -> asyncio.Lock:
    if uid not in _saldo_locks:
        _saldo_locks[uid] = asyncio.Lock()
    return _saldo_locks[uid]


# ── Helpers ───────────────────────────────────────────────────────────────────
async def get_saldo(bot, user: discord.Member) -> int:
    if not bot.db:
        return bot._ram.get(user.id, SALDO_INICIAL)
    row = await bot.db.fetchrow("SELECT saldo FROM fichas WHERE user_id=$1", user.id)
    if row:
        return row["saldo"]
    await bot.db.execute(
        "INSERT INTO fichas (user_id, nome, saldo) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING",
        user.id, user.display_name, SALDO_INICIAL)
    return SALDO_INICIAL


async def set_saldo(bot, user: discord.Member, valor: int):
    valor = max(0, valor)
    if not bot.db:
        bot._ram[user.id] = valor
        return
    await bot.db.execute("""
        INSERT INTO fichas (user_id, nome, saldo) VALUES ($1,$2,$3)
        ON CONFLICT (user_id) DO UPDATE SET saldo=$3, nome=$2
    """, user.id, user.display_name, valor)


async def add_saldo(bot, user: discord.Member, delta: int):
    """Thread-safe: usa lock por user para evitar double-spend."""
    async with _lock(user.id):
        atual = await get_saldo(bot, user)
        await set_saldo(bot, user, atual + delta)


async def registrar_resultado(bot, user: discord.Member, ganhou: bool):
    if not bot.db: return
    col = "vitorias" if ganhou else "derrotas"
    await bot.db.execute(
        f"UPDATE fichas SET {col}={col}+1 WHERE user_id=$1", user.id)


# ── Cog ───────────────────────────────────────────────────────────────────────
class Fichas(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not hasattr(bot, "_ram"):
            bot._ram = {}

    @app_commands.command(name="fichas", description="Ver seu saldo, vitórias e derrotas")
    async def cmd_fichas(self, interaction: discord.Interaction):
        saldo = await get_saldo(self.bot, interaction.user)
        v = d = 0; ultimo = "Nunca"
        if self.bot.db:
            row = await self.bot.db.fetchrow(
                "SELECT vitorias, derrotas, ultimo_bonus FROM fichas WHERE user_id=$1",
                interaction.user.id)
            if row:
                v = row["vitorias"] or 0
                d = row["derrotas"] or 0
                ultimo = row["ultimo_bonus"].strftime("%d/%m %H:%M") if row["ultimo_bonus"] else "Nunca"
        total = v + d
        taxa  = f"{v/total*100:.1f}%" if total > 0 else "—"
        embed = discord.Embed(
            title=f"🪙 {interaction.user.display_name}",
            color=0xFFD700)
        embed.add_field(name="💰 Fichas",    value=f"{saldo:,}",  inline=True)
        embed.add_field(name="✅ Vitórias",  value=str(v),        inline=True)
        embed.add_field(name="❌ Derrotas",  value=str(d),        inline=True)
        embed.add_field(name="📈 Taxa W",    value=taxa,          inline=True)
        embed.add_field(name="🎁 Ult. Bônus", value=ultimo,      inline=True)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="bonus", description="Bônus diário de fichas")
    async def cmd_bonus(self, interaction: discord.Interaction):
        agora = datetime.now(timezone.utc)
        if self.bot.db:
            row = await self.bot.db.fetchrow(
                "SELECT ultimo_bonus FROM fichas WHERE user_id=$1", interaction.user.id)
            ultimo = row["ultimo_bonus"] if row and row["ultimo_bonus"] else None
            if ultimo and ultimo.tzinfo is None:
                ultimo = ultimo.replace(tzinfo=timezone.utc)
        else:
            ultimo = None

        if ultimo and (agora - ultimo) < BONUS_COOLDOWN:
            restante = BONUS_COOLDOWN - (agora - ultimo)
            h = int(restante.total_seconds()) // 3600
            m = (int(restante.total_seconds()) % 3600) // 60
            return await interaction.response.send_message(
                f"⏳ Próximo bônus em **{h}h {m}min**.", ephemeral=True)

        await add_saldo(self.bot, interaction.user, BONUS_VALOR)
        if self.bot.db:
            await self.bot.db.execute(
                "UPDATE fichas SET ultimo_bonus=$1 WHERE user_id=$2", agora, interaction.user.id)
        saldo = await get_saldo(self.bot, interaction.user)
        await interaction.response.send_message(
            f"🎁 **+{BONUS_VALOR} fichas!** Saldo: **{saldo:,}**", ephemeral=True)

    @app_commands.command(name="ranking", description="Top 10 jogadores por fichas")
    async def cmd_ranking(self, interaction: discord.Interaction):
        if not self.bot.db:
            return await interaction.response.send_message("Ranking indisponível sem banco.", ephemeral=True)
        rows = await self.bot.db.fetch(
            "SELECT nome, saldo, vitorias, derrotas FROM fichas ORDER BY saldo DESC LIMIT 10")
        medals = ["🥇","🥈","🥉"] + ["🏅"]*7
        linhas = []
        for i, r in enumerate(rows):
            total = (r["vitorias"] or 0) + (r["derrotas"] or 0)
            taxa  = f"{r['vitorias']/total*100:.0f}%W" if total > 0 else "—"
            linhas.append(
                f"{medals[i]} **{r['nome'] or 'Anônimo'}** — {r['saldo']:,} fichas "
                f"({r['vitorias']}W/{r['derrotas']}L · {taxa})")
        embed = discord.Embed(
            title="🏆 Ranking",
            description="\n".join(linhas) or "Vazio.",
            color=0xFFD700)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="transferir", description="Transferir fichas para outro jogador")
    @app_commands.describe(usuario="Para quem transferir", valor="Quantidade de fichas")
    async def cmd_transferir(self, interaction: discord.Interaction, usuario: discord.Member, valor: int):
        if valor <= 0:
            return await interaction.response.send_message("Valor deve ser positivo.", ephemeral=True)
        if usuario.id == interaction.user.id:
            return await interaction.response.send_message("Não pode transferir pra si mesmo.", ephemeral=True)
        if usuario.bot:
            return await interaction.response.send_message("Não pode transferir pra bots.", ephemeral=True)
        async with _lock(interaction.user.id):
            saldo = await get_saldo(self.bot, interaction.user)
            if saldo < valor:
                return await interaction.response.send_message(
                    f"Saldo insuficiente ({saldo:,} fichas).", ephemeral=True)
            await set_saldo(self.bot, interaction.user, saldo - valor)
        await add_saldo(self.bot, usuario, valor)
        await interaction.response.send_message(
            f"✅ **{valor:,} fichas** transferidas para {usuario.display_name}.")


async def setup(bot):
    await bot.add_cog(Fichas(bot))
