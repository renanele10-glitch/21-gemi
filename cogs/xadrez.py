"""
cogs/xadrez.py — Xadrez completo. Painel persistente.
Seleciona peça → destaque movimentos → digita destino.
Fim só por xeque-mate ou desistência.
"""
import discord
from discord import app_commands
from discord.ext import commands
from dataclasses import dataclass, field
from .render import render_xadrez

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


def _cp(b): return [r[:] for r in b]
def _wh(p): return p!=".." and p.isupper()
def _bl(p): return p!=".." and p.islower()
def _en(p, w): return _bl(p) if w else _wh(p)
def _fr(p, w): return _wh(p) if w else _bl(p)
def _coord(s):
    s=s.strip().lower()
    if len(s)!=2: return None
    c=ord(s[0])-ord('a'); r=8-int(s[1]) if s[1].isdigit() else -1
    return (r,c) if 0<=r<8 and 0<=c<8 else None
def _sc(r,c): return f"{chr(97+c)}{8-r}"


def _slide(b, r, c, w, dirs):
    mvs=[]
    for dr,dc in dirs:
        nr,nc=r+dr,c+dc
        while 0<=nr<8 and 0<=nc<8:
            if b[nr][nc]==".": mvs.append((nr,nc))
            elif _en(b[nr][nc],w): mvs.append((nr,nc)); break
            else: break
            nr+=dr; nc+=dc
    return mvs

def _legal_raw(b, r, c, w):
    p=b[r][c].lower()
    if p=="p":
        mvs=[]
        d=-1 if w else 1; sr=6 if w else 1
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
    if p=="n":
        return [(r+dr,c+dc) for dr,dc in[(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]
                if 0<=r+dr<8 and 0<=c+dc<8 and not _fr(b[r+dr][c+dc],w)]
    if p=="k":
        return [(r+dr,c+dc) for dr in(-1,0,1) for dc in(-1,0,1)
                if (dr or dc) and 0<=r+dr<8 and 0<=c+dc<8 and not _fr(b[r+dr][c+dc],w)]
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

def _move(b, r1,c1,r2,c2):
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
                for nr,nc in _legal(b,r,c,w):
                    mvs.append((r,c,nr,nc))
    return mvs

def _checkmate(b, w): return _in_check(b,w) and not _all_legal(b,w)
def _stalemate(b, w): return not _in_check(b,w) and not _all_legal(b,w)


@dataclass
class XZGame:
    canal: int
    brancas: discord.Member | None = None
    pretas:  discord.Member | None = None
    board:   list = field(default_factory=lambda: _cp(INICIO))
    vez:     str  = "white"
    estado:  str  = "aguardando"
    selected: tuple|None = None
    last_move: tuple|None = None
    msg: discord.Message|None = None


mesas: dict[int, XZGame] = {}


async def _render(g: XZGame):
    if not g.msg: return
    valid=[]
    if g.selected:
        sr,sc=g.selected; w=g.vez=="white"
        valid=_legal(g.board,sr,sc,w)
    bn=g.brancas.display_name if g.brancas else "Brancas"
    pn=g.pretas.display_name  if g.pretas  else "Pretas"
    buf=render_xadrez(g.board,bn,pn,g.vez,g.last_move,g.selected,valid)
    try: await g.msg.edit(attachments=[discord.File(buf,"xadrez.png")])
    except Exception: pass


class XZView(discord.ui.View):
    def __init__(self, canal, bot):
        super().__init__(timeout=None)
        self.canal=canal; self.bot=bot

    def _vez(self, uid):
        g=mesas.get(self.canal)
        if not g or g.estado!="jogando": return False,None
        if g.vez=="white" and g.brancas and g.brancas.id==uid: return True,g
        if g.vez=="black" and g.pretas  and g.pretas.id ==uid: return True,g
        return False,g

    @discord.ui.button(label="Selecionar Peça", emoji="♟️", style=discord.ButtonStyle.primary, custom_id="xz_sel")
    async def selecionar(self, interaction, btn):
        ok,g=self._vez(interaction.user.id)
        if not ok: return await interaction.response.send_message("Não é sua vez.", ephemeral=True)
        await interaction.response.send_modal(SelModal(self.canal, self.bot))

    @discord.ui.button(label="Mover Para →", emoji="➡️", style=discord.ButtonStyle.success, custom_id="xz_mov")
    async def mover(self, interaction, btn):
        ok,g=self._vez(interaction.user.id)
        if not ok: return await interaction.response.send_message("Não é sua vez.", ephemeral=True)
        if not g.selected: return await interaction.response.send_message("Selecione uma peça primeiro.", ephemeral=True)
        await interaction.response.send_modal(MovModal(self.canal, self.bot))

    @discord.ui.button(label="Desistir", emoji="🏳️", style=discord.ButtonStyle.danger, custom_id="xz_des")
    async def desistir(self, interaction, btn):
        await interaction.response.defer()
        g=mesas.get(self.canal)
        if not g: return
        uid=interaction.user.id
        if g.brancas and g.brancas.id==uid: venc=g.pretas.display_name if g.pretas else "Pretas"
        elif g.pretas and g.pretas.id==uid:  venc=g.brancas.display_name if g.brancas else "Brancas"
        else: return await interaction.followup.send("Você não está nesta partida.", ephemeral=True)
        g.estado="fim"
        await interaction.followup.send(f"🏳️ **{interaction.user.display_name}** desistiu. **{venc}** vence!", view=XZNovaView(self.canal, self.bot))


class SelModal(discord.ui.Modal, title="Selecionar Peça"):
    coord=discord.ui.TextInput(label="Coordenada (ex: e2)", placeholder="e2")
    def __init__(self, canal, bot): super().__init__(); self.canal=canal; self.bot=bot
    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True)
        g=mesas.get(self.canal)
        if not g: return
        pos=_coord(self.coord.value)
        if not pos: return await interaction.followup.send("Coordenada inválida.", ephemeral=True)
        r,c=pos; w=g.vez=="white"; p=g.board[r][c]
        if p=="." or _wh(p)!=w:
            return await interaction.followup.send("Não há sua peça aí.", ephemeral=True)
        mvs=_legal(g.board,r,c,w)
        if not mvs: return await interaction.followup.send("Essa peça não tem movimentos legais.", ephemeral=True)
        g.selected=(r,c)
        await _render(g)
        await interaction.followup.send(
            f"✅ Peça em **{self.coord.value.upper()}** selecionada. Clique **Mover Para →**.", ephemeral=True)


class MovModal(discord.ui.Modal, title="Mover Para"):
    dest=discord.ui.TextInput(label="Destino (ex: e4)", placeholder="e4")
    def __init__(self, canal, bot): super().__init__(); self.canal=canal; self.bot=bot
    async def on_submit(self, interaction):
        await interaction.response.defer()
        g=mesas.get(self.canal)
        if not g or not g.selected: return
        sr,sc=g.selected; w=g.vez=="white"
        pos=_coord(self.dest.value)
        if not pos: return await interaction.followup.send("Coordenada inválida.", ephemeral=True)
        nr,nc=pos
        if (nr,nc) not in _legal(g.board,sr,sc,w):
            return await interaction.followup.send("Movimento ilegal.", ephemeral=True)
        g.board=_move(g.board,sr,sc,nr,nc)
        g.last_move=(sr,sc,nr,nc); g.selected=None
        g.vez="black" if w else "white"

        if _checkmate(g.board, g.vez=="white"):
            venc=(g.brancas if w else g.pretas)
            g.estado="fim"
            await _render(g)
            return await interaction.followup.send(
                f"♟️ **XEQUE-MATE!** {venc.display_name if venc else ''} vence! 🏆",
                view=XZNovaView(g.canal, self.bot))

        if _stalemate(g.board, g.vez=="white"):
            g.estado="fim"
            await _render(g)
            return await interaction.followup.send("🤝 **Afogamento! Empate.**", view=XZNovaView(g.canal, self.bot))

        check=""
        if _in_check(g.board, g.vez=="white"): check=" ⚠️ **XEQUE!**"
        prox=(g.brancas if g.vez=="white" else g.pretas)
        await _render(g)
        await interaction.followup.send(
            f"**{_sc(sr,sc).upper()}→{_sc(nr,nc).upper()}**{check} Vez de **{prox.display_name if prox else g.vez}**.",
            view=XZView(g.canal, self.bot))


class XZEntrarView(discord.ui.View):
    def __init__(self, canal, bot): super().__init__(timeout=120); self.canal=canal; self.bot=bot

    @discord.ui.button(label="Jogar com Brancas ⬜", style=discord.ButtonStyle.secondary)
    async def brancas(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g=mesas.get(self.canal)
        if not g: return
        if g.brancas: return await interaction.followup.send("Brancas já ocupado.", ephemeral=True)
        g.brancas=interaction.user
        await interaction.followup.send("✅ Você é **brancas**.")
        await _checar_start(g, self.bot, interaction)

    @discord.ui.button(label="Jogar com Pretas ⬛", style=discord.ButtonStyle.primary)
    async def pretas(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g=mesas.get(self.canal)
        if not g: return
        if g.pretas: return await interaction.followup.send("Pretas já ocupado.", ephemeral=True)
        g.pretas=interaction.user
        await interaction.followup.send("✅ Você é **pretas**.")
        await _checar_start(g, self.bot, interaction)


async def _checar_start(g, bot, interaction):
    if not (g.brancas and g.pretas): return
    g.estado="jogando"; g.board=_cp(INICIO); g.vez="white"
    bn=g.brancas.display_name; pn=g.pretas.display_name
    buf=render_xadrez(g.board,bn,pn,"white")
    msg=await interaction.channel.send(file=discord.File(buf,"xadrez.png"), view=XZView(g.canal,bot))
    g.msg=msg
    await interaction.channel.send(f"♟️ **{bn}** ⬜ vs ⬛ **{pn}** — vez das **brancas**.")


class XZNovaView(discord.ui.View):
    def __init__(self, canal, bot): super().__init__(timeout=120); self.canal=canal; self.bot=bot

    @discord.ui.button(label="Revanche", emoji="🔄", style=discord.ButtonStyle.success)
    async def nova(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g=mesas.get(self.canal)
        if not g: return
        # Trocar lados
        g.brancas, g.pretas = g.pretas, g.brancas
        g.board=_cp(INICIO); g.vez="white"; g.estado="aguardando"
        g.selected=None; g.last_move=None
        bn=g.brancas.display_name if g.brancas else ""; pn=g.pretas.display_name if g.pretas else ""
        buf=render_xadrez(g.board,bn,pn,"white")
        msg=await interaction.channel.send(file=discord.File(buf,"xadrez.png"), view=XZView(g.canal, self.bot))
        g.msg=msg; g.estado="jogando"
        await interaction.channel.send(f"🔄 Revanche! **{bn}** ⬜ vs ⬛ **{pn}** — vez das brancas.")

    @discord.ui.button(label="Encerrar", emoji="🚪", style=discord.ButtonStyle.danger)
    async def encerrar(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        mesas.pop(self.canal, None)
        await interaction.followup.send("Mesa encerrada.")


class Xadrez(commands.Cog):
    def __init__(self, bot): self.bot=bot

    @app_commands.command(name="xadrez", description="Iniciar partida de Xadrez")
    async def cmd_xadrez(self, interaction: discord.Interaction):
        cid=interaction.channel_id
        if cid in mesas and mesas[cid].estado=="jogando":
            return await interaction.response.send_message("Partida em andamento.", ephemeral=True)
        mesas[cid]=XZGame(canal=cid)
        await interaction.response.send_message("♟️ **Xadrez!** Escolham os lados:", view=XZEntrarView(cid, self.bot))


async def setup(bot):
    await bot.add_cog(Xadrez(bot))
