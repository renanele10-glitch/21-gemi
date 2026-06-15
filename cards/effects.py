"""
cards/effects.py
Efeitos visuais reutilizáveis para qualquer jogo de cartas.
Retorna layers RGBA para compor sobre a mesa.
"""
from __future__ import annotations
import math
from PIL import Image, ImageDraw, ImageFilter

GOLD    = (210, 170,  80)
GOLD_LT = (248, 218, 130)


def glow_border(size: tuple[int, int],
                color: tuple = GOLD,
                radius: int = 12,
                alpha: int = 160) -> Image.Image:
    """Borda brilhante para destacar carta ou área."""
    w, h = size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer, "RGBA")
    for i in range(3):
        a = int(alpha * (1 - i * 0.3))
        draw.rounded_rectangle([i, i, w-1-i, h-1-i],
                                radius=radius - i,
                                outline=(*color, a), width=2)
    return layer.filter(ImageFilter.GaussianBlur(1))


def winner_glow(size: tuple[int, int],
                color: tuple = (80, 220, 80),
                alpha: int = 120) -> Image.Image:
    """Brilho verde para carta/jogador vencedor."""
    w, h = size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer, "RGBA")
    draw.rounded_rectangle([0, 0, w-1, h-1], radius=10,
                            fill=(*color, alpha))
    return layer.filter(ImageFilter.GaussianBlur(4))


def fade_layer(size: tuple[int, int],
               alpha: float) -> Image.Image:
    """Layer preto semitransparente para fade."""
    w, h = size
    a    = max(0, min(255, int(255 * (1.0 - alpha))))
    return Image.new("RGBA", (w, h), (0, 0, 0, a))


def result_box(w: int = 520, h: int = 56,
               text: str = "",
               color: tuple = GOLD_LT,
               alpha: float = 1.0) -> Image.Image:
    """Caixa de resultado com texto centralizado."""
    from pathlib import Path
    from PIL import ImageFont

    def _font(size):
        for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
            if Path(p).exists():
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    pass
        return ImageFont.load_default(size=size)

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer, "RGBA")

    bg_a = int(238 * alpha)
    bd_a = int(180 * alpha)
    draw.rounded_rectangle([0, 0, w-1, h-1], radius=10,
                            fill=(6, 3, 14, bg_a),
                            outline=(*GOLD, bd_a), width=2)
    if text:
        f = _font(max(12, int(20 * alpha)))
        r, g, b = color
        tc = (int(r * alpha), int(g * alpha), int(b * alpha))
        draw.text((w // 2 + 1, h // 2 + 1), text,
                  font=f, fill=(0, 0, 0, int(180 * alpha)), anchor="mm")
        draw.text((w // 2, h // 2), text, font=f, fill=tc, anchor="mm")
    return layer


def chip_stack(value: int,
               w: int = 48, h: int = 48) -> Image.Image:
    """Renderiza stack de fichas com valor."""
    from pathlib import Path
    from PIL import ImageFont

    def _font(size):
        for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
            if Path(p).exists():
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    pass
        return ImageFont.load_default(size=size)

    img  = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    # Cor da ficha por valor
    if value >= 500:
        chip_color = (180, 10, 10)      # vermelho
    elif value >= 100:
        chip_color = (10, 80, 200)      # azul
    elif value >= 25:
        chip_color = (20, 140, 40)      # verde
    else:
        chip_color = (140, 140, 140)    # cinza

    cx, cy, r = w // 2, h // 2, w // 2 - 3
    # Sombra
    draw.ellipse([cx-r+3, cy-r+3, cx+r+3, cy+r+3], fill=(0, 0, 0, 80))
    # Corpo
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=chip_color)
    # Aro externo
    draw.ellipse([cx-r, cy-r, cx+r, cy+r],
                 outline=(255, 255, 255, 120), width=2)
    # Valor
    f = _font(max(7, w // 4))
    txt = str(value) if value < 1000 else f"{value//1000}k"
    draw.text((cx, cy), txt, font=f, fill=(255, 255, 255), anchor="mm")
    return img


def pulse_frame(base: Image.Image,
                x: int, y: int,
                w: int, h: int,
                t: float,
                color: tuple = GOLD) -> Image.Image:
    """
    Adiciona pulso dourado sobre área (x,y,w,h) em frame t (0→1).
    Retorna cópia da imagem base com efeito aplicado.
    """
    frame = base.copy().convert("RGBA")
    alpha = int(120 * math.sin(t * math.pi))
    if alpha <= 0:
        return frame
    layer = Image.new("RGBA", (w + 8, h + 8), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer, "RGBA")
    draw.rounded_rectangle([0, 0, w + 7, h + 7], radius=10,
                            fill=(*color, alpha))
    blurred = layer.filter(ImageFilter.GaussianBlur(3))
    frame.paste(blurred, (x - 4, y - 4), blurred)
    return frame
