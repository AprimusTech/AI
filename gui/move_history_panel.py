"""Two identical move-history views with independent scrolling."""

import chess

from gui.player_panel import PlayerPanel


class DualMoveHistoryPanels:
	def __init__(self, parent, review_callback):
		self.left = PlayerPanel(parent, chess.WHITE, review_callback)
		self.right = PlayerPanel(parent, chess.BLACK, review_callback)

	def layout(self, aspect):
		offset = max(.72, aspect - .38)
		self.left.set_position(-offset)
		self.right.set_position(offset)

	def update(self, records, white, black, clocks, captured, current_ply, review_ply=None):
		for panel, color, player in (
			(self.left, chess.WHITE, white),
			(self.right, chess.BLACK, black),
		):
			panel.update_player(
				player.name,
				player.player_type.value,
				clocks[int(color)],
				captured[color],
			)
			panel.update_history(records, current_ply, review_ply)

	def destroy(self):
		self.left.destroy()
		self.right.destroy()
