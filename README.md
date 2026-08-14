# AURA - Your Personal AI Assistant 🚀

**AURA** (Adaptive Utility & Reasoning Assistant) is a voice-activated personal AI assistant running on your Fedora workstation. She can have conversations, answer questions, control your PC, launch applications, and remember context within sessions.

## Features ✨

- **🎤 Voice Activation**: Wake AURA with "Hey Mycroft" (or custom "Hey Sebastian")
- **💬 Conversation Memory**: AURA remembers your conversation within sessions
- **⏰ Auto-Sleep**: Automatically sleeps after 10 minutes of inactivity
- **😴 Voice Sleep Word**: Put AURA to sleep by saying "Good night AURA"
- **🖥️ PC Control**: Shutdown, restart, sleep, lock screen, adjust volume/brightness
- **🚀 App Launcher**: Open/close Firefox, VS Code, Spotify, Terminal, and more
- **❓ Q&A**: Answer questions and provide information
- **💾 Session Logging**: All conversations are saved to `data/sessions/`

## Prerequisites

Ensure you have the following installed:

```bash
# System packages
sudo dnf install python3.11 python3-pip ffmpeg portaudio-devel

# Python packages (listed in requirements.txt)
pip install -r requirements.txt
```

### External Services (Required)

1. **Ollama** (LLM)

   ```bash
   # Install and start Ollama
   # Pull the model
   ollama pull qwen3.6:latest
   # Start the server (usually runs on http://localhost:11434)
   ollama serve
   ```

2. **Kokoro TTS** (Text-to-Speech)
   ```bash
   # Clone and run Kokoro (in a separate terminal)
   git clone https://github.com/remsky/Kokoro-82M
   cd Kokoro-82M
   python3 server.py
   # Runs on http://localhost:8880
   ```

## Configuration ⚙️

Edit `core/config.py` to customize AURA:

```python
# Use custom wakeword model
USE_CUSTOM_MODEL = False  # Set to True for "hey_sebastian"

# Session timeout (seconds)
SESSION_TIMEOUT = 600  # 10 minutes

# LLM Model
OLLAMA_MODEL = "qwen3.6:latest"

# Voice settings
WHISPER_MODEL_SIZE = "small"  # Options: tiny, base, small, medium
WHISPER_DEVICE = "cuda"  # Options: cuda, cpu
TTS_VOICE = "af_bella"  # Female voice
```

## Usage 🎙️

### Start AURA

```bash
# Activate the virtual environment
source myenv/bin/activate

# Run AURA
python main.py
```

### During a Session

1. **Activate**: Say "Hey Mycroft" to wake AURA
2. **Interact**: Ask her anything:
   - "What time is it?"
   - "Open Firefox"
   - "Shut down the PC"
   - "Tell me about Python"
3. **Deactivate**: Say "Good night AURA" to put her to sleep
4. **Auto-Sleep**: After 10 minutes of silence, AURA will ask if you're still there

### Example Commands

**Information Queries**

- "What is the weather?"
- "Tell me about quantum computing"
- "How do I make pasta?"

**PC Control**

- "Shutdown the PC"
- "Restart"
- "Lock the screen"
- "Volume up"
- "Brightness down"

**Application Control**

- "Open Firefox"
- "Launch VS Code"
- "Close Spotify"
- "Open terminal"

**Conversation**

- "Hi AURA, how are you?"
- "Tell me a joke"
- "What can you do?"

## Project Structure 📁

```
AURA/
├── main.py                    # Main application entry point
├── requirements.txt           # Python dependencies
├── setup.py                   # Installation script
├── core/
│   ├── config.py             # Configuration settings
│   ├── llm.py                # LLM integration (Ollama)
│   ├── memory.py             # Session & conversation memory
│   └── task_executor.py      # Task execution framework
├── voice/
│   ├── Wakeup.py             # Wakeword detection
│   ├── Speech2Text.py        # Audio transcription (Whisper)
│   ├── Text2Speech.py        # Speech synthesis (Kokoro)
│   └── Assitant_name.MD      # AURA background
├── tools/
│   ├── PC_control            # PC control utilities
│   ├── V_assist              # Voice assistant helpers
│   └── Ollama_connect        # LLM connection
├── data/
│   └── sessions/             # Saved conversation sessions (JSON)
├── resources/
│   └── audio/
│       ├── Input/            # Input audio files
│       └── Output/           # Generated speech output
└── wake_model/
    └── hey_sebastian.onnx    # Custom wakeword model
```

## Session Memory 🧠

Each session is saved as a JSON file in `data/sessions/` with:

- Conversation history
- Timestamps
- Session duration
- Message count
- Timeout events

Example: `data/sessions/session_20260813_142530.json`

## Troubleshooting 🔧

### "Connection refused" error

- Make sure Ollama is running: `ollama serve`
- Check Ollama URL in `config.py`: `OLLAMA_URL = "http://127.0.0.1:11434/api/generate"`

### "No audio input" error

- Check microphone: `arecord -d 3 /tmp/test.wav`
- Verify PyAudio installation: `pip install pyaudio`

### Whisper model download fails

- Models auto-download on first run
- If stuck, manually download: See `faster_whisper` documentation
- Ensure sufficient disk space (~2-3 GB for 'small' model)

### Speech not playing

- Check audio output: `aplay /tmp/test.wav`
- Verify Kokoro is running: `http://localhost:8880/docs`
- Check speaker volume: `amixer get Master`

## Advanced Usage 🎯

### Switch to Custom Wakeword

1. Train/obtain a custom wakeword model (`.onnx` file)
2. Place in `wake_model/` directory
3. In `core/config.py`:
   ```python
   USE_CUSTOM_MODEL = True
   WAKEWORD_CUSTOM = "your_word_name"
   WAKEWORD_CUSTOM_PATH = "wake_model/your_word.onnx"
   ```

### Change Sleep Wakeword

Edit in `core/config.py`:

```python
SLEEP_WAKEWORD = "your custom sleep phrase"
```

### Adjust LLM Behavior

The system prompt in `config.py` defines AURA's personality. Modify `SYSTEM_PROMPT` to change behavior:

```python
SYSTEM_PROMPT = """You are AURA, a personal AI...
[Customize this]
"""
```

## Performance Notes 📊

- **GPU Acceleration** (Recommended): Much faster speech-to-text
  - CUDA setup: `WHISPER_DEVICE = "cuda"` with NVIDIA GPU
  - CPU Fallback: `WHISPER_DEVICE = "cpu"` (slower)

- **Model Sizes**:
  - `tiny`: Fastest, lower accuracy
  - `small`: Balanced (default)
  - `base`, `medium`: Higher accuracy, slower

## Future Enhancements 🚀

- [ ] Integration with system calendar/reminders
- [ ] Web search capabilities
- [ ] Email integration
- [ ] Custom skill plugins
- [ ] Multi-language support
- [ ] Emotion recognition
- [ ] Personal profile learning

## Contributing

Feel free to extend AURA with:

- New task types in `core/task_executor.py`
- Additional tools in `tools/` directory
- Custom skills or integrations

## License

Personal use only

## Support

For issues, check:

1. All external services running (Ollama, Kokoro)
2. `core/config.py` settings
3. Audio device permissions: `sudo usermod -a -G audio $USER`
4. Python version: `python3 --version` (3.10+)

---

**Enjoy using AURA! 🎉**

Questions? Start a session and ask AURA herself!
