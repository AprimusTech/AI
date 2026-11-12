"""A simple console-based Ludo game for two to four players."""

import math
import random
import tkinter as tk

PLAYER_NAMES = ("Red", "Green", "Yellow", "Blue")
TRACK_SIZE = 52
HOME = 57
START_SQUARES = (0, 13, 26, 39)
SAFE_SQUARES = {0, 8, 13, 21, 26, 34, 39, 47}


def show_popup(message):
	"""Display a result message with a simple Ludo-themed image."""
	try:
		window = tk.Tk()
	except tk.TclError:
		print(message)
		return

	window.title("Ludo")
	window.resizable(False, False)
	canvas = tk.Canvas(window, width=220, height=100, bg="white", highlightthickness=0)
	canvas.pack(padx=16, pady=(16, 8))
	for x, y, color in (
		(55, 50, "#dc2828"), (165, 50, "#28a046"),
		(110, 25, "#ebc319"), (110, 75, "#2d5ad2"),
	):
		canvas.create_oval(x - 18, y - 18, x + 18, y + 18, fill=color, outline="")
	tk.Label(window, text=message, font=("TkDefaultFont", 12)).pack(padx=16, pady=8)
	tk.Button(window, text="OK", command=window.destroy).pack(pady=(0, 16))
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
			self.players = list(PLAYER_NAMES)
			self.pawns = {name: [-1, -1, -1, -1] for name in self.players}
			self.turn = 0
			self.roll = None
			self.choices = []
			self.finished = False

			controls = tk.Frame(self.root, padx=10, pady=8)
			controls.pack(fill="x")
			tk.Label(controls, text="Players:").pack(side="left")
			self.player_count = tk.IntVar(value=4)
			tk.Spinbox(controls, from_=2, to=4, width=3,
					   textvariable=self.player_count).pack(side="left", padx=5)
			self.roll_button = tk.Button(controls, text="Roll dice",
									 command=self.roll_dice)
			self.roll_button.pack(side="left", padx=6)
			self.status = tk.Label(controls, text="Red's turn — click Roll dice")
			self.status.pack(side="left", padx=8)
			self.canvas = tk.Canvas(self.root, width=self.WIDTH, height=self.WIDTH,
								 bg="#faf7ed", highlightthickness=0)
			self.canvas.pack(padx=8, pady=(0, 8))
			self.canvas.bind("<Button-1>", self.select_pawn)
			self.draw_board()
			self.draw_pawns()

		def point(self, square, radius=None):
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
			c.create_rectangle(left - 5, top - 5, right + 5, bottom + 5,
							fill="#fffdf7", outline="#594832", width=3)
			# Four colored home yards and their inset pawn areas.
			for index, (row, col) in enumerate(((1, 1), (1, 9), (9, 9), (9, 1))):
				x1, y1 = self.cell_center(row, col)
				x2, y2 = self.cell_center(row + 4, col + 4)
				c.create_rectangle(x1 - 17, y1 - 17, x2 + 17, y2 + 17,
								fill=self.COLORS[index], outline="#594832", width=2)
				c.create_rectangle(x1 + 10, y1 + 10, x2 - 10, y2 - 10,
								fill="#fffdf7", outline="white", width=3)
			lanes = (
				[(row, 7) for row in range(1, 6)],
				[(7, col) for col in range(13, 8, -1)],
				[(row, 7) for row in range(13, 8, -1)],
				[(7, col) for col in range(1, 6)],
			)
			for color, lane in zip(self.COLORS, lanes):
				for row, col in lane:
					x, y = self.cell_center(row, col)
					c.create_rectangle(x - 15, y - 15, x + 15, y + 15,
									fill=color, outline="#8d806c", width=1)
			for square in range(TRACK_SIZE):
				x, y = self.point(square)
				color = "#fffdf7" if square in SAFE_SQUARES else "#e8dfce"
				c.create_rectangle(x - 15, y - 15, x + 15, y + 15,
								   fill=color, outline="#8d806c", width=1)
				if square in START_SQUARES:
					idx = START_SQUARES.index(square)
					c.create_rectangle(x - 13, y - 13, x + 13, y + 13,
									   fill=self.COLORS[idx], outline="#594832", width=1)
				elif square in SAFE_SQUARES:
					c.create_text(x, y, text="★", fill="#b58a25",
								  font=("TkDefaultFont", 12, "bold"))
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
			c.create_oval(cx - 13, cy - 13, cx + 13, cy + 13,
						   fill="#fffdf7", outline="#594832", width=2)

		def pawn_point(self, player_index, pawn_index, position):
			if position == -1:
				bases = ((3, 3), (3, 11), (11, 11), (11, 3))
				row, col = bases[player_index]
				offsets = ((-20, -20), (20, -20), (-20, 20), (20, 20))
				dx, dy = offsets[pawn_index]
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
					self.canvas.create_oval(x - 10, y - 10, x + 10, y + 10,
										fill=self.COLORS[player_index], outline=outline,
										width=width, tags="pawn")
					self.canvas.create_text(x, y, text=str(pawn_index + 1),
										fill="white", font=("TkDefaultFont", 8, "bold"),
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
				if (event.x - x) ** 2 + (event.y - y) ** 2 <= 22 ** 2:
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
