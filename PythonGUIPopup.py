"""A simple console-based Ludo game for two to four players."""

import random
import tkinter as tk

PLAYER_NAMES = ("Red", "Green", "Yellow", "Blue")
TRACK_SIZE = 52
HOME = 57
START_SQUARES = (0, 13, 26, 39)
SAFE_SQUARES = {0, 8, 13, 21, 26, 34, 39, 47}


def screen_fit_scale(root, base_width, base_height, vertical_reserve=100, maximum=1.8):
	"""Choose a readable scale that keeps a window inside the current screen."""
	available_width = max(1, root.winfo_screenwidth() - 32)
	available_height = max(1, root.winfo_screenheight() - vertical_reserve)
	return max(
		0.4,
		min(maximum, available_width / base_width, available_height / base_height),
	)


def show_popup(message):
	"""Display a result message with a simple Ludo-themed image."""
	try:
		window = tk.Tk()
	except tk.TclError:
		print(message)
		return

	window.title("Ludo")
	window.resizable(False, False)
	scale = screen_fit_scale(window, 280, 190, vertical_reserve=80, maximum=1.8)
	size = lambda value: max(1, round(value * scale))
	canvas = tk.Canvas(
		window, width=size(220), height=size(100),
		bg="white", highlightthickness=0,
	)
	canvas.pack(padx=16, pady=(16, 8))
	for x, y, color in (
		(55, 50, "#dc2828"), (165, 50, "#28a046"),
		(110, 25, "#ebc319"), (110, 75, "#2d5ad2"),
	):
		x, y, radius = size(x), size(y), size(18)
		canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=color, outline="")
	tk.Label(window, text=message, font=("TkDefaultFont", size(12))).pack(padx=16, pady=8)
	tk.Button(window, text="OK", command=window.destroy, font=("TkDefaultFont", size(10))).pack(pady=(0, 16))
	window.mainloop()


def play_ludo():
	class LudoGUI:
		COLORS = ("#dc2828", "#28a046", "#ebc319", "#2d5ad2")
		WIDTH = 620
		CENTER = WIDTH / 2
		CELL = 34
		BOARD_ORIGIN = 55
		TRACK = (
			[(0, col) for col in range(1, 14)]
			+ [(row, 14) for row in range(1, 14)]
			+ [(14, col) for col in range(13, 0, -1)]
			+ [(row, 0) for row in range(13, 0, -1)]
		)

		def __init__(self):
			self.root = tk.Tk()
			self.root.title("Ludo")
			self.root.resizable(False, False)
			self.scale = screen_fit_scale(
				self.root, self.WIDTH, self.WIDTH, vertical_reserve=110,
			)
			self.WIDTH = round(type(self).WIDTH * self.scale)
			self.CENTER = self.WIDTH / 2
			self.CELL = round(type(self).CELL * self.scale)
			self.BOARD_ORIGIN = round(type(self).BOARD_ORIGIN * self.scale)
			window_width = self.WIDTH + 32
			window_height = self.WIDTH + 96
			screen_width = self.root.winfo_screenwidth()
			screen_height = self.root.winfo_screenheight()
			x = max(0, (screen_width - window_width) // 2)
			y = max(0, (screen_height - window_height) // 2)
			self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
			self.players = list(PLAYER_NAMES)
			self.pawns = {name: [-1, -1, -1, -1] for name in self.players}
			self.turn = 0
			self.roll = None
			self.choices = []
			self.finished = False

			controls = tk.Frame(
				self.root, padx=self.px(10), pady=self.px(8),
			)
			controls.pack(fill="x")
			tk.Label(
				controls, text="Players:",
				font=("TkDefaultFont", self.px(10)),
			).pack(side="left")
			self.player_count = tk.IntVar(value=4)
			tk.Spinbox(
				controls, from_=2, to=4, width=3,
				textvariable=self.player_count, font=("TkDefaultFont", self.px(10)),
			).pack(side="left", padx=self.px(5))
			self.roll_button = tk.Button(
				controls, text="Roll dice", command=self.roll_dice,
				font=("TkDefaultFont", self.px(10)),
			)
			self.roll_button.pack(side="left", padx=self.px(6))
			self.status = tk.Label(
				controls, text="Red's turn — click Roll dice",
				font=("TkDefaultFont", self.px(10)),
			)
			self.status.pack(side="left", padx=self.px(8))
			self.canvas = tk.Canvas(self.root, width=self.WIDTH, height=self.WIDTH,
								 bg="#faf7ed", highlightthickness=0)
			self.canvas.pack(padx=self.px(8), pady=(0, self.px(8)))
			self.canvas.bind("<Button-1>", self.select_pawn)
			self.draw_board()
			self.draw_pawns()

		def px(self, value):
			return max(1, round(value * self.scale))

		def point(self, square):
			row, col = self.TRACK[square % TRACK_SIZE]
			return self.cell_center(row, col)

		def cell_center(self, row, col):
			return (self.BOARD_ORIGIN + (col + 0.5) * self.CELL,
				self.BOARD_ORIGIN + (row + 0.5) * self.CELL)

		def draw_board(self):
			c = self.canvas
			left = top = self.BOARD_ORIGIN
			right = left + 15 * self.CELL
			bottom = top + 15 * self.CELL
			c.create_rectangle(left - self.px(5), top - self.px(5),
							right + self.px(5), bottom + self.px(5),
							fill="#fffdf7", outline="#594832", width=self.px(3))
			# Four colored home yards and their inset pawn areas.
			for index, (row, col) in enumerate(((1, 1), (1, 9), (9, 9), (9, 1))):
				x1, y1 = self.cell_center(row, col)
				x2, y2 = self.cell_center(row + 4, col + 4)
				inset, outer = self.px(10), self.px(17)
				c.create_rectangle(x1 - outer, y1 - outer, x2 + outer, y2 + outer,
								fill=self.COLORS[index], outline="#594832", width=self.px(2))
				c.create_rectangle(x1 + inset, y1 + inset, x2 - inset, y2 - inset,
								fill="#fffdf7", outline="white", width=self.px(3))
			lanes = (
				[(row, 7) for row in range(1, 6)],
				[(7, col) for col in range(13, 8, -1)],
				[(row, 7) for row in range(13, 8, -1)],
				[(7, col) for col in range(1, 6)],
			)
			for color, lane in zip(self.COLORS, lanes):
				for row, col in lane:
					x, y = self.cell_center(row, col)
					half_cell = self.px(15)
					c.create_rectangle(x - half_cell, y - half_cell, x + half_cell, y + half_cell,
									fill=color, outline="#8d806c", width=self.px(1))
			for square in range(TRACK_SIZE):
				x, y = self.point(square)
				color = "#fffdf7" if square in SAFE_SQUARES else "#e8dfce"
				half_cell = self.px(15)
				c.create_rectangle(x - half_cell, y - half_cell, x + half_cell, y + half_cell,
								   fill=color, outline="#8d806c", width=self.px(1))
				if square in START_SQUARES:
					idx = START_SQUARES.index(square)
					start_inset = self.px(13)
					c.create_rectangle(x - start_inset, y - start_inset,
									   x + start_inset, y + start_inset,
									   fill=self.COLORS[idx], outline="#594832", width=self.px(1))
				elif square in SAFE_SQUARES:
					c.create_text(x, y, text="★", fill="#b58a25",
								  font=("TkDefaultFont", self.px(12), "bold"))
			# Decorative four-color home finish.
			cx, cy = self.CENTER, self.CENTER
			h = 2.5 * self.CELL
			c.create_polygon(cx, cy, cx - h, cy - h, cx, cy - h,
							 fill=self.COLORS[0], outline="white", width=2)
			c.create_polygon(cx, cy, cx, cy - h, cx + h, cy - h,
							 fill=self.COLORS[1], outline="white", width=2)
			c.create_polygon(cx, cy, cx + h, cy + h, cx, cy + h,
							 fill=self.COLORS[2], outline="white", width=2)
			c.create_polygon(cx, cy, cx, cy + h, cx - h, cy + h,
							 fill=self.COLORS[3], outline="white", width=2)
			center_radius = self.px(13)
			c.create_oval(cx - center_radius, cy - center_radius,
						   cx + center_radius, cy + center_radius,
						   fill="#fffdf7", outline="#594832", width=self.px(2))

		def pawn_point(self, player_index, pawn_index, position):
			if position == -1:
				bases = ((3, 3), (3, 11), (11, 11), (11, 3))
				row, col = bases[player_index]
				offsets = ((-20, -20), (20, -20), (-20, 20), (20, 20))
				dx, dy = (self.px(offset) for offset in offsets[pawn_index])
				x, y = self.cell_center(row, col)
				return x + dx, y + dy
			if position < TRACK_SIZE:
				return self.point((START_SQUARES[player_index] + position) % TRACK_SIZE)
			if position == HOME:
				return self.CENTER, self.CENTER
			lanes = (
				[(row, 7) for row in range(1, 6)],
				[(7, col) for col in range(13, 8, -1)],
				[(row, 7) for row in range(13, 8, -1)],
				[(7, col) for col in range(1, 6)],
			)
			return self.cell_center(*lanes[player_index][position - TRACK_SIZE])

		def draw_pawns(self):
			self.canvas.delete("pawn")
			for player_index, name in enumerate(self.players):
				for pawn_index, position in enumerate(self.pawns[name]):
					x, y = self.pawn_point(player_index, pawn_index, position)
					outline = "white" if (player_index == self.turn and pawn_index in self.choices) else "#30291f"
					width = 4 if pawn_index in self.choices and player_index == self.turn else 1
					radius = self.px(10)
					self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius,
										fill=self.COLORS[player_index], outline=outline,
										width=self.px(width), tags="pawn")
					self.canvas.create_text(x, y, text=str(pawn_index + 1),
										fill="white", font=("TkDefaultFont", self.px(8), "bold"),
										tags="pawn")

		def roll_dice(self):
			if self.finished or self.roll is not None:
				return
			name = self.players[self.turn]
			self.roll = random.randint(1, 6)
			self.choices = [
				index for index, position in enumerate(self.pawns[name])
				if (position == -1 and self.roll == 6)
				or (0 <= position < HOME and position + self.roll <= HOME)
			]
			self.roll_button.config(state="disabled")
			if not self.choices:
				self.status.config(text=f"{name} rolled {self.roll}; no legal move")
				self.root.after(900, self.next_turn)
			else:
				self.status.config(text=f"{name} rolled {self.roll} — click a highlighted pawn")
			self.draw_pawns()

		def select_pawn(self, event):
			if self.roll is None or self.finished:
				return
			name = self.players[self.turn]
			for pawn_index in self.choices:
				x, y = self.pawn_point(self.turn, pawn_index, self.pawns[name][pawn_index])
				if (event.x - x) ** 2 + (event.y - y) ** 2 <= self.px(22) ** 2:
					self.move_pawn(pawn_index)
					return

		def move_pawn(self, pawn_index):
			name = self.players[self.turn]
			position = self.pawns[name][pawn_index]
			self.pawns[name][pawn_index] = 0 if position == -1 else position + self.roll
			position = self.pawns[name][pawn_index]
			if position < TRACK_SIZE:
				square = (START_SQUARES[self.turn] + position) % TRACK_SIZE
				if square not in SAFE_SQUARES:
					for opponent_index, opponent in enumerate(self.players):
						if opponent_index == self.turn:
							continue
						for other_pawn, other_position in enumerate(self.pawns[opponent]):
							if 0 <= other_position < TRACK_SIZE and (
									START_SQUARES[opponent_index] + other_position
							) % TRACK_SIZE == square:
								self.pawns[opponent][other_pawn] = -1
			if all(pawn == HOME for pawn in self.pawns[name]):
				self.finished = True
				self.choices = []
				self.draw_pawns()
				self.status.config(text=f"{name} wins!")
				self.roll_button.config(state="disabled")
				return
			self.next_turn()

		def next_turn(self):
			self.turn = (self.turn + 1) % len(self.players)
			self.roll = None
			self.choices = []
			self.status.config(text=f"{self.players[self.turn]}'s turn — click Roll dice")
			self.roll_button.config(state="normal")
			self.draw_pawns()

	game = LudoGUI()
	game.root.mainloop()


if __name__ == "__main__":
	try:
		play_ludo()
	except (ValueError, EOFError) as error:
		print(f"Game ended: {error}")
		show_popup(f"Game ended: {error}")
