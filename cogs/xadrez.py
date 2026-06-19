"""
cogs/xadrez.py — Xadrez v4: Thread privada por jogador + Select Menu de movimentos.

Fluxo:
  1. /xadrez [aposta] → abre XZEntrarView no canal
  2. Cada jogador escolhe lado → bot cria thread privada para ele
  3. Na thread: Select Menu "Qual peça?" → Select Menu "Mover para?" (só destinos legais)
  4. Tabuleiro público atualiza no canal original a cada jogada
  5. Timeout 15 min → fecha threads e devolve apostas
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
MESA_TIMEOUT   = 900   # 15 min
PECAS_NOMES    = {"p":"Peão","r":"Torre","n":"Cavalo","b":"Bispo","q":"Rainha","k":"Rei"}
users_em_jogo: set[int] = set()


# ── Engine ────────────────────────────────────────────────────────────────────
def _cp(b): return [r[:] for r in b]
def _wh(p): return p != "." and p.isupper()
def _bl(p): return p != "." and p.islower()
def _en(p, w): return _bl(p) if w else _wh(p)
def _fr(p, w): return _wh(p) if w else _bl(p)

def _coord(s):
    s = s.strip().lower()
    if len(s) != 2: return None
    c = ord(s[0]) - ord('a')
    r = 8 - int(s[1]) if s[1].isdigit() else -1
    return (r, c) if 0 <= r < 8 and 0 <= c < 8 else None

def _sc(r, c): return f"{chr(97+c)}{8-r}"

def _slide(b, r, c, w, dirs):
    mvs = []
    for dr, dc in dirs:
        nr, nc = r+dr, c+dc
        while 0 <= nr < 8 and 0 <= nc < 8:
            if b[nr][nc] == ".": mvs.append((nr, nc))
            elif _en(b[nr][nc], w): mvs.append((nr, nc)); break
            else: break
            nr += dr; nc += dc
    return mvs

def _legal_raw(b, r, c, w):
    p = b[r][c].lower()
    if p == "p":
        mvs = []; d = -1 if w else 1; sr = 6 if w else 1
        nr = r + d
        if 0 <= nr < 8:
            if b[nr][c] == ".":
                mvs.append((nr, c))
                if r == sr and b[r+2*d][c] == ".": mvs.append((r+2*d, c))
            for dc in (-1, 1):
                if 0 <= c+dc < 8 and _en(b[nr][c+dc], w): mvs.append((nr, c+dc))
        return mvs
    if p == "r": return _slide(b,r,c,w,[(0,1),(0,-1),(1,0),(-1,0)])
    if p == "b": return _slide(b,r,c,w,[(1,1),(1,-1),(-1,1),(-1,-1)])
    if p == "q": return _slide(b,r,c,w,[(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)])
    if p == "n":
        return [(r+dr,c+dc) for dr,dc in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]
                if 0<=r+dr<8 and 0<=c+dc<8 and not _fr(b[r+dr][c+dc],w)]
    if p == "k":
        return [(r+dr,c+dc) for dr in(-1,0,1) for dc in(-1,0,1)
                if (dr or dc) and 0<=r+dr<8 and 0<=c+dc<8 and not _fr(b[r+dr][c+dc],w)]
    return []

def _king(b, w):
    k = "K" if w else "k"
    for r in range(8):
        for c in range(8):
            if b[r][c] == k: return r, c
    return None

def _in_check(b, w):
    pos = _king(b, w)
    if not pos: return False
    kr, kc = pos
    for r in range(8):
        for c in range(8):
            p = b[r][c]
            if (w and _bl(p)) or (not w and _wh(p)):
                if (kr, kc) in _legal_raw(b, r, c, not w): return True
    return False

def _move(b, r1, c1, r2, c2):
    nb = _cp(b); p = nb[r1][c1]
    nb[r2][c2] = p; nb[r1][c1] = "."
    if p == "P" and r2 == 0: nb[r2][c2] = "Q"
    if p == "p" and r2 == 7: nb[r2][c2] = "q"
    return nb

def _legal(b, r, c, w):
    return [(nr,nc) for nr,nc in _legal_raw(b,r,c,w)
            if not _in_check(_move(b,r,c,nr,nc), w)]

def _all_legal(b, w):
    mvs = []
    for r in range(8):
        for c in range(8):
            p = b[r][c]
            if (w and _wh(p)) or (not w and _bl(p)):
                for nr, nc in _legal(b, r, c, w):
                    mvs.append((r, c, nr, nc))
    return mvs

def _checkmate(b, w): return _in_check(b, w) and not _all_legal(b, w)
def _stalemate(b, w): return not _in_check(b, w) and not _all_legal(b, w)

def _pecas_moviveis(b, w):
    """Retorna lista de (r,c) com peças que têm ao menos 1 movimento legal."""
    result = []
    for r in range(8):
        for c in range(8):
            p = b[r][c]
            if (w and _wh(p)) or (not w and _bl(p)):
                if _legal(b, r, c, w):
                    result.append((r, c))
    return result


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
    msg: discord.Message | None = None          # tabuleiro público no canal
    thread_b: discord.Thread | None = None      # thread privada das brancas
    thread_p: discord.Thread | None = None      # thread privada das pretas
    msg_b: discord.Message | None = None        # última msg de controle na thread brancas
    msg_p: discord.Message | None = None        # última msg de controle na thread pretas
    _timeout_task: object = field(default=None, repr=False)


mesas: dict[int, XZGame] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────
async def _cancelar_timeout(g: XZGame):
    if g._timeout_task and not g._timeout_task.done():
        g._timeout_task.cancel()

async def _fechar_threads(g: XZGame):
    for t in [g.thread_b, g.thread_p]:
        if t:
            try: await t.edit(archived=True, locked=True)
            except: pass

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
        await _fechar_threads(g)
        if g.msg:
            try: await g.msg.edit(
                content="⏰ Partida encerrada por inatividade. Apostas devolvidas.",
                attachments=[])
            except: pass
    g._timeout_task = asyncio.create_task(_exp())

async def _render_publico(g: XZGame):
    """Atualiza tabuleiro público no canal."""
    if not g.msg: return
    bn = g.brancas.display_name if g.brancas else "Brancas"
    pn = g.pretas.display_name  if g.pretas  else "Pretas"
    buf = render_xadrez(g.board, bn, pn, g.vez, last_move=g.last_move)
    try: await g.msg.edit(attachments=[discord.File(buf, "xadrez.png")])
    except: pass

async def _encerrar_partida(g: XZGame, bot, vencedor: discord.Member | None):
    await _cancelar_timeout(g)
    perdedor = (g.pretas if vencedor == g.brancas else g.brancas) if vencedor else None
    if g.aposta > 0 and vencedor:
        await add_saldo(bot, vencedor, g.aposta * 2)
        await registrar_resultado(bot, vencedor, True)
        if perdedor: await registrar_resultado(bot, perdedor, False)
    elif g.aposta > 0 and not vencedor:
        for j in [g.brancas, g.pretas]:
            if j: await add_saldo(bot, j, g.aposta)
    for j in [g.brancas, g.pretas]:
        if j: users_em_jogo.discard(j.id)
    g.estado = "fim"
    await _fechar_threads(g)


async def _enviar_controles(g: XZGame, bot, vez_w: bool):
    """Envia select menu de peças na thread do jogador da vez."""
    thread  = g.thread_b if vez_w else g.thread_p
    jogador = g.brancas  if vez_w else g.pretas
    if not thread or not jogador: return

    pecas = _pecas_moviveis(g.board, vez_w)
    if not pecas: return

    # Monta opções do select: "Peão e2", "Torre a1", etc.
    opcoes = []
    for r, c in pecas[:25]:   # Discord limita 25 opções
        p    = g.board[r][c]
        nome = PECAS_NOMES.get(p.lower(), p)
        coord = _sc(r, c).upper()
        opcoes.append(discord.SelectOption(
            label=f"{nome} {coord}",
            value=f"{r},{c}",
            emoji=_emoji_peca(p)
        ))

    view = XZSelecionarView(g.canal, bot, opcoes, vez_w)
    check_str = " ⚠️ **XEQUE!**" if _in_check(g.board, vez_w) else ""
    msg = await thread.send(
        f"**Sua vez!**{check_str} Escolha a peça para mover:",
        view=view)

    if vez_w: g.msg_b = msg
    else:     g.msg_p = msg

def _emoji_peca(p: str) -> str:
    mapa = {"P":"♙","R":"♖","N":"♘","B":"♗","Q":"♕","K":"♔",
            "p":"♟","r":"♜","n":"♞","b":"♝","q":"♛","k":"♚"}
    return mapa.get(p, "♟")


# ── Select: escolher peça ─────────────────────────────────────────────────────
class XZSelecionarView(discord.ui.View):
    def __init__(self, canal, bot, opcoes, vez_w):
        super().__init__(timeout=MESA_TIMEOUT)
        self.canal  = canal
        self.bot    = bot
        self.vez_w  = vez_w
        sel = discord.ui.Select(
            placeholder="Escolha a peça...",
            options=opcoes,
            custom_id="xz_peca"
        )
        sel.callback = self._on_peca
        self.add_item(sel)

        # Botão desistir
        des = discord.ui.Button(label="Desistir", emoji="🏳️",
                                style=discord.ButtonStyle.danger,
                                custom_id="xz_des_thread")
        des.callback = self._on_desistir
        self.add_item(des)

    async def _on_peca(self, interaction: discord.Interaction):
        await interaction.response.defer()
        g = mesas.get(self.canal)
        if not g or g.estado != "jogando": return

        esperado = g.brancas if self.vez_w else g.pretas
        if not esperado or esperado.id != interaction.user.id:
            return await interaction.followup.send("Não é você.", ephemeral=True)

        val  = interaction.data["values"][0]
        r, c = int(val.split(",")[0]), int(val.split(",")[1])
        mvs  = _legal(g.board, r, c, self.vez_w)
        if not mvs:
            return await interaction.followup.send("Essa peça não tem movimentos.", ephemeral=True)

        # Monta opções de destino
        dest_opts = []
        for nr, nc in mvs[:25]:
            alvo = g.board[nr][nc]
            captura = f" ✕{_emoji_peca(alvo)}" if alvo != "." else ""
            dest_opts.append(discord.SelectOption(
                label=f"{_sc(nr,nc).upper()}{captura}",
                value=f"{r},{c},{nr},{nc}"
            ))

        peca_nome = PECAS_NOMES.get(g.board[r][c].lower(), "Peça")
        view = XZMoverView(self.canal, self.bot, self.vez_w, r, c)
        view.add_destinos(dest_opts)

        # Desabilita a mensagem anterior e envia nova
        self.stop()
        for item in self.children: item.disabled = True
        try: await interaction.message.edit(view=self)
        except: pass

        thread = g.thread_b if self.vez_w else g.thread_p
        buf = render_xadrez(g.board, "", "", self.vez_w and "white" or "black",
                            highlight=(r,c), last_move=g.last_move)
        await thread.send(
            f"**{peca_nome} {_sc(r,c).upper()}** selecionada. Para onde mover?",
            file=discord.File(buf, "sel.png"),
            view=view)

    async def _on_desistir(self, interaction: discord.Interaction):
        await interaction.response.defer()
        g = mesas.get(self.canal)
        if not g: return
        esperado = g.brancas if self.vez_w else g.pretas
        if not esperado or esperado.id != interaction.user.id:
            return await interaction.followup.send("Não é você.", ephemeral=True)
        venc = g.pretas if self.vez_w else g.brancas
        await _encerrar_partida(g, self.bot, venc)
        mesas.pop(self.canal, None)
        await _render_publico(g)
        premio_str = f" **+{g.aposta*2:,} fichas** para {venc.display_name}!" if g.aposta > 0 and venc else ""
        canal_obj  = interaction.client.get_channel(self.canal)
        if canal_obj:
            await canal_obj.send(
                f"🏳️ **{interaction.user.display_name}** desistiu. "
                f"**{venc.display_name if venc else '?'}** vence!{premio_str}",
                view=XZNovaView(self.canal, self.bot))


# ── Select: escolher destino ──────────────────────────────────────────────────
class XZMoverView(discord.ui.View):
    def __init__(self, canal, bot, vez_w, sr, sc):
        super().__init__(timeout=MESA_TIMEOUT)
        self.canal  = canal
        self.bot    = bot
        self.vez_w  = vez_w
        self.sr     = sr
        self.sc     = sc

    def add_destinos(self, opcoes):
        sel = discord.ui.Select(
            placeholder="Mover para...",
            options=opcoes,
            custom_id="xz_dest"
        )
        sel.callback = self._on_dest
        self.add_item(sel)

        # Botão voltar
        back = discord.ui.Button(label="← Voltar", style=discord.ButtonStyle.grey)
        back.callback = self._on_voltar
        self.add_item(back)

    async def _on_dest(self, interaction: discord.Interaction):
        await interaction.response.defer()
        g = mesas.get(self.canal)
        if not g or g.estado != "jogando": return

        esperado = g.brancas if self.vez_w else g.pretas
        if not esperado or esperado.id != interaction.user.id:
            return await interaction.followup.send("Não é você.", ephemeral=True)

        val = interaction.data["values"][0]
        parts = val.split(",")
        sr, sc, nr, nc = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])

        if (nr, nc) not in _legal(g.board, sr, sc, self.vez_w):
            return await interaction.followup.send("Movimento ilegal.", ephemeral=True)

        g.board    = _move(g.board, sr, sc, nr, nc)
        g.last_move = (sr, sc, nr, nc)
        g.vez      = "black" if self.vez_w else "white"

        # Desabilita view atual
        self.stop()
        for item in self.children: item.disabled = True
        try: await interaction.message.edit(view=self)
        except: pass

        move_str = f"{_sc(sr,sc).upper()}→{_sc(nr,nc).upper()}"
        canal_obj = interaction.client.get_channel(self.canal)

        # Xeque-mate
        if _checkmate(g.board, g.vez == "white"):
            venc = g.brancas if self.vez_w else g.pretas
            await _encerrar_partida(g, self.bot, venc)
            mesas.pop(self.canal, None)
            await _render_publico(g)
            premio_str = f" **+{g.aposta*2:,} fichas**!" if g.aposta > 0 else ""
            if canal_obj:
                await canal_obj.send(
                    f"♟️ **{move_str}** — XEQUE-MATE! "
                    f"**{venc.display_name if venc else '?'}** vence!{premio_str} 🏆",
                    view=XZNovaView(self.canal, self.bot))
            return

        # Afogamento
        if _stalemate(g.board, g.vez == "white"):
            await _encerrar_partida(g, self.bot, None)
            mesas.pop(self.canal, None)
            await _render_publico(g)
            dev = " Apostas devolvidas." if g.aposta > 0 else ""
            if canal_obj:
                await canal_obj.send(
                    f"♟️ **{move_str}** — 🤝 Afogamento! Empate.{dev}",
                    view=XZNovaView(self.canal, self.bot))
            return

        # Turno normal
        prox = g.brancas if g.vez == "white" else g.pretas
        check_str = " ⚠️ XEQUE!" if _in_check(g.board, g.vez == "white") else ""
        await _render_publico(g)
        await _agendar_timeout(g, self.bot)

        # Avisa no canal público
        if canal_obj:
            await canal_obj.send(
                f"♟️ **{move_str}**{check_str} Vez de **{prox.display_name if prox else '?'}**.")

        # Envia controles na thread do próximo
        await _enviar_controles(g, self.bot, g.vez == "white")

    async def _on_voltar(self, interaction: discord.Interaction):
        """Volta ao select de peças."""
        await interaction.response.defer()
        g = mesas.get(self.canal)
        if not g: return
        self.stop()
        for item in self.children: item.disabled = True
        try: await interaction.message.edit(view=self)
        except: pass
        await _enviar_controles(g, self.bot, self.vez_w)


# ── View de entrada ───────────────────────────────────────────────────────────
class XZEntrarView(discord.ui.View):
    def __init__(self, canal, bot, aposta=0):
        super().__init__(timeout=120)
        self.canal = canal; self.bot = bot; self.aposta = aposta

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

    g.estado = "jogando"; g.board = _cp(INICIO); g.vez = "white"
    bn = g.brancas.display_name; pn = g.pretas.display_name

    # Tabuleiro público
    buf = render_xadrez(g.board, bn, pn, "white")
    aposta_str = f" | Aposta: **{g.aposta:,}** cada" if g.aposta > 0 else ""
    g.msg = await interaction.channel.send(
        f"♟️ **{bn}** ⬜ vs ⬛ **{pn}**{aposta_str}",
        file=discord.File(buf, "xadrez.png"))

    # Cria threads privadas — tenta private_thread, cai pra public se não tiver permissão
    async def _criar_thread(nome: str, membro: discord.Member) -> discord.Thread:
        try:
            t = await interaction.channel.create_thread(
                name=nome,
                type=discord.ChannelType.private_thread,
                invitable=False,
                auto_archive_duration=60)
            await t.add_user(membro)
            return t
        except (discord.Forbidden, discord.HTTPException):
            # Fallback: thread pública sem mensagem âncora
            t = await interaction.channel.create_thread(
                name=nome,
                auto_archive_duration=60,
                type=discord.ChannelType.public_thread)
            await t.add_user(membro)
            return t

    g.thread_b = await _criar_thread(f"♟️ {bn} ⬜", g.brancas)
    g.thread_p = await _criar_thread(f"♟️ {pn} ⬛", g.pretas)

    # Aguarda Discord registrar as threads antes de mandar views
    await asyncio.sleep(1.5)

    await g.thread_b.send(
        f"🏰 **{bn}**, esta é sua thread!\n"
        f"Você joga com as **brancas ⬜**. O menu de jogada aparecerá abaixo:")
    await g.thread_p.send(
        f"🏰 **{pn}**, esta é sua thread!\n"
        f"Você joga com as **pretas ⬛**. Aguarde — o menu aparecerá aqui quando for sua vez.")

    await _agendar_timeout(g, bot)
    await asyncio.sleep(0.5)
    # Brancas começam
    await _enviar_controles(g, bot, vez_w=True)


class XZNovaView(discord.ui.View):
    def __init__(self, canal, bot):
        super().__init__(timeout=120)
        self.canal = canal; self.bot = bot

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
        g.board = _cp(INICIO); g.vez = "white"; g.estado = "aguardando"
        g.last_move = None; g.aposta = aposta_ant
        g.thread_b = g.thread_p = None
        g.msg_b = g.msg_p = None
        for j in [g.brancas, g.pretas]:
            if j: users_em_jogo.add(j.id)
        await _checar_start(g, self.bot, interaction)

    @discord.ui.button(label="Encerrar", emoji="🚪", style=discord.ButtonStyle.danger)
    async def encerrar(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.pop(self.canal, None)
        if g:
            await _cancelar_timeout(g)
            await _fechar_threads(g)
            for j in [g.brancas, g.pretas]:
                if j: users_em_jogo.discard(j.id)
        await interaction.followup.send("Mesa encerrada.")


# ── Cog ───────────────────────────────────────────────────────────────────────
class Xadrez(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name="xadrez", description="Iniciar partida de Xadrez")
    @app_commands.describe(aposta="Fichas a apostar cada jogador (opcional)")
    async def cmd_xadrez(self, interaction: discord.Interaction, aposta: int = 0):
        cid = interaction.channel_id
        if cid in mesas and mesas[cid].estado == "jogando":
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
        aposta_str = f" com **{aposta:,} fichas** cada" if aposta > 0 else ""
        await interaction.response.send_message(
            f"♟️ **Xadrez{aposta_str}!** Escolham os lados:",
            view=XZEntrarView(cid, self.bot, aposta=aposta))


async def setup(bot):
    await bot.add_cog(Xadrez(bot))
