"""
cogs/animator.py — Engine de animação GIF para cartas.

Funções exportadas:
  gif_carta_nova(mesa_img, x, y, rank, suit, cw, ch)  → BytesIO (GIF)
  gif_flip_dealer(mesa_img, x, y, rank, suit, cw, ch) → BytesIO (GIF)
  gif_resultado(mesa_img, texto, cor)                  → BytesIO (GIF)

Uso no blackjack:
  - Quando jogador compra carta   → gif_carta_nova(...)
  - Quando dealer revela carta    → gif_flip_dealer(...)
  - Quando partida termina        → gif_resultado(...)

Cada função retorna um BytesIO pronto pra:
  discord.File(buf, "anim.gif")
"""

import io
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

# ── Paleta (igual ao render.py) ───────────────────────────────────────────────
BG      = (12,  6, 16)
GOLD    = (210, 170, 80)
GOLD_LT = (240, 210, 130)
CREAM   = (235, 220, 195)
RED_D   = (140,  15, 15)
SHADOW  = (0, 0, 0)

# ── Fonte ────────────────────────────────────────────────────────────────────
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
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default(size=size)


# ── Helpers de carta ──────────────────────────────────────────────────────────

def _draw_frente(draw, img, x, y, rank, suit, cw, ch, scale_x=1.0):
    """Desenha carta de frente com compressão horizontal (efeito 3D flip)."""
    w = max(2, int(cw * scale_x))
    offset = (cw - w) // 2
    rx, ry = x + offset, y

    is_red = suit in ("♥", "♦")
    fc = (180, 15, 15) if is_red else (10, 10, 15)

    draw.rounded_rectangle([rx, ry, rx+w, ry+ch], radius=max(2, int(8*scale_x)),
                            fill=(245, 238, 220), outline=(180, 160, 120), width=1)
    if scale_x > 0.3:
        fr = _font(max(8, int(15*scale_x)))
        fs = _font(max(10, int(28*scale_x)))
        draw.text((rx+max(3,int(7*scale_x)), ry+6), rank, font=fr, fill=fc)
        draw.text((rx+w//2, ry+ch//2), suit, font=fs, fill=fc, anchor="mm")


def _draw_verso(draw, img, x, y, cw, ch, scale_x=1.0):
    """Desenha verso da carta com compressão horizontal."""
    w = max(2, int(cw * scale_x))
    offset = (cw - w) // 2
    rx, ry = x + offset, y

    draw.rounded_rectangle([rx, ry, rx+w, ry+ch], radius=max(2, int(8*scale_x)),
                            fill=(20, 10, 35), outline=GOLD, width=max(1, int(2*scale_x)))
    if scale_x > 0.25:
        cx2, cy2 = rx + w//2, ry + ch//2
        d = max(5, int(18 * scale_x))
        draw.polygon([(cx2,cy2-d),(cx2+d,cy2),(cx2,cy2+d),(cx2-d,cy2)], fill=RED_D)
        d2 = max(2, int(7 * scale_x))
        draw.polygon([(cx2,cy2-d2),(cx2+d2,cy2),(cx2,cy2+d2),(cx2-d2,cy2)], fill=GOLD)


def _save_gif(frames, durations, loop=0) -> io.BytesIO:
    buf = io.BytesIO()
    frames[0].save(
        buf, format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=loop,
        optimize=False,
        disposal=2,
    )
    buf.seek(0)
    return buf


def _clone(base: Image.Image) -> Image.Image:
    """Copia a mesa base convertida para RGB (sem alpha para GIF)."""
    return base.convert("RGB").copy()


# ══════════════════════════════════════════════════════════════════════════════
# 1. CARTA NOVA — desliza de cima pra posição final
# ══════════════════════════════════════════════════════════════════════════════

def gif_carta_nova(mesa_img: Image.Image,
                   x: int, y: int,
                   rank: str, suit: str,
                   cw: int = 85, ch: int = 120,
                   n_frames: int = 10) -> io.BytesIO:
    """
    Gera GIF de carta chegando de cima até a posição (x, y).
    mesa_img: imagem PIL da mesa SEM a carta nova (será reutilizada como fundo).
    """
    frames = []
    durations = []

    start_y = y - 160   # começa acima da tela

    for i in range(n_frames):
        t = i / (n_frames - 1)           # 0.0 → 1.0
        # Ease out: desacelera no final
        ease = 1 - (1 - t) ** 3

        cur_y = int(start_y + (y - start_y) * ease)
        # Leve rotação simulada por escala horizontal
        scale = 0.7 + 0.3 * ease

        frame = _clone(mesa_img)
        draw  = ImageDraw.Draw(frame, "RGBA")
        _draw_frente(draw, frame, x, cur_y, rank, suit, cw, ch, scale_x=scale)
        frames.append(frame)
        durations.append(40 if i < n_frames-1 else 80)

    return _save_gif(frames, durations)


# ══════════════════════════════════════════════════════════════════════════════
# 2. FLIP DEALER — carta vira de costas pra frente (efeito 3D)
# ══════════════════════════════════════════════════════════════════════════════

def gif_flip_dealer(mesa_img: Image.Image,
                    x: int, y: int,
                    rank: str, suit: str,
                    cw: int = 85, ch: int = 120,
                    n_frames: int = 14) -> io.BytesIO:
    """
    Gera GIF de flip 3D: verso → frente.
    Primeira metade: verso encolhe (scale_x 1→0).
    Segunda metade: frente cresce (scale_x 0→1).
    """
    frames = []
    durations = []
    half = n_frames // 2

    for i in range(n_frames):
        frame = _clone(mesa_img)
        draw  = ImageDraw.Draw(frame, "RGBA")

        if i < half:
            # Verso encolhendo
            t = i / half
            scale = 1.0 - t
            _draw_verso(draw, frame, x, y, cw, ch, scale_x=max(0.01, scale))
        else:
            # Frente crescendo
            t = (i - half) / half
            # Ease in-out
            ease = t * t * (3 - 2 * t)
            scale = ease
            _draw_frente(draw, frame, x, y, rank, suit, cw, ch, scale_x=max(0.01, scale))

        frames.append(frame)
        durations.append(35)

    # Último frame parado por mais tempo
    durations[-1] = 600

    return _save_gif(frames, durations)


# ══════════════════════════════════════════════════════════════════════════════
# 3. RESULTADO — texto aparece com fade + pulso
# ══════════════════════════════════════════════════════════════════════════════

def gif_resultado(mesa_img: Image.Image,
                  texto: str,
                  cor: tuple = GOLD_LT,
                  n_frames: int = 16) -> io.BytesIO:
    """
    Gera GIF com texto de resultado pulsando sobre a mesa.
    """
    frames = []
    durations = []
    ow, oh = mesa_img.size

    for i in range(n_frames):
        t = i / (n_frames - 1)

        # Fade in nos primeiros 40%, depois pulsa
        if t < 0.4:
            alpha = t / 0.4
            scale = 0.8 + 0.2 * (t / 0.4)
        else:
            # Pulso suave: oscila entre 1.0 e 1.05
            import math
            pulse = 0.5 + 0.5 * math.sin((t - 0.4) / 0.6 * math.pi * 4)
            alpha = 1.0
            scale = 1.0 + 0.05 * pulse

        frame = _clone(mesa_img)
        draw  = ImageDraw.Draw(frame, "RGBA")

        # Caixa de fundo semitransparente
        box_w = int(400 * scale)
        box_h = int(60 * scale)
        bx = ow//2 - box_w//2
        by = oh//2 - box_h//2

        # Simular transparência misturando com BG
        alpha_int = int(220 * alpha)
        overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay, "RGBA")
        od.rounded_rectangle([bx, by, bx+box_w, by+box_h],
                              radius=8, fill=(8, 4, 16, alpha_int),
                              outline=(*GOLD, int(180*alpha)), width=2)
        frame_rgba = frame.convert("RGBA")
        frame_rgba.alpha_composite(overlay)
        frame = frame_rgba.convert("RGB")
        draw  = ImageDraw.Draw(frame)

        # Texto
        fsize = max(12, int(22 * scale))
        f = _font(fsize)
        r, g, b = cor
        text_col = (int(r*alpha), int(g*alpha), int(b*alpha))
        draw.text((ow//2+1, oh//2+1), texto, font=f, fill=(0,0,0), anchor="mm")
        draw.text((ow//2, oh//2), texto, font=f, fill=text_col, anchor="mm")

        frames.append(frame)
        durations.append(50 if i < n_frames-1 else 1500)

    return _save_gif(frames, durations, loop=1)


# ══════════════════════════════════════════════════════════════════════════════
# 4. DISTRIBUIÇÃO — cartas saindo do baralho uma a uma (intro do jogo)
# ══════════════════════════════════════════════════════════════════════════════

def gif_distribuicao(mesa_img: Image.Image,
                     cartas_jogador: list,
                     cartas_dealer: list,
                     posicoes_j: list,
                     posicoes_d: list,
                     cw: int = 85, ch: int = 120) -> io.BytesIO:
    """
    Gera GIF mostrando cartas sendo distribuídas uma a uma.
    cartas_jogador: [(rank, suit), ...]
    posicoes_j:     [(x, y), ...]  — posição final de cada carta do jogador
    cartas_dealer:  [(rank, suit), ...] — dealer sempre começa virada
    posicoes_d:     [(x, y), ...]
    """
    frames = []
    durations = []

    # Ordem de distribuição: j1, d1, j2, d2 (como no blackjack real)
    ordem = []
    for i in range(max(len(cartas_jogador), len(cartas_dealer))):
        if i < len(cartas_jogador): ordem.append(("j", i))
        if i < len(cartas_dealer):  ordem.append(("d", i))

    deck_x = mesa_img.width  // 2
    deck_y = mesa_img.height // 2

    revealed_j = []
    revealed_d = []

    N_SLIDE = 8  # frames por carta

    for quem, idx in ordem:
        if quem == "j":
            rank, suit = cartas_jogador[idx]
            tx, ty = posicoes_j[idx]
            face_down = False
        else:
            rank, suit = cartas_dealer[idx]
            tx, ty = posicoes_d[idx]
            face_down = (idx == 0)  # primeira carta do dealer fica virada

        for fi in range(N_SLIDE):
            t = fi / (N_SLIDE - 1)
            ease = 1 - (1 - t) ** 2
            cx2 = int(deck_x + (tx - deck_x) * ease)
            cy2 = int(deck_y + (ty - deck_y) * ease)
            scale = 0.5 + 0.5 * ease

            frame = _clone(mesa_img)
            draw  = ImageDraw.Draw(frame, "RGBA")

            # Já reveladas
            for ri, (rr, rs) in enumerate(revealed_j):
                _draw_frente(draw, frame, posicoes_j[ri][0], posicoes_j[ri][1], rr, rs, cw, ch)
            for ri, (rr, rs) in enumerate(revealed_d):
                fd = (ri == 0)
                if fd:
                    _draw_verso(draw, frame, posicoes_d[ri][0], posicoes_d[ri][1], cw, ch)
                else:
                    _draw_frente(draw, frame, posicoes_d[ri][0], posicoes_d[ri][1], rr, rs, cw, ch)

            # Carta em movimento
            if face_down:
                _draw_verso(draw, frame, cx2 - cw//2, cy2 - ch//2, cw, ch, scale_x=scale)
            else:
                _draw_frente(draw, frame, cx2 - cw//2, cy2 - ch//2, rank, suit, cw, ch, scale_x=scale)

            frames.append(frame)
            durations.append(35)

        # Registrar como revelada
        if quem == "j":
            revealed_j.append((rank, suit))
        else:
            revealed_d.append((rank, suit))

    # Frame final parado
    if frames:
        frames.append(frames[-1].copy())
        durations.append(800)

    return _save_gif(frames, durations, loop=0)
