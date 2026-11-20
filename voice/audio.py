"""Microphone input: one PyAudio stream shared by wake word, VAD and STT."""

import collections
import logging
import queue
import threading
import time
from typing import Callable, Optional

import numpy as np
import pyaudio

from core.alsa import suppress_alsa_errors
from core.config import (
    AUDIO_CHANNELS, AUDIO_FRAMES_PER_BUFFER, AUDIO_RATE, ECHO_TAIL_MS,
    MAX_UTTERANCE_SECONDS, VAD_END_SILENCE_MS, VAD_MIN_SPEECH_MS, VAD_PRE_ROLL_MS,
    VAD_THRESHOLD, WAKEWORD_KEY, WAKEWORD_MODEL_PATH, WAKEWORD_THRESHOLD,
)

log = logging.getLogger("aura.audio")
FRAME_MS = AUDIO_FRAMES_PER_BUFFER * 1000 // AUDIO_RATE   # 80 ms


class Microphone:
    """Background reader that pushes 80 ms int16 frames into a queue."""

    def __init__(self):
        with suppress_alsa_errors():
            self.pa = pyaudio.PyAudio()
            self.stream = self.pa.open(
                format=pyaudio.paInt16, channels=AUDIO_CHANNELS, rate=AUDIO_RATE,
                input=True, frames_per_buffer=AUDIO_FRAMES_PER_BUFFER,
            )
        self.frames: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=400)
        self.level = 0.0                     # RMS 0..1, for the HUD
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, name="aura-mic", daemon=True)
        self._thread.start()

    def _read_loop(self):
        while self._running:
            try:
                data = self.stream.read(AUDIO_FRAMES_PER_BUFFER, exception_on_overflow=False)
            except OSError as error:
                log.warning("mic read failed: %s", error)
                time.sleep(0.1)
                continue
            frame = np.frombuffer(data, dtype=np.int16)
            self.level = float(np.sqrt(np.mean((frame / 32768.0) ** 2)))
            if self.frames.full():
                self.frames.get_nowait()     # drop oldest rather than block
            self.frames.put(frame)

    def read(self, timeout=1.0) -> Optional[np.ndarray]:
        try:
            return self.frames.get(timeout=timeout)
        except queue.Empty:
            return None

    def flush(self):
        while not self.frames.empty():
            self.frames.get_nowait()

    def close(self):
        self._running = False
        self._thread.join(timeout=1)
        try:
            self.stream.stop_stream()
            self.stream.close()
        finally:
            self.pa.terminate()


class WakeWord:
    def __init__(self, path=WAKEWORD_MODEL_PATH, key=WAKEWORD_KEY, threshold=WAKEWORD_THRESHOLD):
        import openwakeword
        self.model = openwakeword.Model(wakeword_models=[path], inference_framework="onnx")
        self.key = key if key in self.model.models else next(iter(self.model.models))
        self.threshold = threshold
        self.peak = 0.0

    def score(self, frame: np.ndarray) -> float:
        value = float(self.model.predict(frame)[self.key])
        self.peak = max(self.peak, value)
        return value

    def detected(self, frame: np.ndarray) -> bool:
        if self.score(frame) >= self.threshold:
            log.info("wake word (score %.2f)", self.peak)
            self.reset()
            return True
        return False

    def reset(self):
        self.model.reset()
        self.peak = 0.0


class VAD:
    """Stateful Silero VAD (bundled with OpenWakeWord)."""

    def __init__(self):
        from openwakeword.vad import VAD as SileroVAD
        self.model = SileroVAD()

    def is_speech(self, frame: np.ndarray) -> bool:
        return self.model.predict(frame, frame_size=640) >= VAD_THRESHOLD

    def reset(self):
        self.model.reset_states()


class Listener:
    """Turns the raw mic into wake events and complete utterances."""

    def __init__(self, mic: Microphone, is_speaking: Callable[[], bool] = lambda: False,
                 quiet_since: Callable[[], float] = lambda: 0.0):
        self.mic = mic
        self.wake = WakeWord()
        self.vad = VAD()
        self.is_speaking = is_speaking
        self.quiet_since = quiet_since

    def _echo_guard(self) -> bool:
        """True while AURA's own voice may be in the mic."""
        return self.is_speaking() or (time.time() - self.quiet_since()) * 1000 < ECHO_TAIL_MS

    def wait_for_wake_word(self, should_stop: Callable[[], bool] = lambda: False) -> bool:
        self.mic.flush()
        self.wake.reset()
        while not should_stop():
            frame = self.mic.read()
            if frame is not None and self.wake.detected(frame):
                return True
        return False

    def check_barge_in(self, frame: np.ndarray) -> bool:
        return self.wake.detected(frame)

    def record_utterance(self, wait_seconds: float,
                         on_speech_start: Callable[[], None] = lambda: None,
                         on_barge_in: Callable[[], None] = lambda: None) -> Optional[np.ndarray]:
        """Wait up to `wait_seconds` for speech to start, then record until the
        speaker pauses. Returns float32 audio or None if nobody spoke."""
        self.vad.reset()
        pre_roll = collections.deque(maxlen=max(1, VAD_PRE_ROLL_MS // FRAME_MS))
        speech, voiced_ms, silence_ms = [], 0, 0
        started = False
        deadline = time.time() + wait_seconds
        max_frames = MAX_UTTERANCE_SECONDS * 1000 // FRAME_MS

        while True:
            frame = self.mic.read(timeout=0.5)
            if frame is None:
                if not started and time.time() > deadline:
                    return None
                continue
            if self._echo_guard():
                # Half-duplex: ignore our own voice, but listen for the wake
                # word so the user can interrupt.
                if self.is_speaking() and self.check_barge_in(frame):
                    on_barge_in()
                deadline = max(deadline, time.time() + 1)
                continue

            voiced = self.vad.is_speech(frame)
            if not started:
                pre_roll.append(frame)
                voiced_ms = voiced_ms + FRAME_MS if voiced else 0
                if voiced_ms >= VAD_MIN_SPEECH_MS:
                    started = True
                    speech.extend(pre_roll)
                    on_speech_start()
                elif time.time() > deadline:
                    return None
                continue

            speech.append(frame)
            silence_ms = 0 if voiced else silence_ms + FRAME_MS
            if silence_ms >= VAD_END_SILENCE_MS or len(speech) >= max_frames:
                break

        return np.concatenate(speech).astype(np.float32) / 32768.0
