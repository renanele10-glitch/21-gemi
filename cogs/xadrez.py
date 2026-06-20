"""
cogs/xadrez.py — Xadrez v5: Ephemeral select menu (sem threads).

Fluxo:
  1. /xadrez [aposta] → XZEntrarView no canal
  2. Dois jogadores escolhem lado
  3. Bot posta tabuleiro público no canal
  4. Bot manda mensagem pública "Vez de X — clique para jogar"
     com botão que abre select menu EPHEMERAL só pro jogador da vez
  5. Jogador escolhe peça → escolhe destino (tudo ephemeral, só ele vê)
  6. Tabuleiro público atualiza a cada jogada
"""
import discord, asyncio
from discord import app_commands
from discord.ext import commands
from dataclasses import dataclass, field
from .render import render_xadrez
from .fichas import get_saldo, add_saldo, registrar_resultado

INICIO = [
    list("rnbqkbnr"),
    list("pppppppp"),
    list("........"),
    list("........"),
    list("........"),
    list("........"),
    list("PPPPPPPP"),
    list("RNBQKBNR"),
]
MESA_TIMEOUT = 900
PECAS_NOMES  = {"p":"Peão","r":"Torre","n":"Cavalo","b":"Bispo","q":"Rainha","k":"Rei"}
users_em_jogo: set[int] = set()


# ── Engine ────────────────────────────────────────────────────────────────────
def _cp(b): return [r[:] for r in b]
def _wh(p): return p != "." and p.isupper()
def _bl(p): return p != "." and p.islower()
def _en(p, w): return _bl(p) if w else _wh(p)
def _fr(p, w): return _wh(p) if w else _bl(p)
def _sc(r, c): return f"{chr(97+c)}{8-r}"

def _slide(b, r, c, w, dirs):
    mvs = []
    for dr, dc in dirs:
        nr, nc = r+dr, c+dc
        while 0<=nr<8 and 0<=nc<8:
            if b[nr][nc] == ".": mvs.append((nr,nc))
            elif _en(b[nr][nc],w): mvs.append((nr,nc)); break
            else: break
            nr+=dr; nc+=dc
    return mvs

def _legal_raw(b, r, c, w):
    p = b[r][c].lower()
    if p == "p":
        mvs=[]; d=-1 if w else 1; sr=6 if w else 1
        nr=r+d
        if 0<=nr<8:
            if b[nr][c]==".":
                mvs.append((nr,c))
                if r==sr and b[r+2*d][c]==".": mvs.append((r+2*d,c))
            for dc in(-1,1):
                if 0<=c+dc<8 and _en(b[nr][c+dc],w): mvs.append((nr,c+dc))
        return mvs
    if p=="r": return _slide(b,r,c,w,[(0,1),(0,-1),(1,0),(-1,0)])
    if p=="b": return _slide(b,r,c,w,[(1,1),(1,-1),(-1,1),(-1,-1)])
    if p=="q": return _slide(b,r,c,w,[(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)])
    if p=="n": return [(r+dr,c+dc) for dr,dc in[(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]
                       if 0<=r+dr<8 and 0<=c+dc<8 and not _fr(b[r+dr][c+dc],w)]
    if p=="k": return [(r+dr,c+dc) for dr in(-1,0,1) for dc in(-1,0,1)
                       if(dr or dc) and 0<=r+dr<8 and 0<=c+dc<8 and not _fr(b[r+dr][c+dc],w)]
    return []

def _king(b, w):
    k="K" if w else "k"
    for r in range(8):
        for c in range(8):
            if b[r][c]==k: return r,c
    return None

def _in_check(b, w):
    pos=_king(b,w)
    if not pos: return False
    kr,kc=pos
    for r in range(8):
        for c in range(8):
            p=b[r][c]
            if (w and _bl(p)) or (not w and _wh(p)):
                if (kr,kc) in _legal_raw(b,r,c,not w): return True
    return False

def _move(b, r1, c1, r2, c2):
    nb=_cp(b); p=nb[r1][c1]
    nb[r2][c2]=p; nb[r1][c1]="."
    if p=="P" and r2==0: nb[r2][c2]="Q"
    if p=="p" and r2==7: nb[r2][c2]="q"
    return nb

def _legal(b, r, c, w):
    return [(nr,nc) for nr,nc in _legal_raw(b,r,c,w)
            if not _in_check(_move(b,r,c,nr,nc),w)]

def _all_legal(b, w):
    mvs=[]
    for r in range(8):
        for c in range(8):
            p=b[r][c]
            if (w and _wh(p)) or (not w and _bl(p)):
                for nr,nc in _legal(b,r,c,w): mvs.append((r,c,nr,nc))
    return mvs

def _checkmate(b,w): return _in_check(b,w) and not _all_legal(b,w)
def _stalemate(b,w): return not _in_check(b,w) and not _all_legal(b,w)

def _pecas_moviveis(b, w):
    result=[]
    for r in range(8):
        for c in range(8):
            p=b[r][c]
            if (w and _wh(p)) or (not w and _bl(p)):
                if _legal(b,r,c,w): result.append((r,c))
    return result

def _emoji_peca(p):
    return {"P":"♙","R":"♖","N":"♘","B":"♗","Q":"♕","K":"♔",
            "p":"♟","r":"♜","n":"♞","b":"♝","q":"♛","k":"♚"}.get(p,"♟")


# ── Dataclass ─────────────────────────────────────────────────────────────────
@dataclass
class XZGame:
    canal: int
    brancas: discord.Member | None = None
    pretas:  discord.Member | None = None
    board:   list = field(default_factory=lambda: _cp(INICIO))
    vez:     str  = "white"
    estado:  str  = "aguardando"
    aposta:  int  = 0
    last_move: tuple | None = None
    sel_peca:  tuple | None = None   # peça selecionada pelo jogador atual
    msg_tab: discord.Message | None = None   # tabuleiro público
    msg_vez: discord.Message | None = None   # "vez de X — clique para jogar"
    _timeout_task: object = field(default=None, repr=False)


mesas: dict[int, XZGame] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────
async def _cancelar_timeout(g: XZGame):
    if g._timeout_task and not g._timeout_task.done():
        g._timeout_task.cancel()

async def _agendar_timeout(g: XZGame, bot):
    await _cancelar_timeout(g)
    async def _exp():
        await asyncio.sleep(MESA_TIMEOUT)
        if mesas.get(g.canal) is not g: return
        if g.aposta > 0:
            for j in [g.brancas, g.pretas]:
                if j: await add_saldo(bot, j, g.aposta)
        for j in [g.brancas, g.pretas]:
            if j: users_em_jogo.discard(j.id)
        mesas.pop(g.canal, None)
        if g.msg_tab:
            try: await g.msg_tab.edit(
                content="⏰ Partida encerrada por inatividade. Apostas devolvidas.",
                attachments=[])
            except: pass
        if g.msg_vez:
            try: await g.msg_vez.delete()
            except: pass
    g._timeout_task = asyncio.create_task(_exp())

async def _render_publico(g: XZGame):
    if not g.msg_tab: return
    bn = g.brancas.display_name if g.brancas else "Brancas"
    pn = g.pretas.display_name  if g.pretas  else "Pretas"
    buf = render_xadrez(g.board, bn, pn, g.vez, last_move=g.last_move)
    try: await g.msg_tab.edit(attachments=[discord.File(buf,"xadrez.png")])
    except: pass

async def _encerrar_partida(g: XZGame, bot, vencedor: discord.Member | None):
    await _cancelar_timeout(g)
    perdedor = (g.pretas if vencedor==g.brancas else g.brancas) if vencedor else None
    if g.aposta > 0 and vencedor:
        await add_saldo(bot, vencedor, g.aposta*2)
        await registrar_resultado(bot, vencedor, True)
        if perdedor: await registrar_resultado(bot, perdedor, False)
    elif g.aposta > 0 and not vencedor:
        for j in [g.brancas, g.pretas]:
            if j: await add_saldo(bot, j, g.aposta)
    for j in [g.brancas, g.pretas]:
        if j: users_em_jogo.discard(j.id)
    g.estado = "fim"
    if g.msg_vez:
        try: await g.msg_vez.delete()
        except: pass

async def _postar_vez(g: XZGame, bot, canal_obj):
    """Posta/edita mensagem pública com botão 'Jogar' pro jogador da vez."""
    prox = g.brancas if g.vez=="white" else g.pretas
    if not prox: return
    check_str = " ⚠️ **XEQUE!**" if _in_check(g.board, g.vez=="white") else ""
    conteudo = f"♟️ Vez de **{prox.display_name}**{check_str} — clique para jogar:"
    view = XZVezView(g.canal, bot)
    if g.msg_vez:
        try:
            await g.msg_vez.edit(content=conteudo, view=view)
            return
        except: pass
    g.msg_vez = await canal_obj.send(conteudo, view=view)


# ── View pública: botão "Jogar" ────────────────────────────────────────────────
class XZVezView(discord.ui.View):
    def __init__(self, canal, bot):
        super().__init__(timeout=MESA_TIMEOUT)
        self.canal = canal; self.bot = bot

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        import traceback; traceback.print_exc()
        try:
            await interaction.response.send_message(
                f"Erro interno: `{error}`", ephemeral=True)
        except: pass

    @discord.ui.button(label="♟️ Jogar", style=discord.ButtonStyle.success, custom_id="xz_jogar")
    async def jogar(self, interaction: discord.Interaction, btn):
        g = mesas.get(self.canal)
        if not g or g.estado != "jogando":
            return await interaction.response.send_message("Sem partida ativa.", ephemeral=True)
        esperado = g.brancas if g.vez=="white" else g.pretas
        if not esperado or esperado.id != interaction.user.id:
            return await interaction.response.send_message("Não é sua vez.", ephemeral=True)

        # Monta select de peças
        pecas = _pecas_moviveis(g.board, g.vez=="white")
        opcoes = []
        for r, c in pecas[:25]:
            p = g.board[r][c]
            nome = PECAS_NOMES.get(p.lower(), p)
            opcoes.append(discord.SelectOption(
                label=f"{nome} {_sc(r,c).upper()}",
                value=f"{r},{c}",
                emoji=_emoji_peca(p)))

        await interaction.response.send_message(
            "Escolha a peça para mover:",
            view=XZSelecionarView(self.canal, self.bot, opcoes, g.vez=="white"),
            ephemeral=True)

    @discord.ui.button(label="🏳️ Desistir", style=discord.ButtonStyle.danger, custom_id="xz_desistir")
    async def desistir(self, interaction: discord.Interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.get(self.canal)
        if not g: return
        if interaction.user.id not in (
            g.brancas.id if g.brancas else 0,
            g.pretas.id  if g.pretas  else 0):
            return await interaction.followup.send("Você não está nesta partida.", ephemeral=True)
        venc = g.pretas if (g.brancas and g.brancas.id==interaction.user.id) else g.brancas
        await _encerrar_partida(g, self.bot, venc)
        mesas.pop(self.canal, None)
        await _render_publico(g)
        premio_str = f" **+{g.aposta*2:,} fichas**!" if g.aposta>0 and venc else ""
        await interaction.channel.send(
            f"🏳️ **{interaction.user.display_name}** desistiu. "
            f"**{venc.display_name if venc else '?'}** vence!{premio_str}",
            view=XZNovaView(self.canal, self.bot))


# ── Select: escolher peça (ephemeral) ────────────────────────────────────────
class XZSelecionarView(discord.ui.View):
    def __init__(self, canal, bot, opcoes, vez_w):
        super().__init__(timeout=120)
        self.canal=canal; self.bot=bot; self.vez_w=vez_w
        sel = discord.ui.Select(placeholder="Escolha a peça...", options=opcoes)
        sel.callback = self._on_peca
        self.add_item(sel)

    async def on_error(self, interaction, error, item):
        import traceback; traceback.print_exc()
        try: await interaction.response.send_message(f"Erro: `{error}`", ephemeral=True)
        except: pass

    async def _on_peca(self, interaction: discord.Interaction):
        g = mesas.get(self.canal)
        if not g or g.estado != "jogando":
            return await interaction.response.send_message("Partida encerrada.", ephemeral=True)
        esperado = g.brancas if self.vez_w else g.pretas
        if not esperado or esperado.id != interaction.user.id:
            return await interaction.response.send_message("Não é você.", ephemeral=True)

        val = interaction.data["values"][0]
        r, c = int(val.split(",")[0]), int(val.split(",")[1])
        mvs = _legal(g.board, r, c, self.vez_w)
        if not mvs:
            return await interaction.response.send_message("Sem movimentos para essa peça.", ephemeral=True)

        dest_opts = []
        for nr, nc in mvs[:25]:
            alvo = g.board[nr][nc]
            cap = f" ✕{_emoji_peca(alvo)}" if alvo!="." else ""
            dest_opts.append(discord.SelectOption(
                label=f"{_sc(nr,nc).upper()}{cap}",
                value=f"{r},{c},{nr},{nc}"))

        peca_nome = PECAS_NOMES.get(g.board[r][c].lower(), "Peça")
        await interaction.response.edit_message(
            content=f"**{peca_nome} {_sc(r,c).upper()}** — para onde mover?",
            view=XZMoverView(self.canal, self.bot, self.vez_w, dest_opts))


# ── Select: escolher destino (ephemeral) ──────────────────────────────────────
class XZMoverView(discord.ui.View):
    def __init__(self, canal, bot, vez_w, dest_opts):
        super().__init__(timeout=120)
        self.canal=canal; self.bot=bot; self.vez_w=vez_w

        sel = discord.ui.Select(placeholder="Mover para...", options=dest_opts)
        sel.callback = self._on_dest
        self.add_item(sel)

    async def on_error(self, interaction, error, item):
        import traceback; traceback.print_exc()
        try: await interaction.response.send_message(f"Erro: `{error}`", ephemeral=True)
        except: pass

        back = discord.ui.Button(label="← Voltar", style=discord.ButtonStyle.grey)
        back.callback = self._on_voltar
        self.add_item(back)

    async def _on_dest(self, interaction: discord.Interaction):
        g = mesas.get(self.canal)
        if not g or g.estado != "jogando":
            return await interaction.response.edit_message(content="Partida encerrada.", view=None)

        esperado = g.brancas if self.vez_w else g.pretas
        if not esperado or esperado.id != interaction.user.id:
            return await interaction.response.send_message("Não é você.", ephemeral=True)

        val = interaction.data["values"][0]
        parts = val.split(",")
        sr, sc, nr, nc = int(parts[0]),int(parts[1]),int(parts[2]),int(parts[3])

        if (nr,nc) not in _legal(g.board,sr,sc,self.vez_w):
            return await interaction.response.edit_message(content="Movimento ilegal.", view=None)

        g.board = _move(g.board,sr,sc,nr,nc)
        g.last_move = (sr,sc,nr,nc)
        g.vez = "black" if self.vez_w else "white"
        move_str = f"{_sc(sr,sc).upper()}→{_sc(nr,nc).upper()}"

        # Fecha o ephemeral
        await interaction.response.edit_message(content=f"✅ **{move_str}** jogado!", view=None)

        canal_obj = interaction.client.get_channel(self.canal)
        await _render_publico(g)

        # Xeque-mate
        if _checkmate(g.board, g.vez=="white"):
            venc = g.brancas if self.vez_w else g.pretas
            await _encerrar_partida(g, self.bot, venc)
            mesas.pop(self.canal, None)
            premio_str = f" **+{g.aposta*2:,} fichas**!" if g.aposta>0 else ""
            if canal_obj:
                await canal_obj.send(
                    f"♟️ **{move_str}** — XEQUE-MATE! **{venc.display_name if venc else '?'}** vence!{premio_str} 🏆",
                    view=XZNovaView(self.canal, self.bot))
            return

        # Afogamento
        if _stalemate(g.board, g.vez=="white"):
            await _encerrar_partida(g, self.bot, None)
            mesas.pop(self.canal, None)
            dev = " Apostas devolvidas." if g.aposta>0 else ""
            if canal_obj:
                await canal_obj.send(
                    f"♟️ **{move_str}** — 🤝 Afogamento! Empate.{dev}",
                    view=XZNovaView(self.canal, self.bot))
            return

        await _agendar_timeout(g, self.bot)
        if canal_obj:
            await _postar_vez(g, self.bot, canal_obj)

    async def _on_voltar(self, interaction: discord.Interaction):
        g = mesas.get(self.canal)
        if not g:
            return await interaction.response.edit_message(content="Partida encerrada.", view=None)
        pecas = _pecas_moviveis(g.board, self.vez_w)
        opcoes = []
        for r, c in pecas[:25]:
            p = g.board[r][c]
            nome = PECAS_NOMES.get(p.lower(), p)
            opcoes.append(discord.SelectOption(
                label=f"{nome} {_sc(r,c).upper()}",
                value=f"{r},{c}",
                emoji=_emoji_peca(p)))
        await interaction.response.edit_message(
            content="Escolha a peça para mover:",
            view=XZSelecionarView(self.canal, self.bot, opcoes, self.vez_w))


# ── View de entrada ───────────────────────────────────────────────────────────
class XZEntrarView(discord.ui.View):
    def __init__(self, canal, bot, aposta=0):
        super().__init__(timeout=120)
        self.canal=canal; self.bot=bot; self.aposta=aposta

    @discord.ui.button(label="Jogar com Brancas ⬜", style=discord.ButtonStyle.secondary)
    async def brancas(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.get(self.canal)
        if not g: return
        if g.brancas: return await interaction.followup.send("Brancas já ocupado.", ephemeral=True)
        if interaction.user.id in users_em_jogo:
            return await interaction.followup.send("Você já está em outro jogo.", ephemeral=True)
        g.brancas = interaction.user
        users_em_jogo.add(interaction.user.id)
        await interaction.followup.send("✅ Você é **brancas**.")
        await _checar_start(g, self.bot, interaction)

    @discord.ui.button(label="Jogar com Pretas ⬛", style=discord.ButtonStyle.primary)
    async def pretas(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.get(self.canal)
        if not g: return
        if g.pretas: return await interaction.followup.send("Pretas já ocupado.", ephemeral=True)
        if interaction.user.id in users_em_jogo:
            return await interaction.followup.send("Você já está em outro jogo.", ephemeral=True)
        g.pretas = interaction.user
        users_em_jogo.add(interaction.user.id)
        await interaction.followup.send("✅ Você é **pretas**.")
        await _checar_start(g, self.bot, interaction)


async def _checar_start(g: XZGame, bot, interaction: discord.Interaction):
    if not (g.brancas and g.pretas): return
    if g.aposta > 0:
        for j in [g.brancas, g.pretas]:
            await add_saldo(bot, j, -g.aposta)

    g.estado="jogando"; g.board=_cp(INICIO); g.vez="white"
    bn=g.brancas.display_name; pn=g.pretas.display_name

    buf = render_xadrez(g.board, bn, pn, "white")
    aposta_str = f" | Aposta: **{g.aposta:,}** cada" if g.aposta>0 else ""
    g.msg_tab = await interaction.channel.send(
        f"♟️ **{bn}** ⬜ vs ⬛ **{pn}**{aposta_str}",
        file=discord.File(buf,"xadrez.png"))

    await _agendar_timeout(g, bot)
    await _postar_vez(g, bot, interaction.channel)


class XZNovaView(discord.ui.View):
    def __init__(self, canal, bot):
        super().__init__(timeout=120)
        self.canal=canal; self.bot=bot

    @discord.ui.button(label="Revanche", emoji="🔄", style=discord.ButtonStyle.success)
    async def nova(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.get(self.canal)
        if not g: return
        aposta_ant = g.aposta
        if aposta_ant > 0:
            for j in [g.brancas, g.pretas]:
                if j:
                    s = await get_saldo(self.bot, j)
                    if s < aposta_ant:
                        return await interaction.followup.send(
                            f"{j.display_name} sem fichas para revanche.", ephemeral=True)
        g.brancas, g.pretas = g.pretas, g.brancas
        g.board=_cp(INICIO); g.vez="white"; g.estado="aguardando"
        g.last_move=None; g.aposta=aposta_ant; g.msg_vez=None
        for j in [g.brancas, g.pretas]:
            if j: users_em_jogo.add(j.id)
        await _checar_start(g, self.bot, interaction)

    @discord.ui.button(label="Encerrar", emoji="🚪", style=discord.ButtonStyle.danger)
    async def encerrar(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.pop(self.canal, None)
        if g:
            await _cancelar_timeout(g)
            for j in [g.brancas, g.pretas]:
                if j: users_em_jogo.discard(j.id)
            if g.msg_vez:
                try: await g.msg_vez.delete()
                except: pass
        await interaction.followup.send("Mesa encerrada.")


class Xadrez(commands.Cog):
    def __init__(self, bot): self.bot=bot

    @app_commands.command(name="xadrez", description="Iniciar partida de Xadrez")
    @app_commands.describe(aposta="Fichas a apostar cada jogador (opcional)")
    async def cmd_xadrez(self, interaction: discord.Interaction, aposta: int=0):
        cid = interaction.channel_id
        if cid in mesas and mesas[cid].estado=="jogando":
            return await interaction.response.send_message("Partida em andamento.", ephemeral=True)
        if interaction.user.id in users_em_jogo:
            return await interaction.response.send_message("Você já está em outro jogo.", ephemeral=True)
        if aposta < 0:
            return await interaction.response.send_message("Aposta não pode ser negativa.", ephemeral=True)
        if aposta > 0:
            saldo = await get_saldo(self.bot, interaction.user)
            if saldo < aposta:
                return await interaction.response.send_message(
                    f"Saldo insuficiente ({saldo:,}).", ephemeral=True)
        g = XZGame(canal=cid, aposta=aposta)
        mesas[cid] = g
        aposta_str = f" com **{aposta:,} fichas** cada" if aposta>0 else ""
        await interaction.response.send_message(
            f"♟️ **Xadrez{aposta_str}!** Escolham os lados:",
            view=XZEntrarView(cid, self.bot, aposta=aposta))


async def setup(bot):
    await bot.add_cog(Xadrez(bot))
    # Registra view persistente (botões funcionam mesmo após restart)
    bot.add_view(XZVezView(canal=0, bot=bot))
