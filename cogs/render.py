"""
cogs/render.py — Layout grande, cartas grandes, português.
Imagem 1024x600 preenche bem o Discord em mobile e PC.
"""
import io
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

# ── Dimensões ─────────────────────────────────────────────────────────────────
W,  H  = 1024, 600   # blackjack / poker / truco
WP, HP = 600,  820   # xadrez (portrait)

# ── Paleta ────────────────────────────────────────────────────────────────────
BG     = (10,  4, 14)
FELT   = (18,  8, 28)
GOLD   = (210, 170, 80)
GOLDL  = (245, 215, 130)
CREAM  = (238, 222, 196)
RED_D  = (145,  12, 12)
SHADOW = (0, 0, 0)
GRAY   = (75, 75, 85)
GREEN  = (18, 88, 38)

# ── Fonte ─────────────────────────────────────────────────────────────────────
def _font(size, bold=True):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    if not bold:
        candidates = [p.replace("Bold","Regular").replace("-Bold","") for p in candidates]
    for p in candidates:
        if Path(p).exists():
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default(size=size)

# ── Helpers ───────────────────────────────────────────────────────────────────
def _bytes(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf

def _base(portrait=False):
    ow, oh = (WP, HP) if portrait else (W, H)
    img  = Image.new("RGB", (ow, oh), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    # Fundo feltro interno
    draw.rounded_rectangle([12, 12, ow-13, oh-13], radius=18, fill=FELT)
    # Borda dupla dourada
    draw.rounded_rectangle([4,  4,  ow-5,  oh-5],  radius=20, outline=GOLD,          width=3)
    draw.rounded_rectangle([9,  9,  ow-10, oh-10], radius=16, outline=(*GOLD, 60),   width=1)
    return img, draw, ow, oh

def _title(draw, text, ow, y=30):
    f = _font(24)
    draw.text((ow//2+1, y+1), text, font=f, fill=SHADOW,  anchor="mm")
    draw.text((ow//2,   y),   text, font=f, fill=GOLDL,   anchor="mm")
    # Linha decorativa
    lw = 180
    draw.line([(ow//2 - lw, y+15), (ow//2 + lw, y+15)], fill=(*GOLD, 80), width=1)

def _label(draw, text, cx, y, color=CREAM, size=15):
    f = _font(size)
    draw.text((cx+1, y+1), text, font=f, fill=SHADOW, anchor="mm")
    draw.text((cx,   y),   text, font=f, fill=color,  anchor="mm")

# ── Carta ─────────────────────────────────────────────────────────────────────
def _card(draw, img, x, y, rank, suit, face_down=False, cw=110, ch=155):
    r = 10
    if face_down:
        draw.rounded_rectangle([x, y, x+cw, y+ch], radius=r,
                                fill=(18, 8, 30), outline=GOLD, width=2)
        cx2, cy2 = x+cw//2, y+ch//2
        d  = 22
        d2 = 9
        draw.polygon([(cx2,cy2-d),(cx2+d,cy2),(cx2,cy2+d),(cx2-d,cy2)], fill=RED_D)
        draw.polygon([(cx2,cy2-d2),(cx2+d2,cy2),(cx2,cy2+d2),(cx2-d2,cy2)], fill=GOLD)
        return

    is_red = suit in ("♥","♦")
    fc     = (175, 12, 12) if is_red else (8, 8, 12)

    # Sombra
    draw.rounded_rectangle([x+3, y+3, x+cw+3, y+ch+3], radius=r, fill=(0,0,0,90))
    # Corpo
    draw.rounded_rectangle([x, y, x+cw, y+ch], radius=r,
                            fill=(248, 240, 224), outline=(175, 155, 115), width=1)
    # Rank cantos
    fr = _font(17)
    draw.text((x+8,       y+7),       rank, font=fr, fill=fc)
    draw.text((x+cw-8,    y+ch-8),    rank, font=fr, fill=fc, anchor="rb")
    # Naipe central grande
    fs = _font(46)
    draw.text((x+cw//2, y+ch//2), suit, font=fs, fill=fc, anchor="mm")

# ══════════════════════════════════════════════════════════════════════════════
# BLACKJACK
# ══════════════════════════════════════════════════════════════════════════════
def render_blackjack(dealer_cards, dealer_val, player_cards, player_val,
                     reveal_dealer=False, result=""):
    img, draw, ow, oh = _base()
    _title(draw, "✦  BLACKJACK 21  ✦", ow)

    CW, CH, GAP = 110, 155, 14

    # ── Dealer ──────────────────────────────────────────────────────────────
    dv_str = str(dealer_val) if reveal_dealer else "?"
    _label(draw, f"⚜  DEALER  [ {dv_str} ]", ow//2, 62, GOLD, 15)

    nd = len(dealer_cards)
    tw = nd*CW + (nd-1)*GAP
    sx = ow//2 - tw//2
    dy = 78
    for i, (rank, suit) in enumerate(dealer_cards):
        _card(draw, img, sx + i*(CW+GAP), dy, rank, suit,
              face_down=(i==0 and not reveal_dealer), cw=CW, ch=CH)

    # ── Separador ───────────────────────────────────────────────────────────
    sep_y = dy + CH + 14
    draw.line([(60, sep_y), (ow-60, sep_y)], fill=(*GOLD, 50), width=1)

    # ── Jogador ─────────────────────────────────────────────────────────────
    _label(draw, f"VOCÊ  [ {player_val} ]", ow//2, sep_y+16, CREAM, 15)

    np2 = len(player_cards)
    tw2 = np2*CW + (np2-1)*GAP
    sx2 = ow//2 - tw2//2
    py  = sep_y + 30

    # Se cartas saem da tela, diminui escala
    if tw2 > ow - 80:
        scale = (ow - 80) / tw2
        cw2 = int(CW * scale)
        ch2 = int(CH * scale)
        gap2 = int(GAP * scale)
        tw2s = np2*cw2 + (np2-1)*gap2
        sx2  = ow//2 - tw2s//2
        for i, (rank, suit) in enumerate(player_cards):
            _card(draw, img, sx2 + i*(cw2+gap2), py, rank, suit, cw=cw2, ch=ch2)
    else:
        for i, (rank, suit) in enumerate(player_cards):
            _card(draw, img, sx2 + i*(CW+GAP), py, rank, suit, cw=CW, ch=CH)

    # ── Resultado ────────────────────────────────────────────────────────────
    if result:
        rw, rh = 480, 52
        rx, ry = ow//2 - rw//2, oh - rh - 10
        draw.rounded_rectangle([rx, ry, rx+rw, ry+rh], radius=8,
                                fill=(8,4,16,230), outline=(*GOLD,160), width=2)
        _label(draw, result, ow//2, ry+rh//2, GOLDL, 18)

    return _bytes(img)


# ══════════════════════════════════════════════════════════════════════════════
# POKER
# ══════════════════════════════════════════════════════════════════════════════
def render_poker(community, players, pot, current_name=""):
    img, draw, ow, oh = _base()
    _title(draw, "✦  TEXAS HOLD'EM  ✦", ow)
    _label(draw, f"💰  POT: {pot:,} fichas", ow//2, 60, GOLDL, 15)

    CW, CH, GAP = 80, 112, 8

    # Community cards
    cc_y = 76
    n = len(community)
    if n:
        tw = n*CW + (n-1)*GAP
        sx = ow//2 - tw//2
        for i, (r, s) in enumerate(community):
            _card(draw, img, sx+i*(CW+GAP), cc_y, r, s, cw=CW, ch=CH)
    else:
        _label(draw, "Aguardando cartas da mesa...", ow//2, cc_y+CH//2, GRAY, 13)

    # Jogadores
    np2 = len(players)
    slot = ow // max(np2, 1)
    cw2, ch2 = 55, 77
    p_y = cc_y + CH + 28

    SC = {"active":CREAM, "folded":GRAY, "all-in":(255,130,0), "winner":(80,220,80)}

    for i, p in enumerate(players):
        px   = i*slot + slot//2
        col  = SC.get(p.get("status","active"), CREAM)
        is_c = p["name"] == current_name

        if is_c:
            draw.rounded_rectangle([px-slot//2+4, p_y-4, px+slot//2-4, p_y+ch2+58],
                                    radius=6, fill=(40,15,5,130), outline=(*GOLD,180), width=2)

        tag = " 🎩" if p.get("dealer") else ""
        _label(draw, p["name"][:10]+tag, px, p_y+8, col, 11)
        _label(draw, f"{p['chips']:,} 🪙", px, p_y+22, CREAM, 10)
        if p.get("bet",0):
            _label(draw, f"Bet: {p['bet']}", px, p_y+35, GOLD, 10)

        cards = p.get("cards",[])
        tw2 = len(cards)*cw2 + (len(cards)-1)*4
        sx2 = px - tw2//2
        for j, (r, s) in enumerate(cards):
            _card(draw, img, sx2+j*(cw2+4), p_y+48, r, s,
                  face_down=(s=="?"), cw=cw2, ch=ch2)

        st = p.get("status","")
        if st in ("folded","all-in","winner"):
            lbs = {"folded":"FOLD","all-in":"ALL-IN","winner":"🏆"}
            _label(draw, lbs[st], px, p_y+ch2+56, col, 11)

    return _bytes(img)


# ══════════════════════════════════════════════════════════════════════════════
# TRUCO
# ══════════════════════════════════════════════════════════════════════════════
def render_truco(equipe_nos, equipe_eles, pontos_nos, pontos_eles,
                 vira, mesa_cartas, rodada, max_pontos):
    img, draw, ow, oh = _base()
    _title(draw, f"✦  TRUCO PAULISTA  ✦", ow)

    CW, CH = 62, 87
    cx = ow//2; cy = oh//2

    _label(draw, f"NÓS: {pontos_nos}", 90,    52, (80,220,80), 16)
    _label(draw, f"ELES: {pontos_eles}", ow-90, 52, (220,80,80), 16)
    _label(draw, f"Rodada {rodada}/3", cx, 52, GOLD, 13)

    # Vira
    vr, vs = vira
    _label(draw, "VIRA", cx, cy-CH//2-16, GOLD, 11)
    _card(draw, img, cx-CW//2, cy-CH//2, vr, vs, cw=CW, ch=CH)

    # Cartas na mesa
    offs = [(-120,-25),(120,-25),(-120,35),(120,35),(0,-90),(0,80)]
    for i, (r, s, nome) in enumerate(mesa_cartas[:6]):
        ox, oy = offs[i]
        _card(draw, img, cx+ox-CW//2+5, cy+oy-CH//2, r, s, cw=CW-10, ch=CH-14)
        _label(draw, nome[:8], cx+ox+5, cy+oy+CH//2, CREAM, 9)

    _draw_equipe(draw, img, equipe_nos,  14,    70, oh-20, left=True)
    _draw_equipe(draw, img, equipe_eles, ow-14, 70, oh-20, left=False)

    return _bytes(img)

def _draw_equipe(draw, img, jogadores, bx, y1, y2, left=True):
    slot = (y2-y1) // max(len(jogadores),1)
    CW, CH, GAP = 44, 61, 3
    for i, p in enumerate(jogadores):
        py  = y1 + i*slot + slot//2
        anc = "lm" if left else "rm"
        tx  = bx + (8 if left else -8)
        draw.text((tx, py-CH//2-12), p["name"][:10],
                  font=_font(10), fill=GOLDL, anchor=anc)
        cards = p.get("cards",[])
        n = len(cards)
        sx = bx + (8 if left else -(8+n*(CW+GAP)))
        for j, (r, s) in enumerate(cards):
            fd = p.get("jogou", False) or s=="?"
            _card(draw, img, sx+j*(CW+GAP), py-CH//2, r, s, face_down=fd, cw=CW, ch=CH)


# ══════════════════════════════════════════════════════════════════════════════
# XADREZ
# ══════════════════════════════════════════════════════════════════════════════
PECAS = {
    "K":"♔","Q":"♕","R":"♖","B":"♗","N":"♘","P":"♙",
    "k":"♚","q":"♛","r":"♜","b":"♝","n":"♞","p":"♟",
}

def render_xadrez(board, nome_brancas, nome_pretas, vez,
                  last_move=None, selected=None, valid_moves=None):
    img, draw, ow, oh = _base(portrait=True)
    _title(draw, "✦  XADREZ  ✦", ow)

    margin = 38
    b_size = ow - 2*margin
    cell   = b_size // 8
    bx, by = margin, 55

    LIGHT = (198, 172, 132)
    DARK2 = (88,  52,  22)
    HL_L  = (205, 225, 95,  160)
    HL_D  = (158, 190, 48,  160)
    SEL   = (95,  172, 255, 175)
    VALID = (65,  200, 65,  130)

    lm = set()
    if last_move:
        r1,c1,r2,c2 = last_move
        lm = {(r1,c1),(r2,c2)}
    vm = set(valid_moves or [])

    for row in range(8):
        for col in range(8):
            x1 = bx + col*cell
            y1 = by + row*cell
            light = (row+col)%2 == 0
            draw.rectangle([x1,y1,x1+cell,y1+cell], fill=(LIGHT if light else DARK2))

            if (row,col) in lm:
                ov = Image.new("RGBA",(cell,cell), HL_L if light else HL_D)
                img.paste(ov,(x1,y1),ov); draw=ImageDraw.Draw(img,"RGBA")
            if selected and (row,col)==selected:
                ov = Image.new("RGBA",(cell,cell), SEL)
                img.paste(ov,(x1,y1),ov); draw=ImageDraw.Draw(img,"RGBA")
            if (row,col) in vm:
                ov = Image.new("RGBA",(cell,cell), VALID)
                img.paste(ov,(x1,y1),ov); draw=ImageDraw.Draw(img,"RGBA")

            p = board[row][col]
            if p and p != ".":
                sym   = PECAS.get(p, p)
                white = p.isupper()
                fp    = _font(cell-10)
                cx2   = x1+cell//2
                cy2   = y1+cell//2
                draw.text((cx2+1,cy2+2), sym, font=fp, fill=(0,0,0,180), anchor="mm")
                draw.text((cx2,cy2), sym, font=fp,
                           fill=(242,235,218) if white else (10,5,16), anchor="mm")

    # Coordenadas
    fc = _font(11, bold=False)
    for i in range(8):
        draw.text((bx+i*cell+cell//2, by+b_size+14), chr(65+i), font=fc, fill=GOLD, anchor="mm")
        draw.text((bx-14, by+i*cell+cell//2), str(8-i), font=fc, fill=GOLD, anchor="mm")

    # Info
    iy = by + b_size + 34
    turno = nome_brancas if vez=="white" else nome_pretas
    icone = "⬜" if vez=="white" else "⬛"
    _label(draw, f"{icone}  Vez de: {turno}", ow//2, iy, GOLDL, 14)
    _label(draw, f"⬜ {nome_brancas}   vs   ⬛ {nome_pretas}", ow//2, iy+22, CREAM, 11)

    return _bytes(img)
