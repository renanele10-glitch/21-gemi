"""
cogs/blackjack.py — Blackjack 21. Painel persistente.
Mesa privada por jogador. Sem banco extra — usa fichas compartilhadas.

FIXES:
  - Stand agora faz flip animation DEPOIS mostra resultado (2 edições)
  - Split adicionado (quando primeiro par é igual)
  - Lógica de fichas revisada para garantir consistência
"""
import discord, random, asyncio
from discord import app_commands
from discord.ext import commands
from dataclasses import dataclass, field
from .fichas import get_saldo, add_saldo, registrar_resultado
from .render import render_blackjack
from .animator import gif_carta_nova, gif_flip_dealer, gif_resultado, gif_distribuicao
from .render import bj_posicoes

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
    mao2:   list = field(default_factory=list)   # split hand
    split_ativo: bool = False
    split_vez:   int  = 0   # 0 = mão principal, 1 = mão split
    fim:    bool = False
    result: str  = ""
    wins:   int  = 0
    losses: int  = 0
    ties:   int  = 0
    first:  bool = True

    def deal(self):
        if len(self.deck) < 15:
            self.deck = _baralho()
        self.dealer     = [self.deck.pop(), self.deck.pop()]
        self.mao        = [self.deck.pop(), self.deck.pop()]
        self.mao2       = []
        self.split_ativo = False
        self.split_vez   = 0
        self.fim         = False
        self.result      = ""

    def _dealer_joga(self):
        while _calcular(self.dealer) < 17:
            self.dealer.append(self.deck.pop())

    def _avaliar_mao(self, mao):
        pv = _calcular(mao)
        dv = _calcular(self.dealer)
        if pv > 21:
            self.losses += 1; return -self.aposta, "💥 Bust!"
        elif dv > 21:
            self.wins   += 1; return self.aposta,  "🎉 Dealer estourou!"
        elif pv > dv:
            self.wins   += 1; return self.aposta,  "🎉 Você venceu!"
        elif pv == dv:
            self.ties   += 1; return 0,            "🤝 Empate!"
        else:
            self.losses += 1; return -self.aposta, "😔 Dealer venceu."

    def _finalizar(self):
        self.fim = True
        self._dealer_joga()
        if self.split_ativo:
            d1, r1 = self._avaliar_mao(self.mao)
            d2, r2 = self._avaliar_mao(self.mao2)
            self.result = f"{r1} (mão 1)  |  {r2} (mão 2)"
            return d1 + d2
        else:
            delta, msg = self._avaliar_mao(self.mao)
            self.result = msg
            return delta

    def hit(self):
        mao_atual = self.mao2 if (self.split_ativo and self.split_vez==1) else self.mao
        mao_atual.append(self.deck.pop())
        if _calcular(mao_atual) > 21:
            if self.split_ativo and self.split_vez == 0:
                # Bust na mão 1 → passa pra mão 2
                self.split_vez = 1
                return None
            return self._finalizar()
        return None

    def stand(self):
        if self.split_ativo and self.split_vez == 0:
            self.split_vez = 1
            return None   # vai jogar mão 2
        return self._finalizar()

    def double(self, aposta_extra):
        self.aposta += aposta_extra
        mao_atual = self.mao2 if (self.split_ativo and self.split_vez==1) else self.mao
        mao_atual.append(self.deck.pop())
        return self._finalizar()

    def surrender(self):
        self.result = "🏳️ Você rendeu-se. Metade da aposta devolvida."
        self.fim    = True
        self.losses += 1
        return -(self.aposta // 2)

    def pode_split(self):
        return (not self.split_ativo
                and len(self.mao) == 2
                and self.mao[0][0] == self.mao[1][0])

    def fazer_split(self, aposta_extra):
        """Divide a mão em duas. Retorna True se ok."""
        self.mao2        = [self.mao.pop()]
        self.mao.append(self.deck.pop())
        self.mao2.append(self.deck.pop())
        self.split_ativo = True
        self.split_vez   = 0
        self.aposta     += aposta_extra   # apostou igual na segunda mão

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
        g = self.game
        for c in self.children:
            if c.custom_id in ("bj_hit","bj_stand"):
                c.disabled = g.fim
            elif c.custom_id in ("bj_double","bj_surrender"):
                c.disabled = g.fim or len(g.mao) != 2
            elif c.custom_id == "bj_split":
                c.disabled = g.fim or not g.pode_split()
            elif c.custom_id == "bj_next":
                c.disabled = not g.fim

    def _render(self, animated=False, anim_type=None, new_card=None, reveal_pos=None):
        from PIL import Image
        g = self.game
        pv = _calcular(g.mao)
        dv = _calcular(g.dealer)

        base_buf = render_blackjack(g.dealer, dv, g.mao, pv,
                                    reveal_dealer=g.fim, result="", mobile=True)
        base_img = Image.open(base_buf).convert("RGB")

        if not animated or anim_type is None:
            buf = render_blackjack(g.dealer, dv, g.mao, pv,
                                   reveal_dealer=g.fim, result=g.result, mobile=True)
            return discord.File(buf, "blackjack.png")

        elif anim_type == "hit" and new_card:
            rank, suit = new_card
            pos_d, pos_j, _ = bj_posicoes(g.dealer, g.mao)
            if pos_j:
                px, py, cw2, ch2 = pos_j[-1]
                buf = gif_carta_nova(base_img, px, py, rank, suit, cw2, ch2)
                return discord.File(buf, "blackjack.gif")

        elif anim_type == "flip" and reveal_pos:
            pos_d, pos_j, _ = bj_posicoes(g.dealer, g.mao)
            if pos_d:
                px, py, cw2, ch2 = pos_d[0]
                rank, suit = g.dealer[0]
                buf = gif_flip_dealer(base_img, px, py, rank, suit, cw2, ch2)
                return discord.File(buf, "blackjack.gif")

        elif anim_type == "deal":
            pos_d, pos_j, _ = bj_posicoes(g.dealer, g.mao)
            buf = gif_distribuicao(base_img, g.mao, g.dealer, pos_j, pos_d)
            return discord.File(buf, "blackjack.gif")

        elif anim_type == "result":
            res_col = (80,220,80) if "venceu" in g.result or "BLACKJACK" in g.result else (220,80,80)
            if "Empate" in g.result or "empate" in g.result:
                res_col = (200,200,80)
            buf = gif_resultado(base_img, g.result, cor=res_col)
            return discord.File(buf, "blackjack.gif")

        # fallback
        buf = render_blackjack(g.dealer, dv, g.mao, pv, reveal_dealer=g.fim, result=g.result, mobile=True)
        return discord.File(buf, "blackjack.png")

    def _embed(self, gif=False):
        g = self.game
        ext = "gif" if gif else "png"
        mao2_str = ""
        if g.split_ativo:
            v2 = _calcular(g.mao2)
            mao2_str = f"\n🂠 Mão 2: **{v2}** pts"
        embed = discord.Embed(title="🃏 Blackjack 21", color=0x1a0005)
        embed.description = (
            f"**{g.user.display_name}** — "
            f"✅ {g.wins}  ❌ {g.losses}  🤝 {g.ties}\n"
            f"Aposta atual: **{g.aposta:,} fichas**"
            + mao2_str
        )
        embed.set_image(url=f"attachment://blackjack.{ext}")
        embed.set_footer(text="Próxima Mão para continuar." if g.fim else "Boa sorte!")
        return embed

    async def _update(self, interaction: discord.Interaction, delta: int | None = None,
                      anim_type=None, new_card=None):
        if delta is not None:
            # delta é o lucro/prejuízo líquido. A aposta já foi descontada no início.
            # Aqui devolvemos: aposta (sempre) + lucro se ganhou, ou aposta - prejuízo se perdeu.
            # Como delta já representa isso (ex: +aposta ganhou, -aposta perdeu, 0 empate),
            # basta devolver aposta + delta.
            await add_saldo(self.bot, self.game.user, self.game.aposta + delta)
            await registrar_resultado(self.bot, self.game.user, delta > 0)
        self._sync()
        use_anim = anim_type is not None
        f = self._render(animated=use_anim, anim_type=anim_type, new_card=new_card, reveal_pos=True)
        await interaction.response.edit_message(
            embed=self._embed(gif=use_anim), attachments=[f], view=self
        )

    def _check(self, i): return i.user.id == self.game.user.id

    @discord.ui.button(label="Pedir", emoji="🃏",
                       style=discord.ButtonStyle.green, custom_id="bj_hit", row=0)
    async def hit(self, interaction, btn):
        if not self._check(interaction):
            return await interaction.response.send_message("Mesa de outro jogador.", ephemeral=True)
        deck_antes = len(self.game.mao)
        delta = self.game.hit()
        nova = self.game.mao[-1] if len(self.game.mao) > deck_antes else None
        anim = "result" if self.game.fim else "hit"
        await self._update(interaction, delta, anim_type=anim, new_card=nova)

    @discord.ui.button(label="Manter", emoji="✋",
                       style=discord.ButtonStyle.grey, custom_id="bj_stand", row=0)
    async def stand(self, interaction, btn):
        if not self._check(interaction):
            return await interaction.response.send_message("Mesa de outro jogador.", ephemeral=True)
        delta = self.game.stand()
        if delta is None:
            # Split: passou para mão 2, sem fim ainda
            self._sync()
            f = self._render()
            embed = self._embed()
            embed.set_footer(text="Jogando mão 2 do split…")
            await interaction.response.edit_message(embed=embed, attachments=[f], view=self)
            return
        # FIX: stand faz flip primeiro, depois result em followup
        self._sync()
        f_flip = self._render(animated=True, anim_type="flip", reveal_pos=True)
        await interaction.response.edit_message(
            embed=self._embed(gif=True), attachments=[f_flip], view=self
        )
        await asyncio.sleep(1.2)
        # Agora credita e mostra resultado
        await add_saldo(self.bot, self.game.user, self.game.aposta + delta)
        await registrar_resultado(self.bot, self.game.user, delta > 0)
        f_res = self._render(animated=True, anim_type="result")
        await interaction.edit_original_response(
            embed=self._embed(gif=True), attachments=[f_res], view=self
        )

    @discord.ui.button(label="Dobrar", emoji="2️⃣",
                       style=discord.ButtonStyle.blurple, custom_id="bj_double", row=0)
    async def double(self, interaction, btn):
        if not self._check(interaction):
            return await interaction.response.send_message("Mesa de outro jogador.", ephemeral=True)
        saldo = await get_saldo(self.bot, interaction.user)
        extra = min(self.game.aposta, saldo)
        if extra <= 0:
            return await interaction.response.send_message("Fichas insuficientes para dobrar.", ephemeral=True)
        await add_saldo(self.bot, interaction.user, -extra)
        nova_antes = len(self.game.mao)
        delta = self.game.double(extra)
        nova = self.game.mao[-1] if len(self.game.mao) > nova_antes else None
        await self._update(interaction, delta, anim_type="result", new_card=nova)

    @discord.ui.button(label="Split", emoji="✂️",
                       style=discord.ButtonStyle.blurple, custom_id="bj_split", row=0)
    async def split(self, interaction, btn):
        if not self._check(interaction):
            return await interaction.response.send_message("Mesa de outro jogador.", ephemeral=True)
        if not self.game.pode_split():
            return await interaction.response.send_message("Split só com par inicial.", ephemeral=True)
        saldo = await get_saldo(self.bot, interaction.user)
        extra = self.game.aposta
        if saldo < extra:
            return await interaction.response.send_message(
                f"Fichas insuficientes para split (precisa +{extra:,}).", ephemeral=True)
        await add_saldo(self.bot, interaction.user, -extra)
        self.game.fazer_split(extra)
        self._sync()
        f = self._render()
        embed = self._embed()
        embed.set_footer(text="Split feito! Jogando mão 1…")
        await interaction.response.edit_message(embed=embed, attachments=[f], view=self)

    @discord.ui.button(label="Correr", emoji="🏳️",
                       style=discord.ButtonStyle.red, custom_id="bj_surrender", row=0)
    async def surrender(self, interaction, btn):
        if not self._check(interaction):
            return await interaction.response.send_message("Mesa de outro jogador.", ephemeral=True)
        delta = self.game.surrender()
        await self._update(interaction, delta, anim_type="result")

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

        if self.game.blackjack_natural():
            premio = int(v * 1.5)
            self.game.result = f"🌟 BLACKJACK! +{premio} fichas!"
            self.game.fim    = True
            self.game.wins  += 1
            await add_saldo(self.bot, interaction.user, v + premio)
            await registrar_resultado(self.bot, interaction.user, True)
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

        if game.blackjack_natural():
            premio = int(aposta * 1.5)
            game.result = f"🌟 BLACKJACK! +{premio} fichas!"
            game.fim    = True
            game.wins  += 1
            await add_saldo(self.bot, interaction.user, aposta + premio)
            await registrar_resultado(self.bot, interaction.user, True)
            view._sync()

        f     = view._render()
        embed = view._embed()
        await interaction.response.send_message(embed=embed, file=f, view=view)


async def setup(bot):
    await bot.add_cog(Blackjack(bot))
