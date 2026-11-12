"""Interactive pre-game configuration screen."""

import chess
from direct.gui.DirectGui import (
	DirectButton, DirectEntry, DirectFrame, DirectLabel, DirectOptionMenu,
)

from gui.player_configuration import (
	GameConfiguration, GameMode, PlayerConfiguration, PlayerType,
)


class GameSetupScreen:
	def __init__(self, parent, start_callback, cancel_callback):
		self.parent = parent
		self.start_callback = start_callback
		self.cancel_callback = cancel_callback
		self.frame = DirectFrame(
			parent=parent, frameColor=(.035, .045, .065, .98),
			frameSize=(-1.12, 1.12, -.87, .87), pos=(0, 0, 0),
		)
		self._label("New Game Setup", 0, .77, .065, (.95, .8, .47, 1))
		self._label("Select Game Mode", 0, .63, .035)
		self.mode_menu = DirectOptionMenu(
			parent=self.frame, text=GameMode.PLAYER_VS_PLAYER.value,
			items=[mode.value for mode in GameMode],
			initialitem=1, command=self._mode_changed,
			scale=.035, pos=(0, 0, .52), frameColor=(.13, .16, .2, 1),
			text_fg=(1, 1, 1, 1),
		)
		self._label("White Player", -.52, .35, .038, (.92, .92, .92, 1))
		self._label("Black Player", .52, .35, .038, (.92, .92, .92, 1))
		self.white_name = self._entry("Player 1", -.52, .22)
		self.black_name = self._entry("Player 2", .52, .22)
		self._label("Player Type", -.52, .08, .027)
		self._label("Player Type", .52, .08, .027)
		self.white_type = self._menu(["Human", "Computer"], -.52, -.02)
		self.black_type = self._menu(["Human", "Computer"], .52, -.02)
		self.white_skill_label = self._label("Difficulty (1-20)", -.52, -.17, .027)
		self.black_skill_label = self._label("Difficulty (1-20)", .52, -.17, .027)
		skills = [str(level) for level in range(1, 21)]
		self.white_skill = self._menu(skills, -.52, -.27, initial=7)
		self.black_skill = self._menu(skills, .52, -.27, initial=7)
		self.human_color_label = self._label("Human Player Color", -.52, -.40, .027)
		self.human_color = self._menu(
			["White", "Black"], -.52, -.50, command=self._set_human_color,
		)
		self.engine_time_label = self._label("Engine Thinking Time (sec)", .52, -.40, .025)
		self.engine_time = self._menu(
			["0.2", "0.45", "0.75", "1", "2", "5"], .52, -.50, initial=1,
		)
		self._label("Time Control (minutes)", -.52, -.61, .027)
		self._label("Increment (seconds)", .52, -.61, .027)
		self.time_control = self._menu(
			["No clock", "1", "3", "5", "10", "15", "30"], -.52, -.71, initial=4,
		)
		self.increment = self._entry("0", .52, -.71, width=5)
		self.start_button = DirectButton(
			parent=self.frame, text="Start Game", scale=.043,
			pos=(0, 0, -.81), frameColor=(.42, .29, .08, 1),
			text_fg=(1, 1, 1, 1), command=self._start,
		)
		self.cancel_button = DirectButton(
			parent=self.frame, text="Cancel", scale=.033,
			pos=(.68, 0, -.81), frameColor=(.16, .19, .24, 1),
			text_fg=(1, 1, 1, 1), command=self._cancel,
		)
		self.error = self._label("", 0, -.77, .023, (1, .35, .3, 1))
		self._mode_changed(GameMode.PLAYER_VS_PLAYER.value)
		self.hide()

	def _label(self, text, x, y, scale, color=(.82, .85, .9, 1)):
		return DirectLabel(
			parent=self.frame, text=text, scale=scale, pos=(x, 0, y),
			text_fg=color, frameColor=(0, 0, 0, 0),
		)

	def _entry(self, value, x, y, width=14):
		return DirectEntry(
			parent=self.frame, initialText=value, scale=.031, width=width,
			pos=(x - .27, 0, y), numLines=1, focus=0,
			frameColor=(.13, .16, .2, 1), text_fg=(1, 1, 1, 1),
			entryFont=None,
		)

	def _menu(self, items, x, y, initial=0, command=None):
		return DirectOptionMenu(
			parent=self.frame, items=items, initialitem=initial,
			scale=.028, pos=(x, 0, y), frameColor=(.13, .16, .2, 1),
			text_fg=(1, 1, 1, 1), command=command,
		)

	def _mode_changed(self, value):
		mode = GameMode(value)
		is_pvc = mode is GameMode.PLAYER_VS_COMPUTER
		is_cvc = mode is GameMode.COMPUTER_VS_COMPUTER
		self.human_color.show() if is_pvc else self.human_color.hide()
		self.human_color_label.show() if is_pvc else self.human_color_label.hide()
		self.engine_time.show() if is_pvc or is_cvc else self.engine_time.hide()
		self.engine_time_label.show() if is_pvc or is_cvc else self.engine_time_label.hide()
		self.white_type.show()
		self.black_type.show()
		if mode is GameMode.PLAYER_VS_PLAYER:
			self._replace_items(self.white_type, ["Human"], "Human")
			self._replace_items(self.black_type, ["Human"], "Human")
			self.white_name.enterText("Player 1")
			self.black_name.enterText("Player 2")
		elif mode is GameMode.COMPUTER_VS_COMPUTER:
			self._replace_items(self.white_type, ["Computer"], "Computer")
			self._replace_items(self.black_type, ["Computer"], "Computer")
			self.white_name.enterText("Computer 1")
			self.black_name.enterText("Computer 2")
		else:
			self._replace_items(self.white_type, ["Human", "Computer"], "Human")
			self._replace_items(self.black_type, ["Human", "Computer"], "Computer")
			self._set_human_color(self.human_color.get())
		self._update_difficulty_visibility(mode)

	def _replace_items(self, menu, items, selected):
		menu["items"] = items
		menu.setItems()
		menu.set(selected, fCommand=0)

	def _set_human_color(self, value):
		if not hasattr(self, "white_type"):
			return
		human_white = value != "Black"
		self.white_type.set("Human" if human_white else "Computer")
		self.black_type.set("Computer" if human_white else "Human")
		self.white_name.enterText("Human" if human_white else "Computer")
		self.black_name.enterText("Computer" if human_white else "Human")
		if hasattr(self, "mode_menu"):
			self._update_difficulty_visibility(GameMode(self.mode_menu.get()))

	def _update_difficulty_visibility(self, mode):
		if mode is GameMode.COMPUTER_VS_COMPUTER:
			show_white = show_black = True
		elif mode is GameMode.PLAYER_VS_COMPUTER:
			show_white = self.human_color.get() == "Black"
			show_black = not show_white
		else:
			show_white = show_black = False
		self.white_skill.show() if show_white else self.white_skill.hide()
		self.white_skill_label.show() if show_white else self.white_skill_label.hide()
		self.black_skill.show() if show_black else self.black_skill.hide()
		self.black_skill_label.show() if show_black else self.black_skill_label.hide()

	def _start(self):
		mode = GameMode(self.mode_menu.get())
		human_color = self.human_color.get() != "Black"
		if mode is GameMode.PLAYER_VS_COMPUTER:
			self._set_human_color(self.human_color.get())
		try:
			minutes = 0 if self.time_control.get() == "No clock" else int(self.time_control.get())
			increment = int(self.increment.get())
			configuration = GameConfiguration(
				mode=mode,
				white=PlayerConfiguration(
					self.white_name.get().strip() or ("Player 1" if mode is GameMode.PLAYER_VS_PLAYER else "White"),
					PlayerType(self.white_type.get()),
					int(self.white_skill.get()),
				),
				black=PlayerConfiguration(
					self.black_name.get().strip() or ("Player 2" if mode is GameMode.PLAYER_VS_PLAYER else "Black"),
					PlayerType(self.black_type.get()),
					int(self.black_skill.get()),
				),
				human_color=human_color,
				initial_time_seconds=minutes * 60,
				increment_seconds=increment,
				engine_thinking_seconds=float(self.engine_time.get()),
			)
		except (ValueError, TypeError) as exc:
			self.error["text"] = str(exc)
			return
		self.error["text"] = ""
		self.hide()
		self.start_callback(configuration)

	def _cancel(self):
		self.hide()
		self.cancel_callback()

	def show(self):
		self.frame.show()

	def hide(self):
		self.frame.hide()

	def destroy(self):
		self.frame.destroy()
