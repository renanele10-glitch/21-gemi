# ══════════════════════════════════════════════════════════════════════════════
# BLACKJACK
# ══════════════════════════════════════════════════════════════════════════════

TABLE_BJ = Path(__file__).parent.parent / "assets" / "bj_table.jpg"

# Resolução da imagem da mesa
_BJ_W, _BJ_H = 1536, 768

# Dealer
_BJ_DEALER = (768, 205)

# Slots dos jogadores (esquerda, centro, direita)
_BJ_SLOTS = [
    (280, 560, 0),
    (768, 580, 0),
    (1256, 560, 0),
]

# Tamanho das cartas
_BJ_SLOT_CW = [135, 125, 135]
_BJ_SLOT_CH = [190, 176, 190]


def _make_bj_card(rank, suit, face_down=False, cw=78, ch=112):
    img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if face_down:
        d.rounded_rectangle(
            [0, 0, cw - 1, ch - 1],
            radius=10,
            fill=(20, 8, 35),
            outline=(180, 150, 60),
            width=2
        )

        cx, cy = cw // 2, ch // 2
        dv = int(cw * 0.22)

        d.polygon(
            [(cx, cy - dv), (cx + dv, cy), (cx, cy + dv), (cx - dv, cy)],
            fill=(130, 10, 10)
        )

        d.polygon(
            [(cx, cy - 7), (cx + 7, cy), (cx, cy + 7), (cx - 7, cy)],
            fill=(180, 140, 50)
        )

        return img

    is_red = suit in ("♥", "♦")
    fc = (172, 10, 10) if is_red else (12, 10, 20)

    d.rounded_rectangle(
        [3, 4, cw + 2, ch + 3],
        radius=10,
        fill=(0, 0, 0, 70)
    )

    d.rounded_rectangle(
        [0, 0, cw - 1, ch - 1],
        radius=10,
        fill=(252, 246, 232),
        outline=(160, 140, 100),
        width=1
    )

    fr = _font(int(cw * 0.22))
    d.text((8, 6), rank, font=fr, fill=fc)
    d.text((cw - 8, ch - 6), rank, font=fr, fill=fc, anchor="rb")

    fs = _font(int(cw * 0.42))
    d.text((cw // 2, ch // 2), suit, font=fs, fill=fc, anchor="mm")

    return img


def _bj_paste(base, card, cx, cy, angle=0):
    if angle != 0:
        card = card.rotate(
            angle,
            expand=True,
            resample=Image.BICUBIC
        )

    base.paste(
        card,
        (cx - card.width // 2, cy - card.height // 2),
        card
    )


def _bj_draw_hand(base, cards, cx, cy, angle=0,
                  face_downs=None, cw=78, ch=112):

    import math

    n = len(cards)

    if n == 0:
        return

    face_downs = face_downs or [False] * n

    # Menos sobreposição
    offset = int(cw * 0.58)

    total_w = cw + (n - 1) * offset

    start_x = -(total_w // 2) + (cw // 2)

    rad = math.radians(angle)

    for i, (rank, suit) in enumerate(cards):
        dx = start_x + i * offset

        card = _make_bj_card(
            rank,
            suit,
            face_down=face_downs[i],
            cw=cw,
            ch=ch
        )

        px = int(cx + dx * math.cos(rad))
        py = int(cy + dx * math.sin(rad))

        _bj_paste(base, card, px, py, angle=angle)


def _bj_badge(draw, text, cx, cy,
              fill=(10, 10, 10, 190),
              size=14):

    f = _font(size)

    bb = draw.textbbox((0, 0), text, font=f)

    bw = bb[2] - bb[0] + 18
    bh = 24

    bx = cx - bw // 2
    by = cy - bh // 2

    draw.rounded_rectangle(
        [bx, by, bx + bw, by + bh],
        radius=6,
        fill=fill,
        outline=GOLD,
        width=1
    )

    draw.text(
        (cx, cy),
        text[:20],
        font=f,
        fill=GOLDL,
        anchor="mm"
    )


def _bj_name(draw, text, cx, cy, active=False):
    f = _font(15)

    color = (255, 215, 0) if active else (220, 205, 180)

    draw.text(
        (cx + 1, cy + 1),
        text,
        font=f,
        fill=(0, 0, 0, 200),
        anchor="mm"
    )

    draw.text(
        (cx, cy),
        text,
        font=f,
        fill=color,
        anchor="mm"
    )


def render_blackjack(
    slots,
    dealer_cards,
    dealer_val,
    reveal_dealer=False,
    result_map=None
):
    W, H = _BJ_W, _BJ_H

    if TABLE_BJ.exists():
        table = (
            Image.open(TABLE_BJ)
            .convert("RGB")
            .resize((W, H), Image.LANCZOS)
        )

        base = table.convert("RGBA")

    else:
        base = Image.new("RGBA", (W, H), (8, 48, 8))

    draw = ImageDraw.Draw(base, "RGBA")

    # Dealer
    dcx, dcy = _BJ_DEALER

    face_downs = [
        i == 0 and not reveal_dealer
        for i in range(len(dealer_cards))
    ]

    _bj_draw_hand(
        base,
        dealer_cards,
        dcx,
        dcy,
        face_downs=face_downs,
        cw=115,
        ch=165
    )

    dealer_text = str(dealer_val) if reveal_dealer else "?"

    _bj_badge(
        draw,
        f"{dealer_text} pts",
        dcx,
        dcy - 95
    )

    # Jogadores
    for i, slot in enumerate(slots[:3]):

        cx, cy, angle = _BJ_SLOTS[i]

        cw = _BJ_SLOT_CW[i]
        ch = _BJ_SLOT_CH[i]

        cards = slot.get("cards", [])

        if not cards:
            continue

        val = slot.get("val", 0)
        name = slot.get("name", f"P{i + 1}")
        active = slot.get("active", False)
        result = slot.get("result", "")

        _bj_draw_hand(
            base,
            cards,
            cx,
            cy,
            angle=angle,
            cw=cw,
            ch=ch
        )

        pts_y = cy - (ch // 2) - 30
        name_y = cy + (ch // 2) + 32

        fill = (
            (20, 90, 20, 210)
            if active
            else (10, 10, 10, 190)
        )

        _bj_badge(
            draw,
            f"{val} pts",
            cx,
            pts_y,
            fill=fill
        )

        if result:
            if any(x in result for x in ("venceu", "BLACKJACK")):
                color = (20, 120, 20, 230)

            elif any(x in result for x in ("perdeu", "Bust", "Dealer", "estourou")):
                color = (140, 20, 20, 230)

            else:
                color = (120, 100, 20, 230)

            _bj_badge(
                draw,
                result[:18],
                cx,
                pts_y - 28,
                fill=color
            )

        _bj_name(
            draw,
            name[:14],
            cx,
            name_y,
            active=active
        )

    return _bytes(base.convert("RGB"))


def bj_posicoes(slots_count=1):
    return _BJ_SLOTS[:min(slots_count, 3)]