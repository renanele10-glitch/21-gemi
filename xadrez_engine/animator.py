"""
chess/animator.py
Animações GIF para o xadrez.
Movimento suave, captura com fade, promoção com flash.
"""
from __future__ import annotations
import io
import math
from PIL import Image, ImageDraw
import chess
from .render import render_board, _load_piece, _sq_to_xy, CELL


def _save_gif(frames: list[Image.Image], durations: list[int]) -> io.BytesIO:
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


def _ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def _ease_in_out(t: float) -> float:
    return t * t * (3 - 2 * t)


# ════════════════════════════════════════════════════════════════════════════
# MOVIMENTO SUAVE
# ════════════════════════════════════════════════════════════════════════════

def gif_move(
    board_before: chess.Board,
    board_after: chess.Board,
    from_sq: int,
    to_sq: int,
    flipped: bool = False,
    n_frames: int = 14,
) -> io.BytesIO:
    """
    Anima peça se movendo de from_sq para to_sq.
    board_before: estado antes do movimento
    board_after:  estado depois (usado no frame final)
    """
    frames, durs = [], []

    # Tabuleiro base sem a peça que vai se mover
    board_temp = board_before.copy()
    piece      = board_temp.piece_at(from_sq)
    if not piece:
        # Fallback: só mostra o estado final
        img = render_board(board_after, last_move=(from_sq, to_sq), flipped=flipped)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        return buf

    # Remove a peça do tabuleiro base para os frames intermediários
    board_temp.remove_piece_at(from_sq)

    sx, sy = _sq_to_xy(from_sq, flipped)
    tx, ty = _sq_to_xy(to_sq,   flipped)
    sprite = _load_piece(piece.symbol(), CELL)
    ox     = (CELL - sprite.width)  // 2
    oy     = (CELL - sprite.height) // 2

    # Captura: se há peça no destino, ela some gradualmente
    captured = board_before.piece_at(to_sq)

    for i in range(n_frames):
        t     = i / (n_frames - 1)
        ease  = _ease_in_out(t)

        # Highlight do último movimento vai aparecendo
        lm = (from_sq, to_sq) if t > 0.5 else None

        base = render_board(
            board_temp,
            last_move=lm,
            check_sq=None,
            flipped=flipped,
        ).convert("RGBA")

        # Captura: peça inimiga some
        if captured and t < 0.8:
            cap_sym    = captured.symbol()
            cap_sprite = _load_piece(cap_sym, CELL)
            cap_alpha  = max(0, int(255 * (1.0 - t / 0.8)))
            cap_copy   = cap_sprite.copy()
            r, g, b, a = cap_copy.split()
            a = a.point(lambda p: int(p * cap_alpha / 255))
            cap_copy.putalpha(a)
            base.paste(cap_copy, (tx + ox, ty + oy), cap_copy)

        # Peça em movimento
        cx2 = int(sx + (tx - sx) * ease)
        cy2 = int(sy + (ty - sy) * ease)
        base.paste(sprite, (cx2 + ox, cy2 + oy), sprite)

        frames.append(base.convert("RGB"))
        durs.append(30 if i < n_frames - 1 else 800)

    # Frame final com estado completo
    check_sq = board_after.king(board_after.turn) if board_after.is_check() else None
    final = render_board(board_after,
                         last_move=(from_sq, to_sq),
                         check_sq=check_sq,
                         flipped=flipped)
    frames.append(final.convert("RGB"))
    durs.append(1000)

    return _save_gif(frames, durs)


# ════════════════════════════════════════════════════════════════════════════
# PROMOÇÃO — flash + destaque
# ════════════════════════════════════════════════════════════════════════════

def gif_promotion(
    board_after: chess.Board,
    promoted_sq: int,
    flipped: bool = False,
    n_frames: int = 18,
) -> io.BytesIO:
    """Flash dourado na casa de promoção."""
    frames, durs = [], []
    GOLD = (210, 170, 80)

    for i in range(n_frames):
        t     = i / (n_frames - 1)
        pulse = math.sin(t * math.pi * 3) * 0.5 + 0.5
        alpha = int(200 * pulse)

        base = render_board(board_after, flipped=flipped).convert("RGBA")
        x, y = _sq_to_xy(promoted_sq, flipped)
        ov   = Image.new("RGBA", (CELL, CELL), (*GOLD, alpha))
        base.paste(ov, (x, y), ov)

        frames.append(base.convert("RGB"))
        durs.append(45 if i < n_frames - 1 else 1200)

    return _save_gif(frames, durs)


# ════════════════════════════════════════════════════════════════════════════
# XEQUE-MATE — rei pulsa vermelho
# ════════════════════════════════════════════════════════════════════════════

def gif_checkmate(
    board: chess.Board,
    king_sq: int,
    flipped: bool = False,
    n_cycles: int = 3,
    fps: int = 10,
) -> io.BytesIO:
    frames, durs = [], []
    total = n_cycles * fps

    for fi in range(total):
        t     = fi / total
        pulse = math.sin(t * math.pi * n_cycles * 2)
        alpha = int(100 + 100 * pulse)

        base = render_board(board, flipped=flipped).convert("RGBA")
        x, y = _sq_to_xy(king_sq, flipped)
        ov   = Image.new("RGBA", (CELL, CELL), (255, 20, 20, alpha))
        base.paste(ov, (x, y), ov)

        frames.append(base.convert("RGB"))
        durs.append(1000 // fps)

    return _save_gif(frames, durs)
    
