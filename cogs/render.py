"""
cogs/render.py — Layout otimizado para mobile (800x600).
Cartas e textos gigantes para legibilidade máxima no Discord.
"""
import io
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

# ── Dimensões ─────────────────────────────────────────────────────────────────
W,  H  = 800, 600    # Menor e mais quadrado para renderizar maior no mobile
WP, HP = 600, 820    # xadrez (portrait)

# ── Paleta ────────────────────────────────────────────────────────────────────
BG     = (10,  4, 14)
FELT   = (18,  8, 28)
GOLD   = (210, 170, 80)
GOLDL  = (245, 215, 130)
CREAM  = (238, 222, 196)
RED_D  = (145,  12, 12)
SHADOW = (0, 0, 0)
GRAY   = (75, 75, 85)

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
    draw.rounded_rectangle([10, 10, ow-10, oh-10], radius=18, fill=FELT)
    draw.rounded_rectangle([4,  4,  ow-5,  oh-5],  radius=20, outline=GOLD, width=3)
    draw.rounded_rectangle([9,  9,  ow-10, oh-10], radius=16, outline=(*GOLD, 60), width=1)
    return img, draw, ow, oh

def _title(draw, text, ow, y=30):
    f = _font(32) # Fonte bem maior
    draw.text((ow//2+2, y+2), text, font=f, fill=SHADOW, anchor="mm")
    draw.text((ow//2,   y),   text, font=f, fill=GOLDL,  anchor="mm")
    draw.line([(ow//2 - 200, y+22), (ow//2 + 200, y+22)], fill=(*GOLD, 80), width=2)

def _label(draw, text, cx, y, color=CREAM, size=24):
    f = _font(size)
    draw.text((cx+2, y+2), text, font=f, fill=SHADOW, anchor="mm")
    draw.text((cx,   y),   text, font=f, fill=color,  anchor="mm")

# ── Carta ─────────────────────────────────────────────────────────────────────
def _card(draw, img, x, y, rank, suit, face_down=False, cw=130, ch=185):
    r = 12
    # Sombra
    draw.rounded_rectangle([x+5, y+5, x+cw+5, y+ch+5], radius=r, fill=(0,0,0,100))

    if face_down:
        draw.rounded_rectangle([x, y, x+cw, y+ch], radius=r,
                                fill=(18, 8, 30), outline=GOLD, width=2)
        cx2, cy2 = x+cw//2, y+ch//2
        d  = 28
        d2 = 12
        draw.polygon([(cx2,cy2-d),(cx2+d,cy2),(cx2,cy2+d),(cx2-d,cy2)], fill=RED_D)
        draw.polygon([(cx2,cy2-d2),(cx2+d2,cy2),(cx2,cy2+d2),(cx2-d2,cy2)], fill=GOLD)
        return

    is_red = suit in ("♥","♦")
    fc     = (185, 20, 20) if is_red else (15, 15, 20)

    draw.rounded_rectangle([x, y, x+cw, y+ch], radius=r,
                            fill=(248, 240, 224), outline=(175, 155, 115), width=2)
    
    fr = _font(28)
    draw.text((x+10, y+10), rank, font=fr, fill=fc)
    draw.text((x+cw-10, y+ch-10), rank, font=fr, fill=fc, anchor="rb")
    
    fs = _font(75)
    draw.text((x+cw//2, y+ch//2), suit, font=fs, fill=fc, anchor="mm")

# ══════════════════════════════════════════════════════════════════════════════
# BLACKJACK
# ══════════════════════════════════════════════════════════════════════════════
def render_blackjack(dealer_cards, dealer_val, player_cards, player_val,
                     reveal_dealer=False, result=""):
    img, draw, ow, oh = _base()
    _title(draw, "BLACKJACK 21", ow)

    CW, CH, GAP = 130, 185, 16

    # ── Dealer ──────────────────────────────────────────────────────────────
    dv_str = str(dealer_val) if reveal_dealer else "?"
    _label(draw, f"DEALER  [ {dv_str} ]", ow//2, 85, GOLD, 24)

    nd = len(dealer_cards)
    tw = nd*CW + (nd-1)*GAP
    sx = ow//2 - tw//2
    dy = 110
    for i, (rank, suit) in enumerate(dealer_cards):
        _card(draw, img, sx + i*(CW+GAP), dy, rank, suit,
              face_down=(i==0 and not reveal_dealer), cw=CW, ch=CH)

    # ── Separador ───────────────────────────────────────────────────────────
    sep_y = dy + CH + 20
    draw.line([(100, sep_y), (ow-100, sep_y)], fill=(*GOLD, 50), width=2)

    # ── Jogador ─────────────────────────────────────────────────────────────
    _label(draw, f"VOCÊ  [ {player_val} ]", ow//2, sep_y+25, CREAM, 24)

    np2 = len(player_cards)
    tw2 = np2*CW + (np2-1)*GAP
    sx2 = ow//2 - tw2//2
    py  = sep_y + 45

    if tw2 > ow - 60:
        scale = (ow - 60) / tw2
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
        rw, rh = 540, 65
        rx, ry = ow//2 - rw//2, oh - rh - 15
        draw.rounded_rectangle([rx, ry, rx+rw, ry+rh], radius=10,
                                fill=(8,4,16,240), outline=(*GOLD,180), width=3)
        _label(draw, result, ow//2, ry+rh//2, GOLDL, 26)

    return _bytes(img)

# (Mantenha o resto dos seus renders de poker/truco/xadrez aqui embaixo)
