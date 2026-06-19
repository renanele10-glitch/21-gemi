"""
cogs/admin.py — Comandos administrativos do cassino.

v3 fix: default_member_permissions esconde os comandos de quem não é admin
"""
import discord
from discord import app_commands
from discord.ext import commands
from .fichas import get_saldo, set_saldo, add_saldo, SALDO_INICIAL

PERM_ADMIN = discord.Permissions(manage_guild=True)


class ConfirmarResetView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=30)
        self.bot = bot

    @discord.ui.button(label="Confirmar Reset Total", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirmar(self, interaction: discord.Interaction, btn):
        await interaction.response.defer(ephemeral=True)
        if self.bot.db:
            await self.bot.db.execute("UPDATE fichas SET saldo=$1", SALDO_INICIAL)
            count = await self.bot.db.fetchval("SELECT COUNT(*) FROM fichas")
            await interaction.followup.send(
                f"✅ Saldo de **{count}** usuários resetado para {SALDO_INICIAL:,}.", ephemeral=True)
        else:
            self.bot._ram = {}
            await interaction.followup.send(
                f"✅ RAM limpa. Próximo acesso usa {SALDO_INICIAL:,}.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancelar(self, interaction: discord.Interaction, btn):
        await interaction.response.send_message("Cancelado.", ephemeral=True)
        self.stop()


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="admin_reset", description="[ADMIN] Reseta fichas de um usuário")
    @app_commands.describe(usuario="Usuário a resetar", valor=f"Novo saldo (padrão: {SALDO_INICIAL})")
    @app_commands.default_permissions(manage_guild=True)
    async def cmd_reset(self, interaction: discord.Interaction,
                        usuario: discord.Member, valor: int = SALDO_INICIAL):
        if valor < 0:
            return await interaction.response.send_message("Valor não pode ser negativo.", ephemeral=True)
        saldo_antes = await get_saldo(self.bot, usuario)
        await set_saldo(self.bot, usuario, valor)
        await interaction.response.send_message(
            f"✅ **{usuario.display_name}**: {saldo_antes:,} → **{valor:,}** fichas.", ephemeral=True)

    @app_commands.command(name="admin_dar", description="[ADMIN] Adiciona/remove fichas de um usuário")
    @app_commands.describe(usuario="Usuário alvo", valor="Fichas (negativo para remover)")
    @app_commands.default_permissions(manage_guild=True)
    async def cmd_dar(self, interaction: discord.Interaction,
                      usuario: discord.Member, valor: int):
        saldo_antes = await get_saldo(self.bot, usuario)
        await add_saldo(self.bot, usuario, valor)
        saldo_depois = await get_saldo(self.bot, usuario)
        sinal = "+" if valor >= 0 else ""
        await interaction.response.send_message(
            f"✅ **{usuario.display_name}**: {saldo_antes:,} → **{saldo_depois:,}** ({sinal}{valor:,}).",
            ephemeral=True)

    @app_commands.command(name="historico", description="[ADMIN] Histórico de vitórias/derrotas de um usuário")
    @app_commands.describe(usuario="Usuário (padrão: você mesmo)")
    @app_commands.default_permissions(manage_guild=True)
    async def cmd_historico(self, interaction: discord.Interaction,
                            usuario: discord.Member | None = None):
        alvo = usuario or interaction.user
        saldo = await get_saldo(self.bot, alvo)
        if self.bot.db:
            row = await self.bot.db.fetchrow(
                "SELECT vitorias, derrotas, ultimo_bonus FROM fichas WHERE user_id=$1", alvo.id)
            if row:
                v = row["vitorias"] or 0
                d = row["derrotas"] or 0
                total = v + d
                taxa  = f"{v/total*100:.1f}%" if total > 0 else "—"
                ultimo = row["ultimo_bonus"].strftime("%d/%m %H:%M") if row["ultimo_bonus"] else "Nunca"
            else:
                v = d = 0; taxa = "—"; ultimo = "Nunca"
        else:
            v = d = 0; taxa = "—"; ultimo = "Sem banco"

        embed = discord.Embed(title=f"📊 Histórico — {alvo.display_name}", color=0x9b59b6)
        embed.add_field(name="💰 Saldo",      value=f"{saldo:,} fichas", inline=True)
        embed.add_field(name="✅ Vitórias",   value=str(v),              inline=True)
        embed.add_field(name="❌ Derrotas",   value=str(d),              inline=True)
        embed.add_field(name="📈 Taxa W",     value=taxa,                inline=True)
        embed.add_field(name="🎁 Ult. Bônus", value=ultimo,             inline=True)
        embed.set_thumbnail(url=alvo.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="admin_resetar_todos",
                          description="[ADMIN] ⚠️ Reseta TODOS os saldos do servidor")
    @app_commands.default_permissions(manage_guild=True)
    async def cmd_resetar_todos(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"⚠️ **Isso vai resetar TODOS os saldos para {SALDO_INICIAL:,} fichas.**\nTem certeza?",
            view=ConfirmarResetView(self.bot), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Admin(bot))
