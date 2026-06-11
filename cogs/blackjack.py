"""
cogs/blackjack.py — Blackjack 21. Painel persistente.
Mesa privada por jogador. Sem banco extra — usa fichas compartilhadas.
"""
import discord, random
from discord import app_commands
from discord.ext import commands
from dataclasses import dataclass, field
from .fichas import get_saldo, add_saldo, registrar_resultado
from .render import render_blackjack

SUITS = ["♠","♥","♦","♣"]
RANKS = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]
VALS  = {"A":11,"2":2,"3":3,"4":4,"5":5,"6":6,"7":7,
         "8":8,"9":9,"10":10,"J":10,"Q":10,"K":10}
APOSTA_MIN = 10
APOSTA_MAX = 2000


def _baralho():
    b = [(r,s) for r in RANKS for s in SUITS]
    random.shuffle(b)
    return b


def _calcular(mao):
    total = sum(VALS[r] for r,_ in mao)
    ases  = sum(1 for r,_ in mao if r=="A")
    while total > 21 and ases:
        total -= 10; ases -= 1
    return total


@dataclass
class BJGame:
    user: discord.Member
    aposta: int = 0
    deck:   list = field(default_factory=_baralho)
    dealer: list = field(default_factory=list)
    mao:    list = field(default_factory=list)
    fim:    bool = False
    result: str  = ""
    wins:   int  = 0
    losses: int  = 0
    ties:   int  = 0
    first:  bool = True   # é a primeira mão?

    def deal(self):
        if len(self.deck) < 15:
            self.deck = _baralho()
        self.dealer = [self.deck.pop(), self.deck.pop()]
        self.mao    = [self.deck.pop(), self.deck.pop()]
        self.fim    = False
        self.result = ""

    def _dealer_joga(self):
        while _calcular(self.dealer) < 17:
            self.dealer.append(self.deck.pop())

    def _avaliar(self):
        pv = _calcular(self.mao)
        dv = _calcular(self.dealer)
        if pv > 21:
            self.result = "💥 Bust! Dealer vence."; self.losses += 1; return -self.aposta
        elif dv > 21:
            self.result = "🎉 Dealer estourou! Você venceu!"; self.wins += 1; return self.aposta
        elif pv > dv:
            self.result = "🎉 Você venceu!"; self.wins += 1; return self.aposta
        elif pv == dv:
            self.result = "🤝 Empate!"; self.ties += 1; return 0
        else:
            self.result = "😔 Dealer venceu."; self.losses += 1; return -self.aposta

    def hit(self):
        self.mao.append(self.deck.pop())
        if _calcular(self.mao) > 21:
            self._dealer_joga()
            return self._finalizar()
        return None

    def stand(self):
        self._dealer_joga()
        return self._finalizar()

    def double(self, aposta_extra):
        self.aposta += aposta_extra
        self.mao.append(self.deck.pop())
        self._dealer_joga()
        return self._finalizar()

    def surrender(self):
        self.result = "🏳️ Você rendeu-se. Metade da aposta devolvida."
        self.fim    = True
        self.losses += 1
        return -(self.aposta // 2)

    def _finalizar(self):
        self.fim = True
        return self._avaliar()

    def blackjack_natural(self):
        return _calcular(self.mao) == 21 and len(self.mao) == 2


# ── View ──────────────────────────────────────────────────────────────────────
class BJView(discord.ui.View):
    def __init__(self, game: BJGame, bot):
        super().__init__(timeout=600)
        self.game = game
        self.bot  = bot
        self._sync()

    def _sync(self):
        for c in self.children:
            if c.custom_id in ("bj_hit","bj_stand"):
                c.disabled = self.game.fim
            elif c.custom_id in ("bj_double","bj_surrender"):
                c.disabled = self.game.fim or len(self.game.mao) != 2
            elif c.custom_id == "bj_next":
                c.disabled = not self.game.fim

    def _render(self):
        g = self.game
        pv = _calcular(g.mao)
        dv = _calcular(g.dealer)
        buf = render_blackjack(g.dealer, dv, g.mao, pv,
                               reveal_dealer=g.fim, result=g.result)
        return discord.File(buf, "blackjack.png")

    def _embed(self):
        g = self.game
        embed = discord.Embed(title="🃏 Blackjack 21", color=0x1a0005)
        embed.description = (
            f"**{g.user.display_name}** — "
            f"✅ {g.wins}  ❌ {g.losses}  🤝 {g.ties}\n"
            f"Aposta atual: **{g.aposta:,} fichas**"
        )
        embed.set_image(url="attachment://blackjack.png")
        embed.set_footer(text="Próxima Mão para continuar." if g.fim else "Boa sorte!")
        return embed

    async def _update(self, interaction: discord.Interaction, delta: int | None = None):
        if delta is not None:
            await add_saldo(self.bot, self.game.user, delta + self.game.aposta)
            await registrar_resultado(self.bot, self.game.user, delta > 0)
        self._sync()
        f = self._render()
        await interaction.response.edit_message(embed=self._embed(), attachments=[f], view=self)

    def _check(self, i): return i.user.id == self.game.user.id

    @discord.ui.button(label="Hit / Pedir", emoji="🃏",
                       style=discord.ButtonStyle.green, custom_id="bj_hit", row=0)
    async def hit(self, interaction, btn):
        if not self._check(interaction):
            return await interaction.response.send_message("Mesa de outro jogador.", ephemeral=True)
        delta = self.game.hit()
        await self._update(interaction, delta)

    @discord.ui.button(label="Stand / Manter", emoji="✋",
                       style=discord.ButtonStyle.grey, custom_id="bj_stand", row=0)
    async def stand(self, interaction, btn):
        if not self._check(interaction):
            return await interaction.response.send_message("Mesa de outro jogador.", ephemeral=True)
        delta = self.game.stand()
        await self._update(interaction, delta)

    @discord.ui.button(label="Double / Dobrar", emoji="2️⃣",
                       style=discord.ButtonStyle.blurple, custom_id="bj_double", row=0)
    async def double(self, interaction, btn):
        if not self._check(interaction):
            return await interaction.response.send_message("Mesa de outro jogador.", ephemeral=True)
        saldo = await get_saldo(self.bot, interaction.user)
        extra = min(self.game.aposta, saldo)
        if extra <= 0:
            return await interaction.response.send_message("Fichas insuficientes para dobrar.", ephemeral=True)
        await add_saldo(self.bot, interaction.user, -extra)
        delta = self.game.double(extra)
        await self._update(interaction, delta)

    @discord.ui.button(label="Surrender / Correr", emoji="🏳️",
                       style=discord.ButtonStyle.red, custom_id="bj_surrender", row=0)
    async def surrender(self, interaction, btn):
        if not self._check(interaction):
            return await interaction.response.send_message("Mesa de outro jogador.", ephemeral=True)
        delta = self.game.surrender()
        await self._update(interaction, delta)

    @discord.ui.button(label="Próxima Mão 🔁", emoji="🔄",
                       style=discord.ButtonStyle.blurple, custom_id="bj_next", row=1, disabled=True)
    async def next_hand(self, interaction, btn):
        if not self._check(interaction):
            return await interaction.response.send_message("Mesa de outro jogador.", ephemeral=True)
        await interaction.response.send_modal(ApostaModal(self.game, self.bot))

    @discord.ui.button(label="Encerrar Mesa", emoji="🚪",
                       style=discord.ButtonStyle.grey, custom_id="bj_quit", row=1)
    async def quit(self, interaction, btn):
        if not self._check(interaction):
            return await interaction.response.send_message("Mesa de outro jogador.", ephemeral=True)
        self.stop()
        for c in self.children: c.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("Mesa encerrada. Use `/blackjack` para abrir nova.", ephemeral=True)


class ApostaModal(discord.ui.Modal, title="Nova aposta"):
    valor = discord.ui.TextInput(
        label=f"Fichas ({APOSTA_MIN}–{APOSTA_MAX})",
        placeholder="ex: 100"
    )

    def __init__(self, game: BJGame, bot):
        super().__init__()
        self.game = game
        self.bot  = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            v = int(self.valor.value)
        except ValueError:
            return await interaction.response.send_message("Valor inválido.", ephemeral=True)
        if not APOSTA_MIN <= v <= APOSTA_MAX:
            return await interaction.response.send_message(
                f"Aposta entre {APOSTA_MIN} e {APOSTA_MAX}.", ephemeral=True)
        saldo = await get_saldo(self.bot, interaction.user)
        if saldo < v:
            return await interaction.response.send_message(
                f"Saldo insuficiente ({saldo:,} fichas).", ephemeral=True)
        await add_saldo(self.bot, interaction.user, -v)
        self.game.aposta = v
        self.game.deal()
        view  = BJView(self.game, self.bot)
        f     = view._render()
        embed = view._embed()

        # Blackjack natural?
        if self.game.blackjack_natural():
            premio = int(v * 1.5)
            self.game.result = f"🌟 BLACKJACK! +{premio} fichas!"
            self.game.fim    = True
            self.game.wins  += 1
            await add_saldo(self.bot, interaction.user, v + premio)
            view._sync()
            f = view._render()

        await interaction.response.edit_message(embed=embed, attachments=[f], view=view)


# ── Cog ───────────────────────────────────────────────────────────────────────
class Blackjack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="blackjack", description="Jogar Blackjack 21")
    @app_commands.describe(aposta="Fichas a apostar")
    async def cmd_bj(self, interaction: discord.Interaction, aposta: int):
        if not APOSTA_MIN <= aposta <= APOSTA_MAX:
            return await interaction.response.send_message(
                f"Aposta entre {APOSTA_MIN} e {APOSTA_MAX}.", ephemeral=True)
        saldo = await get_saldo(self.bot, interaction.user)
        if saldo < aposta:
            return await interaction.response.send_message(
                f"Saldo insuficiente. Você tem {saldo:,} fichas.", ephemeral=True)
        await add_saldo(self.bot, interaction.user, -aposta)
        game = BJGame(user=interaction.user, aposta=aposta)
        game.deal()
        view = BJView(game, self.bot)

        # Blackjack natural na abertura
        if game.blackjack_natural():
            premio = int(aposta * 1.5)
            game.result = f"🌟 BLACKJACK! +{premio} fichas!"
            game.fim    = True
            game.wins  += 1
            await add_saldo(self.bot, interaction.user, aposta + premio)
            view._sync()

        f     = view._render()
        embed = view._embed()
        await interaction.response.send_message(embed=embed, file=f, view=view)


async def setup(bot):
    await bot.add_cog(Blackjack(bot))
