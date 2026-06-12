"""
cards/animator.py
Motor de animação GIF premium para todos os jogos de cartas.
Todas as animações tocam UMA vez e param.

API pública:
  gif_deal(...)         → distribuição inicial
  gif_hit(...)          → carta nova chegando
  gif_flip_dealer(...)  → dealer revela carta
  gif_resultado(...)    → texto de resultado
  gif_community(...)    → cartas comunitárias (poker)
  gif_slide_to_center(...)  → carta deslizando pro centro (truco)
  gif_winner_pulse(...) → brilho na combinação vencedora
"""
from __future__ import annotations
import io
import math
from PIL import Image, ImageDraw, ImageFilter

from .card_renderer import card_image
from .effects import result_box, glow_border, winner_glow

GOLD    = (210, 170,  80)
GOLD_LT = (248, 218, 130)
SHADOW  = (  0,   0,   0)


# ── GIF utils ────────────────────────────────────────────────────────────────

def _save_gif(frames: list[Image.Image],
              durations: list[int]) -> io.BytesIO:
    """Sem parâmetro loop → toca UMA vez e para."""
    buf = io.BytesIO()
    frames[0].save(
        buf, format="GIF", save_all=True,
        append_images=frames[1:],
        duration=durations,
        optimize=False,
        disposal=2,
    )
    buf.seek(0)
    return buf


def _clone(img: Image.Image) -> Image.Image:
    return img.convert("RGB").copy()


def _paste_card(base: Image.Image,
                rank: str, suit: str,
                x: int, y: int,
                cw: int, ch: int,
                face_down: bool = False,
                alpha: float = 1.0) -> None:
    """Cola carta na imagem base com alpha opcional."""
    ci = card_image(rank, suit, cw, ch, face_down=face_down)
    if alpha < 1.0:
        a_mask = ci.split()[3] if ci.mode == "RGBA" else None
        if a_mask:
            new_a = a_mask.point(lambda p: int(p * alpha))
            ci.putalpha(new_a)
    base.paste(ci, (x, y), ci if ci.mode == "RGBA" else None)


# ── ease functions ────────────────────────────────────────────────────────────

def _ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def _ease_in_out(t: float) -> float:
    return t * t * (3 - 2 * t)


def _ease_in(t: float) -> float:
    return t * t


# ════════════════════════════════════════════════════════════════════════════
# 1. DISTRIBUIÇÃO INICIAL — cartas saem do centro uma a uma
# ════════════════════════════════════════════════════════════════════════════

def gif_deal(
    mesa_img: Image.Image,
    cartas_j: list[tuple[str, str]],
    cartas_d: list[tuple[str, str]],
    pos_j: list[tuple[int, int, int, int]],
    pos_d: list[tuple[int, int, int, int]],
    frames_per_card: int = 10,
) -> io.BytesIO:
    """
    Distribui cartas animadas. Ordem: j0, d0, j1, d1...
    pos_*: lista de (x, y, cw, ch)
    """
    ow, oh = mesa_img.size
    deck_x, deck_y = ow // 2, oh // 2 - 20

    ordem = []
    for i in range(max(len(cartas_j), len(cartas_d))):
        if i < len(cartas_j): ordem.append(("j", i))
        if i < len(cartas_d): ordem.append(("d", i))

    revealed_j: list[tuple] = []
    revealed_d: list[tuple] = []
    frames, durs = [], []

    for quem, idx in ordem:
        if quem == "j":
            rank, suit = cartas_j[idx]
            tx, ty, cw, ch = pos_j[idx]
            fd = False
        else:
            rank, suit = cartas_d[idx]
            tx, ty, cw, ch = pos_d[idx]
            fd = (idx == 0)

        for fi in range(frames_per_card):
            t     = fi / (frames_per_card - 1)
            ease  = _ease_out(t)
            cx2   = int(deck_x + (tx + cw // 2 - deck_x) * ease - cw // 2)
            cy2   = int(deck_y + (ty + ch // 2 - deck_y) * ease - ch // 2)
            scale = 0.35 + 0.65 * ease

            frame = _clone(mesa_img)
            # Já reveladas
            for ri, (rr, rs) in enumerate(revealed_j):
                ax, ay, acw, ach = pos_j[ri]
                _paste_card(frame, rr, rs, ax, ay, acw, ach)
            for ri, (rr, rs) in enumerate(revealed_d):
                ax, ay, acw, ach = pos_d[ri]
                _paste_card(frame, rr, rs, ax, ay, acw, ach, face_down=(ri == 0))

            # Em movimento (escala simulada)
            cw_s = max(4, int(cw * scale))
            ch_s = max(4, int(ch * scale))
            ox   = (cw - cw_s) // 2
            oy   = (ch - ch_s) // 2
            _paste_card(frame, rank, suit,
                        cx2 + ox, cy2 + oy, cw_s, ch_s, face_down=fd)

            frames.append(frame)
            durs.append(28)

        if quem == "j":
            revealed_j.append((rank, suit))
        else:
            revealed_d.append((rank, suit))

    # Frame final parado
    if frames:
        frames.append(frames[-1].copy())
        durs.append(600)

    return _save_gif(frames, durs)


# ════════════════════════════════════════════════════════════════════════════
# 2. HIT — carta nova desliza de cima
# ════════════════════════════════════════════════════════════════════════════

def gif_hit(
    mesa_img: Image.Image,
    rank: str, suit: str,
    x: int, y: int,
    cw: int, ch: int,
    n_frames: int = 14,
) -> io.BytesIO:
    """Carta chegando de cima com ease-out e leve bounce."""
    frames, durs = [], []
    start_y = -ch - 20

    for i in range(n_frames):
        t    = i / (n_frames - 1)
        # Ease out com micro-bounce
        if t < 0.85:
            ease = _ease_out(t / 0.85)
            cur_y = int(start_y + (y - start_y) * ease)
        else:
            bounce_t = (t - 0.85) / 0.15
            overshoot = math.sin(bounce_t * math.pi) * 8
            cur_y = int(y + overshoot)

        scale = 0.5 + 0.5 * min(t / 0.7, 1.0)
        cw_s  = max(4, int(cw * scale))
        ch_s  = max(4, int(ch * scale))
        ox    = (cw - cw_s) // 2

        frame = _clone(mesa_img)
        _paste_card(frame, rank, suit, x + ox, cur_y, cw_s, ch_s)
        frames.append(frame)
        durs.append(30 if i < n_frames - 1 else 800)

    return _save_gif(frames, durs)


# ════════════════════════════════════════════════════════════════════════════
# 3. FLIP DEALER — verso → frente (3D squeeze)
# ════════════════════════════════════════════════════════════════════════════

def gif_flip_dealer(
    mesa_img: Image.Image,
    rank: str, suit: str,
    x: int, y: int,
    cw: int, ch: int,
    n_frames: int = 22,
) -> io.BytesIO:
    """Flip 3D: verso encolhe horizontalmente, frente cresce."""
    frames, durs = [], []
    half = n_frames // 2

    for i in range(n_frames):
        frame = _clone(mesa_img)

        if i < half:
            t    = _ease_in(i / half)
            sx   = max(0.01, 1.0 - t)
            cw_s = max(2, int(cw * sx))
            ch_s = ch
            ox   = (cw - cw_s) // 2
            _paste_card(frame, rank, suit, x + ox, y, cw_s, ch_s, face_down=True)
            durs.append(28)
        else:
            t    = _ease_out((i - half) / half)
            sx   = max(0.01, t)
            cw_s = max(2, int(cw * sx))
            ch_s = ch
            ox   = (cw - cw_s) // 2
            _paste_card(frame, rank, suit, x + ox, y, cw_s, ch_s, face_down=False)
            durs.append(24 if i < n_frames - 1 else 1200)

        frames.append(frame)

    return _save_gif(frames, durs)


# ════════════════════════════════════════════════════════════════════════════
# 4. RESULTADO — texto aparece, pulsa UMA vez, fica estático
# ════════════════════════════════════════════════════════════════════════════

def gif_resultado(
    mesa_img: Image.Image,
    texto: str,
    cor: tuple = GOLD_LT,
    n_frames: int = 22,
) -> io.BytesIO:
    frames, durs = [], []
    ow, oh = mesa_img.size

    for i in range(n_frames):
        t = i / (n_frames - 1)

        if t < 0.35:
            alpha = _ease_out(t / 0.35)
            scale = 0.7 + 0.3 * alpha
        elif t < 0.72:
            alpha = 1.0
            pulse = math.sin((t - 0.35) / 0.37 * math.pi)
            scale = 1.0 + 0.07 * pulse
        else:
            alpha = 1.0
            scale = 1.0

        rw = int(540 * scale)
        rh = int(58 * scale)
        rx = ow // 2 - rw // 2
        ry = oh // 2 - rh // 2

        box = result_box(rw, rh, texto, cor, alpha)
        frame = _clone(mesa_img)
        frame_rgba = frame.convert("RGBA")
        frame_rgba.paste(box, (rx, ry), box)
        frames.append(frame_rgba.convert("RGB"))
        durs.append(42 if i < n_frames - 1 else 2800)

    return _save_gif(frames, durs)


# ════════════════════════════════════════════════════════════════════════════
# 5. COMMUNITY CARDS (poker) — cartas aparecem com flip
# ════════════════════════════════════════════════════════════════════════════

def gif_community(
    mesa_img: Image.Image,
    new_cards: list[tuple[str, str]],
    positions: list[tuple[int, int, int, int]],
    already_shown: int = 0,
    n_frames: int = 16,
) -> io.BytesIO:
    """
    Revela new_cards com efeito flip.
    already_shown: quantas já estavam visíveis (não animam).
    """
    frames, durs = [], []
    half = n_frames // 2

    for card_i, (rank, suit) in enumerate(new_cards):
        x, y, cw, ch = positions[already_shown + card_i]

        for fi in range(n_frames):
            frame = _clone(mesa_img)

            # Cartas já mostradas (estáticas)
            for prev_i in range(card_i):
                pr, ps = new_cards[prev_i]
                px, py, pcw, pch = positions[already_shown + prev_i]
                _paste_card(frame, pr, ps, px, py, pcw, pch)

            # Carta atual animando
            if fi < half:
                t    = _ease_in(fi / half)
                sx   = max(0.01, 1.0 - t)
                cw_s = max(2, int(cw * sx))
                ox   = (cw - cw_s) // 2
                _paste_card(frame, rank, suit, x + ox, y, cw_s, ch, face_down=True)
            else:
                t    = _ease_out((fi - half) / half)
                sx   = max(0.01, t)
                cw_s = max(2, int(cw * sx))
                ox   = (cw - cw_s) // 2
                _paste_card(frame, rank, suit, x + ox, y, cw_s, ch, face_down=False)

            frames.append(frame)
            durs.append(28 if fi < n_frames - 1 else 400)

    if frames:
        frames.append(frames[-1].copy())
        durs.append(500)

    return _save_gif(frames, durs)


# ════════════════════════════════════════════════════════════════════════════
# 6. SLIDE TO CENTER (truco) — carta desliza pra mesa
# ════════════════════════════════════════════════════════════════════════════

def gif_slide_to_center(
    mesa_img: Image.Image,
    rank: str, suit: str,
    start_x: int, start_y: int,
    end_x: int, end_y: int,
    cw: int, ch: int,
    n_frames: int = 12,
    winner_glow_enabled: bool = False,
) -> io.BytesIO:
    """Carta desliza da mão pra posição no centro da mesa."""
    frames, durs = [], []

    for i in range(n_frames):
        t    = _ease_out(i / (n_frames - 1))
        cx2  = int(start_x + (end_x - start_x) * t)
        cy2  = int(start_y + (end_y - start_y) * t)

        frame = _clone(mesa_img)
        _paste_card(frame, rank, suit, cx2, cy2, cw, ch)

        # Brilho dourado no destino final
        if winner_glow_enabled and i == n_frames - 1:
            glow = winner_glow((cw + 10, ch + 10), color=(210, 170, 80))
            frame_rgba = frame.convert("RGBA")
            frame_rgba.paste(glow, (cx2 - 5, cy2 - 5), glow)
            frame = frame_rgba.convert("RGB")

        frames.append(frame)
        durs.append(32 if i < n_frames - 1 else 700)

    return _save_gif(frames, durs)


# ════════════════════════════════════════════════════════════════════════════
# 7. WINNER PULSE — brilho pulsando na combinação vencedora
# ════════════════════════════════════════════════════════════════════════════

def gif_winner_pulse(
    mesa_img: Image.Image,
    positions: list[tuple[int, int, int, int]],
    cards: list[tuple[str, str]],
    color: tuple = (80, 220, 80),
    n_cycles: int = 2,
    fps: int = 12,
) -> io.BytesIO:
    """Pulsa brilho colorido em volta de cartas vencedoras."""
    frames, durs = [], []
    total = n_cycles * fps

    for fi in range(total):
        t     = fi / total
        pulse = math.sin(t * math.pi * n_cycles * 2)
        alpha = int(80 + 80 * pulse)

        frame = _clone(mesa_img)
        frame_rgba = frame.convert("RGBA")

        for (x, y, cw, ch), (rank, suit) in zip(positions, cards):
            # Glow
            glow = Image.new("RGBA", (cw + 12, ch + 12), (0, 0, 0, 0))
            gd   = ImageDraw.Draw(glow, "RGBA")
            gd.rounded_rectangle([0, 0, cw + 11, ch + 11],
                                  radius=12, fill=(*color, alpha))
            glow = glow.filter(ImageFilter.GaussianBlur(4))
            frame_rgba.paste(glow, (x - 6, y - 6), glow)
            # Carta por cima
            ci = card_image(rank, suit, cw, ch)
            frame_rgba.paste(ci, (x, y), ci)

        frames.append(frame_rgba.convert("RGB"))
        durs.append(1000 // fps)

    if frames:
        frames.append(frames[-1].copy())
        durs.append(1000)

    return _save_gif(frames, durs)


# ════════════════════════════════════════════════════════════════════════════
# 8. CAPTURE (xadrez) — peça capturada some gradualmente
# ════════════════════════════════════════════════════════════════════════════

def gif_piece_capture(
    board_img: Image.Image,
    piece_img: Image.Image,
    x: int, y: int,
    n_frames: int = 10,
) -> list[Image.Image]:
    """
    Retorna lista de frames com peça desaparecendo.
    Usado internamente pelo chess animator.
    """
    frames = []
    for i in range(n_frames):
        t     = i / (n_frames - 1)
        alpha = int(255 * (1.0 - t))
        frame = board_img.copy().convert("RGBA")
        fade  = piece_img.copy().convert("RGBA")
        r, g, b, a = fade.split()
        a = a.point(lambda p: int(p * (1.0 - t)))
        fade.putalpha(a)
        frame.paste(fade, (x, y), fade)
        frames.append(frame.convert("RGB"))
    return frames
