"""AURA - Adaptive Utility & Reasoning Assistant.

    python main.py                 voice mode with HUD; greets you on start
    python main.py --no-greet      start asleep, wait for "Aura, wake up"
    python main.py --text          type to AURA in the terminal (no mic/TTS/HUD)
    python main.py --tune-wakeword print live wake-word scores to pick a threshold
"""

import argparse
import logging
import os
import sys
import threading
import time

from core.config import (
    CHECK_IN_WINDOW, DATA_DIR, FOLLOW_UP_WINDOW, LOG_FILE, USER_NAME,
)
from core.events import EventPublisher
from core.state import AURAState

log = logging.getLogger("aura")


def setup_logging(verbose=False):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(LOG_FILE)],
    )
    for noisy in ("urllib3", "faster_whisper", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


class AuraAssistant:
    """Wires microphone, agent, speaker and HUD together."""

    def __init__(self, events: EventPublisher = None):
        self.events = events or EventPublisher()
        self.state = AURAState.SLEEPING
        self.running = True
        self.in_conversation = False
        self.mic = None
        self.speaker = None
        self.listener = None
        self.agent = None
        self.session = None

    # events -------------------------------------------------------------
    def set_state(self, state: AURAState, **data):
        self.state = state
        self.events.publish("state_changed", state=state, **data)

    def emit(self, name: str, **data):
        return self.events.publish(name, state=self.state, **data)

    @property
    def level(self) -> float:
        if self.speaker and self.speaker.speaking:
            return 0.04 + 0.03 * abs(((time.time() * 7) % 2) - 1)   # gentle shimmer while talking
        return self.mic.level if self.mic else 0.0

    # startup ------------------------------------------------------------
    def start(self):
        from core.agent import Agent
        from core.llm import OllamaClient
        from voice.audio import Listener, Microphone
        from voice.Text2Speech import Speaker, kokoro_ready

        self.set_state(AURAState.WAKING)
        client = OllamaClient()
        if not client.wait_until_ready(timeout=180):
            raise RuntimeError("Ollama is not reachable")
        for _ in range(90):                      # Kokoro is a Docker container; give it time
            if kokoro_ready():
                break
            time.sleep(2)
        else:
            raise RuntimeError("Kokoro TTS is not reachable on its port")
        threading.Thread(target=client.warm, daemon=True).start()
        threading.Thread(target=self._preload_whisper, daemon=True).start()

        self.agent = Agent(client=client, on_tool=self._on_tool)
        self.speaker = Speaker()
        self.speaker.on_start = self._on_speech_start
        self.speaker.on_idle = self._on_speech_idle
        self.mic = Microphone()
        self.listener = Listener(self.mic, is_speaking=lambda: self.speaker.speaking,
                                 quiet_since=lambda: self.speaker.quiet_since)

    @staticmethod
    def _preload_whisper():
        from voice.Speech2Text import get_model
        get_model()

    # callbacks ----------------------------------------------------------
    def _on_tool(self, name, args):
        self.set_state(AURAState.EXECUTING, tool=name)
        self.emit("tool_started", tool=name, args=args)

    def _on_speech_start(self, text):
        if self.state != AURAState.SPEAKING:
            self.set_state(AURAState.SPEAKING)
        self.emit("response_started", text=text)

    def _on_speech_idle(self):
        if self.in_conversation and self.state == AURAState.SPEAKING:
            self.set_state(AURAState.LISTENING)

    def _barge_in(self):
        log.info("Interrupted by wake word")
        self.speaker.stop()
        self.emit("barge_in")

    # conversation -------------------------------------------------------
    def say(self, text):
        self.session.add("assistant", text)
        self.speaker.say(text)

    def converse(self, first_of_day=False):
        """One conversation: greet, then talk until goodbye or silence."""
        from core.memory import SessionLog
        from voice.Speech2Text import transcribe

        self.in_conversation = True
        self.session = SessionLog()
        self.agent.reset()
        self.set_state(AURAState.THINKING)
        try:
            greeting = self.agent.greet(on_sentence=self.speaker.say, first_of_day=first_of_day)
        except Exception as error:
            log.warning("Greeting failed: %s", error)
            greeting = "Hi! I'm here. What can I do for you?"
            self.speaker.say(greeting)
        log.info("AURA: %s", greeting)
        self.session.add("assistant", greeting)
        checked_in = False

        try:
            while self.running:
                if not self.speaker.speaking:
                    self.set_state(AURAState.LISTENING)
                audio = self.listener.record_utterance(
                    wait_seconds=CHECK_IN_WINDOW if checked_in else FOLLOW_UP_WINDOW,
                    on_speech_start=lambda: self.set_state(AURAState.LISTENING, speech=True),
                    on_barge_in=self._barge_in,
                )
                if audio is None:
                    if self.speaker.speaking:
                        continue
                    if checked_in:
                        self.say("I'll let you get to it. Just say Aura, wake up when you need me.")
                        break
                    checked_in = True
                    self.say("Still there? Take your time.")
                    continue

                self.set_state(AURAState.PROCESSING)
                text = transcribe(audio)
                if not text:
                    continue
                checked_in = False
                log.info("You: %s", text)
                self.emit("transcript_received", text=text)
                self.session.add("user", text)

                self.set_state(AURAState.THINKING)
                try:
                    reply = self.agent.respond(text, on_sentence=self.speaker.say)
                except Exception as error:
                    log.exception("Agent failed")
                    self.set_state(AURAState.ERROR, error=str(error))
                    self.emit("error", error=str(error), operation="agent")
                    reply = "Sorry, my brain hiccuped. Could you say that again?"
                    self.speaker.say(reply)
                log.info("AURA: %s", reply)
                self.session.add("assistant", reply)
                if self.agent.end_requested:
                    break
        finally:
            self.speaker.wait()
            self.in_conversation = False
            self.session.save()
            self.emit("session_ended", session_name=self.session.name)

    def run(self, greet=True):
        try:
            self.start()
            if greet:
                self.converse(first_of_day=True)
            while self.running:
                self.set_state(AURAState.SLEEPING)
                log.info("Sleeping. Say 'Aura, wake up'.")
                if self.listener.wait_for_wake_word(should_stop=lambda: not self.running):
                    self.emit("wakeword_detected")
                    self.converse()
        except Exception as error:
            log.exception("Fatal error")
            self.set_state(AURAState.ERROR, error=str(error))
            self.emit("error", error=str(error), operation="main_loop")
            raise
        finally:
            self.shutdown()

    def shutdown(self):
        self.running = False
        if self.speaker:
            self.speaker.stop()
        if self.mic:
            self.mic.close()
            self.mic = None
        self.set_state(AURAState.SLEEPING)


# ---------------------------------------------------------------------------
def run_text_mode():
    from core.agent import Agent
    agent = Agent(on_tool=lambda name, args: print(f"   ⚙ {name} {args}"))
    print("AURA text mode. Ctrl+D to quit.\n")
    print("AURA:", agent.greet())
    while True:
        try:
            text = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if text:
            print("AURA:", agent.respond(text))
            if agent.end_requested:
                break


def run_wakeword_tuner():
    from voice.audio import Microphone, WakeWord
    mic, wake = Microphone(), WakeWord()
    print("Say 'Aura, wake up' a few times. Ctrl+C to stop.\n")
    peak = 0.0
    try:
        while True:
            frame = mic.read()
            if frame is None:
                continue
            score = wake.score(frame)
            peak = max(peak, score)
            if score > 0.05:
                print(f"score {score:.3f}   peak {peak:.3f}   {'#' * int(score * 50)}")
    except KeyboardInterrupt:
        print(f"\nPeak score: {peak:.3f}. Set AURA_WAKEWORD_THRESHOLD (or WAKEWORD_THRESHOLD in "
              f"core/config.py) to about {max(0.1, peak * 0.7):.2f}.")
    finally:
        mic.close()


def run_voice_mode(greet=True, hud=True):
    assistant = AuraAssistant()
    if not hud:
        try:
            assistant.run(greet=greet)
        except KeyboardInterrupt:
            pass
        return

    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")   # Wayland ignores window placement
    from PyQt6.QtWidgets import QApplication
    from ui.orb import AuraHUD

    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    halo = AuraHUD(level_source=lambda: assistant.level)
    halo.place()
    halo.show()
    assistant.events.subscribe(halo.receive_event)

    failed = []

    def worker():
        try:
            assistant.run(greet=greet)
        except Exception as error:
            failed.append(error)
            time.sleep(3)          # leave the error visible on the HUD briefly
        finally:
            app.quit()

    threading.Thread(target=worker, name="aura-assistant", daemon=True).start()
    import signal
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    tick = __import__("PyQt6.QtCore", fromlist=["QTimer"]).QTimer()
    tick.timeout.connect(lambda: None)   # lets Python handle signals while Qt runs
    tick.start(200)
    app.exec()
    assistant.running = False
    assistant.shutdown()
    if failed:
        sys.exit(1)                # non-zero so systemd's Restart=on-failure kicks in


def main():
    parser = argparse.ArgumentParser(description="AURA voice assistant")
    parser.add_argument("--text", action="store_true", help="chat by typing, no audio")
    parser.add_argument("--no-greet", action="store_true", help="start asleep instead of greeting")
    parser.add_argument("--no-hud", action="store_true", help="run without the on-screen halo")
    parser.add_argument("--tune-wakeword", action="store_true", help="show live wake-word scores")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    setup_logging(args.verbose)
    from core.alsa import silence_alsa_errors
    silence_alsa_errors()

    if args.text:
        run_text_mode()
    elif args.tune_wakeword:
        run_wakeword_tuner()
    else:
        log.info("Starting AURA%s", f" for {USER_NAME}" if USER_NAME else "")
        from core.config import HUD_ENABLED
        run_voice_mode(greet=not args.no_greet, hud=HUD_ENABLED and not args.no_hud)


if __name__ == "__main__":
    main()
