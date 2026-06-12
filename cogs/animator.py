"""
cogs/animator.py — Engine de animação GIF para cartas.
LOOP: todas as animações tocam UMA vez e param.
"""

import io, math
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

# Paleta
BG      = (12,  6, 16)
GOLD    = (210, 170, 80)
GOLD_LT = (240, 210, 130)
CREAM   = (235, 220, 195)
RED_D   = (140,  15, 15)

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
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default(size=size)


def _draw_frente(draw, x, y, rank, suit, cw, ch, scale_x=1.0):
    w = max(2, int(cw * scale_x))
    ox = (cw - w) // 2
    rx, ry = x + ox, y
    is_red = suit in ("♥", "♦")
    
    # Cores alinhadas com o render.py
    fc = (175, 12, 12) if is_red else (8, 8, 12)
    bg = (248, 240, 224)
    out = (175, 155, 115)
    
    draw.rounded_rectangle([rx, ry, rx+w, ry+ch], radius=max(2, int(10*scale_x)),
                            fill=bg, outline=out, width=1)
    if scale_x > 0.25:
        # Fontes grandes e consistentes com o render.py
        fr = _font(max(8, int(17*scale_x)))
        fs = _font(max(10, int(46*scale_x)))
        
        # Rank superior esquerdo
        draw.text((rx+max(3,int(8*scale_x)), ry+7), rank, font=fr, fill=fc)
        # Rank inferior direito
        draw.text((rx+w-max(3,int(8*scale_x)), ry+ch-8), rank, font=fr, fill=fc, anchor="rb")
        # Naipe centralizado
        draw.text((rx+w//2, ry+ch//2), suit, font=fs, fill=fc, anchor="mm")


def _draw_verso(draw, x, y, cw, ch, scale_x=1.0):
    w = max(2, int(cw * scale_x))
    ox = (cw - w) // 2
    rx, ry = x + ox, y
    
    # Fundo do verso alinhado com o render.py
    draw.rounded_rectangle([rx, ry, rx+w, ry+ch], radius=max(2, int(10*scale_x)),
                            fill=(18, 8, 30), outline=GOLD, width=max(1, int(2*scale_x)))
    if scale_x > 0.2:
        cx2, cy2 = rx + w//2, ry + ch//2
        d  = max(4, int(22*scale_x))
        d2 = max(2, int(9*scale_x))
        draw.polygon([(cx2,cy2-d),(cx2+d,cy2),(cx2,cy2+d),(cx2-d,cy2)], fill=RED_D)
        draw.polygon([(cx2,cy2-d2),(cx2+d2,cy2),(cx2,cy2+d2),(cx2-d2,cy2)], fill=GOLD)


def _clone(base: Image.Image) -> Image.Image:
    return base.convert("RGB").copy()


def _save_gif(frames, durations) -> io.BytesIO:
    """
    Salva GIF que toca UMA única vez e para no último frame.
    No formato GIF: loop não presente = toca uma vez.
    """
    buf = io.BytesIO()
    # Não passar parâmetro loop = toca somente uma vez
    frames[0].save(
        buf, format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        optimize=False,
        disposal=2,
        # SEM loop= aqui → toca uma vez e para
    )
    buf.seek(0)
    return buf


# ══════════════════════════════════════════════════════════════════════════════
# 1. CARTA NOVA — desliza de cima
# ══════════════════════════════════════════════════════════════════════════════

def gif_carta_nova(mesa_img: Image.Image,
                   x: int, y: int,
                   rank: str, suit: str,
                   cw: int = 100, ch: int = 140,
                   n_frames: int = 12) -> io.BytesIO:
    frames = []
    durations = []
    start_y = y - 200

    for i in range(n_frames):
        t = i / (n_frames - 1)
        ease = 1 - (1 - t) ** 3
        cur_y = int(start_y + (y - start_y) * ease)
        scale = 0.6 + 0.4 * ease

        frame = _clone(mesa_img)
        draw  = ImageDraw.Draw(frame)
        _draw_frente(draw, x, cur_y, rank, suit, cw, ch, scale_x=scale)
        frames.append(frame)
        durations.append(35 if i < n_frames-1 else 1000)

    return _save_gif(frames, durations)


# ══════════════════════════════════════════════════════════════════════════════
# 2. FLIP DEALER — verso → frente (3D)
# ══════════════════════════════════════════════════════════════════════════════

def gif_flip_dealer(mesa_img: Image.Image,
                    x: int, y: int,
                    rank: str, suit: str,
                    cw: int = 100, ch: int = 140,
                    n_frames: int = 16) -> io.BytesIO:
    frames = []
    durations = []
    half = n_frames // 2

    for i in range(n_frames):
        frame = _clone(mesa_img)
        draw  = ImageDraw.Draw(frame)

        if i < half:
            t = i / half
            scale = 1.0 - t
            _draw_verso(draw, x, y, cw, ch, scale_x=max(0.01, scale))
        else:
            t = (i - half) / half
            ease = t * t * (3 - 2*t)
            _draw_frente(draw, x, y, rank, suit, cw, ch, scale_x=max(0.01, ease))

        frames.append(frame)
        # Mais rápido no meio, mais lento no fim
        if i == n_frames - 1:
            durations.append(1200)
        elif abs(i - half) <= 1:
            durations.append(20)
        else:
            durations.append(40)

    return _save_gif(frames, durations)


# ══════════════════════════════════════════════════════════════════════════════
# 3. RESULTADO — texto pulsa UMA vez
# ══════════════════════════════════════════════════════════════════════════════

def gif_resultado(mesa_img: Image.Image,
                  texto: str,
                  cor: tuple = GOLD_LT,
                  n_frames: int = 18) -> io.BytesIO:
    frames = []
    durations = []
    ow, oh = mesa_img.size

    for i in range(n_frames):
        t = i / (n_frames - 1)

        if t < 0.35:
            alpha = t / 0.35
            scale = 0.75 + 0.25 * (t / 0.35)
        elif t < 0.75:
            alpha = 1.0
            pulse = math.sin((t - 0.35) / 0.4 * math.pi)
            scale = 1.0 + 0.06 * pulse
        else:
            alpha = 1.0
            scale = 1.0

        frame = _clone(mesa_img)

        box_w = int(420 * scale)
        box_h = int(65 * scale)
        bx = ow//2 - box_w//2
        by = oh//2 - box_h//2

        overlay = Image.new("RGBA", frame.size, (0,0,0,0))
        od = ImageDraw.Draw(overlay, "RGBA")
        od.rounded_rectangle([bx, by, bx+box_w, by+box_h],
                              radius=10,
                              fill=(8, 4, 16, int(220*alpha)),
                              outline=(*GOLD, int(200*alpha)), width=2)
        frame_rgba = frame.convert("RGBA")
        frame_rgba.alpha_composite(overlay)
        frame = frame_rgba.convert("RGB")

        draw = ImageDraw.Draw(frame)
        fsize = max(14, int(24 * scale))
        f = _font(fsize)
        r, g, b = cor
        tc = (int(r*alpha), int(g*alpha), int(b*alpha))
        draw.text((ow//2+1, oh//2+1), texto, font=f, fill=(0,0,0), anchor="mm")
        draw.text((ow//2, oh//2),     texto, font=f, fill=tc,       anchor="mm")

        frames.append(frame)
        durations.append(45 if i < n_frames-1 else 2000)

    return _save_gif(frames, durations)


# ══════════════════════════════════════════════════════════════════════════════
# 4. DISTRIBUIÇÃO — cartas saindo do centro uma a uma
# ══════════════════════════════════════════════════════════════════════════════

def gif_distribuicao(mesa_img: Image.Image,
                     cartas_jogador: list,
                     cartas_dealer: list,
                     posicoes_j: list,
                     posicoes_d: list,
                     cw: int = 100, ch: int = 140) -> io.BytesIO:
    frames = []
    durations = []

    ordem = []
    for i in range(max(len(cartas_jogador), len(cartas_dealer))):
        if i < len(cartas_jogador): ordem.append(("j", i))
        if i < len(cartas_dealer):  ordem.append(("d", i))

    deck_x = mesa_img.width  // 2
    deck_y = mesa_img.height // 2 - 20
    N = 10

    revealed_j = []
    revealed_d = []

    for quem, idx in ordem:
        if quem == "j":
            rank, suit = cartas_jogador[idx]
            tx, ty = posicoes_j[idx]
            face_down = False
        else:
            rank, suit = cartas_dealer[idx]
            tx, ty = posicoes_d[idx]
            face_down = (idx == 0)

        for fi in range(N):
            t = fi / (N-1)
            ease = 1 - (1-t)**2
            cx2 = int(deck_x + (tx - deck_x) * ease)
            cy2 = int(deck_y + (ty - deck_y) * ease)
            scale = 0.4 + 0.6*ease

            frame = _clone(mesa_img)
            draw  = ImageDraw.Draw(frame)

            for ri, (rr, rs) in enumerate(revealed_j):
                _draw_frente(draw, posicoes_j[ri][0], posicoes_j[ri][1], rr, rs, cw, ch)
            for ri, (rr, rs) in enumerate(revealed_d):
                if ri == 0:
                    _draw_verso(draw, posicoes_d[ri][0], posicoes_d[ri][1], cw, ch)
                else:
                    _draw_frente(draw, posicoes_d[ri][0], posicoes_d[ri][1], rr, rs, cw, ch)

            if face_down:
                _draw_verso(draw, cx2 - cw//2, cy2 - ch//2, cw, ch, scale_x=scale)
            else:
                _draw_frente(draw, cx2 - cw//2, cy2 - ch//2, rank, suit, cw, ch, scale_x=scale)

            frames.append(frame)
            durations.append(30)

        if quem == "j": revealed_j.append((rank, suit))
        else:           revealed_d.append((rank, suit))

    if frames:
        frames.append(frames[-1].copy())
        durations.append(1000)

    return _save_gif(frames, durations)

