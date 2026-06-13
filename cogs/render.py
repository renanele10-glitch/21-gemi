"""
cogs/render.py — Layout otimizado pro Discord mobile.
Imagem 720x900 (portrait) pro blackjack — preenche a tela do celular.
"""
import io
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

# ── Dimensões ─────────────────────────────────────────────────────────────────
# Blackjack usa portrait (mais alto) pra aproveitar tela mobile
BJ_W, BJ_H = 720, 900
# Outros jogos landscape
W,  H  = 1024, 620
WP, HP = 620,  860   # xadrez

# ── Paleta ────────────────────────────────────────────────────────────────────
BG     = (8,   3, 12)
FELT   = (16,  7, 24)
GOLD   = (210, 170, 80)
GOLDL  = (248, 218, 130)
CREAM  = (238, 222, 196)
RED_D  = (148,  10, 10)
SHADOW = (0, 0, 0)
GRAY   = (75, 75, 85)

def _font(size, bold=True):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    if not bold:
        candidates = [p.replace("Bold","Regular").replace("-Bold","") for p in candidates]
    for p in candidates:
        if Path(p).exists():
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default(size=size)

def _bytes(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf

def _base_bj():
    """Base portrait pro blackjack."""
    img  = Image.new("RGB", (BJ_W, BJ_H), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rounded_rectangle([10, 10, BJ_W-11, BJ_H-11], radius=22, fill=FELT)
    draw.rounded_rectangle([3,  3,  BJ_W-4,  BJ_H-4],  radius=24, outline=GOLD,        width=3)
    draw.rounded_rectangle([8,  8,  BJ_W-9,  BJ_H-9],  radius=20, outline=(*GOLD,55),  width=1)
    return img, draw

def _base(portrait=False):
    ow, oh = (WP, HP) if portrait else (W, H)
    img  = Image.new("RGB", (ow, oh), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rounded_rectangle([10, 10, ow-11, oh-11], radius=20, fill=FELT)
    draw.rounded_rectangle([3,  3,  ow-4,  oh-4],  radius=22, outline=GOLD,       width=3)
    draw.rounded_rectangle([8,  8,  ow-9,  oh-9],  radius=18, outline=(*GOLD,55), width=1)
    return img, draw, ow, oh

def _label(draw, text, cx, y, color=CREAM, size=16, shadow=True):
    f = _font(size)
    if shadow:
        draw.text((cx+1, y+1), text, font=f, fill=SHADOW, anchor="mm")
    draw.text((cx, y), text, font=f, fill=color, anchor="mm")

def _divider(draw, ow, y):
    mx = 60
    draw.line([(mx, y), (ow-mx, y)], fill=(*GOLD, 45), width=1)

def _card(draw, img, x, y, rank, suit, face_down=False, cw=130, ch=185):
    """Carta grande e legível."""
    r = 12
    if face_down:
        # Sombra
        draw.rounded_rectangle([x+3, y+3, x+cw+3, y+ch+3], radius=r, fill=(0,0,0,80))
        draw.rounded_rectangle([x, y, x+cw, y+ch], radius=r,
                                fill=(16, 7, 28), outline=GOLD, width=2)
        cx2, cy2 = x+cw//2, y+ch//2
        d, d2 = 26, 10
        draw.polygon([(cx2,cy2-d),(cx2+d,cy2),(cx2,cy2+d),(cx2-d,cy2)], fill=RED_D)
        draw.polygon([(cx2,cy2-d2),(cx2+d2,cy2),(cx2,cy2+d2),(cx2-d2,cy2)], fill=GOLD)
        return

    is_red = suit in ("♥","♦")
    fc = (172, 10, 10) if is_red else (6, 6, 10)

    # Sombra
    draw.rounded_rectangle([x+3, y+4, x+cw+3, y+ch+4], radius=r, fill=(0,0,0,100))
    # Corpo
    draw.rounded_rectangle([x, y, x+cw, y+ch], radius=r,
                            fill=(250, 243, 228), outline=(172, 152, 112), width=1)
    # Rank cantos (grande e legível)
    fr = _font(22)
    draw.text((x+10,    y+10),    rank, font=fr, fill=fc)
    draw.text((x+cw-10, y+ch-10), rank, font=fr, fill=fc, anchor="rb")
    # Naipe central
    fs = _font(62)
    draw.text((x+cw//2, y+ch//2), suit, font=fs, fill=fc, anchor="mm")


# ══════════════════════════════════════════════════════════════════════════════
# BLACKJACK — portrait 720×900
# ══════════════════════════════════════════════════════════════════════════════
def render_blackjack(dealer_cards, dealer_val, player_cards, player_val,
                     reveal_dealer=False, result=""):
    img, draw = _base_bj()
    ow, oh = BJ_W, BJ_H

    # Título
    _label(draw, "✦  BLACKJACK 21  ✦", ow//2, 38, GOLDL, 26)
    _divider(draw, ow, 58)

    CW, CH, GAP = 130, 185, 16

    # ── DEALER ──────────────────────────────────────────────────────────────
    dv_str = str(dealer_val) if reveal_dealer else "?"
    _label(draw, f"⚜  DEALER  [ {dv_str} ]", ow//2, 80, GOLD, 17)

    nd = len(dealer_cards)
    # Máx 5 cartas do dealer visíveis
    nd_vis = min(nd, 5)
    tw_d = nd_vis*CW + (nd_vis-1)*GAP
    # Se não cabe, escala
    max_w = ow - 60
    if tw_d > max_w:
        sc = max_w / tw_d
        cw_d = int(CW*sc); ch_d = int(CH*sc); gap_d = int(GAP*sc)
        tw_d = nd_vis*cw_d + (nd_vis-1)*gap_d
    else:
        cw_d, ch_d, gap_d = CW, CH, GAP

    sx_d = ow//2 - tw_d//2
    dy   = 100
    for i in range(nd_vis):
        rank, suit = dealer_cards[i]
        _card(draw, img, sx_d + i*(cw_d+gap_d), dy, rank, suit,
              face_down=(i==0 and not reveal_dealer), cw=cw_d, ch=ch_d)

    # ── SEPARADOR ───────────────────────────────────────────────────────────
    sep_y = dy + ch_d + 22
    _divider(draw, ow, sep_y)

    # ── JOGADOR ─────────────────────────────────────────────────────────────
    _label(draw, f"VOCÊ  [ {player_val} ]", ow//2, sep_y+22, CREAM, 17)

    np2 = len(player_cards)
    tw_j = np2*CW + (np2-1)*GAP
    if tw_j > max_w:
        sc = max_w / tw_j
        cw_j = int(CW*sc); ch_j = int(CH*sc); gap_j = int(GAP*sc)
        tw_j = np2*cw_j + (np2-1)*gap_j
    else:
        cw_j, ch_j, gap_j = CW, CH, GAP

    sx_j = ow//2 - tw_j//2
    py   = sep_y + 42
    for i, (rank, suit) in enumerate(player_cards):
        _card(draw, img, sx_j + i*(cw_j+gap_j), py, rank, suit, cw=cw_j, ch=ch_j)

    # ── RESULTADO ────────────────────────────────────────────────────────────
    if result:
        rw, rh = 560, 60
        ry = py + ch_j + 20
        rx = ow//2 - rw//2
        draw.rounded_rectangle([rx, ry, rx+rw, ry+rh], radius=10,
                                fill=(6,3,14,235), outline=(*GOLD,170), width=2)
        _label(draw, result, ow//2, ry+rh//2, GOLDL, 20)

    return _bytes(img)

# Exporta posições do blackjack pra o animator usar
def bj_posicoes(dealer_cards, player_cards):
    CW, CH, GAP = 130, 185, 16
    max_w = BJ_W - 60

    nd = min(len(dealer_cards), 5)
    tw_d = nd*CW + (nd-1)*GAP
    if tw_d > max_w:
        sc = max_w/tw_d; cw_d=int(CW*sc); ch_d=int(CH*sc); gap_d=int(GAP*sc)
        tw_d = nd*cw_d+(nd-1)*gap_d
    else: cw_d,ch_d,gap_d = CW,CH,GAP
    sx_d = BJ_W//2 - tw_d//2
    pos_d = [(sx_d+i*(cw_d+gap_d), 100, cw_d, ch_d) for i in range(nd)]

    np2 = len(player_cards)
    tw_j = np2*CW+(np2-1)*GAP
    if tw_j > max_w:
        sc = max_w/tw_j; cw_j=int(CW*sc); ch_j=int(CH*sc); gap_j=int(GAP*sc)
        tw_j = np2*cw_j+(np2-1)*gap_j
    else: cw_j,ch_j,gap_j = CW,CH,GAP
    sep_y = 100+ch_d+22
    sx_j = BJ_W//2 - tw_j//2
    pos_j = [(sx_j+i*(cw_j+gap_j), sep_y+42, cw_j, ch_j) for i in range(np2)]

    return pos_d, pos_j, ch_d


# ══════════════════════════════════════════════════════════════════════════════
# POKER
# ══════════════════════════════════════════════════════════════════════════════
def render_poker(community, players, pot, current_name=""):
    img, draw, ow, oh = _base()
    _label(draw, "✦  TEXAS HOLD'EM  ✦", ow//2, 32, GOLDL, 22)
    _label(draw, f"💰  POT: {pot:,} fichas", ow//2, 60, GOLDL, 15)

    CW, CH, GAP = 82, 116, 8
    cc_y = 76
    n = len(community)
    if n:
        tw = n*CW + (n-1)*GAP
        sx = ow//2 - tw//2
        for i, (r, s) in enumerate(community):
            _card(draw, img, sx+i*(CW+GAP), cc_y, r, s, cw=CW, ch=CH)
    else:
        _label(draw, "Aguardando cartas da mesa...", ow//2, cc_y+CH//2, GRAY, 13)

    np2 = len(players)
    slot = ow // max(np2, 1)
    cw2, ch2 = 55, 78
    p_y = cc_y + CH + 28
    SC = {"active":CREAM,"folded":GRAY,"all-in":(255,130,0),"winner":(80,220,80)}

    for i, p in enumerate(players):
        px  = i*slot + slot//2
        col = SC.get(p.get("status","active"), CREAM)
        if p["name"] == current_name:
            draw.rounded_rectangle([px-slot//2+4, p_y-4, px+slot//2-4, p_y+ch2+58],
                                    radius=6, fill=(40,15,5,130), outline=(*GOLD,180), width=2)
        tag = " 🎩" if p.get("dealer") else ""
        _label(draw, p["name"][:10]+tag, px, p_y+8, col, 11)
        _label(draw, f"{p['chips']:,} 🪙", px, p_y+22, CREAM, 10)
        if p.get("bet",0): _label(draw, f"Bet: {p['bet']}", px, p_y+35, GOLD, 10)
        cards = p.get("cards",[])
        tw2 = len(cards)*cw2+(len(cards)-1)*4
        sx2 = px-tw2//2
        for j,(r,s) in enumerate(cards):
            _card(draw,img,sx2+j*(cw2+4),p_y+48,r,s,face_down=(s=="?"),cw=cw2,ch=ch2)
        st = p.get("status","")
        if st in ("folded","all-in","winner"):
            _label(draw,{"folded":"FOLD","all-in":"ALL-IN","winner":"🏆"}[st],px,p_y+ch2+56,col,11)

    return _bytes(img)


# ══════════════════════════════════════════════════════════════════════════════
# TRUCO
# ══════════════════════════════════════════════════════════════════════════════
def render_truco(equipe_nos, equipe_eles, pontos_nos, pontos_eles,
                 vira, mesa_cartas, rodada, max_pontos):
    img, draw, ow, oh = _base()
    _label(draw, f"✦  TRUCO PAULISTA  ✦", ow//2, 32, GOLDL, 22)
    _label(draw, f"NÓS: {pontos_nos}", 90,     52, (80,220,80), 16)
    _label(draw, f"ELES: {pontos_eles}", ow-90, 52, (220,80,80), 16)
    _label(draw, f"Rodada {rodada}/3", ow//2, 52, GOLD, 13)

    CW, CH = 64, 90
    cx, cy = ow//2, oh//2
    _label(draw, "VIRA", cx, cy-CH//2-16, GOLD, 11)
    vr, vs = vira
    _card(draw, img, cx-CW//2, cy-CH//2, vr, vs, cw=CW, ch=CH)

    offs = [(-125,-28),(125,-28),(-125,38),(125,38),(0,-95),(0,85)]
    for i, (r, s, nome) in enumerate(mesa_cartas[:6]):
        ox, oy = offs[i]
        _card(draw, img, cx+ox-CW//2+5, cy+oy-CH//2, r, s, cw=CW-10, ch=CH-14)
        _label(draw, nome[:8], cx+ox+5, cy+oy+CH//2-2, CREAM, 9)

    _draw_equipe(draw, img, equipe_nos,  14,    68, oh-18, left=True)
    _draw_equipe(draw, img, equipe_eles, ow-14, 68, oh-18, left=False)
    return _bytes(img)

def _draw_equipe(draw, img, jogadores, bx, y1, y2, left=True):
    slot = (y2-y1)//max(len(jogadores),1)
    CW, CH, GAP = 46, 64, 3
    for i, p in enumerate(jogadores):
        py = y1+i*slot+slot//2
        tx = bx+(8 if left else -8)
        draw.text((tx, py-CH//2-12), p["name"][:10], font=_font(10),
                  fill=GOLDL, anchor=("lm" if left else "rm"))
        cards = p.get("cards",[])
        n = len(cards)
        sx = bx+(8 if left else -(8+n*(CW+GAP)))
        for j,(r,s) in enumerate(cards):
            _card(draw,img,sx+j*(CW+GAP),py-CH//2,r,s,face_down=p.get("jogou",False) or s=="?",cw=CW,ch=CH)


# ══════════════════════════════════════════════════════════════════════════════
# XADREZ
# ══════════════════════════════════════════════════════════════════════════════
PECAS = {"K":"♔","Q":"♕","R":"♖","B":"♗","N":"♘","P":"♙",
         "k":"♚","q":"♛","r":"♜","b":"♝","n":"♞","p":"♟"}

def render_xadrez(board, nome_brancas, nome_pretas, vez,
                  last_move=None, selected=None, valid_moves=None):
    img, draw, ow, oh = _base(portrait=True)
    _label(draw, "✦  XADREZ  ✦", ow//2, 30, GOLDL, 22)

    margin = 36; b_size = ow-2*margin; cell = b_size//8
    bx, by = margin, 52
    LIGHT=(198,172,132); DARK2=(88,52,22)
    lm = set()
    if last_move: r1,c1,r2,c2=last_move; lm={(r1,c1),(r2,c2)}
    vm = set(valid_moves or [])

    for row in range(8):
        for col in range(8):
            x1=bx+col*cell; y1=by+row*cell
            light=(row+col)%2==0
            draw.rectangle([x1,y1,x1+cell,y1+cell], fill=(LIGHT if light else DARK2))
            if (row,col) in lm:
                ov=Image.new("RGBA",(cell,cell),(205,225,95,160) if light else (158,190,48,160))
                img.paste(ov,(x1,y1),ov); draw=ImageDraw.Draw(img,"RGBA")
            if selected and (row,col)==selected:
                ov=Image.new("RGBA",(cell,cell),(95,172,255,175))
                img.paste(ov,(x1,y1),ov); draw=ImageDraw.Draw(img,"RGBA")
            if (row,col) in vm:
                ov=Image.new("RGBA",(cell,cell),(65,200,65,130))
                img.paste(ov,(x1,y1),ov); draw=ImageDraw.Draw(img,"RGBA")
            p=board[row][col]
            if p and p!=".":
                sym=PECAS.get(p,p); white=p.isupper(); fp=_font(cell-10)
                cx2=x1+cell//2; cy2=y1+cell//2
                draw.text((cx2+1,cy2+2),sym,font=fp,fill=(0,0,0,180),anchor="mm")
                draw.text((cx2,cy2),sym,font=fp,fill=(242,235,218) if white else (10,5,16),anchor="mm")

    fc=_font(11,bold=False)
    for i in range(8):
        draw.text((bx+i*cell+cell//2, by+b_size+14), chr(65+i), font=fc, fill=GOLD, anchor="mm")
        draw.text((bx-14, by+i*cell+cell//2), str(8-i), font=fc, fill=GOLD, anchor="mm")

    iy=by+b_size+34; turno=nome_brancas if vez=="white" else nome_pretas
    _label(draw, f"{'⬜' if vez=='white' else '⬛'}  Vez de: {turno}", ow//2, iy, GOLDL, 14)
    _label(draw, f"⬜ {nome_brancas}   vs   ⬛ {nome_pretas}", ow//2, iy+22, CREAM, 11)
    return _bytes(img)
