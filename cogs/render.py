"""
cogs/render.py — Gerador de imagens placeholder.
Quando você tiver as imagens finais de IA, substitua as funções
render_blackjack / render_poker / render_truco / render_xadrez.
"""
import io
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

W, H = 900, 1100   # landscape (blackjack, poker, truco)
WP, HP = 520, 720  # portrait (xadrez)

# Paleta
BG      = (12,  6, 16)
FELT    = (25, 12, 35)
GOLD    = (210, 170, 80)
GOLD_LT = (240, 210, 130)
CREAM   = (235, 220, 195)
WHITE   = (245, 240, 230)
RED_D   = (140,  15, 15)
SHADOW  = (0, 0, 0)
GRAY    = (80, 80, 90)
GREEN   = (20, 90, 40)


def _font(size, bold=True):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    if not bold:
        paths = [p.replace("Bold","Regular").replace("-Bold","") for p in paths]
    for p in paths:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default(size=size)


def _base(portrait=False):
    ow, oh = (WP, HP) if portrait else (W, H)
    img  = Image.new("RGB", (ow, oh), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    # Borda dourada
    draw.rectangle([0, 0, ow-1, oh-1], outline=GOLD, width=3)
    draw.rectangle([4, 4, ow-5, oh-5], outline=(*GOLD, 80), width=1)
    return img, draw, ow, oh


def _bytes(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


def _title(draw, text, ow):
    f = _font(22)
    draw.text((ow//2 + 1, 25), text, font=f, fill=SHADOW, anchor="mm")
    draw.text((ow//2, 25), text, font=f, fill=GOLD_LT, anchor="mm")


def _card(draw, img, x, y, rank, suit, face_down=False, cw=85, ch=120):
    """Desenha uma carta placeholder."""
    if face_down:
        draw.rounded_rectangle([x, y, x+cw, y+ch], radius=8,
                                fill=(20, 10, 35), outline=GOLD, width=2)
        # Losango decorativo
        cx, cy = x+cw//2, y+ch//2
        d = 18
        draw.polygon([(cx,cy-d),(cx+d,cy),(cx,cy+d),(cx-d,cy)], fill=RED_D)
        draw.polygon([(cx,cy-7),(cx+7,cy),(cx,cy+7),(cx-7,cy)], fill=GOLD)
        return

    is_red = suit in ("♥", "♦")
    fc = (180, 15, 15) if is_red else (10, 10, 15)

    draw.rounded_rectangle([x, y, x+cw, y+ch], radius=8,
                            fill=(245, 238, 220), outline=(180, 160, 120), width=1)
    fr = _font(15)
    fs = _font(28)
    draw.text((x+7, y+6),       rank, font=fr, fill=fc)
    draw.text((x+cw-7, y+ch-6), rank, font=fr, fill=fc, anchor="rb")
    draw.text((x+cw//2, y+ch//2), suit, font=fs, fill=fc, anchor="mm")


def _valor_box(draw, x, y, w, label, valor):
    draw.rounded_rectangle([x, y, x+w, y+28], radius=5,
                            fill=(10, 5, 20, 200), outline=(*GOLD, 100), width=1)
    f = _font(13)
    draw.text((x+w//2, y+14), f"{label}: {valor}", font=f, fill=CREAM, anchor="mm")


# ══════════════════════════════════════════════════════════════════════════════
# BLACKJACK
# ══════════════════════════════════════════════════════════════════════════════

def render_blackjack(dealer_cards, dealer_val,
                     player_cards, player_val,
                     reveal_dealer=False, result="", titulo="✦ BLACKJACK 21 ✦"):
    """
    dealer_cards / player_cards: lista de (rank, suit) ex: [("A","♠"), ("10","♥")]
    """
    img, draw, ow, oh = _base()
    _title(draw, titulo, ow)

    cw, ch, gap = 85, 120, 10

    # ── Dealer ──
    f = _font(14)
    dv_str = str(dealer_val) if reveal_dealer else "?"
    draw.text((ow//2, 55), f"⚜  DEALER  [{dv_str}]", font=f, fill=GOLD, anchor="mm")

    n = len(dealer_cards)
    total_w = n*cw + (n-1)*gap
    sx = ow//2 - total_w//2
    for i, (rank, suit) in enumerate(dealer_cards):
        _card(draw, img, sx+i*(cw+gap), 68, rank, suit,
              face_down=(i == 0 and not reveal_dealer), cw=cw, ch=ch)

    # ── Player ──
    draw.text((ow//2, 210), f"VOCÊ  [{player_val}]", font=f, fill=CREAM, anchor="mm")
    n2 = len(player_cards)
    total_w2 = n2*cw + (n2-1)*gap
    sx2 = ow//2 - total_w2//2
    for i, (rank, suit) in enumerate(player_cards):
        _card(draw, img, sx2+i*(cw+gap), 225, rank, suit, cw=cw, ch=ch)

    # Resultado
    if result:
        draw.rounded_rectangle([ow//2-200, oh-55, ow//2+200, oh-12],
                                radius=6, fill=(8,4,16,220), outline=(*GOLD,150), width=1)
        fr = _font(16)
        draw.text((ow//2, oh-34), result, font=fr, fill=GOLD_LT, anchor="mm")

    return _bytes(img)


# ══════════════════════════════════════════════════════════════════════════════
# POKER
# ══════════════════════════════════════════════════════════════════════════════

def render_poker(community, players, pot, current_name=""):
    """
    community: [(rank,suit),...] 0-5
    players: [{"name","cards":[(r,s)],"chips","bet","status","dealer"}]
    """
    img, draw, ow, oh = _base()
    _title(draw, "✦ TEXAS HOLD'EM ✦", ow)

    f = _font(13)

    # Pot
    draw.text((ow//2, 52), f"💰 POT: {pot:,} fichas", font=_font(15), fill=GOLD_LT, anchor="mm")

    # Community cards
    cw, ch, gap = 70, 98, 8
    n = len(community)
    cc_y = 68
    if n:
        tw = n*cw + (n-1)*gap
        sx = ow//2 - tw//2
        for i, (r, s) in enumerate(community):
            _card(draw, img, sx+i*(cw+gap), cc_y, r, s, cw=cw, ch=ch)
    else:
        draw.text((ow//2, cc_y+ch//2), "Aguardando cartas...", font=f, fill=GRAY, anchor="mm")

    # Jogadores
    np = len(players)
    slot = ow // max(np, 1)
    cw2, ch2 = 55, 77
    p_y = cc_y + ch + 30

    STATUS_COL = {"active": CREAM, "folded": GRAY, "all-in": (255,130,0), "winner": (80,220,80)}

    for i, p in enumerate(players):
        px = i*slot + slot//2
        col = STATUS_COL.get(p.get("status","active"), CREAM)
        is_cur = p["name"] == current_name

        if is_cur:
            draw.rounded_rectangle([px-slot//2+3, p_y-3, px+slot//2-3, p_y+ch2+55],
                                    radius=5, fill=(40,15,5,130), outline=(*GOLD,180), width=2)

        tag = " 🎩" if p.get("dealer") else ""
        draw.text((px, p_y+5), (p["name"][:10]+tag), font=_font(11), fill=col, anchor="mm")
        draw.text((px, p_y+20), f"{p['chips']:,} 🪙", font=_font(10, bold=False), fill=CREAM, anchor="mm")
        if p.get("bet",0):
            draw.text((px, p_y+34), f"Bet: {p['bet']}", font=_font(10, bold=False), fill=GOLD, anchor="mm")

        cards = p.get("cards", [])
        tw2 = len(cards)*cw2 + (len(cards)-1)*4
        sx2 = px - tw2//2
        for j, (r, s) in enumerate(cards):
            hidden = (s == "?")
            _card(draw, img, sx2+j*(cw2+4), p_y+46, r, s, face_down=hidden, cw=cw2, ch=ch2)

        st = p.get("status","")
        if st in ("folded","all-in","winner"):
            labels = {"folded":"FOLD","all-in":"ALL-IN","winner":"🏆"}
            draw.text((px, p_y+ch2+55), labels[st], font=_font(11), fill=col, anchor="mm")

    return _bytes(img)


# ══════════════════════════════════════════════════════════════════════════════
# TRUCO
# ══════════════════════════════════════════════════════════════════════════════

def render_truco(equipe_nos, equipe_eles, pontos_nos, pontos_eles,
                 vira, mesa_cartas, rodada, max_pontos):
    """
    equipe_nos/eles: [{"name", "cards":[(r,s)], "jogou": bool}]
    mesa_cartas: [(rank,suit,nome_jogador)]
    """
    img, draw, ow, oh = _base()
    _title(draw, f"✦ TRUCO PAULISTA — até {max_pontos} pts ✦", ow)

    f = _font(13)
    cw, ch = 60, 84
    cx = ow//2
    cy = oh//2

    # Placar
    draw.text((80, 50), f"NÓS: {pontos_nos}", font=_font(16), fill=(80,220,80), anchor="mm")
    draw.text((ow-80, 50), f"ELES: {pontos_eles}", font=_font(16), fill=(220,80,80), anchor="mm")
    draw.text((cx, 50), f"Rodada {rodada}/3", font=f, fill=GOLD, anchor="mm")

    # Vira (centro)
    vr, vs = vira
    draw.text((cx, cy-ch//2-18), "VIRA", font=_font(11), fill=GOLD, anchor="mm")
    _card(draw, img, cx-cw//2, cy-ch//2, vr, vs, cw=cw, ch=ch)

    # Cartas já jogadas na mesa (ao redor da vira)
    offsets = [(-130,-20),(130,-20),(-130,30),(130,30),(0,-90),(0,80)]
    for i, (r, s, nome) in enumerate(mesa_cartas[:6]):
        ox, oy = offsets[i]
        _card(draw, img, cx+ox-cw//2, cy+oy-ch//2, r, s, cw=cw-10, ch=ch-14)
        draw.text((cx+ox, cy+oy+ch//2-2), nome[:8], font=_font(9,bold=False), fill=CREAM, anchor="mm")

    # Equipe NÓS (esquerda)
    _draw_equipe(draw, img, equipe_nos, 12, 80, oh-20, left=True)
    # Equipe ELES (direita)
    _draw_equipe(draw, img, equipe_eles, ow-12, 80, oh-20, left=False)

    return _bytes(img)


def _draw_equipe(draw, img, jogadores, bx, y1, y2, left=True):
    slot = (y2-y1) // max(len(jogadores),1)
    cw, ch = 42, 58
    gap = 4
    for i, p in enumerate(jogadores):
        py = y1 + i*slot + slot//2
        nome = p["name"][:10]
        anc = "lm" if left else "rm"
        tx  = bx + (8 if left else -8)
        draw.text((tx, py-ch//2-10), nome, font=_font(10), fill=GOLD_LT, anchor=anc)
        cards = p.get("cards", [])
        n = len(cards)
        sx = bx + (8 if left else -(8 + n*(cw+gap)))
        for j, (r, s) in enumerate(cards):
            fd = p.get("jogou", False) or s == "?"
            _card(draw, img, sx+j*(cw+gap), py-ch//2, r, s, face_down=fd, cw=cw, ch=ch)


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
    _title(draw, "✦ XADREZ ✦", ow)

    margin  = 40
    b_size  = ow - 2*margin
    cell    = b_size // 8
    bx      = margin
    by      = 50

    LIGHT = (200, 175, 135)
    DARK2 = (90,  55,  25)
    HL_L  = (200, 220, 100, 160)
    HL_D  = (155, 185,  50, 160)
    SEL   = (100, 175, 255, 170)
    VALID = (70,  200,  70, 130)

    lm  = set()
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
                img.paste(ov,(x1,y1),ov)
                draw = ImageDraw.Draw(img,"RGBA")
            if selected and (row,col)==selected:
                ov = Image.new("RGBA",(cell,cell),SEL)
                img.paste(ov,(x1,y1),ov)
                draw = ImageDraw.Draw(img,"RGBA")
            if (row,col) in vm:
                ov = Image.new("RGBA",(cell,cell),VALID)
                img.paste(ov,(x1,y1),ov)
                draw = ImageDraw.Draw(img,"RGBA")

            p = board[row][col]
            if p and p != ".":
                sym   = PECAS.get(p, p)
                white = p.isupper()
                fp    = _font(cell-8)
                cx2   = x1+cell//2
                cy2   = y1+cell//2
                draw.text((cx2+1,cy2+2), sym, font=fp, fill=(0,0,0,180), anchor="mm")
                draw.text((cx2,cy2), sym, font=fp,
                           fill=(240,235,220) if white else (12,6,18), anchor="mm")

    fc = _font(11, bold=False)
    for i in range(8):
        draw.text((bx+i*cell+cell//2, by+b_size+14), chr(65+i), font=fc, fill=GOLD, anchor="mm")
        draw.text((bx-14, by+i*cell+cell//2), str(8-i), font=fc, fill=GOLD, anchor="mm")

    iy = by + b_size + 32
    turno = nome_brancas if vez=="white" else nome_pretas
    icone = "⬜" if vez=="white" else "⬛"
    draw.text((ow//2, iy), f"{icone} Vez de: {turno}", font=_font(13), fill=GOLD_LT, anchor="mm")
    draw.text((ow//2, iy+20), f"⬜ {nome_brancas}  vs  ⬛ {nome_pretas}",
              font=_font(11,bold=False), fill=CREAM, anchor="mm")

    return _bytes(img)
