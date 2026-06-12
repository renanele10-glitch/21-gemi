"""
chess/chess_view.py
Interface Discord para xadrez.
O jogador clica em botões de coluna (A-H) e linha (1-8) para selecionar.
Movimentos possíveis ficam destacados no tabuleiro.
Sem digitação de coordenadas.
"""
from __future__ import annotations
import io
import discord
from discord import app_commands
from discord.ext import commands
import chess

from .chess_game import ChessGame, GameState
from .render import render_board, render_board_bytes, TOTAL
from .animator import gif_move, gif_promotion, gif_checkmate

# ── Estado global ─────────────────────────────────────────────────────────
games: dict[int, ChessGame] = {}  # canal_id → ChessGame


# ════════════════════════════════════════════════════════════════════════════
# VIEW PRINCIPAL — grade de botões 8×8 compacta
# ════════════════════════════════════════════════════════════════════════════

FILES = "ABCDEFGH"
RANKS = "87654321"   # de cima pra baixo visualmente


class ChessView(discord.ui.View):
    """
    Layout: 5 linhas de botões.
    Linhas 1-4: seleção via coluna × linha (dois cliques)
    Linha 5: ações (Desistir, Embaralhar visão, Passar)

    Fluxo:
    1. Clique em coluna (botão A-H, primeira linha)
    2. Clique em linha  (botão 1-8, segunda linha) → seleciona peça
    3. Movimentos destacados no tabuleiro
    4. Segundo clique coluna+linha → move
    """

    def __init__(self, canal_id: int):
        super().__init__(timeout=None)
        self.canal_id   = canal_id
        self._sel_file: int | None = None   # 0-7
        self.stage      = "file"            # "file" ou "rank"
        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()

        # Linha 1: Colunas A-H
        for i, f in enumerate(FILES):
            btn = discord.ui.Button(
                label=f,
                style=discord.ButtonStyle.secondary,
                custom_id=f"chess_file_{i}",
                row=0,
            )
            btn.callback = self._make_file_cb(i)
            self.add_item(btn)

        # Linha 2: Linhas 1-8 (desabilitadas até escolher coluna)
        for i, r in enumerate(RANKS):
            btn = discord.ui.Button(
                label=r,
                style=discord.ButtonStyle.secondary,
                custom_id=f"chess_rank_{i}",
                row=1,
                disabled=(self.stage == "file"),
            )
            btn.callback = self._make_rank_cb(i)
            self.add_item(btn)

        # Linha 3: Ações
        desistir = discord.ui.Button(
            label="Desistir", emoji="🏳️",
            style=discord.ButtonStyle.danger,
            custom_id="chess_resign", row=2,
        )
        desistir.callback = self._cb_resign
        self.add_item(desistir)

        cancelar = discord.ui.Button(
            label="Cancelar seleção", emoji="❌",
            style=discord.ButtonStyle.secondary,
            custom_id="chess_cancel", row=2,
        )
        cancelar.callback = self._cb_cancel
        self.add_item(cancelar)

    def _rank_buttons(self, enabled: bool):
        for item in self.children:
            if hasattr(item, "custom_id") and item.custom_id.startswith("chess_rank_"):
                item.disabled = not enabled

    def _make_file_cb(self, file_idx: int):
        async def cb(interaction: discord.Interaction):
            game = games.get(self.canal_id)
            if not game:
                return await interaction.response.send_message("Partida não encontrada.", ephemeral=True)
            if not game.is_turn(interaction.user.id):
                return await interaction.response.send_message("Não é sua vez.", ephemeral=True)

            self._sel_file = file_idx
            self.stage     = "rank"
            self._rank_buttons(True)

            # Destaque coluna no tabuleiro
            file_letter = FILES[file_idx]
            await _update_board(interaction, game, hint=f"Coluna **{file_letter}** — agora escolha a linha:")
        return cb

    def _make_rank_cb(self, rank_display_idx: int):
        """rank_display_idx: 0=topo(8) até 7=base(1)"""
        async def cb(interaction: discord.Interaction):
            game = games.get(self.canal_id)
            if not game:
                return await interaction.response.send_message("Partida não encontrada.", ephemeral=True)
            if not game.is_turn(interaction.user.id):
                return await interaction.response.send_message("Não é sua vez.", ephemeral=True)
            if self._sel_file is None:
                return await interaction.response.send_message("Escolha a coluna primeiro.", ephemeral=True)

            # rank visual → rank chess (0=rank1 ... 7=rank8)
            rank_chess = 7 - rank_display_idx
            square = chess.square(self._sel_file, rank_chess)

            ok, msg = game.select(square, interaction.user.id)

            if ok and game.selected_square is None:
                # Acabou de MOVER
                await _animate_move(interaction, game, square)
            else:
                # Selecionou peça ou erro
                self.stage    = "file"
                self._sel_file = None
                self._rank_buttons(False)
                legal = game.legal_moves_from(game.selected_square) \
                    if game.selected_square is not None else []
                await _update_board(interaction, game,
                                    hint=msg,
                                    legal_moves=legal)

        return cb

    async def _cb_resign(self, interaction: discord.Interaction):
        game = games.get(self.canal_id)
        if not game or not game.is_player(interaction.user.id):
            return await interaction.response.send_message("Você não está nesta partida.", ephemeral=True)
        winner = game.resign(interaction.user.id)
        await interaction.response.defer()
        # Animação xeque-mate reutilizada para dramaticidade
        king_sq = game.board.king(game.board.turn)
        buf = gif_checkmate(game.board, king_sq, flipped=_flipped(game, interaction.user.id))
        await interaction.followup.send(
            f"🏳️ **{interaction.user.display_name}** desistiu. **{winner}** vence!",
            file=discord.File(buf, "xadrez.gif"),
        )
        self.stop()
        del games[self.canal_id]

    async def _cb_cancel(self, interaction: discord.Interaction):
        game = games.get(self.canal_id)
        if not game:
            return await interaction.response.send_message("Partida não encontrada.", ephemeral=True)
        game.selected_square = None
        self.stage    = "file"
        self._sel_file = None
        self._rank_buttons(False)
        await _update_board(interaction, game, hint="Seleção cancelada.")


# ════════════════════════════════════════════════════════════════════════════
# VIEW DE PROMOÇÃO
# ════════════════════════════════════════════════════════════════════════════

class PromotionView(discord.ui.View):
    PIECES = [
        ("♕ Dama",  chess.QUEEN),
        ("♖ Torre", chess.ROOK),
        ("♗ Bispo", chess.BISHOP),
        ("♘ Cavalo",chess.KNIGHT),
    ]

    def __init__(self, canal_id: int, from_sq: int, to_sq: int):
        super().__init__(timeout=60)
        self.canal_id = canal_id
        self.from_sq  = from_sq
        self.to_sq    = to_sq

        for label, pt in self.PIECES:
            btn = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.primary,
                row=0,
            )
            btn.callback = self._make_cb(pt)
            self.add_item(btn)

    def _make_cb(self, piece_type: int):
        async def cb(interaction: discord.Interaction):
            game = games.get(self.canal_id)
            if not game:
                return await interaction.response.send_message("Partida não encontrada.", ephemeral=True)
            if not game.is_turn(interaction.user.id):
                return await interaction.response.send_message("Não é sua vez.", ephemeral=True)

            board_before = game.board.copy()
            ok, san = game.move(self.from_sq, self.to_sq, promotion=piece_type)
            if not ok:
                return await interaction.response.send_message(f"Erro: {san}", ephemeral=True)

            await interaction.response.defer()

            # Anima promoção
            flipped = _flipped(game, interaction.user.id)
            buf = gif_promotion(game.board, self.to_sq, flipped=flipped)
            embed = _make_embed(game, san)
            await interaction.followup.edit_message(
                interaction.message.id,
                embed=embed,
                attachments=[discord.File(buf, "xadrez.gif")],
                view=ChessView(self.canal_id) if game.state == GameState.PLAYING else None,
            )
            self.stop()
        return cb


# ════════════════════════════════════════════════════════════════════════════
# Helpers internos
# ════════════════════════════════════════════════════════════════════════════

def _flipped(game: ChessGame, user_id: int) -> bool:
    return game.color_of(user_id) == chess.BLACK


def _make_embed(game: ChessGame, last_san: str = "") -> discord.Embed:
    status = game.status_text()
    embed  = discord.Embed(title="♟️ Xadrez", color=0x2b1a0e)
    embed.description = (
        f"⬜ **{game.white_name}**  vs  ⬛ **{game.black_name}**\n"
        f"{status}"
    )
    if last_san:
        embed.add_field(name="Último movimento", value=f"`{last_san}`", inline=True)
    if game.move_history:
        moves = "  ".join(
            f"{i//2+1}. {game.move_history[i]}" + (
                f" {game.move_history[i+1]}" if i+1 < len(game.move_history) else "")
            for i in range(0, len(game.move_history[-6:]), 2)
        )
        embed.add_field(name="Últimos lances", value=f"`{moves}`", inline=False)
    embed.set_image(url="attachment://xadrez.gif")
    embed.set_footer(text="Clique coluna → linha para selecionar")
    return embed


async def _update_board(
    interaction: discord.Interaction,
    game: ChessGame,
    hint: str = "",
    legal_moves: list[int] | None = None,
):
    """Atualiza o tabuleiro estático (PNG) na mensagem."""
    await interaction.response.defer()

    flipped   = _flipped(game, interaction.user.id)
    lm_tup    = game.last_move_squares()
    check_sq  = game.king_square

    buf = render_board_bytes(
        game.board,
        selected=game.selected_square,
        legal_moves=legal_moves,
        last_move=lm_tup,
        check_sq=check_sq,
        flipped=flipped,
    )

    embed = _make_embed(game)
    if hint:
        embed.description += f"\n\n💬 {hint}"

    view = ChessView(interaction.channel_id)
    if legal_moves is not None:
        view._rank_buttons(True)
        view.stage    = "rank"
        view._sel_file = None  # já foi consumido

    await interaction.followup.edit_message(
        interaction.message.id,
        embed=embed,
        attachments=[discord.File(buf, "xadrez.png")],
        view=view,
    )


async def _animate_move(
    interaction: discord.Interaction,
    game: ChessGame,
    to_sq: int,
):
    """Gera GIF animado após movimento."""
    await interaction.response.defer()

    # O movimento já foi executado em game.board
    # Precisamos reconstruir o estado antes para animar
    board_after  = game.board
    board_before = board_after.copy()
    # O último movimento está no histórico
    if board_after.move_stack:
        last_move_obj = board_after.peek()
        from_sq = last_move_obj.from_square
        to_sq2  = last_move_obj.to_square

        # Desfaz temporariamente para ter o before
        board_before.pop()
        # (board_before agora tem o estado anterior)
        board_after_real = game.board

        flipped = _flipped(game, interaction.user.id)

        # Verificar xeque-mate primeiro
        if game.state == GameState.CHECKMATE:
            king_sq = board_after_real.king(board_after_real.turn)
            buf = gif_checkmate(board_after_real, king_sq, flipped=flipped)
            embed = _make_embed(game, game.move_history[-1] if game.move_history else "")
            await interaction.followup.edit_message(
                interaction.message.id,
                embed=embed,
                attachments=[discord.File(buf, "xadrez.gif")],
                view=None,
            )
            del games[interaction.channel_id]
            return

        buf = gif_move(
            board_before=board_before,
            board_after=board_after_real,
            from_sq=from_sq,
            to_sq=to_sq2,
            flipped=flipped,
        )
    else:
        # Fallback estático
        buf = render_board_bytes(game.board)

    embed = _make_embed(game, game.move_history[-1] if game.move_history else "")
    view  = ChessView(interaction.channel_id)

    await interaction.followup.edit_message(
        interaction.message.id,
        embed=embed,
        attachments=[discord.File(buf, "xadrez.gif")],
        view=view,
    )


# ════════════════════════════════════════════════════════════════════════════
# Cog Discord
# ════════════════════════════════════════════════════════════════════════════

class XadrezCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="xadrez", description="Iniciar partida de Xadrez")
    async def cmd_xadrez(self, interaction: discord.Interaction):
        cid = interaction.channel_id
        if cid in games and games[cid].state == GameState.PLAYING:
            return await interaction.response.send_message(
                "⚠️ Já há uma partida em andamento neste canal.", ephemeral=True)

        await interaction.response.send_message(
            "♟️ **Xadrez!** Quem joga?",
            view=JoinView(cid),
        )

    @app_commands.command(name="xadrez_status", description="Ver tabuleiro atual")
    async def cmd_status(self, interaction: discord.Interaction):
        cid = interaction.channel_id
        game = games.get(cid)
        if not game:
            return await interaction.response.send_message("Sem partida ativa.", ephemeral=True)
        buf   = render_board_bytes(game.board, last_move=game.last_move_squares(),
                                   check_sq=game.king_square)
        embed = _make_embed(game)
        await interaction.response.send_message(
            embed=embed, file=discord.File(buf, "xadrez.png"), ephemeral=True)


class JoinView(discord.ui.View):
    def __init__(self, canal_id: int):
        super().__init__(timeout=120)
        self.canal_id = canal_id
        self.white: discord.Member | None = None
        self.black: discord.Member | None = None

    @discord.ui.button(label="Jogar com ⬜ Brancas", style=discord.ButtonStyle.secondary, row=0)
    async def join_white(self, interaction: discord.Interaction, btn):
        if self.white:
            return await interaction.response.send_message("Brancas já ocupado.", ephemeral=True)
        self.white = interaction.user
        await interaction.response.send_message(f"✅ {interaction.user.display_name} é **brancas**.", ephemeral=True)
        await self._check_start(interaction)

    @discord.ui.button(label="Jogar com ⬛ Pretas", style=discord.ButtonStyle.primary, row=0)
    async def join_black(self, interaction: discord.Interaction, btn):
        if self.black:
            return await interaction.response.send_message("Pretas já ocupado.", ephemeral=True)
        self.black = interaction.user
        await interaction.response.send_message(f"✅ {interaction.user.display_name} é **pretas**.", ephemeral=True)
        await self._check_start(interaction)

    async def _check_start(self, interaction: discord.Interaction):
        if not (self.white and self.black):
            return
        game = ChessGame(
            white_id=self.white.id,
            black_id=self.black.id,
            white_name=self.white.display_name,
            black_name=self.black.display_name,
        )
        games[self.canal_id] = game

        buf   = render_board_bytes(game.board)
        embed = _make_embed(game)
        view  = ChessView(self.canal_id)

        await interaction.channel.send(
            embed=embed,
            file=discord.File(buf, "xadrez.png"),
            view=view,
        )
        self.stop()


async def setup(bot: commands.Bot):
    await bot.add_cog(XadrezCog(bot))
