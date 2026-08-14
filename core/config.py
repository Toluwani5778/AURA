# AURA Configuration File

# ============================================================================
# WAKEWORD SETTINGS
# ============================================================================

# Toggle between pretrained and custom wakeword models
USE_CUSTOM_MODEL = False  # Set to True to use custom "hey_sebastian.onnx"

# Wakeword models
WAKEWORD_PRETRAINED = "hey_mycroft"
WAKEWORD_CUSTOM = "hey_sebastian"
WAKEWORD_CUSTOM_PATH = "wake_model/hey_sebastian.onnx"

# Wakeword detection threshold (0.0 - 1.0)
WAKEWORD_THRESHOLD = 0.925

# Sleep wakeword to deactivate AURA
SLEEP_WAKEWORD = "good night aura"
SLEEP_WAKEWORD_THRESHOLD = 0.85

# ============================================================================
# LLM SETTINGS
# ============================================================================

# Ollama configuration
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen3.6:latest"

# System prompt for AURA
SYSTEM_PROMPT = """You are AURA (Adaptive Utility & Reasoning Assistant), a personal AI assistant running on the user's Fedora workstation. 
You are intelligent, helpful, and conversational. Keep responses concise but informative. 
When a user asks you to perform a task (like controlling the PC, opening apps, etc.), acknowledge that you're performing it.
Be your authentic self - not overly formal, but professional."""

# ============================================================================
# VOICE SETTINGS
# ============================================================================

# Speech-to-Text (Whisper)
WHISPER_MODEL_SIZE = "small"
WHISPER_DEVICE = "cuda"  # Options: "cuda", "cpu"
WHISPER_COMPUTE_TYPE = "float16"  # Options: "float16", "int8_float16", "int8"

# Text-to-Speech (Kokoro)
TTS_API_URL = "http://localhost:8880"
TTS_VOICE = "af_bella"  # Female voice with a good tone
TTS_OUTPUT_PATH = "resources/audio/Output/output.wav"

# ============================================================================
# SESSION SETTINGS
# ============================================================================

# Timeout (in seconds) after which AURA asks if user is still there
SESSION_TIMEOUT = 600  # 10 minutes

# Maximum number of timeouts before auto-sleep
MAX_TIMEOUTS = 2

# ============================================================================
# AUDIO SETTINGS
# ============================================================================

# PyAudio settings
AUDIO_FORMAT = "paInt16"
AUDIO_CHANNELS = 1
AUDIO_RATE = 16000
AUDIO_FRAMES_PER_BUFFER = 1280
