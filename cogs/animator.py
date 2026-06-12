"""
cogs/animator.py — Sincronizado para matching perfeito com o render base.
"""

import io, math
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

BG      = (12,  6, 16)
GOLD    = (210, 170, 80)
GOLD_LT = (240, 210, 130)
CREAM   = (235, 220, 195)
RED_D   = (145,  12, 12)

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
    
    # Sombra dinâmica proporcional ao scale
    draw.rounded_rectangle([rx+5, ry+5, rx+w+5, ry+ch+5], 
                           radius=max(2, int(12*scale_x)), fill=(0,0,0,100))

    is_red = suit in ("♥", "♦")
    fc = (185, 20, 20) if is_red else (15, 15, 20)
    
    draw.rounded_rectangle([rx, ry, rx+w, ry+ch], 
                           radius=max(2, int(12*scale_x)), fill=(248, 240, 224), 
                           outline=(175, 155, 115), width=max(1, int(2*scale_x)))
    
    if scale_x > 0.25:
        fr = _font(max(8, int(28*scale_x)))
        fs = _font(max(10, int(75*scale_x)))
        draw.text((rx+max(3,int(10*scale_x)), ry+10), rank, font=fr, fill=fc)
        draw.text((rx+w-max(3,int(10*scale_x)), ry+ch-10), rank, font=fr, fill=fc, anchor="rb")
        draw.text((rx+w//2, ry+ch//2), suit, font=fs, fill=fc, anchor="mm")


def _draw_verso(draw, x, y, cw, ch, scale_x=1.0):
    w = max(2, int(cw * scale_x))
    ox = (cw - w) // 2
    rx, ry = x + ox, y
    
    # Sombra
    draw.rounded_rectangle([rx+5, ry+5, rx+w+5, ry+ch+5], 
                           radius=max(2, int(12*scale_x)), fill=(0,0,0,100))

    draw.rounded_rectangle([rx, ry, rx+w, ry+ch], radius=max(2, int(12*scale_x)),
                            fill=(18, 8, 30), outline=GOLD, width=max(1, int(2*scale_x)))
    if scale_x > 0.2:
        cx2, cy2 = rx + w//2, ry + ch//2
        d  = max(4, int(28*scale_x))
        d2 = max(2, int(12*scale_x))
        draw.polygon([(cx2,cy2-d),(cx2+d,cy2),(cx2,cy2+d),(cx2-d,cy2)], fill=RED_D)
        draw.polygon([(cx2,cy2-d2),(cx2+d2,cy2),(cx2,cy2+d2),(cx2-d2,cy2)], fill=GOLD)


def _clone(base: Image.Image) -> Image.Image:
    return base.convert("RGB").copy()


def _save_gif(frames, durations) -> io.BytesIO:
    buf = io.BytesIO()
    frames[0].save(
        buf, format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        optimize=False,
        disposal=2,
    )
    buf.seek(0)
    return buf


# (Mantenha gif_carta_nova, gif_flip_dealer e gif_distribuicao iguais, 
# só mude o gif_resultado para comportar os textos maiores)

def gif_carta_nova(mesa_img, x, y, rank, suit, cw=130, ch=185, n_frames=12):
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

def gif_flip_dealer(mesa_img, x, y, rank, suit, cw=130, ch=185, n_frames=16):
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
        if i == n_frames - 1: durations.append(1200)
        elif abs(i - half) <= 1: durations.append(20)
        else: durations.append(40)

    return _save_gif(frames, durations)

def gif_resultado(mesa_img: Image.Image, texto: str, cor: tuple = GOLD_LT, n_frames: int = 18):
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

        # Caixa do resultado maior agora
        box_w = int(580 * scale)
        box_h = int(80 * scale)
        bx = ow//2 - box_w//2
        by = oh//2 - box_h//2

        overlay = Image.new("RGBA", frame.size, (0,0,0,0))
        od = ImageDraw.Draw(overlay, "RGBA")
        od.rounded_rectangle([bx, by, bx+box_w, by+box_h],
                              radius=10,
                              fill=(8, 4, 16, int(220*alpha)),
                              outline=(*GOLD, int(200*alpha)), width=3)
        frame_rgba = frame.convert("RGBA")
        frame_rgba.alpha_composite(overlay)
        frame = frame_rgba.convert("RGB")

        draw = ImageDraw.Draw(frame)
        fsize = max(18, int(32 * scale)) # Fonte maior
        f = _font(fsize)
        r, g, b = cor
        tc = (int(r*alpha), int(g*alpha), int(b*alpha))
        draw.text((ow//2+2, oh//2+2), texto, font=f, fill=(0,0,0), anchor="mm")
        draw.text((ow//2, oh//2),     texto, font=f, fill=tc,       anchor="mm")

        frames.append(frame)
        durations.append(45 if i < n_frames-1 else 2000)

    return _save_gif(frames, durations)

def gif_distribuicao(mesa_img, cartas_jogador, cartas_dealer, posicoes_j, posicoes_d, cw=130, ch=185):
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
