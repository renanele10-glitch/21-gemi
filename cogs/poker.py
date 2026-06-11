"""
cogs/poker.py — Texas Hold'em. 2–6 jogadores. Painel persistente.
"""
import discord, random, asyncio
from discord import app_commands
from discord.ext import commands
from dataclasses import dataclass, field
from itertools import combinations
from .fichas import get_saldo, add_saldo
from .render import render_poker

SUITS = ["♠","♥","♦","♣"]
RANKS = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
RANK_V = {r:i for i,r in enumerate(RANKS)}

def _baralho():
    b = [(r,s) for r in RANKS for s in SUITS]
    random.shuffle(b); return b

def _rv(c): return RANK_V[c[0]]
def _suit(c): return c[1]

def _hand_rank(cards):
    cards = sorted(cards, key=_rv, reverse=True)
    ranks = [_rv(c) for c in cards]
    suits = [_suit(c) for c in cards]
    flush    = len(set(suits)) == 1
    straight = (ranks == list(range(ranks[0], ranks[0]-5, -1))
                or ranks == [12,3,2,1,0])
    cnt = {}
    for r in ranks: cnt[r] = cnt.get(r,0)+1
    grp  = sorted(cnt.items(), key=lambda x:(x[1],x[0]), reverse=True)
    gc   = [g[1] for g in grp]
    gv   = [g[0] for g in grp]
    if flush and straight:   return (8, ranks)
    if gc[0]==4:             return (7, gv)
    if gc[:2]==[3,2]:        return (6, gv)
    if flush:                return (5, ranks)
    if straight:             return (4, ranks)
    if gc[0]==3:             return (3, gv)
    if gc[:2]==[2,2]:        return (2, gv)
    if gc[0]==2:             return (1, gv)
    return (0, ranks)

def melhor_mao(hole, community):
    best = None
    for combo in combinations(hole+community, 5):
        hr = _hand_rank(list(combo))
        if best is None or hr > best: best = hr
    return best

HAND_NAMES = {8:"Royal/Straight Flush",7:"Quadra",6:"Full House",
              5:"Flush",4:"Sequência",3:"Trinca",2:"Dois Pares",1:"Par",0:"Carta Alta"}


@dataclass
class PKPlayer:
    user: discord.Member
    hole: list = field(default_factory=list)
    stack: int = 0
    bet:   int = 0
    status: str = "active"   # active|folded|all-in|winner
    dealer: bool = False
    acted: bool = False


@dataclass
class PKGame:
    canal: int
    jogadores: list = field(default_factory=list)
    community: list = field(default_factory=list)
    deck: list      = field(default_factory=_baralho)
    pot:  int       = 0
    fase: str       = "aguardando"   # aguardando|pre-flop|flop|turn|river|fim
    cur:  int       = 0
    cur_bet: int    = 0
    dealer_idx: int = 0
    msg: discord.Message | None = None

    def ativos(self): return [p for p in self.jogadores if p.status=="active"]
    def atual(self):
        a = self.ativos()
        return a[self.cur % len(a)] if a else None


mesas: dict[int, PKGame] = {}


async def _render_update(game: PKGame, current_name=""):
    if not game.msg: return
    players = [{
        "name": p.user.display_name,
        "cards": p.hole if p.status!="folded" else [("?","?"),("?","?")],
        "chips": p.stack,
        "bet":   p.bet,
        "status": p.status,
        "dealer": p.dealer,
    } for p in game.jogadores]
    buf = render_poker(game.community, players, game.pot, current_name)
    try:
        await game.msg.edit(attachments=[discord.File(buf,"poker.png")])
    except Exception: pass


async def _avancar_fase(game: PKGame, bot, interaction: discord.Interaction):
    fases = ["pre-flop","flop","turn","river","fim"]
    idx = fases.index(game.fase)
    if idx >= len(fases)-1:
        await _showdown(game, bot, interaction); return
    game.fase = fases[idx+1]
    game.cur_bet = 0
    game.cur     = 0
    for p in game.ativos(): p.bet = 0; p.acted = False
    if game.fase == "flop":
        game.community += [game.deck.pop() for _ in range(3)]
    elif game.fase in ("turn","river"):
        game.community.append(game.deck.pop())
    elif game.fase == "fim":
        await _showdown(game, bot, interaction); return
    a = game.ativos()
    if a:
        await _render_update(game, a[0].user.display_name)
        await interaction.followup.send(
            f"**{game.fase.upper()}** — vez de **{a[0].user.display_name}**",
            view=PKActionsView(game.canal, bot)
        )


async def _showdown(game: PKGame, bot, interaction: discord.Interaction):
    game.fase = "fim"
    ativos = game.ativos()
    if len(ativos) == 1:
        venc = ativos[0]
        venc.status = "winner"
        await add_saldo(bot, venc.user, game.pot)
        result = f"🏆 **{venc.user.display_name}** venceu **{game.pot:,} fichas** (todos foldaram)!"
    else:
        scores = [(p, melhor_mao(p.hole, game.community)) for p in ativos]
        scores.sort(key=lambda x: x[1], reverse=True)
        venc = scores[0][0]
        venc.status = "winner"
        await add_saldo(bot, venc.user, game.pot)
        hand_name = HAND_NAMES.get(scores[0][1][0], "")
        result = f"🏆 **{venc.user.display_name}** venceu **{game.pot:,} fichas** ({hand_name})!"

    await _render_update(game)
    await interaction.followup.send(result, view=PKNextView(game.canal, bot))


class PKActionsView(discord.ui.View):
    def __init__(self, canal, bot):
        super().__init__(timeout=None)
        self.canal = canal
        self.bot   = bot

    def _get_cur(self, uid):
        g = mesas.get(self.canal)
        if not g: return None, None
        a = g.ativos()
        if not a: return None, g
        c = a[g.cur % len(a)]
        if c.user.id != uid: return None, g
        return c, g

    async def _next_player(self, g: PKGame, interaction: discord.Interaction):
        a = g.ativos()
        if not a:
            await _showdown(g, self.bot, interaction); return
        g.cur = (g.cur+1) % len(a)
        # Checar se todos agiram e bets iguais
        bets_iguais = len(set(p.bet for p in a)) <= 1
        todos_agiram = all(p.acted for p in a)
        if bets_iguais and todos_agiram:
            await _avancar_fase(g, self.bot, interaction); return
        prox = a[g.cur % len(a)]
        await _render_update(g, prox.user.display_name)
        await interaction.followup.send(
            f"Vez de **{prox.user.display_name}**",
            view=PKActionsView(self.canal, self.bot)
        )

    @discord.ui.button(label="Check", emoji="✔️", style=discord.ButtonStyle.grey, custom_id="pk_check")
    async def check(self, interaction, btn):
        await interaction.response.defer()
        p, g = self._get_cur(interaction.user.id)
        if not p: return await interaction.followup.send("Não é sua vez.", ephemeral=True)
        if g.cur_bet > p.bet:
            return await interaction.followup.send("Há aposta pendente — use Call.", ephemeral=True)
        p.acted = True
        await self._next_player(g, interaction)

    @discord.ui.button(label="Call", emoji="📞", style=discord.ButtonStyle.green, custom_id="pk_call")
    async def call(self, interaction, btn):
        await interaction.response.defer()
        p, g = self._get_cur(interaction.user.id)
        if not p: return await interaction.followup.send("Não é sua vez.", ephemeral=True)
        diff = g.cur_bet - p.bet
        if diff <= 0:
            return await interaction.followup.send("Nada a igualar — use Check.", ephemeral=True)
        pagar = min(diff, p.stack)
        p.stack -= pagar; g.pot += pagar; p.bet += pagar
        await add_saldo(self.bot, p.user, -pagar)
        if p.stack == 0: p.status = "all-in"
        p.acted = True
        await self._next_player(g, interaction)

    @discord.ui.button(label="Raise", emoji="⬆️", style=discord.ButtonStyle.primary, custom_id="pk_raise")
    async def raise_btn(self, interaction, btn):
        await interaction.response.send_modal(RaiseModal(self.canal, self.bot))

    @discord.ui.button(label="Fold", emoji="🏳️", style=discord.ButtonStyle.red, custom_id="pk_fold")
    async def fold(self, interaction, btn):
        await interaction.response.defer()
        p, g = self._get_cur(interaction.user.id)
        if not p: return await interaction.followup.send("Não é sua vez.", ephemeral=True)
        p.status = "folded"
        a = g.ativos()
        if len(a) == 1:
            await _showdown(g, self.bot, interaction); return
        g.cur %= len(a)
        await self._next_player(g, interaction)


class RaiseModal(discord.ui.Modal, title="Raise — Total da sua aposta"):
    valor = discord.ui.TextInput(label="Valor total (incluindo call)", placeholder="ex: 200")

    def __init__(self, canal, bot):
        super().__init__()
        self.canal = canal; self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try: v = int(self.valor.value)
        except ValueError:
            return await interaction.followup.send("Valor inválido.", ephemeral=True)
        g = mesas.get(self.canal)
        if not g: return
        a = g.ativos()
        p = a[g.cur % len(a)]
        if p.user.id != interaction.user.id:
            return await interaction.followup.send("Não é sua vez.", ephemeral=True)
        diff = v - p.bet
        if diff <= 0 or p.stack < diff:
            return await interaction.followup.send("Valor inválido ou stack insuficiente.", ephemeral=True)
        p.stack -= diff; g.pot += diff; p.bet = v
        await add_saldo(self.bot, p.user, -diff)
        g.cur_bet = v
        for ap in a: ap.acted = False
        p.acted = True
        g.cur = (g.cur+1) % len(a)
        prox = a[g.cur % len(a)]
        await _render_update(g, prox.user.display_name)
        await interaction.followup.send(
            f"Raise para {v}! Vez de **{prox.user.display_name}**",
            view=PKActionsView(self.canal, self.bot)
        )


class PKNextView(discord.ui.View):
    def __init__(self, canal, bot):
        super().__init__(timeout=120)
        self.canal = canal; self.bot = bot

    @discord.ui.button(label="Nova Mão", emoji="🔄", style=discord.ButtonStyle.success)
    async def nova(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.get(self.canal)
        if not g: return
        g.deck = _baralho(); g.community = []; g.pot = 0
        g.fase = "pre-flop"; g.cur_bet = 0; g.cur = 0
        g.dealer_idx = (g.dealer_idx+1) % len(g.jogadores)
        for p in g.jogadores:
            p.hole=[]; p.bet=0; p.status="active"; p.dealer=False; p.acted=False
        await _iniciar_mao(g, self.bot, interaction)

    @discord.ui.button(label="Sair", emoji="🚪", style=discord.ButtonStyle.danger)
    async def sair(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        mesas.pop(self.canal, None)
        await interaction.followup.send("Mesa encerrada.")


class PKEntrarView(discord.ui.View):
    def __init__(self, canal, bot):
        super().__init__(timeout=120)
        self.canal = canal; self.bot = bot

    @discord.ui.button(label="Sentar na Mesa", emoji="🃏", style=discord.ButtonStyle.success)
    async def sentar(self, interaction, btn):
        await interaction.response.send_modal(PKBuyinModal(self.canal, self.bot))

    @discord.ui.button(label="Iniciar (min 2)", emoji="▶️", style=discord.ButtonStyle.primary)
    async def iniciar(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.get(self.canal)
        if not g or len(g.jogadores) < 2:
            return await interaction.followup.send("Mínimo 2 jogadores.", ephemeral=True)
        await _iniciar_mao(g, self.bot, interaction)


class PKBuyinModal(discord.ui.Modal, title="Buy-in (fichas para sentar)"):
    fichas = discord.ui.TextInput(label="Fichas", placeholder="ex: 500")

    def __init__(self, canal, bot):
        super().__init__()
        self.canal = canal; self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try: v = int(self.fichas.value)
        except ValueError:
            return await interaction.response.send_message("Valor inválido.", ephemeral=True)
        if v < 50:
            return await interaction.response.send_message("Mínimo 50 fichas.", ephemeral=True)
        saldo = await get_saldo(self.bot, interaction.user)
        if saldo < v:
            return await interaction.response.send_message(f"Saldo insuficiente ({saldo:,}).", ephemeral=True)
        g = mesas.get(self.canal)
        if not g or len(g.jogadores) >= 6 or any(p.user.id==interaction.user.id for p in g.jogadores):
            return await interaction.response.send_message("Não foi possível sentar.", ephemeral=True)
        await add_saldo(self.bot, interaction.user, -v)
        g.jogadores.append(PKPlayer(user=interaction.user, stack=v))
        await interaction.response.send_message(
            f"✅ {interaction.user.display_name} sentou com **{v:,} fichas**.", ephemeral=True)


async def _iniciar_mao(g: PKGame, bot, interaction: discord.Interaction):
    g.deck = _baralho(); g.community = []; g.pot = 0
    g.fase = "pre-flop"; g.cur_bet = 20; g.cur = 0

    n = len(g.jogadores)
    g.jogadores[g.dealer_idx % n].dealer = True

    # Small & big blind
    sb = (g.dealer_idx+1) % n
    bb = (g.dealer_idx+2) % n
    for idx, blind in [(sb,10),(bb,20)]:
        p = g.jogadores[idx]
        pagar = min(blind, p.stack)
        p.stack -= pagar; g.pot += pagar; p.bet = pagar
        await add_saldo(bot, p.user, -pagar)

    for p in g.jogadores:
        p.hole = [g.deck.pop(), g.deck.pop()]
        p.status = "active"; p.acted = False

    g.cur = (bb+1) % n
    players = [{"name":p.user.display_name,"cards":p.hole,"chips":p.stack,
                "bet":p.bet,"status":p.status,"dealer":p.dealer} for p in g.jogadores]
    buf = render_poker([], players, g.pot, g.jogadores[g.cur].user.display_name)
    msg = await interaction.channel.send(
        file=discord.File(buf,"poker.png"),
        view=PKActionsView(g.canal, bot)
    )
    g.msg = msg


class Poker(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name="poker", description="Abrir mesa de Texas Hold'em")
    async def cmd_poker(self, interaction: discord.Interaction):
        cid = interaction.channel_id
        if cid in mesas and mesas[cid].fase not in ("aguardando","fim"):
            return await interaction.response.send_message("Partida em andamento.", ephemeral=True)
        mesas[cid] = PKGame(canal=cid)
        await interaction.response.send_message(
            "🃏 **Texas Hold'em!** Máx 6 jogadores, mín 2.", view=PKEntrarView(cid, self.bot))


async def setup(bot):
    await bot.add_cog(Poker(bot))
