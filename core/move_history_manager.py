"""Notation and review positions derived from the authoritative chess board."""

from dataclasses import dataclass

import chess


@dataclass(frozen=True)
class MoveRecord:
	ply: int
	number: int
	color: bool
	san: str
	from_square: int
	to_square: int
	fen: str
	captured_symbol: str | None


class MoveHistoryManager:
	def __init__(self):
		self.records = []

	def synchronize(self, board):
		replay = board.root()
		records = []
		for ply, move in enumerate(board.move_stack, start=1):
			color = replay.turn
			number = replay.fullmove_number
			san = replay.san(move)
			captured = replay.piece_at(move.to_square)
			if replay.is_en_passant(move):
				captured = replay.piece_at(move.to_square - 8 if color else move.to_square + 8)
			replay.push(move)
			records.append(MoveRecord(
				ply=ply,
				number=number,
				color=color,
				san=san,
				from_square=move.from_square,
				to_square=move.to_square,
				fen=replay.fen(),
				captured_symbol=captured.symbol() if captured else None,
			))
		self.records = records
		return self.records

	def board_at(self, board, ply):
		if not 0 <= ply <= len(self.records):
			raise ValueError("Requested move is outside the current game history.")
		position = board.root()
		for move in board.move_stack[:ply]:
			position.push(move)
		return position
