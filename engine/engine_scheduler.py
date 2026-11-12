"""Coordinates asynchronous engine turns and game pause/stop state."""

class EngineScheduler:
	def __init__(self, stockfish_manager):
		self.stockfish = stockfish_manager
		self.paused = False
		self.stopped = True

	def start(self):
		self.paused = False
		self.stopped = False

	def pause(self):
		self.paused = True
		self.stockfish.stop()

	def resume(self):
		if not self.stopped:
			self.paused = False

	def stop(self):
		self.paused = False
		self.stopped = True
		self.stockfish.stop()

	def can_schedule(self):
		return not self.paused and not self.stopped and not self.stockfish.busy
