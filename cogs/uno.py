"""
cogs/uno.py — UNO 2-4 jogadores. Painel persistente por canal.

v3 fixes:
  - Timeout 8 min (mesa não fica viva pra sempre)
  - Paginação: mãos com 11+ cartas têm páginas (10 por página)
  - Fichas integradas: vencedor ganha PREMIO por jogador eliminado
  - Proteção anti-spam: user não pode entrar em dois jogos ao mesmo tempo
"""
import discord, random, asyncio, io
from discord import app_commands
from discord.ext import commands
from dataclasses import dataclass, field
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from .fichas import add_saldo

ASSETS  = Path(__file__).parent.parent / "assets" / "uno"
COLORS  = ["blue","green","red","yellow"]
SPECIALS = {10:"Skip", 11:"Reverse", 12:"+2", 13:"Wild", 14:"+4"}
CARD_W, CARD_H = 100, 148
MESA_TIMEOUT   = 480   # 8 min
PREMIO_BASE    = 150   # fichas por jogador eliminado
MAX_CARDS_PAGE = 10

# Rastreia users em jogo (evita entrar em duas mesas)
users_em_jogo: set[int] = set()


# ── Imagens ───────────────────────────────────────────────────────────────────
def _card_img(color, num) -> Image.Image:
    p = ASSETS / f"{color}{num}.png"
    if p.exists():
        return Image.open(p).convert("RGBA").resize((CARD_W, CARD_H), Image.LANCZOS)
    img = Image.new("RGBA", (CARD_W, CARD_H), (40,40,40,255))
    d   = ImageDraw.Draw(img)
    CMAP = {"blue":(30,80,200),"green":(20,160,60),"red":(200,30,30),
            "yellow":(210,180,10),"wild":(80,0,160)}
    d.rounded_rectangle([2,2,CARD_W-3,CARD_H-3], radius=10, fill=CMAP.get(color,(80,80,80)))
    try:    f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    except: f = ImageFont.load_default(size=28)
    d.text((CARD_W//2, CARD_H//2), SPECIALS.get(num, str(num)), font=f,
           fill=(255,255,255), anchor="mm")
    return img

def _back_img() -> Image.Image:
    p = ASSETS / "back.png"
    if p.exists():
        return Image.open(p).convert("RGBA").resize((CARD_W, CARD_H), Image.LANCZOS)
    return Image.new("RGBA", (CARD_W, CARD_H), (20,20,60))

def _render_hand(cards: list, highlight: set = None, page=0) -> io.BytesIO:
    highlight = highlight or set()
    start = page * MAX_CARDS_PAGE
    slice_ = cards[start:start + MAX_CARDS_PAGE]
    GAP = 8
    W   = len(slice_) * (CARD_W + GAP) + GAP
    H   = CARD_H + 32
    img = Image.new("RGBA", (max(W, 120), H), (0,0,0,0))
    for i, (c, n) in enumerate(slice_):
        ci  = _card_img(c, n)
        x   = GAP + i * (CARD_W + GAP)
        img.paste(ci, (x, 16), ci)
        real_idx = start + i
        if real_idx in highlight:
            d = ImageDraw.Draw(img)
            d.rounded_rectangle([x-2, 14, x+CARD_W+2, 16+CARD_H+2],
                                 radius=6, outline=(255,255,0,220), width=3)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf

def _render_table(topo, descarte_count, jogadores_info) -> io.BytesIO:
    W, H = 720, 520
    BG   = (12, 5, 20)
    img  = Image.new("RGB", (W, H), BG)
    d    = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle([4,4,W-5,H-5], radius=18, outline=(200,160,70), width=3)
    try:
        fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        fs = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except:
        fb = fs = ImageFont.load_default(size=20)
    d.text((W//2, 28), "✦  UNO  ✦", font=fb, fill=(248,218,130), anchor="mm")
    tc, tn = topo
    ti = _card_img(tc, tn).resize((120,172), Image.LANCZOS)
    img.paste(ti, (W//2-60, 60), ti)
    d.text((W//2, 240), f"Pilha: {descarte_count}", font=fs, fill=(180,170,150), anchor="mm")
    slot = W // max(len(jogadores_info), 1)
    for i, ji in enumerate(jogadores_info):
        px  = i * slot + slot // 2
        cor = (80,220,80) if ji["vez"] else (180,170,150)
        d.text((px, H-110), ji["name"][:12] + (" 👈" if ji["vez"] else ""),
               font=fb, fill=cor, anchor="mm")
        d.text((px, H-84), f"{ji['cards']} carta{'s' if ji['cards']!=1 else ''}",
               font=fs, fill=(150,140,130), anchor="mm")
        if ji.get("uno"):
            d.text((px, H-64), "UNO!", font=fb, fill=(255,50,50), anchor="mm")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


# ── Lógica ────────────────────────────────────────────────────────────────────
def _make_deck():
    deck = []
    for c in COLORS:
        deck.append((c, 0))
        for n in range(1, 13):
            deck += [(c, n), (c, n)]
    for _ in range(4):
        deck += [("wild",13), ("wild",14)]
    random.shuffle(deck)
    return deck

def _can_play(card, topo, chosen_color=None):
    c, n   = card
    tc, tn = topo
    efetivo = chosen_color or tc
    if c == "wild": return True
    if c == efetivo: return True
    if n == tn: return True
    return False

def _apply_card(game, card):
    """Aplica efeito. Retorna lista de msgs de log."""
    c, n  = card
    nj    = len(game.jogadores)
    prox  = (game.cur + game.dir) % nj
    msgs  = []
    if n == 10:
        game.cur = (prox + game.dir) % nj
        msgs.append(f"⏭️ {game.jogadores[prox].display_name} foi pulado!")
        return msgs
    if n == 11:
        game.dir *= -1
        msgs.append("🔄 Sentido invertido!")
    if n == 12:
        j = game.jogadores[prox]
        drawn = [game.deck.pop() for _ in range(min(2, len(game.deck)))]
        game.maos[j.id].extend(drawn)
        game.cur = (prox + game.dir) % nj
        msgs.append(f"✌️ {j.display_name} comprou 2 e foi pulado!")
        return msgs
    if n == 14:
        j = game.jogadores[prox]
        drawn = [game.deck.pop() for _ in range(min(4, len(game.deck)))]
        game.maos[j.id].extend(drawn)
        game.cur = (prox + game.dir) % nj
        msgs.append(f"✋ {j.display_name} comprou 4 e foi pulado!")
        return msgs
    return msgs


@dataclass
class UNOGame:
    canal: int
    jogadores: list = field(default_factory=list)
    maos: dict      = field(default_factory=dict)
    deck: list      = field(default_factory=list)
    descarte: list  = field(default_factory=list)
    cur: int        = 0
    dir: int        = 1
    estado: str     = "aguardando"
    chosen_color: str | None = None
    msg: discord.Message | None = None
    _timeout_task: object = field(default=None, repr=False)

    def atual(self):
        return self.jogadores[self.cur % len(self.jogadores)] if self.jogadores else None
    def topo(self):
        return self.descarte[-1] if self.descarte else ("wild", 13)


mesas: dict[int, UNOGame] = {}


async def _cancelar_timeout(g: UNOGame):
    if g._timeout_task and not g._timeout_task.done():
        g._timeout_task.cancel()

async def _agendar_timeout(g: UNOGame):
    await _cancelar_timeout(g)
    async def _exp():
        await asyncio.sleep(MESA_TIMEOUT)
        if mesas.get(g.canal) is not g: return
        for j in g.jogadores: users_em_jogo.discard(j.id)
        mesas.pop(g.canal, None)
        if g.msg:
            try: await g.msg.edit(content="⏰ UNO encerrado por inatividade.", attachments=[])
            except: pass
    g._timeout_task = asyncio.create_task(_exp())

async def _render_update(g: UNOGame):
    if not g.msg: return
    ji = [{"name": j.display_name,
           "cards": len(g.maos.get(j.id, [])),
           "vez": i == g.cur % len(g.jogadores),
           "uno": len(g.maos.get(j.id, [])) == 1}
          for i, j in enumerate(g.jogadores)]
    buf = _render_table(g.topo(), len(g.descarte), ji)
    try: await g.msg.edit(attachments=[discord.File(buf, "uno.png")])
    except: pass

def _reembaralhar(g: UNOGame):
    if len(g.deck) < 5 and len(g.descarte) > 1:
        topo = g.descarte.pop()
        g.deck += g.descarte
        random.shuffle(g.deck)
        g.descarte = [topo]


# ── Views ─────────────────────────────────────────────────────────────────────
class UNOView(discord.ui.View):
    def __init__(self, canal, bot):
        super().__init__(timeout=MESA_TIMEOUT)
        self.canal = canal; self.bot = bot

    async def on_timeout(self): pass

    @discord.ui.button(label="🃏 Ver Minha Mão", style=discord.ButtonStyle.primary, custom_id="uno_mao")
    async def ver_mao(self, interaction, btn):
        g = mesas.get(self.canal)
        if not g or g.estado != "jogando":
            return await interaction.response.send_message("Sem jogo ativo.", ephemeral=True)
        mao = g.maos.get(interaction.user.id)
        if mao is None:
            return await interaction.response.send_message("Você não está neste jogo.", ephemeral=True)
        jogaveis = {i for i, c in enumerate(mao)
                    if _can_play(c, g.topo(), g.chosen_color)
                    and g.atual() and g.atual().id == interaction.user.id}
        buf = _render_hand(mao, highlight=jogaveis, page=0)
        pages = (len(mao) - 1) // MAX_CARDS_PAGE + 1
        cor_ativa = f" (cor ativa: **{g.chosen_color}**)" if g.chosen_color else ""
        await interaction.response.send_message(
            f"**Sua mão** | Topo: {SPECIALS.get(g.topo()[1], g.topo()[1])} {g.topo()[0]}{cor_ativa}"
            + (f" | Página 1/{pages}" if pages > 1 else ""),
            file=discord.File(buf, "mao.png"),
            view=UNOJogarView(self.canal, self.bot, mao, g.atual().id if g.atual() else 0,
                              interaction.user.id, page=0),
            ephemeral=True)

    @discord.ui.button(label="📥 Comprar", style=discord.ButtonStyle.secondary, custom_id="uno_draw")
    async def comprar(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.get(self.canal)
        if not g or g.estado != "jogando":
            return await interaction.followup.send("Sem jogo ativo.", ephemeral=True)
        if not g.atual() or g.atual().id != interaction.user.id:
            return await interaction.followup.send("Não é sua vez.", ephemeral=True)
        _reembaralhar(g)
        if not g.deck:
            return await interaction.followup.send("Baralho vazio!", ephemeral=True)
        card = g.deck.pop()
        g.maos[interaction.user.id].append(card)
        g.chosen_color = None
        g.cur = (g.cur + g.dir) % len(g.jogadores)
        await _render_update(g)
        await _agendar_timeout(g)
        prox = g.atual()
        await interaction.followup.send(
            f"📥 Você comprou. Vez de **{prox.display_name if prox else '?'}**.", ephemeral=True)
        await interaction.channel.send(
            f"📥 **{interaction.user.display_name}** comprou. Vez de **{prox.display_name if prox else '?'}**.",
            view=UNOView(self.canal, self.bot))

    @discord.ui.button(label="🚪 Encerrar", style=discord.ButtonStyle.danger, custom_id="uno_end", row=1)
    async def encerrar(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.get(self.canal)
        if not g: return await interaction.followup.send("Sem jogo.", ephemeral=True)
        if not any(j.id == interaction.user.id for j in g.jogadores):
            return await interaction.followup.send("Você não está neste jogo.", ephemeral=True)
        await _cancelar_timeout(g)
        for j in g.jogadores: users_em_jogo.discard(j.id)
        mesas.pop(self.canal, None)
        try: await g.msg.delete()
        except: pass
        await interaction.followup.send("🃏 UNO encerrado.", ephemeral=True)


class UNOJogarView(discord.ui.View):
    """Ephemeral — mostra cartas da mão com paginação."""
    def __init__(self, canal, bot, mao, vez_uid, user_id, page=0):
        super().__init__(timeout=120)
        self.canal   = canal
        self.bot     = bot
        self.mao     = mao
        self.vez_uid = vez_uid
        self.user_id = user_id
        self.page    = page
        self.pages   = max(1, (len(mao) - 1) // MAX_CARDS_PAGE + 1)

        if user_id == vez_uid:
            start = page * MAX_CARDS_PAGE
            for i, (c, n) in enumerate(mao[start:start + MAX_CARDS_PAGE]):
                real_idx = start + i
                label    = f"{real_idx}: {SPECIALS.get(n, n)} {c}"[:25]
                btn      = discord.ui.Button(
                    label=label, style=discord.ButtonStyle.success, row=i // 5)
                btn.callback = self._make_cb(real_idx)
                self.add_item(btn)

        # Paginação
        if self.pages > 1:
            prev = discord.ui.Button(label="◀", style=discord.ButtonStyle.grey,
                                     disabled=(page == 0), row=2)
            nxt  = discord.ui.Button(label="▶", style=discord.ButtonStyle.grey,
                                     disabled=(page >= self.pages - 1), row=2)
            prev.callback = self._prev
            nxt.callback  = self._next
            self.add_item(prev)
            self.add_item(nxt)

    def _make_cb(self, idx):
        async def cb(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            g = mesas.get(self.canal)
            if not g or g.estado != "jogando":
                return await interaction.followup.send("Jogo encerrado.", ephemeral=True)
            if g.atual() and g.atual().id != interaction.user.id:
                return await interaction.followup.send("Não é mais sua vez.", ephemeral=True)
            mao = g.maos.get(interaction.user.id, [])
            if idx >= len(mao):
                return await interaction.followup.send("Carta inválida.", ephemeral=True)
            card = mao[idx]
            if not _can_play(card, g.topo(), g.chosen_color):
                return await interaction.followup.send("Não pode jogar essa carta agora.", ephemeral=True)

            mao.pop(idx)
            g.descarte.append(card)
            g.chosen_color = None
            c, n = card

            # Vitória
            if len(mao) == 0:
                g.estado = "fim"
                await _render_update(g)
                n_eliminados = len(g.jogadores) - 1
                premio = PREMIO_BASE * n_eliminados
                await add_saldo(self.bot, interaction.user, premio)
                for j in g.jogadores: users_em_jogo.discard(j.id)
                mesas.pop(self.canal, None)
                try: await g.msg.delete()
                except: pass
                await interaction.channel.send(
                    f"🏆 **{interaction.user.display_name}** venceu o UNO! **+{premio} fichas!** 🎉")
                return

            if len(mao) == 1:
                await interaction.channel.send(
                    f"⚠️ **UNO!** {interaction.user.display_name} tem 1 carta!")

            # Wild → pedir cor antes de avançar turno
            if c == "wild":
                await interaction.followup.send(
                    "Escolha a cor:", view=UNOCorView(self.canal, self.bot), ephemeral=True)
                return

            logs = _apply_card(g, card)
            if not logs:
                g.cur = (g.cur + g.dir) % len(g.jogadores)

            await _render_update(g)
            await _agendar_timeout(g)
            prox = g.atual()
            log_str = " | ".join(logs) + " " if logs else ""
            await interaction.channel.send(
                f"🃏 **{interaction.user.display_name}** jogou **{SPECIALS.get(n,n)} {c}**. "
                f"{log_str}Vez de **{prox.display_name if prox else '?'}**.",
                view=UNOView(self.canal, self.bot))
            await interaction.followup.send("Carta jogada!", ephemeral=True)
        return cb

    async def _prev(self, interaction: discord.Interaction):
        await self._flip_page(interaction, self.page - 1)

    async def _next(self, interaction: discord.Interaction):
        await self._flip_page(interaction, self.page + 1)

    async def _flip_page(self, interaction: discord.Interaction, new_page: int):
        g   = mesas.get(self.canal)
        mao = g.maos.get(interaction.user.id, []) if g else self.mao
        jogaveis = {i for i, c in enumerate(mao)
                    if _can_play(c, g.topo(), g.chosen_color)
                    and g.atual() and g.atual().id == interaction.user.id} if g else set()
        buf = _render_hand(mao, highlight=jogaveis, page=new_page)
        pages = max(1, (len(mao)-1)//MAX_CARDS_PAGE+1)
        await interaction.response.edit_message(
            content=f"**Sua mão** | Página {new_page+1}/{pages}",
            attachments=[discord.File(buf, "mao.png")],
            view=UNOJogarView(self.canal, self.bot, mao, self.vez_uid,
                              interaction.user.id, page=new_page))


class UNOCorView(discord.ui.View):
    CORES = [("🔵","Azul"),("🟢","Verde"),("🔴","vermelho"),("🟡","Amarelo")]

    def __init__(self, canal, bot):
        super().__init__(timeout=30)
        self.canal = canal; self.bot = bot
        for emoji, c in self.CORES:
            btn = discord.ui.Button(label=f"{emoji} {c.capitalize()}",
                                    style=discord.ButtonStyle.primary)
            btn.callback = self._make_cb(c)
            self.add_item(btn)

    def _make_cb(self, cor):
        async def cb(interaction):
            await interaction.response.defer(ephemeral=True)
            g = mesas.get(self.canal)
            if not g: return
            g.chosen_color = cor
            tc, tn = g.topo()
            nj = len(g.jogadores)
            if tn == 14:
                prox = (g.cur + g.dir) % nj
                j    = g.jogadores[prox]
                _reembaralhar(g)
                drawn = [g.deck.pop() for _ in range(min(4, len(g.deck)))]
                g.maos[j.id].extend(drawn)
                g.cur = (prox + g.dir) % nj
                await interaction.channel.send(
                    f"✋ {j.display_name} comprou 4 e pulou! Cor: **{cor}**",
                    view=UNOView(self.canal, self.bot))
            else:
                g.cur = (g.cur + g.dir) % nj
                prox  = g.atual()
                await interaction.channel.send(
                    f"🎨 Cor: **{cor}**. Vez de **{prox.display_name if prox else '?'}**.",
                    view=UNOView(self.canal, self.bot))
            await _render_update(g)
            await _agendar_timeout(g)
            await interaction.followup.send(f"Cor **{cor}** escolhida!", ephemeral=True)
            self.stop()
        return cb


class UNOEntrarView(discord.ui.View):
    def __init__(self, canal, bot):
        super().__init__(timeout=120)
        self.canal = canal; self.bot = bot

    @discord.ui.button(label="Entrar", emoji="🃏", style=discord.ButtonStyle.success)
    async def entrar(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.get(self.canal)
        if not g: return
        uid = interaction.user.id
        if uid in users_em_jogo:
            return await interaction.followup.send("Você já está em outro jogo.", ephemeral=True)
        if len(g.jogadores) >= 4:
            return await interaction.followup.send("Máximo 4 jogadores.", ephemeral=True)
        if any(j.id == uid for j in g.jogadores):
            return await interaction.followup.send("Você já entrou.", ephemeral=True)
        g.jogadores.append(interaction.user)
        users_em_jogo.add(uid)
        await interaction.followup.send(
            f"✅ {interaction.user.display_name} entrou! ({len(g.jogadores)}/4)")

    @discord.ui.button(label="Iniciar (min 2)", emoji="▶️", style=discord.ButtonStyle.primary)
    async def iniciar(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.get(self.canal)
        if not g or len(g.jogadores) < 2:
            return await interaction.followup.send("Mínimo 2 jogadores.", ephemeral=True)
        g.deck = _make_deck()
        g.maos = {}
        for j in g.jogadores:
            g.maos[j.id] = [g.deck.pop() for _ in range(7)]
        # Carta inicial não-especial
        while True:
            c = g.deck.pop()
            if c[0] != "wild" and c[1] < 10: break
            g.deck.insert(0, c)
        g.descarte = [c]; g.estado = "jogando"; g.cur = 0; g.dir = 1
        ji = [{"name":j.display_name,"cards":7,"vez":i==0,"uno":False}
              for i, j in enumerate(g.jogadores)]
        buf = _render_table(g.topo(), 1, ji)
        try: await interaction.message.delete()
        except: pass
        msg = await interaction.channel.send(
            f"🃏 **UNO!** Vez de **{g.jogadores[0].display_name}**. Premio: **{PREMIO_BASE}** fichas/jogador eliminado.",
            file=discord.File(buf, "uno.png"),
            view=UNOView(self.canal, self.bot))
        g.msg = msg
        await _agendar_timeout(g)


class UNO(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name="uno", description="Iniciar UNO (2-4 jogadores)")
    async def cmd_uno(self, interaction: discord.Interaction):
        cid = interaction.channel_id
        if cid in mesas and mesas[cid].estado == "jogando":
            return await interaction.response.send_message("Partida em andamento.", ephemeral=True)
        if interaction.user.id in users_em_jogo:
            return await interaction.response.send_message("Você já está em outro jogo.", ephemeral=True)
        mesas[cid] = UNOGame(canal=cid)
        await interaction.response.send_message(
            "🃏 **UNO!** 2-4 jogadores. Clique para entrar:", view=UNOEntrarView(cid, self.bot))


async def setup(bot):
    await bot.add_cog(UNO(bot))
