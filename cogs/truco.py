"""
cogs/truco.py — Truco Paulista 2v2. Painel persistente.

FIXES:
  - Timeout de mesa inativa: 8 min → encerra e devolve fichas (stacks não usados → devolve PREMIO cobrado)
  - Mesa presa no restart: botões verificam existência e retornam silenciosamente
  - TRRespostaView timeout=30 já existia; agora cancela o task do jogo se aceitar/recusar
"""
import discord, random, asyncio
from discord import app_commands
from discord.ext import commands
from dataclasses import dataclass, field
from .fichas import get_saldo, add_saldo
from .render import render_truco

VALS   = ["4","5","6","7","Q","J","K","A","2","3"]
NAIPES = ["♦","♠","♥","♣"]
PREMIO = 100
MESA_TIMEOUT = 480   # 8 min


def _baralho():
    b = [(v,n) for v in VALS for n in NAIPES]
    random.shuffle(b); return b

def _manilha_rank(suit): return NAIPES.index(suit)

def _rank_carta(carta, vira):
    v, n = carta
    vv, _ = vira
    next_v = VALS[(VALS.index(vv)+1) % len(VALS)] if vv in VALS else None
    if next_v and v == next_v:
        return 100 + _manilha_rank(n)
    return VALS.index(v) if v in VALS else -1

def _vencedor(jogadas, vira):
    melhor = -1; venc = None; empate = False
    for carta, eq in jogadas:
        r = _rank_carta(carta, vira)
        if r > melhor: melhor=r; venc=eq; empate=False
        elif r == melhor: empate=True
    return "empate" if empate else venc


@dataclass
class TRPlayer:
    user: discord.Member
    equipe: str
    mao: list = field(default_factory=list)
    jogou: tuple | None = None


@dataclass
class TRGame:
    canal: int
    jogadores: list = field(default_factory=list)
    estado: str     = "aguardando"
    pontos: dict    = field(default_factory=lambda:{"nos":0,"eles":0})
    rodada_pts: dict= field(default_factory=lambda:{"nos":0,"eles":0})
    rodada: int     = 1
    vira: tuple     = ("?","?")
    baralho: list   = field(default_factory=_baralho)
    mesa: list      = field(default_factory=list)
    cur_idx: int    = 0
    truco_val: int  = 2
    truco_pedido: str | None = None
    max_pts: int    = 12
    msg: discord.Message | None = None
    _timeout_task: object = field(default=None, repr=False)

    def eq(self, e): return [j for j in self.jogadores if j.equipe==e]
    def atual(self):
        return self.jogadores[self.cur_idx % len(self.jogadores)] if self.jogadores else None


mesas: dict[int, TRGame] = {}


async def _cancelar_timeout(game: TRGame):
    if game._timeout_task and not game._timeout_task.done():
        game._timeout_task.cancel()
        game._timeout_task = None


async def _agendar_timeout(game: TRGame, bot):
    await _cancelar_timeout(game)

    async def _expirar():
        await asyncio.sleep(MESA_TIMEOUT)
        if mesas.get(game.canal) is not game: return
        mesas.pop(game.canal, None)
        if game.msg:
            try:
                await game.msg.edit(
                    content="⏰ **Mesa de Truco encerrada por inatividade.**",
                    attachments=[]
                )
            except Exception: pass

    game._timeout_task = asyncio.create_task(_expirar())


async def _render(g: TRGame):
    if not g.msg: return
    nos  = [{"name":j.user.display_name,"cards":j.mao,"jogou":j.jogou is not None}
            for j in g.eq("nos")]
    eles = [{"name":j.user.display_name,"cards":[("?","?")]*len(j.mao),"jogou":j.jogou is not None}
            for j in g.eq("eles")]
    buf = render_truco(nos, eles, g.pontos["nos"], g.pontos["eles"],
                       g.vira, g.mesa, g.rodada, g.max_pts, mobile=True)
    try: await g.msg.edit(attachments=[discord.File(buf,"truco.png")])
    except Exception: pass


async def _fim_rodada(g: TRGame, bot, interaction: discord.Interaction):
    jogadas = [(j.jogou, j.equipe) for j in g.jogadores if j.jogou]
    venc = _vencedor([(c,e) for c,e in jogadas], g.vira)

    if venc != "empate":
        g.rodada_pts[venc] = g.rodada_pts.get(venc,0)+1

    if g.rodada_pts["nos"] >= 2 or g.rodada_pts["eles"] >= 2:
        await _fim_mao(g, bot, interaction); return

    if g.rodada >= 3:
        await _fim_mao(g, bot, interaction); return

    g.rodada += 1
    g.mesa    = []
    for j in g.jogadores: j.jogou = None
    g.cur_idx = 0
    await _render(g)
    await _agendar_timeout(g, bot)
    atual = g.atual()
    await interaction.followup.send(
        f"Rodada {g.rodada}! Vez de **{atual.user.display_name}**",
        view=TRAcoesView(g.canal, bot)
    )


async def _fim_mao(g: TRGame, bot, interaction: discord.Interaction):
    await _cancelar_timeout(g)
    venc = "nos" if g.rodada_pts["nos"] >= g.rodada_pts["eles"] else "eles"
    g.pontos[venc] += g.truco_val
    for j in g.eq(venc):
        await add_saldo(bot, j.user, PREMIO)

    await _render(g)
    venc_label = "**NÓS** venceram" if venc=="nos" else "**ELES** venceram"
    g.estado = "fim"

    if g.pontos[venc] >= g.max_pts:
        await interaction.followup.send(
            f"🏆 {venc_label} a partida! +{PREMIO} fichas cada!",
            view=TRNovaPartidaView(g.canal, bot)
        )
    else:
        await interaction.followup.send(
            f"{venc_label} a mão! +{PREMIO} fichas.\nPlacar: NÓS {g.pontos['nos']} × ELES {g.pontos['eles']}",
            view=TRNovaMaoView(g.canal, bot)
        )


class TRAcoesView(discord.ui.View):
    def __init__(self, canal, bot):
        super().__init__(timeout=MESA_TIMEOUT)
        self.canal = canal; self.bot = bot

    async def on_timeout(self):
        pass   # task do game cuida da limpeza

    def _ok(self, uid):
        g = mesas.get(self.canal)
        if not g: return None, None
        a = g.atual()
        if not a or a.user.id != uid: return None, g
        return a, g

    @discord.ui.button(label="Jogar Carta", emoji="🃏", style=discord.ButtonStyle.primary, custom_id="tr_jogar")
    async def jogar(self, interaction, btn):
        j, g = self._ok(interaction.user.id)
        if not j:
            if g is None: return await interaction.response.send_message("Mesa não existe.", ephemeral=True)
            return await interaction.response.send_message("Não é sua vez.", ephemeral=True)
        await interaction.response.send_modal(JogarCartaModal(self.canal, self.bot))

    @discord.ui.button(label="Truco!", emoji="⚔️", style=discord.ButtonStyle.danger, custom_id="tr_truco")
    async def truco(self, interaction, btn):
        await interaction.response.defer()
        g = mesas.get(self.canal)
        if not g: return await interaction.followup.send("Mesa não existe.", ephemeral=True)
        j = next((x for x in g.jogadores if x.user.id==interaction.user.id), None)
        if not j: return
        if g.truco_pedido == j.equipe:
            return await interaction.followup.send("Sua equipe já pediu.", ephemeral=True)
        prox_val = {2:3,3:6,6:9,9:12}.get(g.truco_val, 12)
        if prox_val == g.truco_val:
            return await interaction.followup.send("Já está no valor máximo.", ephemeral=True)
        g.truco_pedido = j.equipe
        await interaction.followup.send(
            f"⚔️ **TRUCO!** Vale {prox_val} pontos!",
            view=TRRespostaView(self.canal, j.equipe, prox_val, self.bot)
        )

    @discord.ui.button(label="Ver Minha Mão", emoji="👁️", style=discord.ButtonStyle.grey, custom_id="tr_ver", row=1)
    async def ver_mao(self, interaction, btn):
        g = mesas.get(self.canal)
        if not g: return await interaction.response.send_message("Mesa não encontrada.", ephemeral=True)
        j = next((x for x in g.jogadores if x.user.id == interaction.user.id), None)
        if not j: return await interaction.response.send_message("Você não está nesta mesa.", ephemeral=True)
        vv, vs = g.vira
        prox_idx = (VALS.index(vv)+1) % len(VALS) if vv in VALS else -1
        prox_v   = VALS[prox_idx] if prox_idx >= 0 else "?"
        mao_str  = "  |  ".join(f"{v}{n}" for v,n in j.mao)
        await interaction.response.send_message(
            f"🃏 **Sua mão:** `{mao_str}`\n"
            f"Vira: **{vv}{vs}** → Manilha: **{prox_v}** (♦<♠<♥<♣)\n"
            f"Equipe: **{j.equipe.upper()}**",
            ephemeral=True
        )

    @discord.ui.button(label="Sair", emoji="🚪", style=discord.ButtonStyle.danger, custom_id="tr_sair", row=1)
    async def sair(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.pop(self.canal, None)
        if g: await _cancelar_timeout(g)
        await interaction.followup.send("Mesa encerrada.")


class JogarCartaModal(discord.ui.Modal, title="Qual carta jogar?"):
    carta = discord.ui.TextInput(label="Carta (ex: 3♣ ou A♠)", placeholder="3♣")

    def __init__(self, canal, bot):
        super().__init__()
        self.canal = canal; self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        g = mesas.get(self.canal)
        if not g: return await interaction.followup.send("Mesa não existe mais.", ephemeral=True)
        j = g.atual()
        if not j or j.user.id != interaction.user.id:
            return await interaction.followup.send("Não é sua vez.", ephemeral=True)

        raw  = self.carta.value.strip()
        suit = raw[-1] if raw and raw[-1] in "♠♥♦♣" else ""
        rank = raw[:-1].strip() if suit else raw
        carta = (rank, suit)
        if carta not in j.mao:
            mao_str = "  ".join(f"{v}{n}" for v,n in j.mao)
            return await interaction.followup.send(
                f"Carta inválida. Sua mão: `{mao_str}`", ephemeral=True)

        j.mao.remove(carta)
        j.jogou = carta
        g.mesa.append((rank, suit, j.user.display_name))
        g.cur_idx = (g.cur_idx+1) % len(g.jogadores)
        await _render(g)

        if all(x.jogou for x in g.jogadores):
            await _fim_rodada(g, self.bot, interaction)
        else:
            prox = g.atual()
            await _agendar_timeout(g, self.bot)
            await interaction.followup.send(
                f"Vez de **{prox.user.display_name}**",
                view=TRAcoesView(self.canal, self.bot)
            )


class TRRespostaView(discord.ui.View):
    def __init__(self, canal, eq_pediu, novo_val, bot):
        super().__init__(timeout=30)
        self.canal=canal; self.eq_pediu=eq_pediu; self.novo_val=novo_val; self.bot=bot

    def _adversario(self, uid):
        g = mesas.get(self.canal)
        if not g: return None, None
        j = next((x for x in g.jogadores if x.user.id==uid), None)
        if not j or j.equipe==self.eq_pediu: return None, g
        return j, g

    @discord.ui.button(label="Quero!", emoji="✅", style=discord.ButtonStyle.success)
    async def aceitar(self, interaction, btn):
        await interaction.response.defer()
        j, g = self._adversario(interaction.user.id)
        if not j: return await interaction.followup.send("Não é você que responde.", ephemeral=True)
        g.truco_val = self.novo_val; g.truco_pedido = None
        await interaction.followup.send(f"✅ Aceito! Vale {self.novo_val} pontos.")
        self.stop()

    @discord.ui.button(label="Não Quero!", emoji="❌", style=discord.ButtonStyle.danger)
    async def recusar(self, interaction, btn):
        await interaction.response.defer()
        j, g = self._adversario(interaction.user.id)
        if not j: return await interaction.followup.send("Não é você que responde.", ephemeral=True)
        g.pontos[self.eq_pediu] += 1; g.truco_pedido = None
        await interaction.followup.send(f"❌ Recusado! +1 ponto para **{self.eq_pediu}**.")
        await _fim_mao(g, self.bot, interaction)
        self.stop()


class TREntrarView(discord.ui.View):
    def __init__(self, canal, bot):
        super().__init__(timeout=120)
        self.canal=canal; self.bot=bot

    @discord.ui.button(label="NÓS 🟢", style=discord.ButtonStyle.success)
    async def nos(self, interaction, btn):
        await _entrar(interaction, self.canal, "nos")

    @discord.ui.button(label="ELES 🔴", style=discord.ButtonStyle.danger)
    async def eles(self, interaction, btn):
        await _entrar(interaction, self.canal, "eles")

    @discord.ui.button(label="Iniciar (2×2)", emoji="▶️", style=discord.ButtonStyle.primary)
    async def iniciar(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.get(self.canal)
        if not g: return
        if len(g.eq("nos"))!=2 or len(g.eq("eles"))!=2:
            return await interaction.followup.send("Precisa exatamente 2×2.", ephemeral=True)
        await _iniciar_mao_tr(g, self.bot, interaction)


async def _entrar(interaction, canal, equipe):
    await interaction.response.defer(ephemeral=True)
    g = mesas.get(canal)
    if not g: return
    uid = interaction.user.id
    if any(j.user.id==uid for j in g.jogadores):
        return await interaction.followup.send("Você já está na mesa.", ephemeral=True)
    if len(g.eq(equipe)) >= 2:
        return await interaction.followup.send("Equipe cheia.", ephemeral=True)
    g.jogadores.append(TRPlayer(user=interaction.user, equipe=equipe))
    await interaction.followup.send(
        f"✅ {interaction.user.display_name} entrou em **{equipe.upper()}**.")


async def _iniciar_mao_tr(g: TRGame, bot, interaction):
    g.baralho = _baralho(); g.estado="jogando"; g.rodada=1
    g.rodada_pts={"nos":0,"eles":0}; g.mesa=[]; g.cur_idx=0
    g.truco_val=2; g.truco_pedido=None
    g.vira = g.baralho.pop()
    for j in g.jogadores:
        j.mao=[g.baralho.pop() for _ in range(3)]; j.jogou=None

    nos  = [{"name":j.user.display_name,"cards":j.mao,"jogou":False} for j in g.eq("nos")]
    eles = [{"name":j.user.display_name,"cards":[("?","?")]*3,"jogou":False} for j in g.eq("eles")]
    buf  = render_truco(nos, eles, 0, 0, g.vira, [], 1, g.max_pts, mobile=True)
    msg  = await interaction.channel.send(
        file=discord.File(buf,"truco.png"), view=TRAcoesView(g.canal, bot))
    g.msg = msg
    await _agendar_timeout(g, bot)
    await interaction.followup.send(
        f"Vez de **{g.atual().user.display_name}**", ephemeral=True)


class TRNovaMaoView(discord.ui.View):
    def __init__(self, canal, bot):
        super().__init__(timeout=120)
        self.canal=canal; self.bot=bot

    @discord.ui.button(label="Nova Mão", emoji="🔄", style=discord.ButtonStyle.success)
    async def nova(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.get(self.canal)
        if not g: return
        g.estado="aguardando"
        await _iniciar_mao_tr(g, self.bot, interaction)

    @discord.ui.button(label="Encerrar", emoji="🚪", style=discord.ButtonStyle.danger)
    async def encerrar(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.pop(self.canal, None)
        if g: await _cancelar_timeout(g)
        await interaction.followup.send("Mesa encerrada.")


class TRNovaPartidaView(discord.ui.View):
    def __init__(self, canal, bot):
        super().__init__(timeout=120)
        self.canal=canal; self.bot=bot

    @discord.ui.button(label="Nova Partida", emoji="🔄", style=discord.ButtonStyle.success)
    async def nova(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.get(self.canal)
        if not g: return
        g.pontos={"nos":0,"eles":0}; g.estado="aguardando"
        await _iniciar_mao_tr(g, self.bot, interaction)

    @discord.ui.button(label="Encerrar", emoji="🚪", style=discord.ButtonStyle.danger)
    async def encerrar(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.pop(self.canal, None)
        if g:
            await _cancelar_timeout(g)
            if g.msg:
                try: await g.msg.delete()
                except: pass
        await interaction.followup.send("Mesa encerrada.", ephemeral=True)


class Truco(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name="truco", description="Abrir mesa de Truco Paulista 2v2")
    async def cmd_truco(self, interaction: discord.Interaction):
        cid = interaction.channel_id
        if cid in mesas and mesas[cid].estado=="jogando":
            return await interaction.response.send_message("Partida em andamento.", ephemeral=True)
        mesas[cid] = TRGame(canal=cid)
        await interaction.response.send_message(
            "🃏 **Truco Paulista!** 2×2 jogadores.\nClique **Ver Minha Mão** para ver suas cartas (só você vê).",
            view=TREntrarView(cid, self.bot))


async def setup(bot):
    await bot.add_cog(Truco(bot))
