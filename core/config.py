"""AURA configuration. Every tunable lives here; override any value with an
environment variable of the same name prefixed with AURA_ (e.g. AURA_OLLAMA_MODEL)."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def _env(name, default):
    raw = os.environ.get(f"AURA_{name}")
    if raw is None:
        return default
    if isinstance(default, bool):
        return raw.lower() in {"1", "true", "yes", "on"}
    return type(default)(raw)


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
USER_NAME = _env("USER_NAME", "")          # How AURA addresses you ("" = no name)
ASSISTANT_NAME = "AURA"

# ---------------------------------------------------------------------------
# Brain (Ollama)
# ---------------------------------------------------------------------------
OLLAMA_HOST = _env("OLLAMA_HOST", "http://127.0.0.1:11434")
# gemma4:e4b: ~360 tok/s, fits entirely on the 16 GB GPU next to Whisper and
# Kokoro, native tool calling. Swap to "qwen3.6:35b-a3b" for a smarter but
# ~10x slower brain that needs most of the GPU.
OLLAMA_MODEL = _env("OLLAMA_MODEL", "gemma4:e4b")
OLLAMA_KEEP_ALIVE = _env("OLLAMA_KEEP_ALIVE", "2h")
OLLAMA_THINK = _env("OLLAMA_THINK", False)    # thinking adds seconds of silence
OLLAMA_NUM_CTX = _env("OLLAMA_NUM_CTX", 8192)
MAX_TOOL_ROUNDS = 5
HISTORY_TURNS = 20                             # user/assistant pairs kept in context

# ---------------------------------------------------------------------------
# Wake word (OpenWakeWord)
# ---------------------------------------------------------------------------
WAKEWORD_MODEL_PATH = str(PROJECT_ROOT / "wake_model" / "Aura,_Wake_up.onnx")
WAKEWORD_KEY = "Aura,_Wake_up"
# Custom models score lower than the pretrained ones. Run
# `python main.py --tune-wakeword` and set this a little under your peak score.
WAKEWORD_THRESHOLD = _env("WAKEWORD_THRESHOLD", 0.5)

# ---------------------------------------------------------------------------
# Listening (Silero VAD + Faster Whisper)
# ---------------------------------------------------------------------------
WHISPER_MODEL_SIZE = _env("WHISPER_MODEL_SIZE", "small.en")
WHISPER_DEVICE = _env("WHISPER_DEVICE", "cuda")
WHISPER_COMPUTE_TYPE = _env("WHISPER_COMPUTE_TYPE", "float16")

VAD_THRESHOLD = _env("VAD_THRESHOLD", 0.5)          # speech probability
VAD_END_SILENCE_MS = _env("VAD_END_SILENCE_MS", 800)  # silence that ends an utterance
VAD_MIN_SPEECH_MS = 250                              # ignore clicks / coughs
VAD_PRE_ROLL_MS = 300                                # keep audio just before speech
MAX_UTTERANCE_SECONDS = 30
# After AURA stops speaking, ignore the mic briefly so she doesn't hear her
# own echo (half-duplex; use headphones or PipeWire echo-cancel for barge-in).
ECHO_TAIL_MS = 350

# ---------------------------------------------------------------------------
# Voice (Kokoro TTS, Docker container "kokoro")
# ---------------------------------------------------------------------------
TTS_API_URL = _env("TTS_API_URL", "http://localhost:8880")
TTS_VOICE = _env("TTS_VOICE", "af_bella")
TTS_SPEED = _env("TTS_SPEED", 1.05)

# ---------------------------------------------------------------------------
# Conversation flow
# ---------------------------------------------------------------------------
# Seconds of silence in a conversation before AURA checks in, then sleeps.
FOLLOW_UP_WINDOW = _env("FOLLOW_UP_WINDOW", 20)
CHECK_IN_WINDOW = _env("CHECK_IN_WINDOW", 20)

# ---------------------------------------------------------------------------
# Web search (SearXNG container on :8081)
# ---------------------------------------------------------------------------
SEARXNG_URL = _env("SEARXNG_URL", "http://localhost:8081")

# ---------------------------------------------------------------------------
# Audio device
# ---------------------------------------------------------------------------
AUDIO_RATE = 16000
AUDIO_CHANNELS = 1
AUDIO_FRAMES_PER_BUFFER = 1280   # 80 ms; OpenWakeWord's native frame size

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
SESSIONS_DIR = DATA_DIR / "sessions"
MEMORY_FILE = DATA_DIR / "memory.json"
LOG_FILE = DATA_DIR / "aura.log"
