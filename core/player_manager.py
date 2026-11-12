"""Player names, types, and captured-piece summaries."""

import chess

from core.game_mode_manager import GameModeManager
from gui.player_configuration import GameConfiguration


class PlayerManager:
	def __init__(self, configuration=None):
		self.mode_manager = GameModeManager(configuration or GameConfiguration())

	def configure(self, configuration):
		self.mode_manager.configure(configuration)

	def player(self, color):
		return self.mode_manager.player(color)

	def captured_pieces(self, board, color):
		initial = chess.Board()
		expected = initial.piece_count(color)
		remaining = sum(1 for piece in board.piece_map().values() if piece.color == color)
		captured = max(0, expected - remaining)
		return captured
