"""
chess/render.py
Renderiza tabuleiro estilo Chess.com com peças Unicode grandes.
Cache de sprites e tabuleiros.
"""
from __future__ import annotations
import io
import math
from functools import lru_cache
from pathlib import Path
from typing import Optional
import chess
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── Dimensões ─────────────────────────────────────────────────────────────
BOARD_SIZE  = 560       # Tabuleiro em si
BORDER      = 28        # Borda com coordenadas
TOTAL       = BOARD_SIZE + 2 * BORDER   # 616×616
CELL        = BOARD_SIZE // 8           # 70px por casa

# ── Paleta Chess.com premium ─────────────────────────────────────────────
LIGHT_SQ    = (240, 217, 181)   # Bege claro
DARK_SQ     = (181, 136,  99)   # Castanho
BORDER_BG   = ( 48,  36,  26)   # Borda escura madeira
COORD_COL   = (196, 168, 136)   # Cor das coordenadas
HIGHLIGHT   = (247, 247, 105, 180)  # Amarelo — último movimento
SEL_COLOR   = (  0, 128, 255, 160)  # Azul — seleção
MOVE_DOT    = (  0,   0,   0,  60)  # Ponto de movimento possível
CAPTURE_HL  = (255,  50,  50, 120)  # Vermelho — captura possível
CHECK_HL    = (255,  20,  20, 200)  # Vermelho forte — rei em xeque

# Peças Unicode → estilo Chess.com
PIECE_UNICODE = {
    "K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
    "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟",
}

# Mapeamento python-chess piece_type → símbolo
PT_SYM = {
    chess.KING:   ("K", "k"),
    chess.QUEEN:  ("Q", "q"),
    chess.ROOK:   ("R", "r"),
    chess.BISHOP: ("B", "b"),
    chess.KNIGHT: ("N", "n"),
    chess.PAWN:   ("P", "p"),
}


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
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


@lru_cache(maxsize=32)
def _piece_sprite(symbol: str, cell: int = CELL) -> Image.Image:
    """
    Gera sprite de peça com sombra e anti-alias.
    Cached por símbolo + tamanho.
    """
    size   = cell + 8
    img    = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw   = ImageDraw.Draw(img, "RGBA")
    is_white = symbol.isupper()
    sym    = PIECE_UNICODE.get(symbol, symbol)

    # Tamanho da fonte baseado na célula
    fs = max(20, int(cell * 0.78))
    f  = _font(fs)

    cx, cy = size // 2, size // 2

    # Sombra
    draw.text((cx + 2, cy + 3), sym, font=f,
              fill=(0, 0, 0, 120), anchor="mm")
    # Contorno (para peças brancas em fundo claro)
    if is_white:
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            draw.text((cx + dx, cy + dy), sym, font=f,
                      fill=(80, 60, 40, 200), anchor="mm")
    # Peça
    color = (255, 255, 255) if is_white else (30, 20, 10)
    draw.text((cx, cy), sym, font=f, fill=color, anchor="mm")

    return img


def _sq_to_xy(square: int, flipped: bool = False) -> tuple[int, int]:
    """Square index → pixel (top-left da casa) no canvas total."""
    file_ = chess.square_file(square)
    rank_ = chess.square_rank(square)
    if flipped:
        col = 7 - file_
        row = rank_
    else:
        col = file_
        row = 7 - rank_
    x = BORDER + col * CELL
    y = BORDER + row * CELL
    return x, y


@lru_cache(maxsize=4)
def _base_board(flipped: bool = False) -> Image.Image:
    """
    Tabuleiro vazio com borda e coordenadas.
    Cached — recriado apenas se flipped mudar.
    """
    img  = Image.new("RGB", (TOTAL, TOTAL), BORDER_BG)
    draw = ImageDraw.Draw(img)

    # Casas
    for rank in range(8):
        for file_ in range(8):
            sq    = chess.square(file_, rank)
            x, y  = _sq_to_xy(sq, flipped)
            light = (file_ + rank) % 2 == 0
            color = LIGHT_SQ if light else DARK_SQ
            draw.rectangle([x, y, x + CELL - 1, y + CELL - 1], fill=color)

    # Coordenadas
    fc = _font(13, bold=False)
    for i in range(8):
        # Letras (a-h)
        file_ = 7 - i if flipped else i
        lx    = BORDER + i * CELL + CELL // 2
        letter = chr(ord('a') + file_)
        draw.text((lx, TOTAL - BORDER // 2), letter,
                  font=fc, fill=COORD_COL, anchor="mm")
        draw.text((lx, BORDER // 2), letter,
                  font=fc, fill=COORD_COL, anchor="mm")

        # Números (1-8)
        rank_ = i if flipped else 7 - i
        ly    = BORDER + i * CELL + CELL // 2
        draw.text((BORDER // 2, ly), str(rank_ + 1),
                  font=fc, fill=COORD_COL, anchor="mm")
        draw.text((TOTAL - BORDER // 2, ly), str(rank_ + 1),
                  font=fc, fill=COORD_COL, anchor="mm")

    return img


def render_board(
    board: chess.Board,
    selected: Optional[int] = None,
    legal_moves: Optional[list[int]] = None,
    last_move: Optional[tuple[int, int]] = None,
    check_sq: Optional[int] = None,
    flipped: bool = False,
) -> Image.Image:
    """
    Retorna Image PIL do tabuleiro completo.
    (Não serializa — o animator usa a PIL diretamente.)
    """
    img  = _base_board(flipped).copy()
    draw = ImageDraw.Draw(img, "RGBA")
    legal_moves = legal_moves or []

    # ── Highlights ────────────────────────────────────────────────────────

    # Último movimento
    if last_move:
        for sq in last_move:
            x, y = _sq_to_xy(sq, flipped)
            ov   = Image.new("RGBA", (CELL, CELL), HIGHLIGHT)
            img.paste(ov, (x, y), ov)

    # Seleção
    if selected is not None:
        x, y = _sq_to_xy(selected, flipped)
        ov   = Image.new("RGBA", (CELL, CELL), SEL_COLOR)
        img.paste(ov, (x, y), ov)

    # Rei em xeque
    if check_sq is not None:
        x, y = _sq_to_xy(check_sq, flipped)
        ov   = Image.new("RGBA", (CELL, CELL), CHECK_HL)
        img.paste(ov, (x, y), ov)

    # Movimentos possíveis
    for sq in legal_moves:
        x, y = _sq_to_xy(sq, flipped)
        cx2  = x + CELL // 2
        cy2  = y + CELL // 2
        # Se há peça inimiga = círculo de captura
        piece_there = board.piece_at(sq)
        if piece_there:
            ov   = Image.new("RGBA", (CELL, CELL), CAPTURE_HL)
            img.paste(ov, (x, y), ov)
        else:
            # Ponto de movimento
            r    = CELL // 6
            ov   = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
            od   = ImageDraw.Draw(ov, "RGBA")
            od.ellipse([CELL//2-r, CELL//2-r, CELL//2+r, CELL//2+r],
                       fill=MOVE_DOT)
            img.paste(ov, (x, y), ov)

    # ── Peças ─────────────────────────────────────────────────────────────
    draw = ImageDraw.Draw(img, "RGBA")
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece:
            continue
        sym    = piece.symbol()
        sprite = _piece_sprite(sym, CELL)
        x, y   = _sq_to_xy(sq, flipped)
        # Centraliza sprite na casa
        ox     = (CELL - sprite.width)  // 2
        oy     = (CELL - sprite.height) // 2
        img.paste(sprite, (x + ox, y + oy), sprite)

    return img


def render_board_bytes(board: chess.Board, **kwargs) -> io.BytesIO:
    """Versão que retorna BytesIO (para enviar ao Discord)."""
    img = render_board(board, **kwargs)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf
