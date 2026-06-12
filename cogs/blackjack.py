# ... (mantenha os imports, lógica de jogo, botões, etc.)

    def _render(self, animated=False, anim_type=None, new_card=None, reveal_pos=None):
        from PIL import Image
        g = self.game
        pv = _calcular(g.mao)
        dv = _calcular(g.dealer)

        base_buf = render_blackjack(g.dealer, dv, g.mao, pv,
                                    reveal_dealer=g.fim, result="")
        base_img = Image.open(base_buf).convert("RGB")

        # Estas constantes DEVEM ser idênticas ao render.py para a animação bater!
        OW = 800
        CW, CH, GAP = 130, 185, 16
        DY = 110
        PY = 360

        if not animated or anim_type is None:
            buf = render_blackjack(g.dealer, dv, g.mao, pv,
                                   reveal_dealer=g.fim, result=g.result)
            return discord.File(buf, "blackjack.png")

        elif anim_type == "hit" and new_card:
            rank, suit = new_card
            n = len(g.mao)
            
            cw_anim, ch_anim, gap_anim = CW, CH, GAP
            tw = n * CW + (n-1) * GAP
            if tw > OW - 60:
                scale = (OW - 60) / tw
                cw_anim = int(CW * scale)
                ch_anim = int(CH * scale)
                gap_anim = int(GAP * scale)
                tw = n * cw_anim + (n-1) * gap_anim
                
            sx = OW//2 - tw//2
            card_x = sx + (n-1) * (cw_anim + gap_anim)
            
            buf = gif_carta_nova(base_img, card_x, PY, rank, suit, cw_anim, ch_anim)
            return discord.File(buf, "blackjack.gif")

        elif anim_type == "flip" and reveal_pos:
            nd = len(g.dealer)
            tw = nd * CW + (nd-1) * GAP
            sx = OW//2 - tw//2
            rank, suit = g.dealer[0]
            buf = gif_flip_dealer(base_img, sx, DY, rank, suit, CW, CH)
            return discord.File(buf, "blackjack.gif")

        elif anim_type == "deal":
            nd = len(g.dealer)
            nj = len(g.mao)
            tw_d = nd * CW + (nd-1) * GAP
            tw_j = nj * CW + (nj-1) * GAP
            sx_d = OW//2 - tw_d//2
            sx_j = OW//2 - tw_j//2
            
            pos_d = [(sx_d + i*(CW+GAP), DY) for i in range(nd)]
            pos_j = [(sx_j + i*(CW+GAP), PY) for i in range(nj)]
            
            buf = gif_distribuicao(base_img, g.mao, g.dealer, pos_j, pos_d, CW, CH)
            return discord.File(buf, "blackjack.gif")

        elif anim_type == "result":
            res_col = (80,220,80) if "venceu" in g.result or "BLACKJACK" in g.result else (220,80,80)
            if "Empate" in g.result or "empate" in g.result:
                res_col = (200,200,80)
            buf = gif_resultado(base_img, g.result, cor=res_col)
            return discord.File(buf, "blackjack.gif")

        buf = render_blackjack(g.dealer, dv, g.mao, pv, reveal_dealer=g.fim, result=g.result)
        return discord.File(buf, "blackjack.png")

# ... (restante do código igual)
