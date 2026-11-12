"""Player and game setup configuration."""

from dataclasses import dataclass
from enum import Enum


class GameMode(str, Enum):
	PLAYER_VS_COMPUTER = "Player vs Computer"
	PLAYER_VS_PLAYER = "Player vs Player"
	COMPUTER_VS_COMPUTER = "Computer vs Computer"


class PlayerType(str, Enum):
	HUMAN = "Human"
	COMPUTER = "Computer"


@dataclass(frozen=True)
class PlayerConfiguration:
	name: str
	player_type: PlayerType
	difficulty: int = 8


@dataclass(frozen=True)
class GameConfiguration:
	mode: GameMode = GameMode.PLAYER_VS_PLAYER
	white: PlayerConfiguration = PlayerConfiguration("Player 1", PlayerType.HUMAN)
	black: PlayerConfiguration = PlayerConfiguration("Player 2", PlayerType.HUMAN)
	human_color: bool = True
	initial_time_seconds: int = 600
	increment_seconds: int = 0
	engine_thinking_seconds: float = 0.45

	def __post_init__(self):
		if not 1 <= self.white.difficulty <= 20 or not 1 <= self.black.difficulty <= 20:
			raise ValueError("Computer difficulty must be between 1 and 20.")
		if self.initial_time_seconds < 0 or self.increment_seconds < 0:
			raise ValueError("Time control and increment cannot be negative.")
		if self.engine_thinking_seconds <= 0:
			raise ValueError("Engine thinking time must be positive.")
