"""Threaded Stockfish requests with cancellation and result delivery."""

import queue
import threading
from dataclasses import dataclass

import chess
import chess.engine


@dataclass(frozen=True)
class EngineResult:
	generation: int
	color: bool
	move: chess.Move | None
	error: str | None = None


class StockfishManager:
	def __init__(self, path):
		self.path = path
		self.results = queue.Queue()
		self._lock = threading.Lock()
		self._generation = 0
		self._active = False
		self._engines = set()

	@property
	def busy(self):
		with self._lock:
			return self._active

	def request(self, fen, color, difficulty, thinking_seconds):
		with self._lock:
			if self._active:
				return False
			self._active = True
			generation = self._generation
		threading.Thread(
			target=self._calculate,
			args=(generation, fen, color, difficulty, thinking_seconds),
			daemon=True,
		).start()
		return True

	def _calculate(self, generation, fen, color, difficulty, thinking_seconds):
		engine = None
		move = None
		error = None
		try:
			engine = chess.engine.SimpleEngine.popen_uci(self.path)
			with self._lock:
				if generation != self._generation:
					engine.close()
					return
				self._engines.add(engine)
			engine.configure({"Skill Level": max(0, min(20, difficulty))})
			result = engine.play(
				chess.Board(fen),
				chess.engine.Limit(time=max(0.05, thinking_seconds)),
			)
			move = result.move
		except (OSError, chess.engine.EngineError, chess.engine.EngineTerminatedError, ValueError) as exc:
			error = f"Stockfish request failed: {exc}"
		finally:
			if engine is not None:
				with self._lock:
					self._engines.discard(engine)
					is_current = generation == self._generation
				if is_current:
					try:
						engine.quit()
					except (chess.engine.EngineError, chess.engine.EngineTerminatedError):
						engine.close()
				else:
					engine.close()
			with self._lock:
				current = generation == self._generation
				if current:
					self._active = False
			if current:
				self.results.put(EngineResult(generation, color, move, error))

	def stop(self):
		with self._lock:
			self._generation += 1
			self._active = False
			engines = tuple(self._engines)
			self._engines.clear()
		for engine in engines:
			engine.close()

	def close(self):
		self.stop()
