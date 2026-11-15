"""DUAL N-BACK PRO — standalone Windows desktop implementation.

Install: py -m pip install PySide6 pyttsx3
Run:     py Dual_N_Back.py
All settings and session data are stored under %LOCALAPPDATA%\\DualNBackPro.
"""
from __future__ import annotations

import csv
import importlib
import importlib
import json
import random
import sqlite3
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from queue import Queue

try:
	_qt_core = importlib.import_module("PySide6.QtCore")
	_qt_gui = importlib.import_module("PySide6.QtGui")
	_qt_widgets = importlib.import_module("PySide6.QtWidgets")
except ModuleNotFoundError as exc:
	raise SystemExit("PySide6 is required. Install it with: py -m pip install PySide6") from exc

Qt = _qt_core.Qt
QTimer = _qt_core.QTimer
QKeyEvent = _qt_gui.QKeyEvent
QApplication = _qt_widgets.QApplication
QComboBox = _qt_widgets.QComboBox
QDialog = _qt_widgets.QDialog
QFileDialog = _qt_widgets.QFileDialog
QFormLayout = _qt_widgets.QFormLayout
QFrame = _qt_widgets.QFrame
QGridLayout = _qt_widgets.QGridLayout
QHBoxLayout = _qt_widgets.QHBoxLayout
QLabel = _qt_widgets.QLabel
QMainWindow = _qt_widgets.QMainWindow
QMessageBox = _qt_widgets.QMessageBox
QPushButton = _qt_widgets.QPushButton
QProgressBar = _qt_widgets.QProgressBar
QSpinBox = _qt_widgets.QSpinBox
QDoubleSpinBox = _qt_widgets.QDoubleSpinBox
QVBoxLayout = _qt_widgets.QVBoxLayout
QWidget = _qt_widgets.QWidget
QCheckBox = _qt_widgets.QCheckBox

try:
	pyttsx3 = importlib.import_module("pyttsx3")
except ModuleNotFoundError:
	pyttsx3 = None


PRESETS = {
	"Beginner": (1, 18, 3.0), "Easy": (2, 20, 3.0),
	"Standard": (2, 25, 2.5), "Intermediate": (3, 25, 2.0),
	"Advanced": (4, 30, 2.0), "Expert": (5, 35, 1.8),
}
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
APP_DIR = Path(__import__("os").environ.get("LOCALAPPDATA", Path.home())) / "DualNBackPro"


def ensure_storage() -> None:
	for folder in ("config", "database", "audio", "logs", "exports", "profiles"):
		(APP_DIR / folder).mkdir(parents=True, exist_ok=True)


class SpeechService:
	"""Queue-based offline TTS; speech synthesis never blocks the GUI thread."""
	def __init__(self) -> None:
		self.queue: Queue = Queue()
		self.thread = threading.Thread(target=self._worker, daemon=True)
		self.thread.start()

	def speak(self, letter: str, rate: int = 170, volume: float = 1.0) -> None:
		self.queue.put((letter, rate, volume))

	def _worker(self) -> None:
		engine = None
		while True:
			letter, rate, volume = self.queue.get()
			try:
				if engine is None:
					if pyttsx3 is None:
						raise ModuleNotFoundError("pyttsx3 is not installed")
					engine = pyttsx3.init("sapi5" if sys.platform == "win32" else None)
				engine.setProperty("rate", rate)
				engine.setProperty("volume", max(0.0, min(1.0, volume)))
				engine.say(letter)
				engine.runAndWait()
			except Exception:
				# Missing SAPI/audio devices should not interrupt training.
				engine = None
			finally:
				self.queue.task_done()


class SettingsDialog(QDialog):
	def __init__(self, settings: dict, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Training settings")
		self.setMinimumWidth(360)
		self.settings = settings
		form = QFormLayout(self)
		self.n = QSpinBox(); self.n.setRange(1, 10); self.n.setValue(settings["n"])
		self.trials = QSpinBox(); self.trials.setRange(10, 100); self.trials.setValue(settings["trials"])
		self.duration = QDoubleSpinBox(); self.duration.setRange(0.8, 10); self.duration.setSingleStep(.1); self.duration.setValue(settings["duration"])
		self.grid = QComboBox(); self.grid.addItems(["3×3", "4×4", "5×5"]); self.grid.setCurrentIndex(settings.get("grid", 3) - 3)
		self.visual = QCheckBox("Enable visual task"); self.visual.setChecked(settings["visual"])
		self.audio = QCheckBox("Enable audio task"); self.audio.setChecked(settings["audio"])
		self.show_letter = QCheckBox("Show spoken letter on screen"); self.show_letter.setChecked(settings["show_letter"])
		self.voice_rate = QSpinBox(); self.voice_rate.setRange(100, 250); self.voice_rate.setValue(settings["voice_rate"])
		self.volume = QDoubleSpinBox(); self.volume.setRange(0, 1); self.volume.setSingleStep(.1); self.volume.setValue(settings["volume"])
		self.visual_prob = QDoubleSpinBox(); self.visual_prob.setRange(0, .5); self.visual_prob.setSingleStep(.05); self.visual_prob.setValue(settings["match_probability"])
		self.audio_prob = QDoubleSpinBox(); self.audio_prob.setRange(0, .5); self.audio_prob.setSingleStep(.05); self.audio_prob.setValue(settings["audio_probability"])
		for label, widget in (("N-level", self.n), ("Trials", self.trials), ("Trial duration (sec)", self.duration),
							  ("Grid", self.grid), ("Speech speed", self.voice_rate), ("Speech volume", self.volume),
							  ("Visual match probability", self.visual_prob), ("Audio match probability", self.audio_prob)):
			form.addRow(label, widget)
		form.addRow(self.visual); form.addRow(self.audio); form.addRow(self.show_letter)
		buttons = QHBoxLayout(); save = QPushButton("Save"); cancel = QPushButton("Cancel")
		save.clicked.connect(self.accept); cancel.clicked.connect(self.reject)
		buttons.addWidget(save); buttons.addWidget(cancel); form.addRow(buttons)

	def values(self) -> dict:
		return {"n": self.n.value(), "trials": self.trials.value(), "duration": self.duration.value(),
				"grid": self.grid.currentIndex() + 3, "visual": self.visual.isChecked(),
				"audio": self.audio.isChecked(), "show_letter": self.show_letter.isChecked(),
				"voice_rate": self.voice_rate.value(), "volume": self.volume.value(),
				"match_probability": self.visual_prob.value(), "audio_probability": self.audio_prob.value()}


class DualNBackWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		ensure_storage()
		self.config_path = APP_DIR / "config" / "settings.json"
		self.db_path = APP_DIR / "database" / "sessions.sqlite3"
		self.settings = self._load_settings()
		self.speech = SpeechService()
		self.state = "idle"
		self.index = -1
		self.sequence: list[tuple[int, str]] = []
		self.records: list[dict] = []
		self.answers = {"visual": False, "audio": False}
		self.reactions = []
		self.started_at = 0.0
		self.elapsed_before_pause = 0.0
		self._init_db()
		self._build_ui()
		self._apply_theme()
		self.trial_timer = QTimer(self); self.trial_timer.setSingleShot(True); self.trial_timer.timeout.connect(self._next_trial)

	def _load_settings(self) -> dict:
		defaults = {"preset": "Standard", "n": 2, "trials": 25, "duration": 2.5, "grid": 3,
					"visual": True, "audio": True, "show_letter": False, "voice_rate": 170,
					"volume": .8, "match_probability": .25, "audio_probability": .25,
					"position_preset": "Random positions", "letter_preset": "A–Z"}
		try:
			if self.config_path.exists(): defaults.update(json.loads(self.config_path.read_text(encoding="utf-8")))
		except (OSError, ValueError):
			pass
		return defaults

	def _save_settings(self) -> None:
		try: self.config_path.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")
		except OSError as exc: QMessageBox.warning(self, "Settings", f"Could not save settings:\n{exc}")

	def _init_db(self) -> None:
		with sqlite3.connect(self.db_path) as db:
			db.execute("""CREATE TABLE IF NOT EXISTS sessions (
				id INTEGER PRIMARY KEY, completed_at TEXT, preset TEXT, n INTEGER, trials INTEGER,
				duration REAL, visual_accuracy REAL, audio_accuracy REAL, overall_accuracy REAL,
				correct INTEGER, missed INTEGER, false_positives INTEGER, avg_reaction REAL, details TEXT)""")

	def _build_ui(self) -> None:
		self.setWindowTitle("DUAL N-BACK PRO")
		self.setMinimumSize(1100, 750); self.resize(1280, 820)
		root = QWidget(); outer = QVBoxLayout(root); outer.setContentsMargins(24, 18, 24, 18); outer.setSpacing(16)
		header = QHBoxLayout()
		title = QLabel("DUAL N-BACK <span style='color:#7c7cff'>PRO</span>"); title.setObjectName("title")
		self.profile = QLabel("LOCAL PROFILE  ·  TRAINING")
		self.level = QLabel("N=2"); self.level.setObjectName("badge")
		settings_btn = QPushButton("Settings"); stats_btn = QPushButton("Statistics"); help_btn = QPushButton("Help")
		settings_btn.clicked.connect(self.open_settings); stats_btn.clicked.connect(self.show_statistics); help_btn.clicked.connect(self.show_help)
		header.addWidget(title); header.addStretch(); header.addWidget(self.profile); header.addWidget(self.level)
		header.addWidget(settings_btn); header.addWidget(stats_btn); header.addWidget(help_btn); outer.addLayout(header)

		panels = QHBoxLayout(); panels.setSpacing(16)
		self.visual_panel = self._panel("VISUAL POSITION", "Compare the highlighted cell N trials back. Press A to respond.")
		vg = QGridLayout(); vg.setSpacing(8); self.cells = []
		for i in range(25):
			cell = QLabel(""); cell.setAlignment(Qt.AlignCenter); cell.setObjectName("cell")
			vg.addWidget(cell, i // 5, i % 5); self.cells.append(cell)
		self.visual_panel.layout().addLayout(vg)
		self.visual_accuracy = QLabel("Accuracy  —     Correct  0     Missed  0     False  0")
		self.visual_panel.layout().addWidget(self.visual_accuracy)

		center = self._panel("SESSION CONTROL", "Focus on each stimulus; respond independently.")
		self.session_info = QLabel("Ready when you are."); self.session_info.setObjectName("sessionInfo")
		self.progress = QProgressBar(); self.progress.setRange(0, 100); self.progress.setValue(0)
		self.timer_label = QLabel("00:00"); self.timer_label.setAlignment(Qt.AlignCenter); self.timer_label.setObjectName("clock")
		self.preset = QComboBox(); self.preset.addItems(list(PRESETS) + ["Custom"])
		self.preset.setCurrentText(self.settings.get("preset", "Standard")); self.preset.currentTextChanged.connect(self._preset_changed)
		self.trial_label = QLabel("TRIAL  — / —"); self.trial_label.setAlignment(Qt.AlignCenter)
		self.start_btn = QPushButton("Start session"); self.start_btn.setObjectName("primary")
		self.pause_btn = QPushButton("Pause"); self.stop_btn = QPushButton("Stop")
		self.start_btn.clicked.connect(self.start_session); self.pause_btn.clicked.connect(self.pause_resume); self.stop_btn.clicked.connect(self.stop_session)
		controls = QHBoxLayout(); controls.addWidget(self.start_btn); controls.addWidget(self.pause_btn); controls.addWidget(self.stop_btn)
		center.layout().addWidget(self.session_info); center.layout().addWidget(self.timer_label); center.layout().addWidget(self.progress)
		center.layout().addWidget(self.trial_label); center.layout().addWidget(QLabel("TRAINING PRESET")); center.layout().addWidget(self.preset)
		center.layout().addStretch(); center.layout().addLayout(controls)

		self.audio_panel = self._panel("AUDIO STIMULUS", "Compare the spoken letter N trials back. Press L to respond.")
		self.letter_label = QLabel("—"); self.letter_label.setAlignment(Qt.AlignCenter); self.letter_label.setObjectName("letter")
		self.audio_panel.layout().addStretch(); self.audio_panel.layout().addWidget(self.letter_label); self.audio_panel.layout().addStretch()
		self.audio_accuracy = QLabel("Accuracy  —     Correct  0     Missed  0     False  0")
		self.audio_panel.layout().addWidget(self.audio_accuracy)
		panels.addWidget(self.visual_panel, 4); panels.addWidget(center, 3); panels.addWidget(self.audio_panel, 4)
		outer.addLayout(panels, 1)
		footer = QHBoxLayout(); self.status = QLabel("● Offline ready"); self.status.setObjectName("status")
		footer.addWidget(QLabel("A  Visual match     L  Audio match     Space  Pause/Resume     Esc  Stop     F11  Fullscreen"))
		footer.addStretch(); footer.addWidget(self.status); outer.addLayout(footer)
		self.setCentralWidget(root); self._resize_grid()

	def _panel(self, heading: str, hint: str) -> QFrame:
		frame = QFrame(); frame.setObjectName("panel"); layout = QVBoxLayout(frame); layout.setContentsMargins(18, 18, 18, 18); layout.setSpacing(12)
		h = QLabel(heading); h.setObjectName("panelTitle"); layout.addWidget(h)
		sub = QLabel(hint); sub.setWordWrap(True); sub.setObjectName("hint"); layout.addWidget(sub)
		return frame

	def _apply_theme(self) -> None:
		self.setStyleSheet("""
		QMainWindow,QWidget { background:#0b1020; color:#e7eaf4; font-family:'Segoe UI'; font-size:14px; }
		QFrame#panel { background:#131b2f; border:1px solid #25304a; border-radius:16px; }
		QLabel#title { font-size:25px; font-weight:800; letter-spacing:1px; }
		QLabel#panelTitle { color:#aab8d4; font-size:12px; font-weight:700; letter-spacing:1px; }
		QLabel#hint { color:#8491aa; font-size:12px; }
		QLabel#badge { background:#25234b; color:#aaa7ff; padding:8px 14px; border-radius:12px; font-weight:700; }
		QLabel#cell { background:#1b2740; border:1px solid #2b3a5b; border-radius:12px; min-width:35px; min-height:35px; }
		QLabel#letter { color:#aaa7ff; font-size:82px; font-weight:700; }
		QLabel#clock { font-size:36px; font-weight:700; color:#d5d9ff; padding:14px; }
		QLabel#sessionInfo { color:#abb7ce; padding:10px; }
		QLabel#status { color:#7de0b0; }
		QPushButton,QComboBox { background:#202b43; border:1px solid #344360; border-radius:9px; padding:10px 13px; }
		QPushButton:hover { background:#2b3a5b; } QPushButton#primary { background:#5b5bd6; border:0; font-weight:700; }
		QProgressBar { background:#202b43; border:0; border-radius:6px; height:12px; text-align:center; }
		QProgressBar::chunk { background:#7474ed; border-radius:6px; }
		QSpinBox,QDoubleSpinBox { background:#202b43; padding:6px; border-radius:6px; }
		""")

	def _resize_grid(self) -> None:
		size = self.settings["grid"]
		for i, cell in enumerate(self.cells):
			cell.setVisible(i < size * size)
			if i < size * size: self.visual_panel.layout().itemAt(2).layout().addWidget(cell, i // size, i % size)

	def _preset_changed(self, name: str) -> None:
		self.settings["preset"] = name
		if name in PRESETS:
			self.settings["n"], self.settings["trials"], self.settings["duration"] = PRESETS[name]
			self.settings["grid"] = 3
		elif name == "Custom":
			self.open_settings()
		self.level.setText(f"N={self.settings['n']}"); self._resize_grid(); self._save_settings()

	def open_settings(self) -> None:
		dialog = SettingsDialog(self.settings, self)
		if dialog.exec():
			self.settings.update(dialog.values()); self.settings["preset"] = "Custom"
			self.preset.blockSignals(True); self.preset.setCurrentText("Custom"); self.preset.blockSignals(False)
			self.level.setText(f"N={self.settings['n']}"); self._resize_grid(); self._save_settings()

	def _make_sequence(self) -> None:
		n, count, size = self.settings["n"], self.settings["trials"], self.settings["grid"] ** 2
		positions, letters = [], []
		alphabet = LETTERS if self.settings["letter_preset"] == "A–Z" else "ABCDEF"
		for i in range(count):
			if i >= n and self.settings["visual"] and random.random() < self.settings["match_probability"]:
				pos = positions[i - n]
			else: pos = random.randrange(size)
			if i >= n and self.settings["audio"] and random.random() < self.settings["audio_probability"]:
				letter = letters[i - n]
			else: letter = random.choice(alphabet)
			positions.append(pos); letters.append(letter)
		self.sequence = list(zip(positions, letters))

	def start_session(self) -> None:
		if self.state == "running": return
		self._make_sequence(); self.records = []; self.reactions = []; self.index = -1
		self.started_at = time.monotonic(); self.elapsed_before_pause = 0.0; self.state = "running"
		self.start_btn.setEnabled(False); self.preset.setEnabled(False); self.pause_btn.setText("Pause")
		self.session_info.setText("Session in progress — respond with A and/or L.")
		self._next_trial()

	def _next_trial(self) -> None:
		if self.state != "running": return
		self.index += 1
		if self.index >= len(self.sequence): self.finish_session(); return
		self.answers = {"visual": False, "audio": False}
		pos, letter = self.sequence[self.index]
		for i, cell in enumerate(self.cells):
			cell.setStyleSheet("background:#7979ed;border:2px solid #a6a4ff;border-radius:12px;" if i == pos else "")
		self.letter_label.setText(letter if self.settings["show_letter"] else "●")
		if self.settings["audio"]: self.speech.speak(letter, self.settings["voice_rate"], self.settings["volume"])
		if not self.settings["visual"]:
			for cell in self.cells: cell.setStyleSheet("")
		if not self.settings["audio"]: self.letter_label.setText("OFF")
		self.trial_label.setText(f"TRIAL  {self.index + 1} / {len(self.sequence)}")
		self.progress.setValue(int((self.index + 1) / len(self.sequence) * 100))
		self.timer_label.setText(time.strftime("%M:%S", time.gmtime(time.monotonic() - self.started_at)))
		self.records.append({"position": pos, "letter": letter, "visual_response": False, "audio_response": False,
							 "reaction": [], "time": time.monotonic()})
		self.trial_timer.start(int(self.settings["duration"] * 1000))

	def _respond(self, task: str) -> None:
		if self.state != "running" or self.index < self.settings["n"] or self.answers[task]: return
		self.answers[task] = True
		record = self.records[-1]; record[f"{task}_response"] = True
		rt = time.monotonic() - record["time"]; record["reaction"].append(rt); self.reactions.append(rt)
		if task == "visual": self.status.setText("● Visual response registered")
		else: self.status.setText("● Audio response registered")

	def pause_resume(self) -> None:
		if self.state == "running":
			self.elapsed_before_pause = time.monotonic() - self.started_at
			self.trial_timer.stop(); self.state = "paused"; self.pause_btn.setText("Resume")
			self.session_info.setText("Paused — press Space or Resume to continue.")
		elif self.state == "paused":
			self.started_at = time.monotonic() - self.elapsed_before_pause
			self.state = "running"; self.pause_btn.setText("Pause"); self.session_info.setText("Session in progress.")
			self.trial_timer.start(int(self.settings["duration"] * 1000)); self._refresh_clock()

	def _refresh_clock(self) -> None:
		self.timer_label.setText(time.strftime("%M:%S", time.gmtime(time.monotonic() - self.started_at)))

	def stop_session(self) -> None:
		if self.state in ("running", "paused"):
			self.trial_timer.stop(); self.finish_session(stopped=True)

	def _metrics(self) -> dict:
		n = self.settings["n"]; valid = self.records[n:]
		result = {}
		for task, enabled in (("visual", self.settings["visual"]), ("audio", self.settings["audio"])):
			hits = misses = false = correct_rejects = 0
			if enabled:
				for i, row in enumerate(valid, start=n):
					match = row["position" if task == "visual" else "letter"] == self.sequence[i - n][0 if task == "visual" else 1]
					response = row[f"{task}_response"]
					if match and response: hits += 1
					elif match: misses += 1
					elif response: false += 1
					else: correct_rejects += 1
			result[task] = {"hits": hits, "missed": misses, "false": false,
							"accuracy": (hits + correct_rejects) / len(valid) if valid and enabled else 0.0}
		enabled_count = sum((result[t]["accuracy"] for t in result if self.settings[t]))
		task_count = sum((1 for t in result if self.settings[t]))
		result["overall"] = enabled_count / task_count if task_count else 0
		result["correct"] = result["visual"]["hits"] + result["audio"]["hits"]
		result["missed"] = result["visual"]["missed"] + result["audio"]["missed"]
		result["false"] = result["visual"]["false"] + result["audio"]["false"]
		result["reaction"] = sum(self.reactions) / len(self.reactions) if self.reactions else 0
		return result

	def finish_session(self, stopped: bool = False) -> None:
		self.trial_timer.stop(); self.state = "idle"; self.start_btn.setEnabled(True); self.preset.setEnabled(True)
		self.pause_btn.setText("Pause"); self.session_info.setText("Session stopped." if stopped else "Session complete.")
		if not self.records: return
		metrics = self._metrics(); duration = max(0, time.monotonic() - self.started_at)
		try:
			with sqlite3.connect(self.db_path) as db:
				db.execute("INSERT INTO sessions(completed_at,preset,n,trials,duration,visual_accuracy,audio_accuracy,overall_accuracy,correct,missed,false_positives,avg_reaction,details) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
						   (datetime.now().isoformat(timespec="seconds"), self.settings["preset"], self.settings["n"], len(self.records), duration,
							metrics["visual"]["accuracy"], metrics["audio"]["accuracy"], metrics["overall"], metrics["correct"], metrics["missed"], metrics["false"], metrics["reaction"], json.dumps(metrics)))
		except sqlite3.Error as exc: QMessageBox.warning(self, "Save error", f"Could not save session:\n{exc}")
		self.visual_accuracy.setText(f"Accuracy  {metrics['visual']['accuracy']:.0%}     Correct  {metrics['visual']['hits']}     Missed  {metrics['visual']['missed']}     False  {metrics['visual']['false']}")
		self.audio_accuracy.setText(f"Accuracy  {metrics['audio']['accuracy']:.0%}     Correct  {metrics['audio']['hits']}     Missed  {metrics['audio']['missed']}     False  {metrics['audio']['false']}")
		self._show_report(metrics, duration, stopped)

	def _show_report(self, m: dict, duration: float, stopped: bool) -> None:
		text = (f"{'Session stopped' if stopped else 'Session complete'}  ·  N={self.settings['n']}\n\n"
				f"Overall accuracy: {m['overall']:.1%}\nVisual accuracy: {m['visual']['accuracy']:.1%}\n"
				f"Audio accuracy: {m['audio']['accuracy']:.1%}\nCorrect matches: {m['correct']}\n"
				f"Missed matches: {m['missed']}\nFalse positives: {m['false']}\n"
				f"Average reaction: {m['reaction']:.2f} sec\nSession time: {int(duration)//60:02}:{int(duration)%60:02}")
		QMessageBox.information(self, "Performance report", text)

	def show_statistics(self) -> None:
		dialog = QDialog(self); dialog.setWindowTitle("Training history"); dialog.resize(680, 420)
		layout = QVBoxLayout(dialog); heading = QLabel("RECENT SESSIONS"); heading.setObjectName("panelTitle"); layout.addWidget(heading)
		rows = []
		try:
			with sqlite3.connect(self.db_path) as db:
				rows = db.execute("SELECT completed_at,preset,n,trials,overall_accuracy,visual_accuracy,audio_accuracy FROM sessions ORDER BY id DESC LIMIT 50").fetchall()
		except sqlite3.Error as exc: rows = [(f"Database error: {exc}", "", 0, 0, 0, 0, 0)]
		table = QLabel("DATE                         PRESET       N   TRIALS   OVERALL   VISUAL   AUDIO\n" + "\n".join(
			f"{r[0]:19}  {r[1]:12} {r[2]:2}   {r[3]:3}       {r[4]:5.0%}     {r[5]:5.0%}    {r[6]:5.0%}" for r in rows) if rows else "No saved sessions yet.")
		table.setTextInteractionFlags(Qt.TextSelectableByMouse); table.setStyleSheet("font-family:Consolas; color:#c8d2e8;"); layout.addWidget(table)
		buttons = QHBoxLayout(); export = QPushButton("Export CSV…"); close = QPushButton("Close"); buttons.addWidget(export); buttons.addStretch(); buttons.addWidget(close); layout.addLayout(buttons)
		export.clicked.connect(self.export_csv); close.clicked.connect(dialog.accept); dialog.exec()

	def export_csv(self) -> None:
		filename, _ = QFileDialog.getSaveFileName(self, "Export training history", str(APP_DIR / "exports" / "sessions.csv"), "CSV files (*.csv)")
		if not filename: return
		try:
			with sqlite3.connect(self.db_path) as db:
				rows = db.execute("SELECT completed_at,preset,n,trials,duration,visual_accuracy,audio_accuracy,overall_accuracy,correct,missed,false_positives,avg_reaction FROM sessions ORDER BY id").fetchall()
			with open(filename, "w", newline="", encoding="utf-8-sig") as out:
				writer = csv.writer(out); writer.writerow(["completed_at", "preset", "n", "trials", "duration_sec", "visual_accuracy", "audio_accuracy", "overall_accuracy", "correct", "missed", "false_positives", "avg_reaction_sec"]); writer.writerows(rows)
			QMessageBox.information(self, "Export", "Training history exported.")
		except (OSError, sqlite3.Error) as exc: QMessageBox.warning(self, "Export error", str(exc))

	def show_help(self) -> None:
		QMessageBox.information(self, "Dual N-Back Pro", "Each trial, compare the visual position and spoken letter with the stimulus N trials earlier.\n\nA = visual match   L = audio match\nSpace = pause/resume   Esc = stop   F11 = fullscreen\nOnly trials after the initial N are scored. Speech is offline and requires pyttsx3/SAPI.")

	def keyPressEvent(self, event: QKeyEvent) -> None:
		if event.isAutoRepeat(): return
		if event.key() == Qt.Key_A: self._respond("visual")
		elif event.key() == Qt.Key_L: self._respond("audio")
		elif event.key() == Qt.Key_Space: self.pause_resume()
		elif event.key() == Qt.Key_Escape: self.stop_session()
		elif event.key() == Qt.Key_F11: self.showNormal() if self.isFullScreen() else self.showFullScreen()
		else: super().keyPressEvent(event)

	def closeEvent(self, event) -> None:
		if self.state in ("running", "paused"):
			self.trial_timer.stop()
			answer = QMessageBox.question(self, "Exit", "Stop the current session and exit?", QMessageBox.Yes | QMessageBox.No)
			if answer != QMessageBox.Yes: event.ignore(); return
		self._save_settings(); event.accept()


def main() -> int:
	app = QApplication(sys.argv)
	app.setApplicationName("Dual N-Back Pro")
	window = DualNBackWindow(); window.show()
	return app.exec()


if __name__ == "__main__":
	raise SystemExit(main())
