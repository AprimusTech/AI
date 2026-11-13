"""On-screen player panels, game controls, and responsive layout."""

from direct.gui.DirectGui import DirectButton, DirectLabel, DirectOptionMenu
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode

from gui.move_history_panel import DualMoveHistoryPanels


class GameScreen:
	def __init__(self, app):
		self.app = app
		self.root = app.aspect2d.attachNewNode("game-screen")
		self.panels = DualMoveHistoryPanels(self.root, app.review_position)
		self.title = OnscreenText(
			parent=self.root, text="CHESS  /  3D", pos=(0, .94), scale=.045,
			fg=(.95, .8, .47, 1), align=TextNode.ACenter, mayChange=False,
		)
		self.status = OnscreenText(
			parent=self.root, text="White to move", pos=(0, .84), scale=.031,
			fg=(.9, .92, .96, 1), align=TextNode.ACenter, mayChange=True,
		)
		self.message = OnscreenText(
			parent=self.root, text="", pos=(0, -.85), scale=.032,
			fg=(1, .82, .38, 1), mayChange=True,
		)
		self.controls = []
		buttons = [
			("New Game", app.new_game),
			("Undo", app.undo),
			("Save PGN", app.save_pgn),
			("Resign", app.resign),
			("Start", app.start_computers),
			("Pause", app.pause_computers),
			("Resume", app.resume_computers),
			("Stop", app.stop_computers),
			("Return to Live", app.return_to_live),
			("Reset View", app.reset_camera),
			("Load PGN", app.load_pgn),
		]
		for index, (label, callback) in enumerate(buttons):
			button = DirectButton(
				parent=self.root, text=label, scale=1, text_scale=.026,
				frameColor=(.16, .19, .24, 1), text_fg=(.95, .95, .95, 1),
				command=callback, pos=(0, 0, -.95),
				frameSize=(-.14, .14, -.03, .03),
			)
			self.controls.append(button)
		self.promotion_label = DirectLabel(
			parent=self.root, text="Promotion", scale=.025,
			pos=(-.23, 0, -.77), text_fg=(.8, .84, .9, 1),
			frameColor=(0, 0, 0, 0),
		)
		self.promotion_menu = DirectOptionMenu(
			parent=self.root, text="Queen", scale=.027,
			items=["Queen", "Rook", "Bishop", "Knight"], initialitem=0,
			command=app.set_promotion, pos=(.12, 0, -.77),
			frameColor=(.16, .19, .24, 1), text_fg=(1, 1, 1, 1),
		)
		self.engine_controls = self.controls[4:8]
		self.return_live_button = self.controls[8]
		self.set_mode(app.mode)
		self.set_reviewing(False)

	def set_mode(self, mode):
		for control in self.engine_controls:
			control.show() if mode == "Computer vs Computer" else control.hide()

	def set_reviewing(self, reviewing):
		self.return_live_button.show() if reviewing else self.return_live_button.hide()

	def show(self):
		self.root.show()

	def hide(self):
		self.root.hide()

	def layout(self, aspect):
		self.panels.layout(aspect)
		spacing = min(.3, (2 * aspect - .2) / len(self.controls))
		for index, control in enumerate(self.controls):
			control.setX((index - (len(self.controls) - 1) / 2) * spacing)
			control["frameSize"] = (-spacing * .46, spacing * .46, -.03, .03)
			control["text_scale"] = min(.026, spacing * .08)

	def destroy(self):
		self.panels.destroy()
		self.title.destroy()
		self.status.destroy()
		self.message.destroy()
		self.promotion_label.destroy()
		self.promotion_menu.destroy()
		for control in self.controls:
			control.destroy()
		self.root.removeNode()
