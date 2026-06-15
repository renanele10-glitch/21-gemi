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

def render_blackjack(dealer_cards, dealer_val, player_cards, player_val,
                     reveal_dealer=False, result="", mobile=True):
    W, H = (MOB_W, MOB_H) if mobile else (DSK_W, DSK_H)
    img, draw = _base(W, H)

    _label(draw, "✦  BLACKJACK 21  ✦", W//2, 42, GOLDL, 28)
    _divider(draw, W, 66)

    CW, CH, GAP = (130, 185, 14) if mobile else (150, 210, 18)
    max_w = W - 80

    # Dealer
    dv_str = str(dealer_val) if reveal_dealer else "?"
    _label(draw, f"DEALER  [ {dv_str} ]", W//2, 86, GOLD, 19)

    nd_vis = min(len(dealer_cards), 5 if mobile else 7)
    tw_d = nd_vis*CW + (nd_vis-1)*GAP
    if tw_d > max_w:
        sc = max_w/tw_d; cw_d=int(CW*sc); ch_d=int(CH*sc); gap_d=int(GAP*sc)
        tw_d = nd_vis*cw_d+(nd_vis-1)*gap_d
    else: cw_d,ch_d,gap_d = CW,CH,GAP
    sx_d = W//2 - tw_d//2; dy = 108
    for i in range(nd_vis):
        r2, s2 = dealer_cards[i]
        _card(draw, img, sx_d+i*(cw_d+gap_d), dy, r2, s2,
              face_down=(i==0 and not reveal_dealer), cw=cw_d, ch=ch_d)

    sep_y = dy + ch_d + 26
    _divider(draw, W, sep_y)
    _label(draw, f"VOCÊ  [ {player_val} ]", W//2, sep_y+24, CREAM, 19)

    np2 = len(player_cards)
    tw_j = np2*CW+(np2-1)*GAP
    if tw_j > max_w:
        sc = max_w/tw_j; cw_j=int(CW*sc); ch_j=int(CH*sc); gap_j=int(GAP*sc)
        tw_j = np2*cw_j+(np2-1)*gap_j
    else: cw_j,ch_j,gap_j = CW,CH,GAP
    sx_j = W//2 - tw_j//2; py = sep_y + 46
    for i,(r2,s2) in enumerate(player_cards):
        _card(draw, img, sx_j+i*(cw_j+gap_j), py, r2, s2, cw=cw_j, ch=ch_j)

    if result:
        rw, rh = min(560, W-80), 64
        ry = py+ch_j+22; rx = W//2-rw//2
        draw.rounded_rectangle([rx,ry,rx+rw,ry+rh], radius=10,
                                fill=(6,3,14,235), outline=(*GOLD,180), width=2)
        _label(draw, result, W//2, ry+rh//2, GOLDL, 22)

    return _bytes(img)


def bj_posicoes(dealer_cards, player_cards, mobile=True):
    W = MOB_W if mobile else DSK_W
    CW, CH, GAP = (130, 185, 14) if mobile else (150, 210, 18)
    max_w = W - 80
    nd = min(len(dealer_cards), 5 if mobile else 7)
    tw_d = nd*CW+(nd-1)*GAP
    if tw_d > max_w:
        sc=max_w/tw_d; cw_d=int(CW*sc); ch_d=int(CH*sc); gap_d=int(GAP*sc)
        tw_d = nd*cw_d+(nd-1)*gap_d
    else: cw_d,ch_d,gap_d = CW,CH,GAP
    sx_d = W//2-tw_d//2
    pos_d = [(sx_d+i*(cw_d+gap_d), 108, cw_d, ch_d) for i in range(nd)]
    np2 = len(player_cards)
    tw_j = np2*CW+(np2-1)*GAP
    if tw_j > max_w:
        sc=max_w/tw_j; cw_j=int(CW*sc); ch_j=int(CH*sc); gap_j=int(GAP*sc)
        tw_j = np2*cw_j+(np2-1)*gap_j
    else: cw_j,ch_j,gap_j = CW,CH,GAP
    sep_y = 108+ch_d+26
    sx_j = W//2-tw_j//2
    pos_j = [(sx_j+i*(cw_j+gap_j), sep_y+46, cw_j, ch_j) for i in range(np2)]
    return pos_d, pos_j, ch_d


# ══════════════════════════════════════════════════════════════════════════════
# POKER
# ══════════════════════════════════════════════════════════════════════════════

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
