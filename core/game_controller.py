"""Centralized legal move and move-history controller."""

import chess

from core.move_history_manager import MoveHistoryManager


class GameController:
	def __init__(self, board=None):
		self.board = board or chess.Board()
		self.history = MoveHistoryManager()
		self.history.synchronize(self.board)

	def play(self, move):
		if move not in self.board.legal_moves:
			return False
		self.board.push(move)
		self.history.synchronize(self.board)
		return True

	def undo(self):
		if not self.board.move_stack:
			return False
		self.board.pop()
		self.history.synchronize(self.board)
		return True

	def reset(self):
		self.board.reset()
		self.history.synchronize(self.board)

	def position_at(self, ply):
		return self.history.board_at(self.board, ply)
