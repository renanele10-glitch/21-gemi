"""
cards/table_renderer.py
Renderiza a mesa do cassino (blackjack, poker, truco).
Usa as cartas reais do card_renderer.
"""
from __future__ import annotations
import io
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
from .card_renderer import card_image

# ── Dimensões ──────────────────────────────────────────────────────────────
TABLE_W, TABLE_H = 800, 560   # Landscape — discord mobile/pc

# ── Paleta ────────────────────────────────────────────────────────────────
BG       = (8,   4,  14)
FELT     = (14,  6,  22)
FELT2    = (20, 10,  32)
GOLD     = (210, 170,  80)
GOLD_LT  = (248, 218, 130)
GOLD_DIM = (140, 110,  45)
CREAM    = (238, 222, 196)
RED_D    = (150,  10,  10)
GREEN_W  = ( 28, 140,  55)
WHITE    = (255, 255, 255)
SHADOW   = (  0,   0,   0)
GRAY     = ( 70,  70,  82)


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    if not bold:
        paths = [p.replace("Bold", "Regular").replace("-Bold", "") for p in paths]
    for p in paths:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default(size=size)


def _bytes(img: Image.Image) -> io.BytesIO:
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf


def _label(draw: ImageDraw.ImageDraw, text: str,
           cx: int, y: int,
           color: tuple = CREAM,
           size: int = 15,
           shadow: bool = True) -> None:
    f = _font(size)
    if shadow:
        draw.text((cx + 1, y + 1), text, font=f, fill=(*SHADOW, 200), anchor="mm")
    draw.text((cx, y), text, font=f, fill=color, anchor="mm")


def _base_table() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img  = Image.new("RGB", (TABLE_W, TABLE_H), BG)
    draw = ImageDraw.Draw(img, "RGBA")

    # Feltro principal
    draw.rounded_rectangle([8, 8, TABLE_W-9, TABLE_H-9],
                            radius=24, fill=FELT)
    # Borda dupla
    draw.rounded_rectangle([3, 3, TABLE_W-4, TABLE_H-4],
                            radius=26, outline=GOLD, width=3)
    draw.rounded_rectangle([7, 7, TABLE_W-8, TABLE_H-8],
                            radius=22, outline=(*GOLD, 50), width=1)
    return img, draw


def _divider(draw: ImageDraw.ImageDraw, y: int, margin: int = 60) -> None:
    draw.line([(margin, y), (TABLE_W - margin, y)],
              fill=(*GOLD, 40), width=1)


# ═══════════════════════════════════════════════════════════════════════════
# BLACKJACK
# ═══════════════════════════════════════════════════════════════════════════

# Tamanho padrão das cartas no blackjack
BJ_CW, BJ_CH = 100, 140


def _fit_cards(n: int, cw: int, gap: int, max_w: int) -> tuple[int, int]:
    """Reduz tamanho de carta se não couberem."""
    total = n * cw + (n - 1) * gap
    if total <= max_w:
        return cw, gap
    ratio = max_w / total
    return max(40, int(cw * ratio)), max(4, int(gap * ratio))


def render_blackjack(
    dealer_cards: list[tuple[str, str]],
    dealer_val: int,
    player_cards: list[tuple[str, str]],
    player_val: int,
    reveal_dealer: bool = False,
    result: str = "",
) -> io.BytesIO:
    img, draw = _base_table()
    cx = TABLE_W // 2

    # Título
    _label(draw, "✦  BLACKJACK 21  ✦", cx, 26, GOLD_LT, 22)
    _divider(draw, 44)

    GAP = 12
    AREA_W = TABLE_W - 80

    # ── Dealer ──────────────────────────────────────────────────────────
    dv = str(dealer_val) if reveal_dealer else "?"
    _label(draw, f"⚜  DEALER  [ {dv} ]", cx, 62, GOLD, 15)

    nd = len(dealer_cards)
    cw_d, gap_d = _fit_cards(nd, BJ_CW, GAP, AREA_W)
    ch_d = int(BJ_CH * cw_d / BJ_CW)
    tw_d = nd * cw_d + (nd - 1) * gap_d
    sx_d = cx - tw_d // 2
    dy   = 78

    for i, (rank, suit) in enumerate(dealer_cards):
        ci = card_image(rank, suit, cw_d, ch_d,
                        face_down=(i == 0 and not reveal_dealer))
        img.paste(ci, (sx_d + i * (cw_d + gap_d), dy), ci)

    # ── Separador ───────────────────────────────────────────────────────
    sep_y = dy + ch_d + 16
    _divider(draw, sep_y)

    # ── Jogador ─────────────────────────────────────────────────────────
    _label(draw, f"VOCÊ  [ {player_val} ]", cx, sep_y + 18, CREAM, 15)

    np2   = len(player_cards)
    cw_j, gap_j = _fit_cards(np2, BJ_CW, GAP, AREA_W)
    ch_j = int(BJ_CH * cw_j / BJ_CW)
    tw_j = np2 * cw_j + (np2 - 1) * gap_j
    sx_j = cx - tw_j // 2
    py   = sep_y + 34

    for i, (rank, suit) in enumerate(player_cards):
        ci = card_image(rank, suit, cw_j, ch_j)
        img.paste(ci, (sx_j + i * (cw_j + gap_j), py), ci)

    # ── Resultado ────────────────────────────────────────────────────────
    if result:
        rw, rh = 520, 52
        ry = py + ch_j + 16
        rx = cx - rw // 2
        draw.rounded_rectangle([rx, ry, rx + rw, ry + rh],
                                radius=10,
                                fill=(6, 3, 14, 238),
                                outline=(*GOLD, 180), width=2)
        _label(draw, result, cx, ry + rh // 2, GOLD_LT, 19)

    return _bytes(img)


def bj_card_positions(
    dealer_cards: list,
    player_cards: list,
) -> tuple[list[tuple], list[tuple], int, int]:
    """
    Retorna posições exatas (x, y, cw, ch) de cada carta
    para o animator usar.
    """
    GAP    = 12
    AREA_W = TABLE_W - 80
    cx     = TABLE_W // 2

    nd   = len(dealer_cards)
    cw_d, gap_d = _fit_cards(nd, BJ_CW, GAP, AREA_W)
    ch_d = int(BJ_CH * cw_d / BJ_CW)
    tw_d = nd * cw_d + (nd - 1) * gap_d
    sx_d = cx - tw_d // 2
    dy   = 78

    np2  = len(player_cards)
    cw_j, gap_j = _fit_cards(np2, BJ_CW, GAP, AREA_W)
    ch_j = int(BJ_CH * cw_j / BJ_CW)
    tw_j = np2 * cw_j + (np2 - 1) * gap_j
    sx_j = cx - tw_j // 2
    sep_y = dy + ch_d + 16
    py   = sep_y + 34

    pos_d = [(sx_d + i * (cw_d + gap_d), dy, cw_d, ch_d)
             for i in range(nd)]
    pos_j = [(sx_j + i * (cw_j + gap_j), py, cw_j, ch_j)
             for i in range(np2)]

    return pos_d, pos_j, ch_d, ch_j


# ═══════════════════════════════════════════════════════════════════════════
# POKER
# ═══════════════════════════════════════════════════════════════════════════

def render_poker(
    community: list[tuple[str, str]],
    players: list[dict],
    pot: int,
    current_name: str = "",
    winners: list[str] | None = None,
) -> io.BytesIO:
    """
    players = [{"name", "cards": [(r,s)], "chips", "bet", "status", "dealer"}]
    status: active | folded | all-in | winner
    """
    img, draw = _base_table()
    cx = TABLE_W // 2
    winners = winners or []

    _label(draw, "✦  TEXAS HOLD'EM  ✦", cx, 26, GOLD_LT, 22)
    _label(draw, f"💰  POT: {pot:,} fichas", cx, 52, GOLD_LT, 14)

    # ── Community cards ──────────────────────────────────────────────────
    CW, CH, GAP = 72, 101, 8
    cc_y = 66
    n = len(community)
    if n:
        tw = n * CW + (n - 1) * GAP
        sx = cx - tw // 2
        for i, (r, s) in enumerate(community):
            ci = card_image(r, s, CW, CH)
            img.paste(ci, (sx + i * (CW + GAP), cc_y), ci)
    else:
        _label(draw, "Aguardando cartas comunitárias...", cx, cc_y + CH // 2, GRAY, 13)

    # ── Players ──────────────────────────────────────────────────────────
    np2   = len(players)
    slot  = TABLE_W // max(np2, 1)
    cw2, ch2 = 52, 73
    p_y   = cc_y + CH + 24

    STATUS_COL = {
        "active":  CREAM,
        "folded":  GRAY,
        "all-in":  (255, 130,  0),
        "winner":  ( 80, 220, 80),
    }

    for i, p in enumerate(players):
        px   = i * slot + slot // 2
        col  = STATUS_COL.get(p.get("status", "active"), CREAM)
        is_w = p["name"] in winners
        is_c = p["name"] == current_name

        # Destaque jogador atual / vencedor
        if is_w:
            draw.rounded_rectangle(
                [px - slot // 2 + 3, p_y - 4, px + slot // 2 - 3, p_y + ch2 + 58],
                radius=6, fill=(20, 60, 20, 120), outline=(80, 220, 80, 200), width=2)
        elif is_c:
            draw.rounded_rectangle(
                [px - slot // 2 + 3, p_y - 4, px + slot // 2 - 3, p_y + ch2 + 58],
                radius=6, fill=(40, 15, 5, 120), outline=(*GOLD, 180), width=2)

        # Dealer button
        tag = " 🎩" if p.get("dealer") else ""
        _label(draw, p["name"][:10] + tag, px, p_y + 8, col, 11)
        _label(draw, f"{p.get('chips', 0):,} 🪙", px, p_y + 22, CREAM, 10)
        if p.get("bet", 0):
            _label(draw, f"Bet: {p['bet']}", px, p_y + 35, GOLD, 10)

        # Cartas do jogador
        cards = p.get("cards", [])
        tw2   = len(cards) * cw2 + max(0, len(cards) - 1) * 4
        sx2   = px - tw2 // 2
        for j, (r, s) in enumerate(cards):
            hidden = (s == "?" or p.get("status") == "folded")
            ci = card_image(r, s, cw2, ch2, face_down=hidden)
            img.paste(ci, (sx2 + j * (cw2 + 4), p_y + 46), ci)

        # Status label
        st = p.get("status", "")
        if st in ("folded", "all-in", "winner"):
            lbs = {"folded": "FOLD", "all-in": "ALL-IN", "winner": "🏆"}
            _label(draw, lbs[st], px, p_y + ch2 + 55, col, 11)

    return _bytes(img)


# ═══════════════════════════════════════════════════════════════════════════
# TRUCO
# ═══════════════════════════════════════════════════════════════════════════

def render_truco(
    equipe_nos: list[dict],
    equipe_eles: list[dict],
    pontos_nos: int,
    pontos_eles: int,
    vira: tuple[str, str],
    mesa_cartas: list[tuple],
    rodada: int,
    max_pontos: int,
    truco_val: int = 2,
    carta_vencedora: tuple | None = None,
) -> io.BytesIO:
    img, draw = _base_table()
    cx, cy = TABLE_W // 2, TABLE_H // 2

    _label(draw, "✦  TRUCO PAULISTA  ✦", cx, 26, GOLD_LT, 22)

    # Placar
    _label(draw, f"NÓS: {pontos_nos}", 90,          52, ( 80, 220,  80), 16)
    _label(draw, f"ELES: {pontos_eles}", TABLE_W-90, 52, (220,  80,  80), 16)
    _label(draw, f"Rod. {rodada}/3  •  Vale {truco_val}pt", cx, 52, GOLD, 12)

    # Vira
    CW, CH = 60, 84
    vr, vs = vira
    _label(draw, "VIRA", cx, cy - CH // 2 - 16, GOLD, 11)
    ci = card_image(vr, vs, CW, CH)
    img.paste(ci, (cx - CW // 2, cy - CH // 2), ci)

    # Cartas na mesa
    offsets = [(-130, -28), (130, -28), (-130, 38), (130, 38), (0, -92), (0, 82)]
    cw_m, ch_m = 54, 76
    for i, entry in enumerate(mesa_cartas[:6]):
        r, s, nome = entry[0], entry[1], entry[2]
        is_winner = carta_vencedora and (r, s) == (carta_vencedora[0], carta_vencedora[1])
        ox, oy = offsets[i]
        mx = cx + ox - cw_m // 2 + 4
        my = cy + oy - ch_m // 2
        ci = card_image(r, s, cw_m, ch_m)

        # Brilho dourado na carta vencedora
        if is_winner:
            glow = Image.new("RGBA", (cw_m + 8, ch_m + 8), (0, 0, 0, 0))
            gd   = ImageDraw.Draw(glow, "RGBA")
            gd.rounded_rectangle([0, 0, cw_m + 7, ch_m + 7],
                                  radius=10, fill=(210, 170, 80, 100))
            img.paste(glow, (mx - 4, my - 4), glow)

        img.paste(ci, (mx, my), ci)
        _label(draw, nome[:8], cx + ox + 4, cy + oy + ch_m // 2 + 2, CREAM, 9)

    # Equipes nas laterais
    _draw_truco_team(img, draw, equipe_nos,  14,          68, TABLE_H - 18, left=True)
    _draw_truco_team(img, draw, equipe_eles, TABLE_W - 14, 68, TABLE_H - 18, left=False)

    return _bytes(img)


def _draw_truco_team(img, draw, jogadores, bx, y1, y2, left=True):
    if not jogadores:
        return
    slot = (y2 - y1) // max(len(jogadores), 1)
    CW, CH, GAP = 44, 62, 3

    for i, p in enumerate(jogadores):
        py  = y1 + i * slot + slot // 2
        tx  = bx + (8 if left else -8)
        anc = "lm" if left else "rm"
        draw.text((tx, py - CH // 2 - 12),
                  p["name"][:10], font=_font(10),
                  fill=GOLD_LT, anchor=anc)
        cards = p.get("cards", [])
        sx = bx + (8 if left else -(8 + len(cards) * (CW + GAP)))
        for j, (r, s) in enumerate(cards):
            fd = p.get("jogou", False) or s == "?"
            ci = card_image(r, s, CW, CH, face_down=fd)
            img.paste(ci, (sx + j * (CW + GAP), py - CH // 2), ci)
