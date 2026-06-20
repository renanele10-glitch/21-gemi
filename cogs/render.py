"""
cogs/render.py — Renderizador central. Mobile-first, layout adaptável.
"""
import io
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

# ── Dimensões ─────────────────────────────────────────────────────────────────
# Mobile (padrão, portrait)
MOB_W, MOB_H = 720, 960
# Desktop (landscape)
DSK_W, DSK_H = 1200, 680

# Xadrez
XD_MOB_W, XD_MOB_H = 680, 820
XD_DSK_W, XD_DSK_H = 900, 900

# ── Paleta ────────────────────────────────────────────────────────────────────
BG     = (8,   3, 12)
FELT   = (16,  7, 24)
GOLD   = (210, 170, 80)
GOLDL  = (248, 218, 130)
CREAM  = (238, 222, 196)
RED_D  = (148,  10, 10)
SHADOW = (0, 0, 0)
GRAY   = (75, 75, 85)
GREEN  = (60, 180, 80)
WHITE  = (240, 235, 220)


def _font(size, bold=True):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    if not bold:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    for p in candidates:
        if Path(p).exists():
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default(size=size)


def _bytes(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


def _base(w, h):
    img  = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rounded_rectangle([10, 10, w-11, h-11], radius=22, fill=FELT)
    draw.rounded_rectangle([3,  3,  w-4,  h-4],  radius=24, outline=GOLD,       width=3)
    draw.rounded_rectangle([8,  8,  w-9,  h-9],  radius=20, outline=(*GOLD,55), width=1)
    return img, draw


def _label(draw, text, cx, y, color=CREAM, size=18, shadow=True):
    f = _font(size)
    if shadow:
        draw.text((cx+1, y+1), text, font=f, fill=(0,0,0,180), anchor="mm")
    draw.text((cx, y), text, font=f, fill=color, anchor="mm")


def _divider(draw, w, y):
    draw.line([(60, y), (w-60, y)], fill=(*GOLD, 50), width=1)


def _card(draw, img, x, y, rank, suit, face_down=False, cw=140, ch=196):
    r = 12
    if face_down:
        draw.rounded_rectangle([x+3, y+3, x+cw+3, y+ch+3], radius=r, fill=(0,0,0,80))
        draw.rounded_rectangle([x, y, x+cw, y+ch], radius=r,
                                fill=(18, 8, 30), outline=GOLD, width=2)
        cx2, cy2 = x+cw//2, y+ch//2
        d, d2 = 28, 12
        draw.polygon([(cx2,cy2-d),(cx2+d,cy2),(cx2,cy2+d),(cx2-d,cy2)], fill=RED_D)
        draw.polygon([(cx2,cy2-d2),(cx2+d2,cy2),(cx2,cy2+d2),(cx2-d2,cy2)], fill=GOLD)
        return

    is_red = suit in ("♥", "♦")
    fc = (172, 10, 10) if is_red else (8, 6, 14)

    draw.rounded_rectangle([x+3, y+4, x+cw+3, y+ch+4], radius=r, fill=(0,0,0,100))
    draw.rounded_rectangle([x, y, x+cw, y+ch], radius=r,
                            fill=(252, 246, 232), outline=(170, 150, 110), width=1)

    # Rank cantos — fonte legível, sem estilo "estrela/amarelo"
    fr = _font(int(cw * 0.18))
    draw.text((x+10,    y+11),    rank, font=fr, fill=fc)
    draw.text((x+cw-10, y+ch-11), rank, font=fr, fill=fc, anchor="rb")

    # Naipe central
    fs = _font(int(cw * 0.46))
    draw.text((x+cw//2, y+ch//2), suit, font=fs, fill=fc, anchor="mm")


# ══════════════════════════════════════════════════════════════════════════════
# BLACKJACK
# ══════════════════════════════════════════════════════════════════════════════

TABLE_BJ = Path(__file__).parent.parent / "assets" / "bj_table.jpg"

# Posições dos slots na mesa (cx, cy, angulo) — mapeadas da imagem
_BJ_SLOTS  = [(200,430,-14),(620,455,0),(1170,418,14)]
_BJ_DEALER = (700, 185)
_BJ_SLOT_CW = [78, 65, 78]
_BJ_SLOT_CH = [112, 94, 112]
_BJ_W, _BJ_H = 1400, 840


def _make_bj_card(rank, suit, face_down=False, cw=78, ch=112):
    import math
    img  = Image.new("RGBA", (cw, ch), (0,0,0,0))
    d    = ImageDraw.Draw(img)
    if face_down:
        d.rounded_rectangle([0,0,cw-1,ch-1], radius=7,
                             fill=(20,8,35), outline=(180,150,60), width=2)
        cx2,cy2,dv = cw//2,ch//2,16
        d.polygon([(cx2,cy2-dv),(cx2+dv,cy2),(cx2,cy2+dv),(cx2-dv,cy2)], fill=(130,10,10))
        d.polygon([(cx2,cy2-7),(cx2+7,cy2),(cx2,cy2+7),(cx2-7,cy2)],     fill=(180,140,50))
    else:
        is_red = suit in ("♥","♦")
        fc = (172,10,10) if is_red else (12,10,20)
        d.rounded_rectangle([2,3,cw+1,ch+2], radius=7, fill=(0,0,0,60))
        d.rounded_rectangle([0,0,cw-1,ch-1], radius=7,
                             fill=(252,246,232), outline=(160,140,100), width=1)
        fr = _font(int(cw*0.19))
        d.text((5,4),        rank, font=fr, fill=fc)
        d.text((cw-5,ch-4),  rank, font=fr, fill=fc, anchor="rb")
        fs = _font(int(cw*0.40))
        d.text((cw//2,ch//2), suit, font=fs, fill=fc, anchor="mm")
    return img


def _bj_paste(base, card, cx, cy, angle=0):
    if angle != 0:
        card = card.rotate(angle, expand=True, resample=Image.BICUBIC)
    base.paste(card, (cx - card.width//2, cy - card.height//2), card)


def _bj_draw_hand(base, cards, cx, cy, angle=0, face_downs=None, cw=78, ch=112):
    import math
    n = len(cards)
    if n == 0: return
    face_downs = face_downs or [False]*n
    ov = int(cw*0.25)
    ca = [angle+(i-(n-1)/2)*3 for i in range(n)]
    tw = cw+(n-1)*(cw-ov)
    offs = [-(tw//2)+cw//2+i*(cw-ov) for i in range(n)]
    rad = math.radians(angle)
    for i,(r,s) in enumerate(cards):
        dx = offs[i]
        card = _make_bj_card(r, s, face_down=face_downs[i], cw=cw, ch=ch)
        _bj_paste(base, card,
                  int(cx+dx*math.cos(rad)), int(cy+dx*math.sin(rad)),
                  angle=ca[i])


def _bj_badge(draw, text, cx, cy, fill=(10,10,10,190), size=13):
    f  = _font(size)
    bb = draw.textbbox((0,0), text, font=f)
    bw = min(bb[2]-bb[0]+14, 160); bh = 22
    bx,by = cx-bw//2, cy-bh//2
    draw.rounded_rectangle([bx,by,bx+bw,by+bh], radius=5,
                            fill=fill, outline=GOLD, width=1)
    draw.text((cx,cy), text[:20], font=f, fill=GOLDL, anchor="mm")


def _bj_name(draw, text, cx, cy, active=False):
    f   = _font(13)
    col = (255,215,0) if active else (200,185,150)
    draw.text((cx+1,cy+1), text, font=f, fill=(0,0,0,200), anchor="mm")
    draw.text((cx,cy),     text, font=f, fill=col,          anchor="mm")


def render_blackjack(slots, dealer_cards, dealer_val, reveal_dealer=False, result_map=None):
    """
    slots: lista de dicts [{name, cards, val, active, result}]  max 3
    dealer_cards: list of (rank, suit)
    dealer_val: int
    reveal_dealer: bool
    """
    W, H = _BJ_W, _BJ_H
    if TABLE_BJ.exists():
        table = Image.open(TABLE_BJ).convert("RGB").resize((W,H), Image.LANCZOS)
        base  = table.convert("RGBA")
    else:
        base = Image.new("RGBA", (W,H), (8,48,8))
    draw = ImageDraw.Draw(base, "RGBA")

    # Dealer
    dcx, dcy = _BJ_DEALER
    fd_d = [i==0 and not reveal_dealer for i in range(len(dealer_cards))]
    _bj_draw_hand(base, dealer_cards, dcx, dcy, face_downs=fd_d)
    dv = str(dealer_val) if reveal_dealer else "?"
    _bj_badge(draw, f"{dv} pts", dcx, dcy-62)

    # Jogadores
    for i, slot in enumerate(slots[:3]):
        cx, cy, angle = _BJ_SLOTS[i]
        cw, ch = _BJ_SLOT_CW[i], _BJ_SLOT_CH[i]
        cards  = slot.get("cards", [])
        val    = slot.get("val", 0)
        name   = slot.get("name", f"P{i+1}")
        active = slot.get("active", False)
        result = slot.get("result", "")
        if not cards: continue
        _bj_draw_hand(base, cards, cx, cy, angle=angle, cw=cw, ch=ch)
        pts_y  = cy - ch//2 - 18
        name_y = cy + ch//2 + 18
        fill = (20,90,20,210) if active else (10,10,10,190)
        _bj_badge(draw, f"{val} pts", cx, pts_y, fill=fill)
        if result:
            win  = any(w in result for w in ["venceu","BLACKJACK","estourou"])
            lose = any(w in result for w in ["perdeu","Bust","Dealer"])
            rc   = (20,120,20,230) if win else (140,20,20,230) if lose else (100,90,10,230)
            _bj_badge(draw, result[:18], cx, pts_y-26, fill=rc)
        _bj_name(draw, name[:14], cx, name_y, active=active)

    return _bytes(base.convert("RGB"))


def bj_posicoes(slots_count=1):
    """Retorna posições (cx,cy,angle) dos slots ativos — para compatibilidade com animator."""
    return [_BJ_SLOTS[i] for i in range(min(slots_count, 3))]

def render_poker(community, players, pot, current_name="", mobile=True):
    W, H = (MOB_W, MOB_H) if mobile else (DSK_W, DSK_H)
    img, draw = _base(W, H)

    _label(draw, "✦  TEXAS HOLD'EM  ✦", W//2, 36, GOLDL, 26)
    _label(draw, f"POT: {pot:,} fichas", W//2, 66, GOLDL, 18)
    _divider(draw, W, 84)

    # Cartas comunitárias — maiores
    CW, CH, GAP = (110, 158, 10) if mobile else (120, 170, 12)
    cc_y = 94
    n = len(community)
    if n:
        tw = n*CW+(n-1)*GAP
        sx = W//2-tw//2
        for i,(r2,s2) in enumerate(community):
            _card(draw, img, sx+i*(CW+GAP), cc_y, r2, s2, cw=CW, ch=CH)
    else:
        _label(draw, "Aguardando cartas da mesa...", W//2, cc_y+CH//2, GRAY, 16)

    # Jogadores
    np2 = len(players)
    slot = W // max(np2, 1)

    if mobile:
        cw2, ch2 = 82, 116
        p_y = cc_y + CH + 36
    else:
        cw2, ch2 = 90, 128
        p_y = cc_y + CH + 40

    SC = {"active": CREAM, "folded": GRAY, "all-in": (255,130,0), "winner": (80,220,80)}

    for i, p in enumerate(players):
        px  = i*slot + slot//2
        col = SC.get(p.get("status","active"), CREAM)

        if p["name"] == current_name:
            draw.rounded_rectangle([px-slot//2+6, p_y-6, px+slot//2-6, p_y+ch2+72],
                                    radius=8, fill=(40,15,5,130), outline=(*GOLD,200), width=2)

        tag = " 🎩" if p.get("dealer") else ""
        nm = p["name"][:10]+tag
        _label(draw, nm, px, p_y+10, col, 14)
        _label(draw, f"{p['chips']:,} 🪙", px, p_y+28, CREAM, 13)
        if p.get("bet",0): _label(draw, f"Bet: {p['bet']}", px, p_y+44, GOLD, 12)

        cards = p.get("cards",[])
        tw2 = len(cards)*cw2+(len(cards)-1)*6
        sx2 = px-tw2//2
        for j,(r2,s2) in enumerate(cards):
            _card(draw, img, sx2+j*(cw2+6), p_y+60, r2, s2,
                  face_down=(s2=="?"), cw=cw2, ch=ch2)

        st = p.get("status","")
        if st in ("folded","all-in","winner"):
            _label(draw, {"folded":"FOLD","all-in":"ALL-IN","winner":"🏆"}[st],
                   px, p_y+ch2+70, col, 13)

    return _bytes(img)


# ══════════════════════════════════════════════════════════════════════════════
# TRUCO  — até 4 jogadores (2v2)
# ══════════════════════════════════════════════════════════════════════════════

def render_truco(equipe_nos, equipe_eles, pontos_nos, pontos_eles,
                 vira, mesa_cartas, rodada, max_pontos, mobile=True):
    W, H = (MOB_W, MOB_H) if mobile else (DSK_W, DSK_H)
    img, draw = _base(W, H)

    _label(draw, "✦  TRUCO PAULISTA  ✦", W//2, 36, GOLDL, 26)
    _divider(draw, W, 58)

    # Placar
    _label(draw, f"NÓS: {pontos_nos}", W//4,   76, (80,220,80), 20)
    _label(draw, f"ELES: {pontos_eles}", 3*W//4, 76, (220,80,80), 20)
    _label(draw, f"Rodada {rodada}/3", W//2, 76, GOLD, 15)

    # Vira
    CW, CH = (90, 128) if mobile else (100, 140)
    cx, cy = W//2, H//2 - 40
    vr, vs = vira
    _label(draw, "VIRA", cx, cy-CH//2-20, GOLD, 14)
    _card(draw, img, cx-CW//2, cy-CH//2, vr, vs, cw=CW, ch=CH)

    # Cartas na mesa ao redor da vira
    offs = [(-145,-40),(145,-40),(-145,40),(145,40),(0,-115),(0,105)]
    MCW, MCH = (72, 102) if mobile else (82, 116)
    for i,(r2,s2,nome) in enumerate(mesa_cartas[:6]):
        ox, oy = offs[i]
        _card(draw, img, cx+ox-MCW//2, cy+oy-MCH//2, r2, s2, cw=MCW, ch=MCH)
        _label(draw, nome[:10], cx+ox, cy+oy+MCH//2+8, CREAM, 11)

    # Times nas laterais — maiores
    _draw_equipe(draw, img, equipe_nos,  16,    92, H-20, left=True,  mobile=mobile)
    _draw_equipe(draw, img, equipe_eles, W-16, 92, H-20, left=False, mobile=mobile)
    return _bytes(img)


def _draw_equipe(draw, img, jogadores, bx, y1, y2, left=True, mobile=True):
    slot = (y2-y1)//max(len(jogadores),1)
    CW, CH, GAP = (60, 84, 4) if mobile else (68, 96, 5)
    for i, p in enumerate(jogadores):
        py = y1+i*slot+slot//2
        tx = bx+(12 if left else -12)
        draw.text((tx, py-CH//2-16), p["name"][:12], font=_font(12),
                  fill=GOLDL, anchor=("lm" if left else "rm"))
        cards = p.get("cards",[])
        n = len(cards)
        sx = bx+(10 if left else -(10+n*(CW+GAP)))
        for j,(r2,s2) in enumerate(cards):
            _card(draw, img, sx+j*(CW+GAP), py-CH//2, r2, s2,
                  face_down=p.get("jogou",False) or s2=="?", cw=CW, ch=CH)


# ══════════════════════════════════════════════════════════════════════════════
# XADREZ
# ══════════════════════════════════════════════════════════════════════════════

PECAS = {"K":"♔","Q":"♕","R":"♖","B":"♗","N":"♘","P":"♙",
         "k":"♚","q":"♛","r":"♜","b":"♝","n":"♞","p":"♟"}


def render_xadrez(board, nome_brancas, nome_pretas, vez,
                  last_move=None, selected=None, valid_moves=None, mobile=True):
    W, H = (XD_MOB_W, XD_MOB_H) if mobile else (XD_DSK_W, XD_DSK_H)
    img, draw = _base(W, H)
    _label(draw, "✦  XADREZ  ✦", W//2, 34, GOLDL, 24)

    margin = 40
    b_size = W - 2*margin
    cell   = b_size // 8
    bx, by = margin, 56

    LIGHT = (200, 176, 140); DARK2 = (90, 54, 26)
    lm = set()
    if last_move:
        r1,c1,r2,c2=last_move; lm={(r1,c1),(r2,c2)}
    vm = set(valid_moves or [])

    for row in range(8):
        for col in range(8):
            x1=bx+col*cell; y1=by+row*cell
            light=(row+col)%2==0
            draw.rectangle([x1,y1,x1+cell,y1+cell], fill=(LIGHT if light else DARK2))
            if (row,col) in lm:
                ov=Image.new("RGBA",(cell,cell),(210,230,80,155) if light else (165,195,45,155))
                img.paste(ov,(x1,y1),ov); draw=ImageDraw.Draw(img,"RGBA")
            if selected and (row,col)==selected:
                ov=Image.new("RGBA",(cell,cell),(80,160,255,170))
                img.paste(ov,(x1,y1),ov); draw=ImageDraw.Draw(img,"RGBA")
            if (row,col) in vm:
                ov=Image.new("RGBA",(cell,cell),(60,210,60,120))
                img.paste(ov,(x1,y1),ov); draw=ImageDraw.Draw(img,"RGBA")
            p=board[row][col]
            if p and p!=".":
                sym=PECAS.get(p,p); white=p.isupper()
                fp=_font(cell-8)
                cx2=x1+cell//2; cy2=y1+cell//2
                draw.text((cx2+2,cy2+2),sym,font=fp,fill=(0,0,0,200),anchor="mm")
                draw.text((cx2,cy2),sym,font=fp,
                          fill=(245,238,220) if white else (12,6,18),anchor="mm")

    fc=_font(13,bold=False)
    for i in range(8):
        draw.text((bx+i*cell+cell//2, by+b_size+14),chr(65+i),font=fc,fill=GOLD,anchor="mm")
        draw.text((bx-16, by+i*cell+cell//2),str(8-i),font=fc,fill=GOLD,anchor="mm")

    iy=by+b_size+36
    turno=nome_brancas if vez=="white" else nome_pretas
    _label(draw, f"{'⬜' if vez=='white' else '⬛'}  Vez de: {turno}", W//2, iy, GOLDL, 16)
    _label(draw, f"⬜ {nome_brancas}   vs   ⬛ {nome_pretas}", W//2, iy+24, CREAM, 13)
    return _bytes(img)
