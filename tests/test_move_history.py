import unittest

import chess

from core.game_controller import GameController


class MoveHistoryTests(unittest.TestCase):
	def test_san_and_capture_history_are_synchronized_after_each_move(self):
		controller = GameController()
		for uci in ("e2e4", "d7d5", "e4d5"):
			self.assertTrue(controller.play(chess.Move.from_uci(uci)))
		records = controller.history.records
		self.assertEqual([record.san for record in records], ["e4", "d5", "exd5"])
		self.assertEqual(records[-1].captured_symbol, "p")
		self.assertEqual(records[-1].number, 2)

	def test_review_position_does_not_change_live_board_or_move_history(self):
		controller = GameController()
		for uci in ("e2e4", "e7e5", "g1f3", "b8c6"):
			self.assertTrue(controller.play(chess.Move.from_uci(uci)))
		live_fen = controller.board.fen()
		history = tuple(controller.history.records)
		review = controller.position_at(2)
		expected = chess.Board()
		expected.push_uci("e2e4")
		expected.push_uci("e7e5")
		self.assertEqual(review.fen(), expected.fen())
		self.assertEqual(controller.board.fen(), live_fen)
		self.assertEqual(tuple(controller.history.records), history)

	def test_undo_rebuilds_history_and_positions(self):
		controller = GameController()
		for uci in ("e2e4", "e7e5", "g1f3"):
			controller.play(chess.Move.from_uci(uci))
		self.assertTrue(controller.undo())
		self.assertEqual([record.san for record in controller.history.records], ["e4", "e5"])
		self.assertEqual(controller.position_at(2).fen(), controller.board.fen())

	def test_load_rebuilds_authoritative_history(self):
		controller = GameController()
		loaded = chess.Board()
		for uci in ("e2e4", "e7e5", "g1f3"):
			loaded.push_uci(uci)
		controller.load(loaded)
		self.assertIs(controller.board, loaded)
		self.assertEqual([record.san for record in controller.history.records], ["e4", "e5", "Nf3"])

	def test_check_and_checkmate_notation_is_kept(self):
		controller = GameController()
		for uci in ("f2f3", "e7e5", "g2g4", "d8h4"):
			controller.play(chess.Move.from_uci(uci))
		self.assertEqual(controller.history.records[-1].san, "Qh4#")


if __name__ == "__main__":
	unittest.main()
