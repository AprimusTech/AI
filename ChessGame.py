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
import threading
import queue
from datetime import datetime

try:
	import chess  # pyright: ignore[reportMissingImports]
	import chess.pgn  # pyright: ignore[reportMissingImports]
except ImportError as exc:
	raise SystemExit("Missing dependency. Install with: py -m pip install panda3d python-chess") from exc

try:
	from direct.showbase.ShowBase import ShowBase  # pyright: ignore[reportMissingImports]
	from direct.gui.DirectGui import DirectButton, DirectLabel, DirectOptionMenu  # pyright: ignore[reportMissingImports]
	from direct.gui.OnscreenText import OnscreenText  # pyright: ignore[reportMissingImports]
	from panda3d.core import (
		AmbientLight, DirectionalLight, Geom, GeomNode, GeomTriangles,
		GeomVertexData, GeomVertexFormat, GeomVertexWriter, Point2, Point3,
		TextNode, Vec3, Vec4, WindowProperties,
	)
except ImportError as exc:
	raise SystemExit("Missing Panda3D. Install with: py -m pip install panda3d") from exc


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
		self.board = chess.Board()
		self.selected = None
		self.legal_targets = set()
		self.mode = "Human vs Human"
		self.human_color = chess.WHITE
		self.engine = None
		self.engine_busy = False
		self.engine_results = queue.Queue()
		self.engine_path = os.environ.get("STOCKFISH_PATH", "stockfish")
		self.clocks = [600.0, 600.0]
		self.increment = 0
		self.last_tick = datetime.now().timestamp()
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
		self.taskMgr.add(self.update, "game-update")
		self.refresh_board()

	def _setup_scene(self):
		self.camera_distance, self.camera_angle = 16.8, 45.0
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
		self.title = OnscreenText(text="CHESS  /  3D", pos=(-1.28,.92), scale=.065,
								  fg=(.95,.8,.47,1), align=TextNode.ALeft, mayChange=False)
		self.status = OnscreenText(text="White to move", pos=(-1.28,.78), scale=.043,
								   fg=(.9,.92,.96,1), align=TextNode.ALeft, mayChange=True)
		self.clock_text = OnscreenText(text="", pos=(-1.28,.63), scale=.037,
									   fg=(.8,.85,.9,1), align=TextNode.ALeft, mayChange=True)
		self.moves_text = OnscreenText(text="Moves\n", pos=(1.03,.82), scale=.032,
									   fg=(.86,.88,.92,1), align=TextNode.ALeft, mayChange=True,
									   wordwrap=17)
		self.message = OnscreenText(text="", pos=(0,-.92), scale=.042, fg=(1,.82,.38,1), mayChange=True)
		def button(label, x, y, command, width=.19):
			return DirectButton(text=label, scale=.043, frameColor=(.16,.19,.24,1),
								text_fg=(.95,.95,.95,1), relief=1, command=command,
								pos=(x,0,y), frameSize=(-width,width,-.42,.42))
		button("New", -1.05, .43, self.new_game)
		button("Undo", -1.05, .31, self.undo)
		button("Save PGN", -1.05, .19, self.save_pgn, .25)
		button("Resign", -1.05, .07, self.resign)
		button("Vs Computer", -1.05, -.05, self.toggle_engine, .25)
		button("Reset View", -1.05, -.17, self.reset_camera, .25)
		DirectLabel(text="Promotion", scale=.028, pos=(-1.05,0,-.34), text_fg=(.8,.84,.9,1), frameColor=(0,0,0,0))
		DirectOptionMenu(text="Queen", scale=.033, items=["Queen","Rook","Bishop","Knight"],
						 initialitem=0, command=self.set_promotion, pos=(-1.05,0,-.44),
						 frameColor=(.16,.19,.24,1), text_fg=(1,1,1,1))

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
		for square, piece in self.board.piece_map().items():
			self.piece_nodes[square] = self.make_piece(square, piece)
		self.draw_indicators()
		self.update_status()

	def draw_indicators(self):
		for node in self.highlight_nodes: node.removeNode()
		self.highlight_nodes.clear()
		targets = self.legal_targets | ({self.selected} if self.selected is not None else set())
		if self.board.move_stack:
			move=self.board.peek(); targets |= {move.from_square, move.to_square}
		if self.board.is_check():
			king=self.board.king(self.board.turn)
			if king is not None: targets.add(king)
		for sq in targets:
			x,y=self.square_pos(sq)
			color=(.95,.64,.12,.43) if sq in self.legal_targets else (.9,.18,.12,.48) if self.board.is_check() and sq==self.board.king(self.board.turn) else (.25,.55,.85,.36)
			n=make_box(self.overlay_root,"highlight",x,y,.075,SQ-.04,SQ-.04,.025,color)
			self.highlight_nodes.append(n)
		for sq in self.legal_targets:
			x,y=self.square_pos(sq)
			dot=self.overlay_root.attachNewNode("legal-dot"); dot.setPos(x,y,.10); dot.setScale(.11); dot.setColor(.98,.77,.25,.85)
			# Use a small square indicator for clear visibility on all renderers.
			make_box(dot,"marker",0,0,0,.45,.45,.06,(.98,.77,.25,.85))
			self.highlight_nodes.append(dot)

	def on_click(self):
		if not self.mouseWatcherNode.hasMouse() or self.board.is_game_over(claim_draw=True): return
		if self.mode != "Human vs Human" and self.board.turn != self.human_color: return
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

	def play_move(self, move):
		if move not in self.board.legal_moves: return
		mover=self.board.turn
		self.board.push(move)
		self.clocks[int(mover)] += self.increment
		self.selected=None; self.legal_targets=set()
		self.refresh_board(); self.update_move_list()
		if self.board.is_checkmate() or self.board.is_game_over(claim_draw=True): self.finish_game()
		elif self.mode != "Human vs Human" and self.board.turn != self.human_color: self.request_engine_move()

	def update_status(self):
		if self.board.is_checkmate(): text=f"Checkmate — {'Black' if self.board.turn else 'White'} wins"
		elif self.board.is_stalemate(): text="Draw — stalemate"
		elif self.board.is_insufficient_material(): text="Draw — insufficient material"
		elif self.board.is_seventyfive_moves(): text="Draw — 75-move rule"
		elif self.board.is_fivefold_repetition(): text="Draw — fivefold repetition"
		else: text=("White" if self.board.turn else "Black")+(" to move — CHECK" if self.board.is_check() else " to move")
		self.status.setText(text)
		self.clock_text.setText(f"White  {self.format_time(self.clocks[1])}     Black  {self.format_time(self.clocks[0])}\nMode: {self.mode}")

	def update_move_list(self):
		sans=[]; b=chess.Board()
		for move in self.board.move_stack:
			number=b.fullmove_number
			if b.turn==chess.WHITE: sans.append(f"{number}. {b.san(move)}")
			else:
				if sans: sans[-1]+="  "+b.san(move)
				else: sans.append(f"{number}... {b.san(move)}")
			b.push(move)
		self.moves_text.setText("Moves\n"+"\n".join(sans[-18:]))

	@staticmethod
	def format_time(seconds):
		seconds=max(0,int(seconds)); return f"{seconds//60:02d}:{seconds%60:02d}"

	def update(self, task):
		now=datetime.now().timestamp(); elapsed=now-self.last_tick; self.last_tick=now
		if not self.board.is_game_over(claim_draw=True):
			self.clocks[int(self.board.turn)]-=elapsed
			if self.clocks[int(self.board.turn)]<=0:
				self.clocks[int(self.board.turn)]=0
				winner=not self.board.turn
				if self.board.has_insufficient_material(winner): self.message.setText("Draw on time — insufficient mating material")
				else: self.message.setText(("White" if winner else "Black")+" wins on time")
				self.record_game("1-0" if winner else "0-1")
			self.update_status()
		try:
			move=self.engine_results.get_nowait()
			self.engine_busy=False
			if move and move in self.board.legal_moves: self.play_move(move)
		except queue.Empty: pass
		return task.cont

	def set_promotion(self, value):
		self.promotion_type={"Queen":chess.QUEEN,"Rook":chess.ROOK,"Bishop":chess.BISHOP,"Knight":chess.KNIGHT}.get(value,chess.QUEEN)

	def new_game(self):
		self.board.reset(); self.clocks=[600.0,600.0]; self.message.setText("")
		self.refresh_board(); self.update_move_list()

	def undo(self):
		if self.board.move_stack:
			self.board.pop()
			if self.mode != "Human vs Human" and self.board.move_stack: self.board.pop()
			self.refresh_board(); self.update_move_list(); self.message.setText("Last move undone")

	def resign(self):
		if not self.board.is_game_over():
			result="0-1" if self.board.turn==chess.WHITE else "1-0"
			self.message.setText(("Black" if self.board.turn else "White")+" resigns")
			self.record_game(result)

	def toggle_engine(self):
		if self.mode == "Human vs Human":
			self.mode="Human vs Computer"; self.human_color=chess.WHITE
			self.message.setText("Engine mode enabled; Stockfish is used when available")
			if self.board.turn != self.human_color: self.request_engine_move()
		else:
			self.mode="Human vs Human"
			if self.engine:
				try: self.engine.quit()
				except Exception: pass
				self.engine=None
		self.update_status()

	def request_engine_move(self):
		if self.engine_busy: return
		self.engine_busy=True; fen=self.board.fen(); path=self.engine_path
		def worker():
			move=None; local=None
			try:
				import chess.engine
				local=chess.engine.SimpleEngine.popen_uci(path)
				local.configure({"Skill Level": 8})
				result=local.play(chess.Board(fen), chess.engine.Limit(time=.45))
				move=result.move
			except Exception:
				# Missing Stockfish is handled gracefully: leave the board usable and inform the player.
				self.message.setText("Stockfish unavailable. Install it or set STOCKFISH_PATH.")
			finally:
				if local:
					try: local.quit()
					except Exception: pass
				self.engine_results.put(move)
		threading.Thread(target=worker, daemon=True).start()

	def save_pgn(self):
		game=chess.pgn.Game.from_board(self.board)
		game.headers["Event"]="3D Chess"
		game.headers["Date"]=datetime.now().strftime("%Y.%m.%d")
		game.headers["White"]="White"; game.headers["Black"]="Black"
		game.headers["Result"]=self.board.result(claim_draw=True) if self.board.is_game_over(claim_draw=True) else "*"
		filename=f"chess_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pgn"
		with open(filename,"w",encoding="utf-8") as file: print(game,file=file, end="\n")
		self.message.setText(f"Saved {filename}")
		self.record_game(game.headers["Result"])

	def record_game(self, result):
		pgn=chess.pgn.Game.from_board(self.board)
		try:
			self.db.execute("INSERT INTO games(played_at,mode,result,pgn) VALUES(?,?,?,?)",
							(datetime.now().isoformat(timespec="seconds"),self.mode,result,str(pgn)))
			self.db.commit()
		except sqlite3.Error as exc: self.message.setText(f"History save failed: {exc}")

	def finish_game(self):
		result=self.board.result(claim_draw=True)
		self.message.setText("Game over — "+result)
		self.record_game(result)

	def zoom(self, amount):
		self.camera_distance=max(11,min(24,self.camera_distance+amount)); self._place_camera()

	def orbit(self, degrees):
		self.camera_angle=(self.camera_angle+degrees)%360; self._place_camera()

	def reset_camera(self):
		self.camera_angle=45; self.camera_distance=16.8; self._place_camera()

	def userExit(self):
		try:
			if self.engine: self.engine.quit()
			self.db.close()
		except Exception: pass
		super().userExit()


if __name__ == "__main__":
	ChessGame3D().run()
