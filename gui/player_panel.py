"""Player information and an independently scrollable move-history panel."""

import chess
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel, DirectScrolledFrame


class PlayerPanel:
	def __init__(self, parent, color, review_callback):
		self.color = color
		self.review_callback = review_callback
		side = "White" if color == chess.WHITE else "Black"
		self.frame = DirectFrame(
			parent=parent, frameColor=(.055, .065, .085, .94),
			frameSize=(-.34, .34, -.88, .88), pos=(0, 0, 0),
		)
		self.heading = DirectLabel(
			parent=self.frame, text=f"{side} Player", scale=.043,
			pos=(0, 0, .79), text_fg=(.95, .8, .47, 1),
			frameColor=(0, 0, 0, 0),
		)
		self.name = DirectLabel(
			parent=self.frame, text="", scale=.032,
			pos=(0, 0, .69), text_fg=(.92, .93, .96, 1),
			frameColor=(0, 0, 0, 0),
		)
		self.clock = DirectLabel(
			parent=self.frame, text="10:00", scale=.043,
			pos=(0, 0, .57), text_fg=(.95, .95, .95, 1),
			frameColor=(.13, .15, .19, 1),
		)
		self.captured = DirectLabel(
			parent=self.frame, text="Captured: —", scale=.025,
			pos=(0, 0, .45), text_fg=(.84, .86, .9, 1),
			frameColor=(0, 0, 0, 0),
		)
		self.history_heading = DirectLabel(
			parent=self.frame, text="Move     White       Black", scale=.019,
			pos=(0, 0, .395), text_fg=(.68, .72, .79, 1),
			frameColor=(0, 0, 0, 0),
		)
		self.history = DirectScrolledFrame(
			parent=self.frame, frameSize=(-.31, .31, -.79, .37),
			canvasSize=(-.31, .31, -.1, 0), pos=(0, 0, 0),
			scrollBarWidth=.035, frameColor=(.08, .09, .12, 1),
			borderWidth=(.005, .005), verticalScroll_frameColor=(.16, .18, .22, 1),
			horizontalScroll_frameColor=(.16, .18, .22, 1),
		)
		self._rows = []
		self._row_height = .095

	def set_position(self, x, scale=1):
		self.frame.setPos(x, 0, 0)
		self.frame.setScale(scale)

	def update_player(self, name, player_type, clock, captured):
		self.name["text"] = f"{name}  ·  {player_type}"
		self.clock["text"] = clock
		self.captured["text"] = "Captured: " + (" ".join(captured) if captured else "—")

	def update_history(self, records, current_ply, review_ply=None):
		for row in self._rows:
			row.destroy()
		self._rows.clear()

		total_rows = max((record.number for record in records), default=0)
		canvas_height = max(.1, total_rows * self._row_height)
		self.history["canvasSize"] = (-.31, .31, -canvas_height, 0)
		white_moves = {record.number: record for record in records if record.color == chess.WHITE}
		black_moves = {record.number: record for record in records if record.color == chess.BLACK}
		for index in range(total_rows):
			number = index + 1
			y = -(index + .5) * self._row_height
			white = white_moves.get(number)
			black = black_moves.get(number)
			active_ply = review_ply if review_ply is not None else current_ply
			is_latest = max((record.ply for record in (white, black) if record), default=0) == active_ply
			bg = (.34, .25, .10, 1) if is_latest else (
				(.13, .16, .2, 1) if index % 2 == 0 else (.095, .11, .15, 1)
			)
			active_fg = (.98, .78, .3, 1)
			number_label = DirectLabel(
				parent=self.history.getCanvas(), text=str(number),
				scale=.023, pos=(-.245, 0, y), text_fg=(.64, .68, .74, 1),
				frameColor=(0, 0, 0, 0),
			)
			self._rows.append(number_label)
			self._add_move(white, -.075, y, bg, active_fg, active_ply)
			self._add_move(black, .155, y, bg, active_fg, active_ply)

		self.history.verticalScroll.setValue(1)

	def _add_move(self, record, x, y, background, active_fg, review_ply):
		if record is None:
			return
		is_focused = review_ply == record.ply
		color = active_fg if is_focused else (
			(.95, .91, .78, 1) if record.color == chess.WHITE else (.70, .76, .86, 1)
		)
		button = DirectButton(
			parent=self.history.getCanvas(), text=record.san,
			scale=1, text_scale=.023, pos=(x, 0, y),
			frameColor=(.30, .36, .20, 1) if is_focused else background,
			frameSize=(-.078, .078, -.037, .037),
			command=self.review_callback, extraArgs=[record.ply],
			text_fg=color, relief=1, borderWidth=(.004, .004),
		)
		self._rows.append(button)

	def destroy(self):
		self.frame.destroy()
