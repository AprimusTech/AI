"""Rules for assigning human and computer players to chess colors."""

import chess

from gui.player_configuration import GameConfiguration, GameMode, PlayerType


class GameModeManager:
	def __init__(self, configuration=None):
		self.configure(configuration or GameConfiguration())

	def configure(self, configuration):
		if configuration.mode is GameMode.PLAYER_VS_COMPUTER:
			expected_white = PlayerType.HUMAN if configuration.human_color else PlayerType.COMPUTER
			expected_black = PlayerType.COMPUTER if configuration.human_color else PlayerType.HUMAN
			if configuration.white.player_type is not expected_white or configuration.black.player_type is not expected_black:
				raise ValueError("Player-vs-computer mode must assign one human and one computer.")
		elif configuration.mode is GameMode.PLAYER_VS_PLAYER:
			if configuration.white.player_type is not PlayerType.HUMAN or configuration.black.player_type is not PlayerType.HUMAN:
				raise ValueError("Player-vs-player mode requires two human players.")
		elif configuration.mode is GameMode.COMPUTER_VS_COMPUTER:
			if configuration.white.player_type is not PlayerType.COMPUTER or configuration.black.player_type is not PlayerType.COMPUTER:
				raise ValueError("Computer-vs-computer mode requires two computer players.")
		self.configuration = configuration

	def player(self, color):
		return self.configuration.white if color == chess.WHITE else self.configuration.black

	def is_computer_turn(self, color):
		return self.player(color).player_type is PlayerType.COMPUTER

	def accepts_human_move(self, color, *, paused=False, reviewing=False, stopped=False):
		return (
			not paused
			and not reviewing
			and not stopped
			and not self.is_computer_turn(color)
		)

	@property
	def requires_engine(self):
		return any(
			player.player_type is PlayerType.COMPUTER
			for player in (self.configuration.white, self.configuration.black)
		)

	@property
	def is_computer_vs_computer(self):
		return self.configuration.mode is GameMode.COMPUTER_VS_COMPUTER
