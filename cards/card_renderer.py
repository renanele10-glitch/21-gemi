"""
cards/card_renderer.py
Renderiza cartas usando o pack PNG real (242x340 RGBA).
Cache em memória para evitar recarregamento.
"""
from __future__ import annotations
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from functools import lru_cache

ASSETS = Path(__file__).parent.parent / "assets" / "cards"

# Mapeamento naipe: símbolo → nome do arquivo
_SUIT = {"♠": "spades", "♥": "hearts", "♦": "diamonds", "♣": "clubs"}
# Mapeamento valor: símbolo → nome do arquivo
_RANK = {
    "A": "A", "2": "2", "3": "3", "4": "4", "5": "5",
    "6": "6", "7": "7", "8": "8", "9": "9", "10": "10",
    "J": "J", "Q": "Q", "K": "K",
}


@lru_cache(maxsize=60)
def load_card(rank: str, suit: str) -> Image.Image:
    """Carrega carta do pack PNG. Cache automático."""
    suit_name = _SUIT.get(suit, suit.lower())
    rank_name  = _RANK.get(rank, rank)
    path = ASSETS / f"{suit_name}_{rank_name}.png"
    if path.exists():
        return Image.open(path).convert("RGBA")
    return _placeholder_card(rank, suit)


@lru_cache(maxsize=2)
def load_back(dark: bool = True) -> Image.Image:
    """Carrega verso da carta."""
    name = "back_dark.png" if dark else "back_light.png"
    path = ASSETS / name
    if path.exists():
        return Image.open(path).convert("RGBA")
    return _placeholder_back()


def resize_card(img: Image.Image, w: int, h: int) -> Image.Image:
    return img.resize((w, h), Image.LANCZOS)


def card_image(rank: str, suit: str,
               w: int = 110, h: int = 154,
               face_down: bool = False,
               shadow: bool = True) -> Image.Image:
    """
    Retorna carta redimensionada com sombra opcional.
    Resultado pronto pra colar numa mesa.
    """
    src = load_back() if face_down else load_card(rank, suit)
    card = resize_card(src, w, h)

    if not shadow:
        return card

    # Canvas com espaço pra sombra
    canvas = Image.new("RGBA", (w + 6, h + 6), (0, 0, 0, 0))
    # Sombra
    shadow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    shadow_layer.paste((0, 0, 0, 80), mask=card.split()[3])
    blurred = shadow_layer.filter(ImageFilter.GaussianBlur(3))
    canvas.paste(blurred, (4, 4), blurred)
    canvas.paste(card, (0, 0), card)
    return canvas


def _placeholder_card(rank: str, suit: str) -> Image.Image:
    """Fallback se o arquivo não existir."""
    img  = Image.new("RGBA", (242, 340), (250, 243, 228, 255))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([2, 2, 239, 337], radius=14,
                            outline=(170, 150, 110), width=2)
    is_red = suit in ("♥", "♦")
    fc = (180, 12, 12) if is_red else (8, 8, 12)
    try:
        f = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 60)
        fs = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 100)
    except Exception:
        f = ImageFont.load_default(size=60)
        fs = ImageFont.load_default(size=100)
    draw.text((16, 12), rank, font=f, fill=fc)
    draw.text((121, 170), suit, font=fs, fill=fc, anchor="mm")
    return img


def _placeholder_back() -> Image.Image:
    img  = Image.new("RGBA", (242, 340), (18, 8, 32, 255))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([2, 2, 239, 337], radius=14,
                            outline=(210, 170, 80), width=3)
    cx, cy, d = 121, 170, 55
    draw.polygon([(cx, cy-d), (cx+d, cy), (cx, cy+d), (cx-d, cy)],
                 fill=(140, 10, 10))
    draw.polygon([(cx, cy-22), (cx+22, cy), (cx, cy+22), (cx-22, cy)],
                 fill=(210, 170, 80))
    return img
