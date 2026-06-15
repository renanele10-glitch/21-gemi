"""
cogs/uno.py — UNO para 2-4 jogadores. Painel persistente por canal.
Assets: assets/uno/*.png (blue0-9, blue10=skip, blue11=reverse, blue12=+2,
        green/red/yellow idem, wild13=wild, wild14=+4, back.png)
Números 0-9, 10=skip, 11=reverse, 12=+2, 13=wild, 14=wild+4
"""
import discord, random, asyncio, io
from discord import app_commands
from discord.ext import commands
from dataclasses import dataclass, field
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).parent.parent / "assets" / "uno"

COLORS  = ["blue","green","red","yellow"]
SPECIALS = {10:"Skip",11:"Reverse",12:"+2",13:"Wild",14:"+4"}
CARD_W, CARD_H = 100, 148   # tamanho de exibição

# ── helpers de cartas ─────────────────────────────────────────────────────────
def _make_deck():
    deck = []
    for c in COLORS:
        deck.append((c, 0))
        for n in range(1,13):
            deck.append((c, n))
            deck.append((c, n))
    for _ in range(4):
        deck.append(("wild", 13))
        deck.append(("wild", 14))
    random.shuffle(deck)
    return deck

def _card_img(color, num) -> Image.Image:
    fname = f"{color}{num}.png"
    p = ASSETS / fname
    if p.exists():
        return Image.open(p).convert("RGBA").resize((CARD_W, CARD_H), Image.LANCZOS)
    # fallback: rect colorido
    img = Image.new("RGBA", (CARD_W, CARD_H), (40,40,40,255))
    d   = ImageDraw.Draw(img)
    CMAP = {"blue":(30,80,200),"green":(20,160,60),"red":(200,30,30),"yellow":(210,180,10),"wild":(80,0,160)}
    d.rounded_rectangle([2,2,CARD_W-3,CARD_H-3], radius=10, fill=CMAP.get(color,(80,80,80)))
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    except:
        f = ImageFont.load_default(size=28)
    label = SPECIALS.get(num, str(num))
    d.text((CARD_W//2, CARD_H//2), label, font=f, fill=(255,255,255), anchor="mm")
    return img

def _back_img() -> Image.Image:
    p = ASSETS / "back.png"
    if p.exists():
        return Image.open(p).convert("RGBA").resize((CARD_W, CARD_H), Image.LANCZOS)
    img = Image.new("RGBA",(CARD_W,CARD_H),(20,20,60))
    return img

def _render_hand(cards: list, highlight: set = None) -> io.BytesIO:
    """Renderiza mão do jogador em strip horizontal."""
    highlight = highlight or set()
    GAP = 8
    W = len(cards)*(CARD_W+GAP)+GAP
    H = CARD_H + 32
    img = Image.new("RGBA",(W,H),(0,0,0,0))
    for i,(c,n) in enumerate(cards):
        ci = _card_img(c,n)
        x = GAP + i*(CARD_W+GAP)
        img.paste(ci,(x,16),ci)
        if i in highlight:
            d = ImageDraw.Draw(img)
            d.rounded_rectangle([x-2,14,x+CARD_W+2,16+CARD_H+2],radius=6,outline=(255,255,0,220),width=3)
    buf = io.BytesIO()
    img.save(buf,"PNG")
    buf.seek(0)
    return buf

def _render_table(topo, descarte_count, jogadores_info, mobile=True) -> io.BytesIO:
    """Renderiza o estado da mesa: carta do topo + info dos jogadores."""
    W = 720 if mobile else 1100
    H = 520 if mobile else 420
    BG = (12, 5, 20)
    img = Image.new("RGB",(W,H),BG)
    d   = ImageDraw.Draw(img,"RGBA")
    # borda
    d.rounded_rectangle([4,4,W-5,H-5],radius=18,outline=(200,160,70),width=3)

    try:
        fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        fs = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except:
        fb = ImageFont.load_default(size=20)
        fs = fb

    # Título
    d.text((W//2,28),"✦  UNO  ✦",font=fb,fill=(248,218,130),anchor="mm")

    # Carta do topo (grande, centro)
    tc,tn = topo
    ti = _card_img(tc,tn).resize((120,172),Image.LANCZOS)
    tx = W//2 - 60
    ty = 60
    img.paste(ti,(tx,ty),ti)
    d.text((W//2, ty+180), f"Pilha: {descarte_count}", font=fs, fill=(180,170,150), anchor="mm")

    # Jogadores
    slot = W // max(len(jogadores_info),1)
    py_base = H - 110
    for i, ji in enumerate(jogadores_info):
        px = i*slot + slot//2
        cor = (80,220,80) if ji["vez"] else (180,170,150)
        nome = ji["name"][:12] + (" 👈" if ji["vez"] else "")
        d.text((px, py_base), nome, font=fb, fill=cor, anchor="mm")
        d.text((px, py_base+26), f"{ji['cards']} carta{'s' if ji['cards']!=1 else ''}", font=fs, fill=(150,140,130), anchor="mm")
        if ji.get("uno"): d.text((px, py_base+46), "UNO!", font=fb, fill=(255,50,50), anchor="mm")

    buf = io.BytesIO()
    img.save(buf,"PNG")
    buf.seek(0)
    return buf


def _can_play(card, topo, chosen_color=None):
    c,n = card
    tc,tn = topo
    efetivo = chosen_color or tc
    if c == "wild": return True
    if c == efetivo: return True
    if n == tn: return True
    return False

def _apply_card(game, card):
    """Aplica efeito da carta. Retorna msgs de log."""
    c, n = card
    msgs = []
    nj = len(game.jogadores)
    prox = (game.cur + game.dir) % nj

    if n == 10:  # Skip
        game.cur = (prox + game.dir) % nj
        msgs.append(f"⏭️ {game.jogadores[prox].display_name} foi pulado!")
        return msgs
    if n == 11:  # Reverse
        game.dir *= -1
        msgs.append("🔄 Sentido invertido!")
    if n == 12:  # +2
        j = game.jogadores[prox]
        drawn = [game.deck.pop() for _ in range(min(2, len(game.deck)))]
        game.maos[j.id].extend(drawn)
        game.cur = (prox + game.dir) % nj
        msgs.append(f"✌️ {j.display_name} comprou 2 cartas e foi pulado!")
        return msgs
    if n == 14:  # +4
        j = game.jogadores[prox]
        drawn = [game.deck.pop() for _ in range(min(4, len(game.deck)))]
        game.maos[j.id].extend(drawn)
        game.cur = (prox + game.dir) % nj
        msgs.append(f"✋ {j.display_name} comprou 4 cartas e foi pulado!")
        return msgs
    return msgs


@dataclass
class UNOGame:
    canal: int
    jogadores: list = field(default_factory=list)     # lista de discord.Member
    maos: dict      = field(default_factory=dict)      # uid → [(color,num)]
    deck: list      = field(default_factory=list)
    descarte: list  = field(default_factory=list)
    cur: int        = 0
    dir: int        = 1
    estado: str     = "aguardando"   # aguardando|jogando|fim
    chosen_color: str | None = None  # cor escolhida após wild
    msg: discord.Message | None = None
    mobile: bool    = True

    def atual(self):
        return self.jogadores[self.cur % len(self.jogadores)] if self.jogadores else None

    def topo(self):
        return self.descarte[-1] if self.descarte else ("wild",13)


mesas: dict[int,UNOGame] = {}


async def _render_update(g: UNOGame, extra=""):
    if not g.msg: return
    ji = [{
        "name": j.display_name,
        "cards": len(g.maos.get(j.id,[])),
        "vez": g.cur % len(g.jogadores) == i,
        "uno": len(g.maos.get(j.id,[])) == 1,
    } for i,j in enumerate(g.jogadores)]
    buf = _render_table(g.topo(), len(g.descarte), ji, mobile=g.mobile)
    try:
        await g.msg.edit(attachments=[discord.File(buf,"uno.png")])
    except Exception: pass


class UNOView(discord.ui.View):
    def __init__(self, canal, bot):
        super().__init__(timeout=None)
        self.canal = canal; self.bot = bot

    @discord.ui.button(label="🃏 Ver Minha Mão", style=discord.ButtonStyle.primary, custom_id="uno_mao")
    async def ver_mao(self, interaction, btn):
        g = mesas.get(self.canal)
        if not g or g.estado!="jogando":
            return await interaction.response.send_message("Sem jogo ativo.", ephemeral=True)
        mao = g.maos.get(interaction.user.id)
        if mao is None:
            return await interaction.response.send_message("Você não está neste jogo.", ephemeral=True)
        # Quais cartas podem ser jogadas
        jogaveis = {i for i,c in enumerate(mao) if _can_play(c, g.topo(), g.chosen_color)}
        buf = _render_hand(mao, highlight=jogaveis if g.atual() and g.atual().id==interaction.user.id else set())
        nm_topo = f"{SPECIALS.get(g.topo()[1],g.topo()[1])} {g.topo()[0]}" if g.chosen_color else f"{SPECIALS.get(g.topo()[1],g.topo()[1])} {g.topo()[0]}"
        cor_ativa = f" (cor ativa: **{g.chosen_color}**)" if g.chosen_color else ""
        msg_txt = f"**Sua mão** | Topo: {nm_topo}{cor_ativa}\nDigite o número da carta (0 = primeira) ou use os botões:"
        view2 = UNOJogarView(self.canal, self.bot, mao, g.atual().id if g.atual() else 0, interaction.user.id)
        await interaction.response.send_message(
            msg_txt, file=discord.File(buf,"mao.png"), view=view2, ephemeral=True)

    @discord.ui.button(label="📥 Comprar Carta", style=discord.ButtonStyle.secondary, custom_id="uno_draw")
    async def comprar(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.get(self.canal)
        if not g or g.estado!="jogando":
            return await interaction.followup.send("Sem jogo ativo.", ephemeral=True)
        if not g.atual() or g.atual().id != interaction.user.id:
            return await interaction.followup.send("Não é sua vez.", ephemeral=True)
        if not g.deck:
            if len(g.descarte) <= 1:
                return await interaction.followup.send("Baralho vazio!", ephemeral=True)
            topo_save = g.descarte.pop()
            g.deck = g.descarte; random.shuffle(g.deck)
            g.descarte = [topo_save]
        card = g.deck.pop()
        g.maos[interaction.user.id].append(card)
        g.chosen_color = None
        g.cur = (g.cur + g.dir) % len(g.jogadores)
        await _render_update(g)
        prox = g.atual()
        await interaction.followup.send(
            f"📥 Você comprou uma carta. Vez de **{prox.display_name if prox else '?'}**.",
            ephemeral=True)
        await interaction.channel.send(
            f"📥 **{interaction.user.display_name}** comprou uma carta. Vez de **{prox.display_name if prox else '?'}**.",
            view=UNOView(self.canal, self.bot))

    @discord.ui.button(label="🚪 Encerrar", style=discord.ButtonStyle.danger, custom_id="uno_end", row=1)
    async def encerrar(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.get(self.canal)
        if not g:
            return await interaction.followup.send("Sem jogo.", ephemeral=True)
        if not any(j.id==interaction.user.id for j in g.jogadores):
            return await interaction.followup.send("Você não está neste jogo.", ephemeral=True)
        mesas.pop(self.canal, None)
        try: await g.msg.delete()
        except: pass
        await interaction.followup.send("🃏 UNO encerrado.", ephemeral=True)


class UNOJogarView(discord.ui.View):
    """Botões de jogar carta (ephemeral, até 10 cartas por vez)."""
    def __init__(self, canal, bot, mao, vez_uid, user_id):
        super().__init__(timeout=120)
        self.canal=canal; self.bot=bot; self.mao=mao; self.vez_uid=vez_uid; self.user_id=user_id
        if user_id == vez_uid:
            for i in range(min(len(mao),10)):
                c,n = mao[i]
                label = f"{i}: {SPECIALS.get(n,n)} {c}"[:25]
                btn = discord.ui.Button(label=label, style=discord.ButtonStyle.success, row=i//5)
                btn.callback = self._make_cb(i)
                self.add_item(btn)

    def _make_cb(self, idx):
        async def cb(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            g = mesas.get(self.canal)
            if not g or g.estado!="jogando":
                return await interaction.followup.send("Jogo encerrado.", ephemeral=True)
            if g.atual() and g.atual().id != interaction.user.id:
                return await interaction.followup.send("Não é sua vez.", ephemeral=True)
            mao = g.maos.get(interaction.user.id,[])
            if idx >= len(mao):
                return await interaction.followup.send("Carta inválida.", ephemeral=True)
            card = mao[idx]
            if not _can_play(card, g.topo(), g.chosen_color):
                return await interaction.followup.send("Você não pode jogar essa carta agora.", ephemeral=True)

            mao.pop(idx)
            g.descarte.append(card)
            g.chosen_color = None

            # Verificar vitória
            if len(mao) == 0:
                g.estado="fim"
                await _render_update(g)
                mesas.pop(self.canal, None)
                try: await g.msg.delete()
                except: pass
                await interaction.channel.send(
                    f"🏆 **{interaction.user.display_name}** venceu o UNO! Parabéns!")
                return

            # UNO!
            if len(mao) == 1:
                await interaction.channel.send(f"⚠️ **UNO!** {interaction.user.display_name} tem 1 carta!")

            # Wild — pedir cor
            c,n = card
            if c == "wild":
                await interaction.followup.send("Escolha a cor:", view=UNOCorView(self.canal, self.bot), ephemeral=True)
                return

            logs = _apply_card(g, card)
            if not logs:
                g.cur = (g.cur + g.dir) % len(g.jogadores)

            await _render_update(g)
            prox = g.atual()
            log_str = " | ".join(logs) + " " if logs else ""
            await interaction.channel.send(
                f"🃏 **{interaction.user.display_name}** jogou **{SPECIALS.get(n,n)} {c}**. {log_str}Vez de **{prox.display_name if prox else '?'}**.",
                view=UNOView(self.canal, self.bot))
            await interaction.followup.send("Carta jogada!", ephemeral=True)
        return cb


class UNOCorView(discord.ui.View):
    """Escolha de cor após wild."""
    CORES = [("🔵","blue"),("🟢","green"),("🔴","red"),("🟡","yellow")]

    def __init__(self, canal, bot):
        super().__init__(timeout=60)
        self.canal=canal; self.bot=bot
        for emoji,c in self.CORES:
            btn = discord.ui.Button(label=f"{emoji} {c.capitalize()}", style=discord.ButtonStyle.primary)
            btn.callback = self._make_cb(c)
            self.add_item(btn)

    def _make_cb(self, cor):
        async def cb(interaction):
            await interaction.response.defer(ephemeral=True)
            g = mesas.get(self.canal)
            if not g: return
            g.chosen_color = cor
            # Aplicar efeito +4 se for wild+4
            topo_c, topo_n = g.topo()
            if topo_n == 14:
                nj = len(g.jogadores)
                prox = (g.cur + g.dir) % nj
                j = g.jogadores[prox]
                drawn = [g.deck.pop() for _ in range(min(4,len(g.deck)))]
                g.maos[j.id].extend(drawn)
                g.cur = (prox + g.dir) % nj
                await interaction.channel.send(f"✋ {j.display_name} comprou 4 e pulou! Cor: **{cor}**",
                                               view=UNOView(self.canal, self.bot))
            else:
                g.cur = (g.cur + g.dir) % len(g.jogadores)
                prox = g.atual()
                await interaction.channel.send(
                    f"🎨 Cor escolhida: **{cor}**. Vez de **{prox.display_name if prox else '?'}**.",
                    view=UNOView(self.canal, self.bot))
            await _render_update(g)
            await interaction.followup.send(f"Cor **{cor}** escolhida!", ephemeral=True)
            self.stop()
        return cb


class UNOEntrarView(discord.ui.View):
    def __init__(self, canal, bot):
        super().__init__(timeout=120)
        self.canal=canal; self.bot=bot

    @discord.ui.button(label="Entrar", emoji="🃏", style=discord.ButtonStyle.success)
    async def entrar(self, interaction, btn):
        await interaction.response.defer(ephemeral=True)
        g = mesas.get(self.canal)
        if not g: return
        if len(g.jogadores) >= 4:
            return await interaction.followup.send("Máximo 4 jogadores.", ephemeral=True)
        if any(j.id==interaction.user.id for j in g.jogadores):
            return await interaction.followup.send("Você já está na lista.", ephemeral=True)
        g.jogadores.append(interaction.user)
        await interaction.followup.send(f"✅ {interaction.user.display_name} entrou! ({len(g.jogadores)}/4)")

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
        # Carta inicial (não especial)
        while True:
            c = g.deck.pop()
            if c[0] != "wild" and c[1] < 10: break
            g.deck.insert(0, c)
        g.descarte = [c]
        g.estado = "jogando"; g.cur = 0; g.dir = 1
        ji = [{"name":j.display_name,"cards":7,"vez":i==0,"uno":False} for i,j in enumerate(g.jogadores)]
        buf = _render_table(g.topo(), 1, ji, mobile=g.mobile)
        try: await interaction.message.delete()
        except: pass
        msg = await interaction.channel.send(
            f"🃏 **UNO!** Vez de **{g.jogadores[0].display_name}**.",
            file=discord.File(buf,"uno.png"),
            view=UNOView(self.canal, self.bot))
        g.msg = msg


class UNO(commands.Cog):
    def __init__(self, bot): self.bot=bot

    @app_commands.command(name="uno", description="Iniciar jogo de UNO (2-4 jogadores)")
    async def cmd_uno(self, interaction: discord.Interaction):
        cid = interaction.channel_id
        if cid in mesas and mesas[cid].estado=="jogando":
            return await interaction.response.send_message("Partida em andamento.", ephemeral=True)
        mesas[cid] = UNOGame(canal=cid)
        await interaction.response.send_message(
            "🃏 **UNO!** 2-4 jogadores. Clique para entrar:", view=UNOEntrarView(cid, self.bot))


async def setup(bot):
    await bot.add_cog(UNO(bot))
