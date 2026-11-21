"""AURA's HUD: an aurora glow along the bottom of the screen plus a status pill.

The window is transparent, frameless, always on top and click-through, so it
never blocks the panel or the apps beneath it. It only *observes* the engine
through events and never drives assistant logic.

Runs through XWayland (QT_QPA_PLATFORM=xcb) because native Wayland ignores
window positioning.
"""

import math
import random
import time

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QRadialGradient
from PyQt6.QtWidgets import QApplication, QWidget

from core.events import AURAEvent
from core.state import AURAState

# Each state: (palette of aurora colours, base intensity 0..1)
LOOKS = {
    AURAState.SLEEPING:   (["#2b3a55", "#3d2c5c"], 0.00),
    AURAState.WAKING:     (["#ffd27a", "#ff9fb2", "#a58bff"], 0.65),
    AURAState.LISTENING:  (["#38f9d7", "#43e97b", "#4facfe"], 0.45),
    AURAState.PROCESSING: (["#4facfe", "#8e7dff", "#38f9d7"], 0.60),
    AURAState.THINKING:   (["#8e7dff", "#c471f5", "#4facfe"], 0.70),
    AURAState.EXECUTING:  (["#ffb86b", "#ff6f91", "#c471f5"], 0.75),
    AURAState.SPEAKING:   (["#4facfe", "#c471f5", "#38f9d7", "#ff9fb2"], 0.80),
    AURAState.ERROR:      (["#ff4d6d", "#ff8fa3"], 0.70),
}

THINKING_WORDS = ["Pondering", "Mulling it over", "Connecting the dots", "Musing", "Brewing ideas",
                  "Consulting the stars", "Untangling", "Daydreaming productively", "Weaving thoughts",
                  "Shimmering", "Ruminating", "Gathering stardust"]
TOOL_WORDS = {
    "open_app": "Opening {name}", "close_app": "Closing {name}", "web_search": "Searching the web",
    "weather": "Checking the sky", "volume": "Adjusting volume", "media": "Working the music",
    "open_in_browser": "Opening the browser", "system_status": "Checking vitals", "remember": "Noting that down",
    "forget": "Forgetting", "power": "Standing by", "lock_screen": "Locking up", "get_datetime": "Checking the clock",
    "list_apps": "Looking through your apps", "look_at_screen": "Looking at your screen",
}
from core.config import HUD_HEIGHT as HALO_HEIGHT, HUD_OPACITY, HUD_PILL_OPACITY


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t))


class AuraHUD(QWidget):
    event_signal = pyqtSignal(object)

    def __init__(self, level_source=lambda: 0.0):
        super().__init__()
        self.level_source = level_source
        self.state = AURAState.SLEEPING
        self.label = ""
        self.caption = ""
        self.caption_until = 0.0
        self.intensity = 0.0          # smoothed, what we draw
        self.level = 0.0              # smoothed mic / voice energy
        self.colors = [QColor(c) for c in LOOKS[AURAState.SLEEPING][0]]
        self.target_colors = list(self.colors)
        self.t0 = time.time()
        self.seeds = [random.random() * 10 for _ in range(6)]

        self.setWindowTitle("AURA")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                            | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput
                            | Qt.WindowType.WindowDoesNotAcceptFocus | Qt.WindowType.X11BypassWindowManagerHint)
        self.event_signal.connect(self._apply_event)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)

    # placement ---------------------------------------------------------
    def place(self):
        screen = QApplication.primaryScreen()
        if screen:
            g = screen.geometry()
            self.setGeometry(g.x(), g.bottom() - HALO_HEIGHT + 1, g.width(), HALO_HEIGHT)

    place_top_right = place   # backwards compatibility

    # events ------------------------------------------------------------
    def receive_event(self, event: AURAEvent):
        """Thread-safe: called from the assistant thread."""
        self.event_signal.emit(event)

    def _apply_event(self, event: AURAEvent):
        if event.state is not None and event.state != self.state:
            self.state = event.state
            self.target_colors = [QColor(c) for c in LOOKS[self.state][0]]
            self.label = {
                AURAState.SLEEPING: "",
                AURAState.WAKING: "Waking up",
                AURAState.LISTENING: "Listening",
                AURAState.PROCESSING: "Hmm…",
                AURAState.THINKING: random.choice(THINKING_WORDS) + "…",
                AURAState.EXECUTING: "On it…",
                AURAState.SPEAKING: "",
                AURAState.ERROR: "Something went wrong",
            }.get(self.state, "")
        data = event.data
        if event.name == "tool_started":
            words = TOOL_WORDS.get(data.get("tool", ""), "Working on it")
            self.label = words.format(name=str(data.get("args", {}).get("name", "it")).title()) + "…"
        elif event.name == "transcript_received":
            self._show_caption("“" + data.get("text", "") + "”")
        elif event.name == "response_started":
            self._show_caption(data.get("text", ""))
        elif event.name == "error":
            self._show_caption(str(data.get("error", ""))[:120])

    def _show_caption(self, text, seconds=None):
        self.caption = text
        self.caption_until = time.time() + (seconds or max(3.0, len(text) / 14))

    # animation ---------------------------------------------------------
    def _tick(self):
        base = LOOKS[self.state][1]
        raw = float(self.level_source() or 0.0)
        if self.state in (AURAState.LISTENING, AURAState.SPEAKING):
            self.level += (min(1.0, raw * 12) - self.level) * 0.3
        else:
            self.level *= 0.9
        target = base + 0.25 * self.level
        self.intensity += (target - self.intensity) * 0.08
        if len(self.target_colors) != len(self.colors):
            self.colors = (self.colors * 4)[:len(self.target_colors)]
        self.colors = [_mix(c, t, 0.06) for c, t in zip(self.colors, self.target_colors)]
        if self.intensity > 0.003 or self.caption:
            self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        t = time.time() - self.t0
        k = self.intensity
        if k > 0.003:
            speed = 0.35 if self.state != AURAState.THINKING else 0.9
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            n = len(self.colors)
            for i, color in enumerate(self.colors * 2):
                seed = self.seeds[i % len(self.seeds)]
                x = w * (0.5 + 0.42 * math.sin(t * speed * (0.6 + 0.15 * i) + seed))
                breathe = 0.85 + 0.15 * math.sin(t * 1.7 + seed)
                ry = h * (0.45 + 0.25 * self.level) * breathe
                rx = w * (0.22 + 0.06 * math.sin(t * 0.5 + seed))
                # Draw a circle in a vertically squashed space -> soft ellipse
                sy = ry / rx
                cy = (h + ry * 0.05) / sy
                grad = QRadialGradient(QPointF(x, cy), rx)
                c0 = QColor(color); c0.setAlphaF(min(1.0, HUD_OPACITY * k * (1 if i < n else 0.6)))
                c1 = QColor(color); c1.setAlphaF(0.0)
                grad.setColorAt(0.0, c0)
                grad.setColorAt(1.0, c1)
                p.save()
                p.scale(1.0, sy)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(grad)
                p.drawEllipse(QPointF(x, cy), rx, rx)
                p.restore()
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            # thin bright line hugging the screen edge
            edge = QColor(self.colors[0]); edge.setAlphaF(min(1.0, HUD_OPACITY * 1.5 * k))
            p.fillRect(QRectF(0, h - 2, w, 2), edge)

        text = self.label
        if self.caption and time.time() < self.caption_until:
            text = self.caption if not self.label else f"{self.label}   {self.caption}"
        elif self.caption:
            self.caption = ""
        if text and k > 0.05:
            self._draw_pill(p, text, w, h, k)
        p.end()

    def _draw_pill(self, p, text, w, h, k):
        font = QFont("Inter", 13)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        p.setFont(font)
        fm = QFontMetrics(font)
        text = fm.elidedText(text, Qt.TextElideMode.ElideRight, int(w * 0.5))
        tw = fm.horizontalAdvance(text)
        pw, ph = tw + 44, fm.height() + 18
        rect = QRectF((w - pw) / 2, max(2, h - ph - 52), pw, ph)
        path = QPainterPath()
        path.addRoundedRect(rect, ph / 2, ph / 2)
        bg = QColor(12, 14, 28); bg.setAlphaF(min(HUD_PILL_OPACITY, k * 1.2))
        p.fillPath(path, bg)
        rim = QColor(self.colors[0]); rim.setAlphaF(min(0.9, k * 1.3))
        p.setPen(rim)
        p.drawPath(path)
        fg = QColor(240, 244, 255); fg.setAlphaF(min(1.0, k * 1.6))
        p.setPen(fg)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


def demo():
    """`python -m ui.orb` cycles through every state for a visual check."""
    import os
    import sys
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
    app = QApplication(sys.argv)
    hud = AuraHUD(level_source=lambda: abs(math.sin(time.time() * 3)) * 0.06)
    hud.place()
    hud.show()
    states = [AURAState.WAKING, AURAState.LISTENING, AURAState.THINKING, AURAState.EXECUTING,
              AURAState.SPEAKING, AURAState.SLEEPING]
    idx = [0]

    def step():
        s = states[idx[0] % len(states)]
        hud.receive_event(AURAEvent("state_changed", s))
        if s == AURAState.SPEAKING:
            hud.receive_event(AURAEvent("response_started", s, {"text": "Good afternoon! How's your day going?"}))
        idx[0] += 1

    step()
    timer = QTimer(); timer.timeout.connect(step); timer.start(2500)
    QTimer.singleShot(2500 * len(states) + 500, app.quit)
    app.exec()


if __name__ == "__main__":
    demo()
