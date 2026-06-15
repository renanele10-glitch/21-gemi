"""
cogs/animator.py — Animações GIF para blackjack.
Toca UMA vez e para. Usa as posições reais do render_blackjack.
"""
import io, math
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

GOLD  = (210, 170, 80)
GOLDL = (248, 218, 130)
RED_D = (148,  10, 10)
SHADOW= (0, 0, 0)

def _font(size, bold=True):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if Path(p).exists():
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default(size=size)

def _clone(base): return base.convert("RGB").copy()

def _save_gif(frames, durations):
    """Sem parâmetro loop = toca uma vez e para."""
    buf = io.BytesIO()
    frames[0].save(buf, format="GIF", save_all=True,
                   append_images=frames[1:], duration=durations,
                   optimize=False, disposal=2)
    buf.seek(0)
    return buf

def _draw_verso(draw, x, y, cw, ch, sx=1.0):
    w = max(2, int(cw*sx)); ox=(cw-w)//2; rx,ry=x+ox,y
    draw.rounded_rectangle([rx,ry,rx+w,ry+ch], radius=max(2,int(12*sx)),
                            fill=(16,7,28), outline=GOLD, width=max(1,int(2*sx)))
    if sx > 0.2:
        cx2,cy2=rx+w//2,ry+ch//2
        d=max(5,int(26*sx)); d2=max(2,int(10*sx))
        draw.polygon([(cx2,cy2-d),(cx2+d,cy2),(cx2,cy2+d),(cx2-d,cy2)], fill=RED_D)
        draw.polygon([(cx2,cy2-d2),(cx2+d2,cy2),(cx2,cy2+d2),(cx2-d2,cy2)], fill=GOLD)

def _draw_frente(draw, x, y, rank, suit, cw, ch, sx=1.0):
    w = max(2, int(cw*sx)); ox=(cw-w)//2; rx,ry=x+ox,y
    is_red = suit in ("♥","♦")
    fc = (172,10,10) if is_red else (6,6,10)
    draw.rounded_rectangle([rx,ry,rx+w,ry+ch], radius=max(2,int(12*sx)),
                            fill=(250,243,228), outline=(172,152,112), width=1)
    if sx > 0.2:
        fr = _font(max(8, int(22*sx)))
        fs = _font(max(10, int(62*sx)))
        draw.text((rx+max(4,int(10*sx)), ry+10), rank, font=fr, fill=fc)
        draw.text((rx+w//2, ry+ch//2), suit, font=fs, fill=fc, anchor="mm")


# ══════════════════════════════════════════════════════════════════════════════
# 1. CARTA NOVA — desliza de cima com ease-out
# ══════════════════════════════════════════════════════════════════════════════
def gif_carta_nova(mesa_img, x, y, rank, suit, cw=130, ch=185, n=14):
    frames=[]; durs=[]
    start_y = -ch  # começa fora da tela

    for i in range(n):
        t = i/(n-1)
        ease = 1-(1-t)**3  # ease out cubic
        cur_y = int(start_y + (y-start_y)*ease)
        scale = 0.5 + 0.5*ease

        frame=_clone(mesa_img); draw=ImageDraw.Draw(frame)
        # Sombra em movimento
        if scale > 0.5:
            sw = int(cw*scale)
            draw.ellipse([x+sw//4, cur_y+int(ch*scale)+2,
                          x+sw*3//4, cur_y+int(ch*scale)+8],
                         fill=(0,0,0,60))
        _draw_frente(draw, x, cur_y, rank, suit, cw, ch, sx=scale)
        frames.append(frame)
        durs.append(25 if i<n-1 else 800)

    return _save_gif(frames, durs)


# ══════════════════════════════════════════════════════════════════════════════
# 2. FLIP DEALER — verso → frente (3D squeeze)
# ══════════════════════════════════════════════════════════════════════════════
def gif_flip_dealer(mesa_img, x, y, rank, suit, cw=130, ch=185, n=20):
    frames=[]; durs=[]
    half=n//2

    for i in range(n):
        frame=_clone(mesa_img); draw=ImageDraw.Draw(frame)
        if i < half:
            # Verso encolhendo horizontalmente
            t = i/half
            ease = t*t  # ease in
            sx = 1.0-ease
            _draw_verso(draw, x, y, cw, ch, sx=max(0.01, sx))
            durs.append(30)
        else:
            # Frente crescendo
            t = (i-half)/half
            ease = t*(2-t)  # ease out
            _draw_frente(draw, x, y, rank, suit, cw, ch, sx=max(0.01, ease))
            durs.append(25 if i<n-1 else 1000)
        frames.append(frame)

    return _save_gif(frames, durs)


# ══════════════════════════════════════════════════════════════════════════════
# 3. RESULTADO — texto aparece e pulsa UMA vez
# ══════════════════════════════════════════════════════════════════════════════
def gif_resultado(mesa_img, texto, cor=GOLDL, n=20):
    frames=[]; durs=[]
    ow, oh = mesa_img.size

    for i in range(n):
        t = i/(n-1)
        # Fade in + scale up nos primeiros 40%
        if t < 0.4:
            prog  = t/0.4
            alpha = prog
            scale = 0.7+0.3*prog
        elif t < 0.7:
            # Pulso
            prog  = (t-0.4)/0.3
            pulse = math.sin(prog*math.pi)
            alpha = 1.0
            scale = 1.0+0.08*pulse
        else:
            alpha = 1.0; scale = 1.0

        frame=_clone(mesa_img)
        bw=int(580*scale); bh=int(68*scale)
        bx=ow//2-bw//2;    by=oh//2-bh//2

        ov=Image.new("RGBA",frame.size,(0,0,0,0))
        od=ImageDraw.Draw(ov,"RGBA")
        od.rounded_rectangle([bx,by,bx+bw,by+bh], radius=12,
                              fill=(6,3,14,int(240*alpha)),
                              outline=(*GOLD,int(200*alpha)), width=2)
        fr=frame.convert("RGBA"); fr.alpha_composite(ov); frame=fr.convert("RGB")
        draw=ImageDraw.Draw(frame)
        fs=max(14,int(24*scale)); f=_font(fs)
        r,g,b=cor; tc=(int(r*alpha),int(g*alpha),int(b*alpha))
        draw.text((ow//2+1,oh//2+1),texto,font=f,fill=SHADOW,anchor="mm")
        draw.text((ow//2,  oh//2  ),texto,font=f,fill=tc,    anchor="mm")
        frames.append(frame)
        durs.append(40 if i<n-1 else 2500)

    return _save_gif(frames, durs)


# ══════════════════════════════════════════════════════════════════════════════
# 4. DISTRIBUIÇÃO — cartas saindo do centro
# ══════════════════════════════════════════════════════════════════════════════
def gif_distribuicao(mesa_img, cartas_j, cartas_d, pos_j, pos_d):
    """
    pos_j/pos_d: lista de (x, y, cw, ch)
    """
    frames=[]; durs=[]
    ow,oh=mesa_img.size
    deck_x=ow//2; deck_y=oh//2-30
    N=10

    # Ordem: j0, d0, j1, d1
    ordem=[]
    for i in range(max(len(cartas_j),len(cartas_d))):
        if i<len(cartas_j): ordem.append(("j",i))
        if i<len(cartas_d): ordem.append(("d",i))

    rev_j=[]; rev_d=[]

    for quem,idx in ordem:
        if quem=="j":
            rank,suit = cartas_j[idx]
            tx,ty,cw,ch = pos_j[idx]
            fd=False
        else:
            rank,suit = cartas_d[idx]
            tx,ty,cw,ch = pos_d[idx]
            fd=(idx==0)

        for fi in range(N):
            t=fi/(N-1); ease=1-(1-t)**2
            cx2=int(deck_x+(tx+cw//2-deck_x)*ease - cw//2)
            cy2=int(deck_y+(ty+ch//2-deck_y)*ease - ch//2)
            scale=0.3+0.7*ease

            frame=_clone(mesa_img); draw=ImageDraw.Draw(frame)

            # Já distribuídas
            for ri,(rr,rs) in enumerate(rev_j):
                ax,ay,acw,ach=pos_j[ri]
                _draw_frente(draw,ax,ay,rr,rs,acw,ach)
            for ri,(rr,rs) in enumerate(rev_d):
                ax,ay,acw,ach=pos_d[ri]
                if ri==0: _draw_verso(draw,ax,ay,acw,ach)
                else:     _draw_frente(draw,ax,ay,rr,rs,acw,ach)

            # Em movimento
            if fd: _draw_verso(draw,cx2,cy2,cw,ch,sx=scale)
            else:  _draw_frente(draw,cx2,cy2,rank,suit,cw,ch,sx=scale)

            frames.append(frame)
            durs.append(28)

        if quem=="j": rev_j.append((rank,suit))
        else:         rev_d.append((rank,suit))

    if frames:
        frames.append(frames[-1].copy())
        durs.append(600)

    return _save_gif(frames, durs)
