"""Floating, state-driven HUD for AURA."""

import math

from PyQt6.QtCore import QPoint, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QWidget

from core.events import AURAEvent
from core.state import AURAState


class AuraHUD(QWidget):
	"""Small always-on-top orb that visualizes AURA's current state."""

	event_signal = pyqtSignal(object)

	COLORS = {
		AURAState.SLEEPING: QColor("#52606d"),
		AURAState.WAKING: QColor("#f6bd60"),
		AURAState.LISTENING: QColor("#4ecdc4"),
		AURAState.PROCESSING: QColor("#6c8cff"),
		AURAState.THINKING: QColor("#9b87f5"),
		AURAState.EXECUTING: QColor("#f28482"),
		AURAState.SPEAKING: QColor("#70d6ff"),
		AURAState.ERROR: QColor("#ef476f"),
	}

	def __init__(self):
		super().__init__()
		self.state = AURAState.SLEEPING
		self.last_event = "sleeping"
		self.pulse = 0.0
		self.setFixedSize(112, 112)
		self.setWindowTitle("AURA")
		self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
		self.setWindowFlags(
			self.windowFlags()
			| Qt.WindowType.FramelessWindowHint
			| Qt.WindowType.Tool
			| Qt.WindowType.WindowStaysOnTopHint
		)
		self.event_signal.connect(self._apply_event)

		self.timer = QTimer(self)
		self.timer.timeout.connect(self._animate)
		self.timer.start(40)

	def place_top_right(self):
		screen = QApplication.primaryScreen()
		if screen:
			available = screen.availableGeometry()
			self.move(available.right() - self.width() - 24, available.top() + 24)

	def receive_event(self, event: AURAEvent):
		"""Queue an event safely from the assistant worker thread."""
		self.event_signal.emit(event)

	def _apply_event(self, event: AURAEvent):
		if event.state is not None:
			self.state = event.state
		self.last_event = event.name
		self.update()

	def _animate(self):
		self.pulse = (self.pulse + 0.08) % (math.pi * 2)
		self.update()

	def paintEvent(self, event):
		del event
		painter = QPainter(self)
		painter.setRenderHint(QPainter.RenderHint.Antialiasing)

		center = self.rect().center()
		color = self.COLORS.get(self.state, self.COLORS[AURAState.SLEEPING])
		active = self.state != AURAState.SLEEPING
		pulse = (math.sin(self.pulse) + 1.0) / 2.0
		radius = 19 + (5 * pulse if active else 0)

		glow = QColor(color)
		glow.setAlpha(35 if active else 18)
		painter.setBrush(glow)
		painter.setPen(QPen(glow, 1))
		painter.drawEllipse(center, int(radius + 17), int(radius + 17))

		ring = QColor(color)
		ring.setAlpha(180 if active else 90)
		painter.setBrush(QColor(15, 23, 42, 215))
		painter.setPen(QPen(ring, 2))
		painter.drawEllipse(center, int(radius + 7), int(radius + 7))

		painter.setBrush(color)
		painter.setPen(QPen(color.lighter(125), 1))
		painter.drawEllipse(center, int(radius), int(radius))

		if self.state in {AURAState.THINKING, AURAState.EXECUTING}:
			painter.setBrush(QColor(255, 255, 255, 210))
			orbit = radius + 14
			angle = self.pulse * 2.0
			dot = QPoint(
				int(center.x() + math.cos(angle) * orbit),
				int(center.y() + math.sin(angle) * orbit),
			)
			painter.drawEllipse(dot, 3, 3)

		painter.end()
