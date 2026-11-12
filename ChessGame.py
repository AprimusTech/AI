"""Single-file 3D chess game.

Install: py -m pip install panda3d python-chess
Optional computer opponent: install Stockfish and set STOCKFISH_PATH to its executable.
Run: py ChessGame.py

This self-contained build uses Panda3D's DirectGUI rather than PySide6 so that the
entire application can live in the one source file available to this project.
python-chess is the sole authority for legal moves and game results.
"""

from __future__ import annotations

import os
import math
import sqlite3
from queue import Empty
from datetime import datetime

try:
	import chess  # pyright: ignore[reportMissingImports]
	import chess.pgn  # pyright: ignore[reportMissingImports]
except ImportError as exc:
	raise SystemExit("Missing dependency. Install with: py -m pip install panda3d python-chess") from exc

try:
	from direct.showbase.ShowBase import ShowBase  # pyright: ignore[reportMissingImports]
	from panda3d.core import (
		AmbientLight, DirectionalLight, Geom, GeomNode, GeomTriangles,
		GeomVertexData, GeomVertexFormat, GeomVertexWriter, Point2, Point3,
		Vec4,
	)
except ImportError as exc:
	raise SystemExit("Missing Panda3D. Install with: py -m pip install panda3d") from exc

from core.game_controller import GameController
from core.game_mode_manager import GameModeManager
from core.player_manager import PlayerManager
from engine.engine_scheduler import EngineScheduler
from engine.stockfish_manager import StockfishManager
from gui.game_screen import GameScreen
from gui.game_setup_screen import GameSetupScreen
from gui.player_configuration import GameConfiguration, GameMode


SQ = 1.2
LIGHT = (0.78, 0.67, 0.48, 1)
DARK = (0.22, 0.13, 0.09, 1)
GOLD = (0.92, 0.68, 0.18, 1)
PIECES = {chess.PAWN: "Pawn", chess.KNIGHT: "Knight", chess.BISHOP: "Bishop",
		  chess.ROOK: "Rook", chess.QUEEN: "Queen", chess.KING: "King"}
UNICODE = {"P": "♙", "N": "♘", "B": "♗", "R": "♖", "Q": "♕", "K": "♔",
		   "p": "♟", "n": "♞", "b": "♝", "r": "♜", "q": "♛", "k": "♚"}


def mesh_from_profile(parent, name, profile, color, sides=24):
	"""Create a smooth rotationally symmetric piece component from a profile."""
	fmt = GeomVertexFormat.getV3n3()
	data = GeomVertexData(name, fmt, Geom.UHStatic)
	vertices, normals = GeomVertexWriter(data, "vertex"), GeomVertexWriter(data, "normal")
	tris = GeomTriangles(Geom.UHStatic)
	for z, radius in profile:
		for i in range(sides):
			a = 2 * math.pi * i / sides
			vertices.addData3(radius * math.cos(a), radius * math.sin(a), z)
			normals.addData3(math.cos(a), math.sin(a), 0.25)
	for row in range(len(profile) - 1):
		for col in range(sides):
			a = row * sides + col
			b = row * sides + (col + 1) % sides
			c, d = (row + 1) * sides + col, (row + 1) * sides + (col + 1) % sides
			tris.addVertices(a, b, d)
			tris.addVertices(a, d, c)
	tris.closePrimitive()
	geom = Geom(data)
	geom.addPrimitive(tris)
	node = GeomNode(name)
	node.addGeom(geom)
	np = parent.attachNewNode(node)
	np.setColor(*color)
	np.setTwoSided(True)
	np.setShaderAuto()
	return np


def make_box(parent, name, x, y, z, sx, sy, sz, color):
	"""A beveled-looking slab made from a small stack of cuboids."""
	root = parent.attachNewNode(name)
	corners = [(-sx/2,-sy/2,-sz/2),(sx/2,-sy/2,-sz/2),(sx/2,sy/2,-sz/2),(-sx/2,sy/2,-sz/2),
			   (-sx/2,-sy/2,sz/2),(sx/2,-sy/2,sz/2),(sx/2,sy/2,sz/2),(-sx/2,sy/2,sz/2)]
	faces = [(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]
	fmt = GeomVertexFormat.getV3n3()
	vd = GeomVertexData(name, fmt, Geom.UHStatic)
	vw, nw = GeomVertexWriter(vd, "vertex"), GeomVertexWriter(vd, "normal")
	prim = GeomTriangles(Geom.UHStatic)
	for face in faces:
		start = vw.getWriteRow()
		for idx in face:
			vw.addData3(*corners[idx]); nw.addData3(0, 0, 1)
		prim.addVertices(start, start+1, start+2); prim.addVertices(start, start+2, start+3)
	prim.closePrimitive()
	geom = Geom(vd); geom.addPrimitive(prim)
	gn = GeomNode(name); gn.addGeom(geom)
	obj = root.attachNewNode(gn); obj.setColor(*color); obj.setTwoSided(True)
	root.setPos(x, y, z)
	return root


class ChessGame3D(ShowBase):
	def __init__(self):
		super().__init__()
		self.disableMouse()
		self.setBackgroundColor(0.055, 0.065, 0.085, 1)
		self.controller = GameController()
		self.board = self.controller.board
		self.selected = None
		self.legal_targets = set()
		self.configuration = GameConfiguration()
		self.mode_manager = GameModeManager(self.configuration)
		self.player_manager = PlayerManager(self.configuration)
		self.mode = self.configuration.mode.value
		self.human_color = chess.WHITE
		self.engine_path = os.environ.get("STOCKFISH_PATH", "stockfish")
		self.stockfish = StockfishManager(self.engine_path)
		self.engine_scheduler = EngineScheduler(self.stockfish)
		self.clocks = [600.0, 600.0]
		self.increment = self.configuration.increment_seconds
		self.last_tick = datetime.now().timestamp()
		self.last_panel_tick = 0
		self.review_ply = None
		self.review_board = None
		self.game_finished = False
		self.time_expired = False
		self.promotion_type = chess.QUEEN
		self.square_nodes = {}
		self.piece_nodes = {}
		self.highlight_nodes = []
		self._setup_scene()
		self._setup_ui()
		self._setup_database()
		self.accept("mouse1", self.on_click)
		self.accept("wheel_up", lambda: self.zoom(-1.0))
		self.accept("wheel_down", lambda: self.zoom(1.0))
		self.accept("arrow_left", lambda: self.orbit(-5))
		self.accept("arrow_right", lambda: self.orbit(5))
		self.accept("escape", self.clear_selection)
		self.accept("window-event", self._window_resized)
		self.taskMgr.add(self.update, "game-update")
		self.refresh_board()
		self.refresh_player_panels()

	def _setup_scene(self):
		self.camera_distance, self.camera_angle = 23.0, 45.0
		self._place_camera()
		ambient = AmbientLight("ambient"); ambient.setColor(Vec4(.42,.42,.48,1))
		self.render.setLight(self.render.attachNewNode(ambient))
		sun = DirectionalLight("key-light"); sun.setColor(Vec4(1,.92,.78,1))
		sun_np = self.render.attachNewNode(sun); sun_np.setHpr(-35,-55,0)
		self.render.setLight(sun_np)
		board_root = self.render.attachNewNode("board")
		make_box(board_root, "walnut-frame", 0, 0, -0.18, 10.1, 10.1, .34, (.20,.10,.055,1))
		for rank in range(8):
			for file in range(8):
				x, y = (file-3.5)*SQ, (rank-3.5)*SQ
				color = LIGHT if (file+rank)%2 else DARK
				self.square_nodes[(file,rank)] = make_box(
					board_root, f"square-{file}-{rank}", x, y, 0, SQ-.025, SQ-.025, .09, color)
		self.pieces_root = self.render.attachNewNode("pieces")
		self.overlay_root = self.render.attachNewNode("indicators")

	def _place_camera(self):
		theta = math.radians(self.camera_angle)
		self.camera.setPos(self.camera_distance*math.cos(theta), -self.camera_distance*math.sin(theta), self.camera_distance*.78)
		self.camera.lookAt(0, 0, .1)

	def _setup_ui(self):
		self.game_screen = GameScreen(self)
		self.setup_screen = GameSetupScreen(self.aspect2d, self.start_game, self.cancel_setup)
		self.game_screen.layout(self.getAspectRatio())
		self.game_started = False
		self.setup_open = True
		self.setup_screen.show()

	def _window_resized(self, window):
		if window is None:
			return
		aspect = window.getAspectRatio()
		self.game_screen.layout(aspect)
		self.camera_distance = max(21.5, 23.0 * 1.6 / max(.8, aspect))
		self._place_camera()

	def _setup_database(self):
		self.db = sqlite3.connect("chess_history.sqlite3", check_same_thread=False)
		self.db.execute("CREATE TABLE IF NOT EXISTS games (id INTEGER PRIMARY KEY, played_at TEXT, mode TEXT, result TEXT, pgn TEXT)")
		self.db.commit()

	def square_pos(self, square):
		return ((chess.square_file(square)-3.5)*SQ, (chess.square_rank(square)-3.5)*SQ)

	def make_piece(self, square, piece):
		x, y = self.square_pos(square)
		white = piece.color == chess.WHITE
		color = (.88,.84,.72,1) if white else (.10,.105,.12,1)
		root = self.pieces_root.attachNewNode(f"{piece.symbol()}-{chess.square_name(square)}")
		root.setPos(x,y,.06)
		profile = [(0,.34),(.06,.40),(.13,.38),(.19,.28),(.24,.24),(.32,.20),(.44,.16),(.60,.14),(.76,.19),(.86,.14),(.91,.10)]
		kind = piece.piece_type
		if kind == chess.PAWN: profile = [(0,.32),(.06,.38),(.14,.34),(.22,.22),(.40,.14),(.56,.12),(.67,.19),(.72,.15)]
		elif kind == chess.ROOK: profile = [(0,.34),(.08,.40),(.16,.36),(.24,.24),(.58,.22),(.65,.31),(.72,.31),(.75,.24),(.91,.24)]
		elif kind == chess.BISHOP: profile = [(0,.33),(.08,.4),(.16,.35),(.25,.23),(.55,.17),(.67,.21),(.79,.13),(.91,.025)]
		elif kind == chess.KNIGHT: profile = [(0,.33),(.08,.4),(.17,.34),(.26,.22),(.46,.19),(.62,.27),(.75,.17),(.84,.08)]
		elif kind == chess.QUEEN: profile += [(.94,.26),(1.00,.20)]
		mesh_from_profile(root, "carved-body", profile, color, 32)
		if kind == chess.KNIGHT:
			head = root.attachNewNode("horse-head")
			head.setPos(.04,0,.68); head.setScale(.22,.15,.29); head.setColor(*color)
			# A compact geometric head keeps the knight distinctive without external assets.
			from panda3d.core import CardMaker
			cm = CardMaker("knight-head"); cm.setFrame(-1,1,-1,1)
			card = head.attachNewNode(cm.generate()); card.setP(-90); card.setScale(.7)
		elif kind in (chess.KING, chess.QUEEN):
			crown_z = 1.00 if kind == chess.KING else .96
			if kind == chess.KING:
				make_box(root,"crown-cross",0,0,crown_z+.10,.10,.10,.34,color)
				make_box(root,"crown-arms",0,0,crown_z+.14,.29,.10,.09,color)
			else:
				for i in range(5):
					a=i*2*math.pi/5
					orb=root.attachNewNode("crown-point"); orb.setPos(.17*math.cos(a),.17*math.sin(a),crown_z)
					orb.setScale(.065); orb.setColor(*color)
		return root

	def refresh_board(self):
		for node in self.piece_nodes.values(): node.removeNode()
		self.piece_nodes.clear()
		for square, piece in self.display_board.piece_map().items():
			self.piece_nodes[square] = self.make_piece(square, piece)
		self.draw_indicators()
		self.update_status()
		self.refresh_player_panels()

	@property
	def display_board(self):
		return self.review_board if self.review_board is not None else self.board

	def draw_indicators(self):
		for node in self.highlight_nodes: node.removeNode()
		self.highlight_nodes.clear()
		targets = self.legal_targets | ({self.selected} if self.selected is not None else set())
		board = self.display_board
		if board.move_stack:
			move=board.peek(); targets |= {move.from_square, move.to_square}
		if board.is_check():
			king=board.king(board.turn)
			if king is not None: targets.add(king)
		for sq in targets:
			x,y=self.square_pos(sq)
			color=(.95,.64,.12,.43) if sq in self.legal_targets else (.9,.18,.12,.48) if board.is_check() and sq==board.king(board.turn) else (.25,.55,.85,.36)
			n=make_box(self.overlay_root,"highlight",x,y,.075,SQ-.04,SQ-.04,.025,color)
			self.highlight_nodes.append(n)
		for sq in self.legal_targets:
			x,y=self.square_pos(sq)
			dot=self.overlay_root.attachNewNode("legal-dot"); dot.setPos(x,y,.10); dot.setScale(.11); dot.setColor(.98,.77,.25,.85)
			# Use a small square indicator for clear visibility on all renderers.
			make_box(dot,"marker",0,0,0,.45,.45,.06,(.98,.77,.25,.85))
			self.highlight_nodes.append(dot)

	def on_click(self):
		if (
			not self.mouseWatcherNode.hasMouse()
			or not self.game_started
			or self.game_finished
			or self.board.is_game_over(claim_draw=True)
			or self.review_ply is not None
			or not self.mode_manager.accepts_human_move(
				self.board.turn,
				paused=self.engine_scheduler.paused,
				stopped=self.engine_scheduler.stopped and self.mode_manager.is_computer_turn(self.board.turn),
			)
		):
			return
		m=self.mouseWatcherNode.getMouse(); near,far=Point3(),Point3()
		if not self.camLens.extrude(Point2(m.getX(),m.getY()),near,far): return
		a=self.render.getRelativePoint(self.camera,near); b=self.render.getRelativePoint(self.camera,far)
		if abs(b.z-a.z)<1e-6: return
		t=-a.z/(b.z-a.z); x=a.x+t*(b.x-a.x); y=a.y+t*(b.y-a.y)
		file=round(x/SQ+3.5); rank=round(y/SQ+3.5)
		if not (0<=file<8 and 0<=rank<8): return
		sq=chess.square(file,rank)
		if self.selected is not None and sq in self.legal_targets:
			move=next(mv for mv in self.board.legal_moves if mv.from_square==self.selected and mv.to_square==sq)
			if move.promotion: move.promotion=self.promotion_type
			self.play_move(move); return
		piece=self.board.piece_at(sq)
		if piece and piece.color==self.board.turn:
			self.selected=sq
			self.legal_targets={mv.to_square for mv in self.board.legal_moves if mv.from_square==sq}
		else: self.clear_selection()
		self.draw_indicators()

	def clear_selection(self):
		self.selected=None; self.legal_targets=set(); self.draw_indicators()

	def play_move(self, move, source="human"):
		if self.game_finished or self.review_ply is not None:
			return False
		mover=self.board.turn
		if source == "human" and not self.mode_manager.accepts_human_move(
			mover, paused=self.engine_scheduler.paused, stopped=self.engine_scheduler.stopped,
		):
			return False
		if source == "computer" and not self.mode_manager.is_computer_turn(mover):
			return False
		if not self.controller.play(move):
			return False
		if self.configuration.initial_time_seconds:
			self.clocks[int(mover)] += self.increment
		self.selected=None; self.legal_targets=set()
		self.refresh_board()
		if self.board.is_game_over(claim_draw=True):
			self.finish_game()
		else:
			self.request_engine_move()
		return True

	def update_status(self):
		board = self.display_board
		if self.review_ply is not None:
			record = self.controller.history.records[self.review_ply - 1]
			text = f"Reviewing move {record.number}: {record.san}"
		elif self.board.is_checkmate(): text=f"Checkmate — {'Black' if self.board.turn else 'White'} wins"
		elif self.board.is_stalemate(): text="Draw — stalemate"
		elif self.board.is_insufficient_material(): text="Draw — insufficient material"
		elif self.board.is_seventyfive_moves(): text="Draw — 75-move rule"
		elif self.board.is_fivefold_repetition(): text="Draw — fivefold repetition"
		else:
			player = self.player_manager.player(board.turn)
			text=f"{player.name} to move" + (" — CHECK" if board.is_check() else "")
		self.game_screen.status.setText(text)

	def refresh_player_panels(self):
		if not hasattr(self, "game_screen"):
			return
		captured = {chess.WHITE: [], chess.BLACK: []}
		for record in self.controller.history.records:
			if record.captured_symbol:
				captured[record.color].append(UNICODE[record.captured_symbol])
		clocks = [
			self.format_time(value) if self.configuration.initial_time_seconds else "No clock"
			for value in self.clocks
		]
		self.game_screen.panels.update(
			self.controller.history.records,
			self.configuration.white,
			self.configuration.black,
			clocks,
			captured,
			len(self.controller.history.records),
			self.review_ply,
		)

	def review_position(self, ply):
		if not 1 <= ply <= len(self.controller.history.records):
			return
		self.review_ply = ply
		self.review_board = self.controller.position_at(ply)
		self.game_screen.set_reviewing(True)
		self.selected = None
		self.legal_targets.clear()
		self.refresh_board()
		self.game_screen.message.setText("History review — use Return to Live to continue")

	def return_to_live(self):
		if self.review_ply is None:
			return
		self.review_ply = None
		self.review_board = None
		self.game_screen.set_reviewing(False)
		self.refresh_board()
		self.game_screen.message.setText("")

	@staticmethod
	def format_time(seconds):
		seconds=max(0,int(seconds)); return f"{seconds//60:02d}:{seconds%60:02d}"

	def update(self, task):
		now=datetime.now().timestamp(); elapsed=now-self.last_tick; self.last_tick=now
		if (
			self.game_started
			and not self.setup_open
			and not self.game_finished
			and self.configuration.initial_time_seconds
			and not self.board.is_game_over(claim_draw=True)
		):
			self.clocks[int(self.board.turn)]-=elapsed
			if self.clocks[int(self.board.turn)]<=0:
				self.clocks[int(self.board.turn)]=0
				winner=not self.board.turn
				if self.board.has_insufficient_material(winner):
					self.game_screen.message.setText("Draw on time — insufficient mating material")
					result = "1/2-1/2"
				else:
					self.game_screen.message.setText(("White" if winner else "Black")+" wins on time")
					result = "1-0" if winner else "0-1"
				self.time_expired=True
				self.game_finished=True
				self.record_game(result)
				self.engine_scheduler.stop()
			self.update_status()
		if now - self.last_panel_tick >= 1:
			self.last_panel_tick = now
			self.refresh_player_panels()
		try:
			result = self.stockfish.results.get_nowait()
		except Empty:
			result = None
		if result is not None:
			if result.error:
				self.game_screen.message.setText(result.error)
				self.engine_scheduler.stop()
			elif result.move is not None:
				self.play_move(result.move, source="computer")
		return task.cont

	def set_promotion(self, value):
		self.promotion_type={"Queen":chess.QUEEN,"Rook":chess.ROOK,"Bishop":chess.BISHOP,"Knight":chess.KNIGHT}.get(value,chess.QUEEN)

	def new_game(self):
		self.setup_open = True
		self.engine_scheduler.pause()
		self.setup_screen.show()

	def start_game(self, configuration):
		self.engine_scheduler.stop()
		self.configuration = configuration
		self.mode_manager.configure(configuration)
		self.player_manager.configure(configuration)
		self.mode = configuration.mode.value
		self.human_color = configuration.human_color
		self.increment = configuration.increment_seconds
		self.controller.reset()
		self.clocks = [float(configuration.initial_time_seconds)] * 2
		self.review_ply = None
		self.review_board = None
		self.selected = None
		self.legal_targets.clear()
		self.game_finished = False
		self.time_expired = False
		self.game_screen.set_reviewing(False)
		self.game_started = True
		self.setup_open = False
		self.last_tick = datetime.now().timestamp()
		self.engine_scheduler.start()
		self.game_screen.set_mode(self.mode)
		self.game_screen.message.setText("")
		self.refresh_board()
		self.request_engine_move()

	def cancel_setup(self):
		self.setup_open = False
		if self.game_started:
			self.engine_scheduler.resume()
			self.request_engine_move()
		else:
			self.start_game(GameConfiguration())

	def undo(self):
		if self.review_ply is not None or not self.board.move_stack:
			return
		was_stopped = self.engine_scheduler.stopped
		self.engine_scheduler.stop()
		self.controller.undo()
		if (
			self.configuration.mode is GameMode.PLAYER_VS_COMPUTER
			and self.board.turn == self.human_color
			and self.board.move_stack
		):
			self.controller.undo()
		self.review_ply = None
		self.review_board = None
		if not was_stopped:
			self.engine_scheduler.start()
		self.refresh_board()
		self.game_screen.message.setText("Last move undone")
		self.request_engine_move()

	def resign(self):
		if self.game_started and not self.game_finished and not self.board.is_game_over():
			result="0-1" if self.board.turn==chess.WHITE else "1-0"
			self.game_finished = True
			self.engine_scheduler.stop()
			self.game_screen.message.setText(("Black" if self.board.turn else "White")+" resigns")
			self.record_game(result)

	def start_computers(self):
		if not self.game_started or not self.mode_manager.is_computer_vs_computer or self.game_finished:
			return
		self.engine_scheduler.start()
		self.game_screen.message.setText("Computer game started")
		self.request_engine_move()

	def pause_computers(self):
		if self.mode_manager.is_computer_vs_computer and not self.engine_scheduler.stopped:
			self.engine_scheduler.pause()
			self.game_screen.message.setText("Computer game paused")

	def resume_computers(self):
		if self.mode_manager.is_computer_vs_computer and self.game_started and not self.game_finished:
			self.engine_scheduler.resume()
			self.game_screen.message.setText("Computer game resumed")
			self.request_engine_move()

	def stop_computers(self):
		if self.mode_manager.is_computer_vs_computer:
			self.engine_scheduler.stop()
			self.game_screen.message.setText("Computer game stopped")

	def request_engine_move(self):
		if (
			not self.game_started
			or self.game_finished
			or self.setup_open
			or self.review_ply is not None
			or self.board.is_game_over(claim_draw=True)
			or not self.mode_manager.is_computer_turn(self.board.turn)
			or not self.engine_scheduler.can_schedule()
		):
			return
		player = self.mode_manager.player(self.board.turn)
		self.stockfish.request(
			self.board.fen(), self.board.turn, player.difficulty,
			self.configuration.engine_thinking_seconds,
		)

	def save_pgn(self):
		game=chess.pgn.Game.from_board(self.board)
		game.headers["Event"]="3D Chess"
		game.headers["Date"]=datetime.now().strftime("%Y.%m.%d")
		game.headers["White"]=self.configuration.white.name
		game.headers["Black"]=self.configuration.black.name
		game.headers["Result"]=self.board.result(claim_draw=True) if self.board.is_game_over(claim_draw=True) else "*"
		filename=f"chess_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pgn"
		with open(filename,"w",encoding="utf-8") as file: print(game,file=file, end="\n")
		self.game_screen.message.setText(f"Saved {filename}")
		self.record_game(game.headers["Result"])

	def record_game(self, result):
		pgn=chess.pgn.Game.from_board(self.board)
		pgn.headers["White"] = self.configuration.white.name
		pgn.headers["Black"] = self.configuration.black.name
		pgn.headers["Result"] = result
		try:
			self.db.execute("INSERT INTO games(played_at,mode,result,pgn) VALUES(?,?,?,?)",
							(datetime.now().isoformat(timespec="seconds"),self.mode,result,str(pgn)))
			self.db.commit()
		except sqlite3.Error as exc: self.game_screen.message.setText(f"History save failed: {exc}")

	def finish_game(self):
		result=self.board.result(claim_draw=True)
		self.game_finished = True
		self.engine_scheduler.stop()
		self.game_screen.message.setText("Game over — "+result)
		self.record_game(result)

	def zoom(self, amount):
		self.camera_distance=max(18,min(32,self.camera_distance+amount)); self._place_camera()

	def orbit(self, degrees):
		self.camera_angle=(self.camera_angle+degrees)%360; self._place_camera()

	def reset_camera(self):
		self.camera_angle=45; self.camera_distance=23.0; self._place_camera()

	def userExit(self):
		self.engine_scheduler.stop()
		self.stockfish.close()
		self.setup_screen.destroy()
		self.game_screen.destroy()
		self.db.close()
		super().userExit()


if __name__ == "__main__":
	ChessGame3D().run()
