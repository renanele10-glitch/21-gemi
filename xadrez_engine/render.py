"""
chess/render.py
Tabuleiro estilo Chess.com usando assets PNG reais.
Board: dark_wood.png (560x560 tabuleiro puro, sem borda)
Peças: neo/*.png (140x140 RGBA)
"""
from __future__ import annotations
import io
from functools import lru_cache
from pathlib import Path
from typing import Optional
import chess
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ASSETS   = Path(__file__).parent.parent / "assets" / "chess"
PIECES_DIR = ASSETS / "pieces_neo"
BOARD_IMG  = ASSETS / "board_dark_wood.png"

# Dimensões
BOARD_SIZE = 560
BORDER     = 28
TOTAL      = BOARD_SIZE + 2 * BORDER
CELL       = BOARD_SIZE // 8   # 70

# Highlights (RGBA)
HIGHLIGHT  = (247, 247, 105, 160)
SEL_COLOR  = (  0, 148, 255, 150)
MOVE_DOT   = (  0,   0,   0,  55)
CAPTURE_HL = (255,  60,  60, 110)
CHECK_HL   = (255,  20,  20, 190)
COORD_COL  = (196, 168, 136)
BORDER_BG  = ( 48,  36,  26)


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]:
        if Path(p).exists():
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default(size=size)


@lru_cache(maxsize=1)
def _load_board() -> Image.Image:
    """Carrega tabuleiro base 560x560."""
    if BOARD_IMG.exists():
        return Image.open(BOARD_IMG).convert("RGBA").resize(
            (BOARD_SIZE, BOARD_SIZE), Image.LANCZOS)
    # Fallback: tabuleiro simples
    img  = Image.new("RGBA", (BOARD_SIZE, BOARD_SIZE))
    draw = ImageDraw.Draw(img)
    LIGHT = (240, 217, 181); DARK = (181, 136, 99)
    for r in range(8):
        for f in range(8):
            c = LIGHT if (r+f)%2==0 else DARK
            draw.rectangle([f*CELL, r*CELL, (f+1)*CELL-1, (r+1)*CELL-1], fill=c)
    return img


@lru_cache(maxsize=14)
def _load_piece(symbol: str) -> Image.Image:
    """
    Carrega peça PNG do Chess.com.
    symbol: 'K','Q','R','B','N','P' (brancas) ou minúsculas (pretas)
    """
    color  = "w" if symbol.isupper() else "b"
    ptype  = symbol.lower()
    path   = PIECES_DIR / f"{color}{ptype}.png"
    if path.exists():
        img = Image.open(path).convert("RGBA")
        return img.resize((CELL, CELL), Image.LANCZOS)
    # Fallback Unicode
    return _piece_fallback(symbol)


def _piece_fallback(symbol: str) -> Image.Image:
    UNICODE = {"K":"♔","Q":"♕","R":"♖","B":"♗","N":"♘","P":"♙",
               "k":"♚","q":"♛","r":"♜","b":"♝","n":"♞","p":"♟"}
    img  = Image.new("RGBA", (CELL, CELL), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    f    = _font(int(CELL*0.75))
    col  = (255,255,255) if symbol.isupper() else (20,10,5)
    draw.text((CELL//2+1, CELL//2+2), UNICODE.get(symbol,"?"),
              font=f, fill=(0,0,0,150), anchor="mm")
    draw.text((CELL//2, CELL//2), UNICODE.get(symbol,"?"),
              font=f, fill=col, anchor="mm")
    return img


def _sq_to_xy(square: int, flipped: bool = False) -> tuple[int, int]:
    """Square → pixel top-left no canvas TOTAL (com borda)."""
    file_ = chess.square_file(square)
    rank_ = chess.square_rank(square)
    col = (7 - file_) if flipped else file_
    row = rank_        if flipped else (7 - rank_)
    return BORDER + col * CELL, BORDER + row * CELL


def render_board(
    board: chess.Board,
    selected: Optional[int] = None,
    legal_moves: Optional[list[int]] = None,
    last_move: Optional[tuple[int, int]] = None,
    check_sq: Optional[int] = None,
    flipped: bool = False,
) -> Image.Image:
    legal_moves = legal_moves or []

    # Canvas com borda de madeira
    canvas = Image.new("RGB", (TOTAL, TOTAL), BORDER_BG)

    # Tabuleiro base
    board_img = _load_board().copy()
    board_rgba = board_img.convert("RGBA")

    # ── Highlights sobre o tabuleiro ─────────────────────────────────────
    def _ov(color_rgba):
        ov = Image.new("RGBA", (CELL, CELL), color_rgba)
        return ov

    if last_move:
        for sq in last_move:
            x, y = _sq_to_xy(sq, flipped)
            bx, by = x - BORDER, y - BORDER
            board_rgba.paste(_ov(HIGHLIGHT), (bx, by), _ov(HIGHLIGHT))

    if selected is not None:
        x, y = _sq_to_xy(selected, flipped)
        bx, by = x - BORDER, y - BORDER
        board_rgba.paste(_ov(SEL_COLOR), (bx, by), _ov(SEL_COLOR))

    if check_sq is not None:
        x, y = _sq_to_xy(check_sq, flipped)
        bx, by = x - BORDER, y - BORDER
        board_rgba.paste(_ov(CHECK_HL), (bx, by), _ov(CHECK_HL))

    # Movimentos possíveis
    for sq in legal_moves:
        x, y = _sq_to_xy(sq, flipped)
        bx, by = x - BORDER, y - BORDER
        piece_there = board.piece_at(sq)
        if piece_there:
            board_rgba.paste(_ov(CAPTURE_HL), (bx, by), _ov(CAPTURE_HL))
        else:
            # Ponto central
            dot = Image.new("RGBA", (CELL, CELL), (0,0,0,0))
            dd  = ImageDraw.Draw(dot, "RGBA")
            r   = CELL // 6
            dd.ellipse([CELL//2-r, CELL//2-r, CELL//2+r, CELL//2+r],
                       fill=MOVE_DOT)
            board_rgba.paste(dot, (bx, by), dot)

    # Cola tabuleiro no canvas
    canvas.paste(board_rgba.convert("RGB"), (BORDER, BORDER))

    # ── Peças ─────────────────────────────────────────────────────────────
    canvas_rgba = canvas.convert("RGBA")
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece: continue
        sprite = _load_piece(piece.symbol())
        x, y   = _sq_to_xy(sq, flipped)
        canvas_rgba.paste(sprite, (x, y), sprite)

    # ── Coordenadas ───────────────────────────────────────────────────────
    draw = ImageDraw.Draw(canvas_rgba)
    fc   = _font(13)
    for i in range(8):
        file_ = (7-i) if flipped else i
        rank_ = i     if flipped else (7-i)
        # Letras embaixo e em cima
        lx = BORDER + i*CELL + CELL//2
        draw.text((lx, TOTAL - BORDER//2), chr(65+file_),
                  font=fc, fill=COORD_COL, anchor="mm")
        # Números esquerda
        ly = BORDER + i*CELL + CELL//2
        draw.text((BORDER//2, ly), str(rank_+1),
                  font=fc, fill=COORD_COL, anchor="mm")

    return canvas_rgba.convert("RGB")


def render_board_bytes(board: chess.Board, **kwargs) -> io.BytesIO:
    img = render_board(board, **kwargs)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf
