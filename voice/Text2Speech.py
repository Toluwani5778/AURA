"""Text-to-speech through the Kokoro container, with sentence streaming.

Speaker.say() queues a sentence and returns immediately. One thread
synthesizes ahead while another plays, so the next sentence is ready by the
time the current one finishes. stop() cuts playback off (barge-in).
"""

import logging
import os
import queue
import subprocess
import tempfile
import threading
import time

import requests

from core.config import TTS_API_URL, TTS_SPEED, TTS_VOICE

log = logging.getLogger("aura.tts")


def synthesize(text: str) -> bytes:
    response = requests.post(
        f"{TTS_API_URL}/v1/audio/speech",
        json={"model": "kokoro", "input": text, "voice": TTS_VOICE,
              "response_format": "wav", "speed": TTS_SPEED},
        timeout=(3, 60),
    )
    response.raise_for_status()
    return response.content


def kokoro_ready() -> bool:
    try:
        return requests.get(f"{TTS_API_URL}/v1/audio/voices", timeout=2).ok
    except requests.RequestException:
        return False


class Speaker:
    def __init__(self, player=None, synth=synthesize):
        self.player = player or (["pw-play"] if _has("pw-play") else ["aplay", "-q"])
        self.synth = synth
        self._text_q: "queue.Queue" = queue.Queue()
        self._audio_q: "queue.Queue" = queue.Queue()
        self._pending = 0
        self._lock = threading.Lock()
        self._proc = None
        self._generation = 0              # bumped by stop() to discard queued audio
        self.quiet_since = time.time()
        self.on_start = lambda text: None
        self.on_idle = lambda: None
        self._tmp = tempfile.mkdtemp(prefix="aura-tts-")
        threading.Thread(target=self._synth_loop, name="aura-tts-synth", daemon=True).start()
        threading.Thread(target=self._play_loop, name="aura-tts-play", daemon=True).start()

    # public -------------------------------------------------------------
    def say(self, text: str) -> None:
        if not text.strip():
            return
        with self._lock:
            self._pending += 1
        self._text_q.put((self._generation, text))

    @property
    def speaking(self) -> bool:
        return self._pending > 0

    def wait(self, timeout=120) -> None:
        deadline = time.time() + timeout
        while self.speaking and time.time() < deadline:
            time.sleep(0.05)

    def stop(self) -> None:
        self._generation += 1
        proc = self._proc
        if proc and proc.poll() is None:
            proc.terminate()

    # workers ------------------------------------------------------------
    def _done_one(self):
        with self._lock:
            self._pending = max(0, self._pending - 1)
            idle = self._pending == 0
        if idle:
            self.quiet_since = time.time()
            self.on_idle()

    def _synth_loop(self):
        n = 0
        while True:
            gen, text = self._text_q.get()
            if gen != self._generation:
                self._done_one()
                continue
            try:
                audio = self.synth(text)
            except Exception as error:
                log.error("TTS failed: %s", error)
                self._done_one()
                continue
            n += 1
            path = os.path.join(self._tmp, f"{n % 8}.wav")
            with open(path, "wb") as f:
                f.write(audio)
            self._audio_q.put((gen, text, path))

    def _play_loop(self):
        while True:
            gen, text, path = self._audio_q.get()
            if gen == self._generation:
                self.on_start(text)
                try:
                    self._proc = subprocess.Popen(self.player + [path], stdout=subprocess.DEVNULL,
                                                  stderr=subprocess.DEVNULL)
                    self._proc.wait()
                except OSError as error:
                    log.error("Playback failed: %s", error)
                finally:
                    self._proc = None
            self._done_one()


def _has(cmd):
    from shutil import which
    return which(cmd) is not None


# Backwards-compatible helpers --------------------------------------------
def speak(text, path="resources/audio/Output/output.wav"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(synthesize(text))
    return path


def play_audio(file):
    subprocess.run(["aplay", "-q", file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
