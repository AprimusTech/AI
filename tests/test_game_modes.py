import unittest

import chess

from core.game_mode_manager import GameModeManager
from gui.player_configuration import (
	GameConfiguration, GameMode, PlayerConfiguration, PlayerType,
)


class GameModeManagerTests(unittest.TestCase):
	def test_player_vs_computer_assigns_only_selected_human_color(self):
		for human_color in (chess.WHITE, chess.BLACK):
			white_type = PlayerType.HUMAN if human_color else PlayerType.COMPUTER
			black_type = PlayerType.COMPUTER if human_color else PlayerType.HUMAN
			manager = GameModeManager(GameConfiguration(
				mode=GameMode.PLAYER_VS_COMPUTER,
				white=PlayerConfiguration("White", white_type),
				black=PlayerConfiguration("Black", black_type),
				human_color=human_color,
			))
			self.assertTrue(manager.accepts_human_move(human_color))
			self.assertFalse(manager.accepts_human_move(not human_color))
			self.assertTrue(manager.is_computer_turn(not human_color))

	def test_player_vs_player_never_requires_an_engine(self):
		manager = GameModeManager(GameConfiguration())
		self.assertFalse(manager.requires_engine)
		self.assertTrue(manager.accepts_human_move(chess.WHITE))
		self.assertTrue(manager.accepts_human_move(chess.BLACK))

	def test_computer_vs_computer_requires_engines_for_both_sides(self):
		manager = GameModeManager(GameConfiguration(
			mode=GameMode.COMPUTER_VS_COMPUTER,
			white=PlayerConfiguration("CPU 1", PlayerType.COMPUTER, 5),
			black=PlayerConfiguration("CPU 2", PlayerType.COMPUTER, 15),
		))
		self.assertTrue(manager.requires_engine)
		self.assertTrue(manager.is_computer_turn(chess.WHITE))
		self.assertTrue(manager.is_computer_turn(chess.BLACK))
		self.assertFalse(manager.accepts_human_move(chess.WHITE))

	def test_invalid_player_assignment_is_rejected(self):
		with self.assertRaises(ValueError):
			GameModeManager(GameConfiguration(
				mode=GameMode.COMPUTER_VS_COMPUTER,
				white=PlayerConfiguration("CPU", PlayerType.COMPUTER),
				black=PlayerConfiguration("Human", PlayerType.HUMAN),
			))


if __name__ == "__main__":
	unittest.main()
