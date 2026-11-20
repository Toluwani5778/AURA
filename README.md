# AURA

**Adaptive Utility & Reasoning Assistant**: a fully local voice assistant for my Fedora (KDE Plasma) workstation.

AURA starts when I log in, greets me like a secretary would, and then I just talk to her: "open Firefox and turn the volume down", "what's the weather tomorrow?", "what's this error on my screen?", "remember that my sister's name is Ada", "good night, Aura". She's an **agent**, not a script. An LLM decides what to say and which tools to use, so requests don't need special phrasing. Everything runs on this machine: the brain, the ears and the voice.

The name and personality are explained in [docs/naming.md](docs/naming.md). Progress and plans are in [ROADMAP.md](ROADMAP.md).

---

## How it works

```
 mic ──► one shared PyAudio stream (16 kHz, 80 ms frames)
           │
           ├─ asleep:   OpenWakeWord  "Aura, wake up"
           ├─ awake:    Silero VAD ── detects when you start and stop talking
           │                 │
           │                 ▼
           │            Faster Whisper (GPU) ── text
           │                 │
           │                 ▼
           │            Agent (core/agent.py)
           │              Ollama /api/chat + tools, streamed
           │              ├─ tool calls ─► core/tools.py ─► result back to model (≤5 rounds)
           │              └─ each finished sentence ─┐
           │                                          ▼
           └─ while she talks: echo guard     Kokoro TTS (Docker :8880) ─► speakers
              + "Aura, wake up" interrupts       synth-ahead queue, interruptible

 EventPublisher ─► HUD (ui/orb.py): aurora glow along the bottom of the screen + status pill
```

**A conversation:** login (or the wake word) → AURA greets you → you talk, with no wake word needed between turns → after ~20 s of silence she checks in, and after another ~20 s she goes back to sleep. Saying goodbye ("that's all", "good night") also ends it. Sessions are saved to `data/sessions/`.

**Safety:** power actions (shutdown, reboot, suspend, logout) are never executed directly. The code, not the prompt, holds them and asks "Just to be sure…?", and only a spoken yes runs them. There is no raw shell tool.

### The brain

`gemma4:e4b` via Ollama. It runs at about 360 tokens/s, fits entirely on the 16 GB GPU alongside Whisper and Kokoro, and supports native tool calling and vision. For a smarter but roughly 10× slower brain, set `AURA_OLLAMA_MODEL=qwen3.6:35b-a3b` (it needs about 12 GB of VRAM, so it competes with everything else).

> **VRAM note:** Open WebUI / n8n can load other large models (e.g. the 23 GB abliterated Qwen) and evict AURA's model. When that happens, her next reply takes a few extra seconds while the model reloads, and Whisper may fall back to CPU.

---

## Setup

Requirements: Fedora with PipeWire, an NVIDIA GPU (CPU works but is slower), Python 3.11, and Docker.

```bash
sudo dnf install python3.11 portaudio-devel pipewire-utils playerctl
python3.11 -m venv myenv && source myenv/bin/activate
pip install -r requirements.txt
python -c "import openwakeword; openwakeword.utils.download_models()"   # one-time: shared wake-word models

ollama pull gemma4:e4b            # the brain (Ollama runs as a system service)
docker start kokoro searxng       # voice (:8880) and private web search (:8081)

python doctor.py                  # checks everything above
```

SearXNG must have `json` enabled under `search.formats` in its `settings.yml` for the web-search tool to work.

### Start at login

```bash
scripts/install-service.sh          # enable (starts at next login)
scripts/install-service.sh --now    # enable and start now
scripts/install-service.sh --remove # uninstall

systemctl --user status aura        # is she running?
journalctl --user -u aura -f        # live log
systemctl --user restart aura       # after changing code/config
```

---

## Usage

```bash
python main.py                  # voice + HUD; greets you right away
python main.py --no-greet       # start asleep, wait for "Aura, wake up"
python main.py --no-hud         # no on-screen glow
python main.py --text           # type instead of talk (great for testing prompts/tools)
python main.py --tune-wakeword  # live wake-word scores, to pick the threshold
python -m ui.orb                # preview the HUD's states
```

**Things to say:**

| | |
|---|---|
| Apps | "open console", "launch VS Code", "close Firefox", "what apps do I have?" |
| System | "volume to 30", "mute", "pause the music", "lock the screen", "how's my GPU doing?", "shut down" (she'll confirm) |
| Info | "what's the weather in Toronto tomorrow?", "search for the latest Fedora release", "what time is it?" |
| Browser | "open YouTube", "look up pasta recipes in the browser" |
| Screen | "what's this error on my screen?", "summarize what I'm looking at" |
| Memory | "remember I prefer Celsius", "forget what I said about Celsius" |
| Done | "thanks, that's all", "good night Aura" |

**Interrupting:** say "Aura, wake up" while she's talking.

### Wake word

The custom model is `wake_model/Aura,_Wake_up.onnx`. Custom models score lower than the pretrained ones, so tune the threshold once: run `python main.py --tune-wakeword`, say the phrase a few times, and set `WAKEWORD_THRESHOLD` (or `AURA_WAKEWORD_THRESHOLD`) to the suggested value. The default is 0.5.

---

## Configuration

Everything is in [`core/config.py`](core/config.py). Any value can be overridden with an environment variable prefixed `AURA_`, for example by adding `Environment=AURA_USER_NAME=YourName` to the service:

| Setting | Default | |
|---|---|---|
| `USER_NAME` | "" | what AURA calls you |
| `OLLAMA_MODEL` | `gemma4:e4b` | the brain |
| `VISION_MODEL` | `gemma4:e4b` | used by `look_at_screen` |
| `TTS_VOICE` / `TTS_SPEED` | `af_bella` / 1.05 | any Kokoro voice |
| `WHISPER_MODEL_SIZE` | `small.en` | `base.en` is faster, `medium.en` more accurate |
| `WAKEWORD_THRESHOLD` | 0.5 | see above |
| `VAD_END_SILENCE_MS` | 800 | how long a pause ends your sentence |
| `FOLLOW_UP_WINDOW` / `CHECK_IN_WINDOW` | 20 / 20 s | silence before check-in / sleep |

Data lives in `data/` (git-ignored): `sessions/` holds conversation logs, `memory.json` holds long-term facts (you can edit it by hand), and `aura.log` is the main log.

---

## Adding a tool

Tools live in [`core/tools.py`](core/tools.py). Decorate a function; the docstring becomes what the model sees, so describe *when* to use it:

```python
@tool(params={"city": {"type": "string", "description": "City name"}}, required=["city"])
def local_time(city: str) -> str:
    """Get the current time in another city."""
    ...
    return "It's 9:14 PM in Tokyo."      # short plain text, fed back to the model
```

- Return short plain text. On failure, return an error string instead of raising.
- Mark anything destructive with `risk=CONFIRM`. The agent will ask for a spoken yes first.
- Add a friendly HUD label in `TOOL_WORDS` in `ui/orb.py`.
- Try it with `python main.py --text`.

---

## Project layout

```
main.py               entry point: voice loop, text mode, wake-word tuner
doctor.py             health check
core/
  agent.py            LLM agent loop, persona prompt, confirmations, sentence streaming
  tools.py            tool registry + all tools
  memory.py           session logs + long-term memory (remember/forget tools)
  llm.py              streaming Ollama client
  config.py           settings
  events.py, state.py lifecycle events/states observed by the HUD
  alsa.py             silences ALSA noise
voice/
  audio.py            Microphone, WakeWord, VAD, Listener (utterance capture, echo guard)
  Speech2Text.py      Faster Whisper (GPU with CPU fallback)
  Text2Speech.py      Kokoro speaker with streaming + interruption
  extraSTT.py         standalone: transcribe + summarize an audio file
ui/orb.py             aurora HUD
systemd/, scripts/    login service
tests/                offline tests (no mic, GPU or services needed)
wake_model/           OpenWakeWord models ("Aura, wake up" + older test models)
docs/naming.md        why "AURA"
```

## Tests

```bash
python -m unittest discover -s tests -t .
```

The tests use a scripted fake LLM, so they run offline and never launch apps or touch the system.

## Troubleshooting

| Symptom | Fix |
|---|---|
| She never wakes | `--tune-wakeword`, then lower the threshold; check the mic with `pactl get-default-source` |
| She answers herself / repeats | speakers are too loud near the mic: use headphones, or raise `ECHO_TAIL_MS` |
| Cuts you off mid-sentence | raise `VAD_END_SILENCE_MS` to ~1200 |
| Slow first reply | the model was evicted from VRAM (see the VRAM note above) |
| "Kokoro TTS is not reachable" | `docker start kokoro` |
| Weird transcripts on silence | known Whisper habit; common hallucinations are filtered in `Speech2Text.py` |
