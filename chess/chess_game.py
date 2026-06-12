"""
chess/chess_game.py
Toda a lógica de xadrez usando python-chess.
Sem dependência de Discord aqui.
"""
from __future__ import annotations
import chess
import chess.svg
from dataclasses import dataclass, field
from enum import Enum


class GameState(Enum):
    WAITING    = "waiting"
    PLAYING    = "playing"
    CHECKMATE  = "checkmate"
    STALEMATE  = "stalemate"
    DRAW       = "draw"
    RESIGNED   = "resigned"


@dataclass
class ChessGame:
    white_id: int
    black_id: int
    white_name: str = "Brancas"
    black_name: str = "Pretas"
    board: chess.Board = field(default_factory=chess.Board)
    state: GameState = GameState.PLAYING
    move_history: list[str] = field(default_factory=list)
    selected_square: int | None = None   # square index 0-63

    # ── Consultas ─────────────────────────────────────────────────────────

    @property
    def turn(self) -> chess.Color:
        return self.board.turn

    @property
    def turn_id(self) -> int:
        return self.white_id if self.turn == chess.WHITE else self.black_id

    @property
    def turn_name(self) -> str:
        return self.white_name if self.turn == chess.WHITE else self.black_name

    def is_player(self, user_id: int) -> bool:
        return user_id in (self.white_id, self.black_id)

    def is_turn(self, user_id: int) -> bool:
        return user_id == self.turn_id

    def color_of(self, user_id: int) -> chess.Color | None:
        if user_id == self.white_id: return chess.WHITE
        if user_id == self.black_id: return chess.BLACK
        return None

    # ── Seleção e movimentos ──────────────────────────────────────────────

    def legal_moves_from(self, square: int) -> list[int]:
        """Squares de destino legais para a peça em `square`."""
        return [
            m.to_square
            for m in self.board.legal_moves
            if m.from_square == square
        ]

    def select(self, square: int, user_id: int) -> tuple[bool, str]:
        """
        Seleciona uma peça. Retorna (ok, mensagem).
        Se já tinha seleção e o destino é legal → move.
        """
        if not self.is_turn(user_id):
            return False, "Não é sua vez."
        if self.state != GameState.PLAYING:
            return False, "Partida encerrada."

        piece = self.board.piece_at(square)
        color = self.color_of(user_id)

        # Já tinha peça selecionada → tentar mover
        if self.selected_square is not None:
            if square in self.legal_moves_from(self.selected_square):
                ok, msg = self.move(self.selected_square, square)
                self.selected_square = None
                return ok, msg
            # Clicou em outra peça própria → reselecionar
            if piece and piece.color == color:
                self.selected_square = square
                return True, f"Peça em {chess.square_name(square).upper()} selecionada."
            self.selected_square = None
            return False, "Movimento inválido."

        # Primeira seleção
        if not piece:
            return False, "Casa vazia."
        if piece.color != color:
            return False, "Essa peça não é sua."
        if not self.legal_moves_from(square):
            return False, "Essa peça não tem movimentos legais."

        self.selected_square = square
        return True, f"Peça em {chess.square_name(square).upper()} selecionada."

    def move(self, from_sq: int, to_sq: int,
             promotion: int = chess.QUEEN) -> tuple[bool, str]:
        """
        Executa movimento. Retorna (ok, mensagem).
        Promoção padrão = Dama.
        """
        move = chess.Move(from_sq, to_sq)
        # Verificar promoção
        piece = self.board.piece_at(from_sq)
        if piece and piece.piece_type == chess.PAWN:
            if (piece.color == chess.WHITE and chess.square_rank(to_sq) == 7) or \
               (piece.color == chess.BLACK and chess.square_rank(to_sq) == 0):
                move = chess.Move(from_sq, to_sq, promotion=promotion)

        if move not in self.board.legal_moves:
            return False, "Movimento ilegal."

        san = self.board.san(move)
        self.board.push(move)
        self.move_history.append(san)
        self._update_state()
        return True, san

    def resign(self, user_id: int) -> str:
        color = self.color_of(user_id)
        self.state = GameState.RESIGNED
        winner = self.white_name if color == chess.BLACK else self.black_name
        return winner

    def _update_state(self):
        if self.board.is_checkmate():
            self.state = GameState.CHECKMATE
        elif self.board.is_stalemate():
            self.state = GameState.STALEMATE
        elif self.board.is_insufficient_material() or \
             self.board.is_seventyfive_moves() or \
             self.board.is_fivefold_repetition():
            self.state = GameState.DRAW

    # ── Info ──────────────────────────────────────────────────────────────

    @property
    def in_check(self) -> bool:
        return self.board.is_check()

    @property
    def king_square(self) -> int | None:
        """Square do rei em xeque."""
        if self.in_check:
            return self.board.king(self.turn)
        return None

    def last_move_squares(self) -> tuple[int, int] | None:
        if self.board.move_stack:
            m = self.board.peek()
            return m.from_square, m.to_square
        return None

    def promotion_needed(self, from_sq: int, to_sq: int) -> bool:
        piece = self.board.piece_at(from_sq)
        if not piece or piece.piece_type != chess.PAWN:
            return False
        return (piece.color == chess.WHITE and chess.square_rank(to_sq) == 7) or \
               (piece.color == chess.BLACK and chess.square_rank(to_sq) == 0)

    def status_text(self) -> str:
        match self.state:
            case GameState.CHECKMATE:
                winner = self.black_name if self.turn == chess.WHITE else self.white_name
                return f"♟️ XEQUE-MATE! {winner} venceu!"
            case GameState.STALEMATE:
                return "🤝 Afogamento — Empate!"
            case GameState.DRAW:
                return "🤝 Empate!"
            case GameState.RESIGNED:
                return "🏳️ Desistência"
            case _:
                check = " ⚠️ XEQUE!" if self.in_check else ""
                return f"{'⬜' if self.turn == chess.WHITE else '⬛'} Vez de {self.turn_name}{check}"
