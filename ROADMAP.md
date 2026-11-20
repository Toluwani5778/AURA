# AURA Roadmap

The single source of truth for where AURA is and where she's going. **AI assistants working on this repo:** read README.md, then this file, then update the status here when you finish something.

Last updated: 2026-11-20

## Where we are

AURA was rebuilt from a rule-based pipeline (keyword classifier → skills → canned replies) into an **agent**: an LLM with conversation history and tools that decides what to do. The table below maps the original 12-stage plan onto what exists now.

| # | Stage | Status | Notes |
|---|---|---|---|
| 1 | Stabilize the loop | ✅ Done | clean session lifecycle, sessions saved once, resources closed, survives errors |
| 2 | State and event layer | ✅ Done | `core/state.py`, `core/events.py`; HUD only observes |
| 3 | Floating HUD | ✅ Done | aurora glow at the screen bottom, status pill with playful "thinking" words and live captions, click-through, mic-reactive |
| 4 | Start at login (systemd) | ✅ Done | `systemd/aura.service`, `scripts/install-service.sh`; waits for Ollama and Kokoro, then greets |
| 5 | Continuous conversation | ✅ Done | no wake word between turns; check-in after silence, then sleep; goodbye ends it |
| 6 | Voice activity detection | ✅ Done | Silero VAD on the shared stream; recording ends when you stop talking |
| 7 | Tool registry with risk levels | ✅ Done | `core/tools.py`, `@tool` decorator, `SAFE` / `CONFIRM` |
| 8 | LLM tool calling | ✅ Done | native Ollama tools, up to 5 chained rounds, confirmation enforced in code |
| 9 | System awareness | 🟡 Partial | `system_status` (CPU, RAM, GPU, disk, uptime); no network or battery yet |
| 10 | Long-term memory | 🟡 Partial | `remember` / `forget` facts in `data/memory.json`, injected into the prompt; no episodic memory or retrieval yet |
| 11 | Barge-in and audio-reactive HUD | 🟡 Partial | the wake word interrupts speech; the HUD reacts to the mic. Missing: "stop" without the wake word (needs echo cancellation), HUD driven by the actual TTS waveform |
| 12 | Vision, web, developer tools | 🟡 Partial | ✅ `look_at_screen` (gemma4 vision), ✅ `web_search` (SearXNG), ✅ `weather`; ❌ developer mode |

## Next up (suggested order)

1. **Tune the wake word on real voice.** Run `python main.py --tune-wakeword` and set the threshold. If "Aura, wake up" is unreliable, retrain it with more samples of my voice (OpenWakeWord training notebook).
2. **Echo cancellation** with PipeWire `module-echo-cancel`. This would allow true barge-in ("stop", "actually…") on speakers without the wake word, and enable a lower `ECHO_TAIL_MS`.
3. **Episodic memory:** summarize each session into one or two lines on save, store them, and retrieve relevant ones into the prompt (`embeddinggemma` is already installed and `chromadb` is in the venv).
4. **Morning briefing:** at the first greeting of the day, optionally include the weather and today's calendar.
5. **Developer mode tools:** `git status` and diff summaries, Docker container status and start/stop, running tests, systemd service status. Each is its own tool, with `CONFIRM` on anything that changes state.
6. **More desktop control:** window focus and switching (KWin scripting / `kdotool`), notifications (`notify-send`), timers and reminders (with a background scheduler thread), clipboard read/write.
7. **Brain tiers:** route hard questions to `qwen3.6:35b-a3b` (e.g. an "ask_expert" tool) while keeping gemma for fast turns.
8. **Speaker-aware HUD:** feed TTS amplitude to the HUD instead of the synthetic shimmer.

## Known issues

- **VRAM contention:** other Ollama clients (Open WebUI, n8n) can evict `gemma4:e4b`, which makes the next reply slow, and Whisper falls back to CPU if VRAM is full at startup.
- **Unverified on real speech:** the end-to-end loop was verified with injected audio and a real mic pickup, but the wake word and VAD thresholds still need tuning with my actual voice and room.
- **Speakers without headphones:** half-duplex only, so AURA ignores the mic while she talks and for 350 ms afterwards.
- The HUD runs through XWayland (`QT_QPA_PLATFORM=xcb`) because native Wayland ignores window positioning. A proper fix is `layer-shell` via `LayerShellQt`.

## Principles (apply to every change)

- **Agentic, not rule-based.** New abilities are tools the model can choose; don't add keyword routing.
- **Safety in code.** Destructive actions use `risk=CONFIRM`; no raw shell tool; allowlisted commands with structured arguments.
- **Privacy.** Everything stays local except explicit web lookups (SearXNG, Open-Meteo). Screenshots happen only on request and are deleted right after. No secrets in memory or logs.
- **Voice first.** Replies are short spoken sentences, with no markdown. Latency matters more than cleverness.
- **The UI observes and never drives.** A HUD crash must not take down the assistant.
- **Tests stay offline:** `python -m unittest discover -s tests -t .` must pass without a mic, GPU or any services.

## Changelog

- **2026-11-20:** Agentic rebuild. Ollama tool-calling agent with streamed speech; tool registry (apps, web, weather, volume, media, power with confirmation, system status, screen vision, memory); "Aura, wake up" wake word; Silero VAD; continuous conversation; aurora HUD; systemd login service; brain switched to `gemma4:e4b`; docs consolidated into README + ROADMAP. Fixed: AURA could never wake a second time (the session end stopped the main loop and terminated PyAudio), requests with no timeout, TTS ignoring config, broken `.gitignore` rules, Whisper CUDA library loading.
- **Before:** Stages 1–2 (state/events), an orb HUD prototype, a keyword-routed planner, a skills framework.
