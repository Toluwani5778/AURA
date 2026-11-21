# AURA User Manual

How to live with AURA day to day: talking to her, turning her on and off, changing how she looks and behaves, and working on her code by hand. For setup see [README.md](README.md); for plans see [ROADMAP.md](ROADMAP.md).

---

## 1. Daily use

### Her states

| What you see (bottom of the screen) | What she's doing |
|---|---|
| Nothing | **Asleep.** Only listening for "Aura, wake up". |
| Warm gold glow, "Waking up" | Starting up or just woken |
| Green/teal glow, "Listening" | Waiting for you to talk. It brightens when you speak. |
| Purple glow, "Pondering…" etc. | Thinking (the word changes for fun) |
| Orange/pink glow, "Opening Firefox…" | Using a tool |
| Mixed shimmer + caption | Speaking (the caption shows what she's saying) |
| Red glow | Error (check the log, see section 5) |

### Waking her up
- **At login** she starts by herself and greets you. No wake word is needed.
- **Any other time** say **"Aura, wake up"** and wait for the glow and her greeting.

### Talking
Just talk normally. Once she's awake you **don't** need the wake word between sentences. Pause for about a second when you're done; that's how she knows your turn is over.

Examples: "open console", "open Mozilla and turn the volume down", "what's the weather tomorrow?", "what's this error on my screen?", "remember my sister's name is Ada", "how's my GPU doing?".

### Putting her to sleep
Say any of these (short sentences, 10 words or fewer):
**"Good night Aura"**, "goodbye", "that's all", "go to sleep", "stop listening", "I'm done", "talk later".
She says a one-line farewell and goes to sleep straight away.

If you just stop talking, she says "Still there?" after about 20 s and goes to sleep about 20 s after that.

### Interrupting her
Say **"Aura, wake up"** while she's talking and she stops mid-sentence.

### Dangerous actions
Shutdown, restart, suspend and logout always get a question: *"Just to be sure, do you want me to shut down the computer?"* Only a **short** answer like "yes" or "yeah, do it" within 30 seconds confirms. Anything else cancels.

### Background noise (games, TV, other people)
While she's awake, she treats any speech she hears as talking to her. That's why your friend's game chatter can keep a conversation going. Some tips:
- Put her to sleep ("good night Aura") when you're not using her. Asleep, she only reacts to the wake word.
- A headset mic or a directional mic helps a lot.
- If chatter often ends sentences early, raise `VAD_THRESHOLD` (see section 3).

---

## 2. Turning AURA on and off

AURA runs as a **systemd user service** called `aura`. These commands don't need sudo:

| I want to… | Command |
|---|---|
| Stop her now | `systemctl --user stop aura` |
| Start her | `systemctl --user start aura` |
| Restart her (after editing code/config) | `systemctl --user restart aura` |
| Check if she's running | `systemctl --user status aura` |
| Watch her live log | `journalctl --user -u aura -f` |
| Stop her starting at login | `systemctl --user disable aura` |
| Make her start at login again | `systemctl --user enable aura` |
| Uninstall the service completely | `scripts/install-service.sh --remove` |

> ⚠️ Only **one** AURA should run at a time, because two copies would fight over the mic. Always `stop` the service before running `python main.py` yourself.

If she crashes, systemd restarts her after 10 seconds, up to 5 times in 5 minutes.

---

## 3. Changing how she behaves

All settings live in **`core/config.py`**. Edit the file, then run `systemctl --user restart aura`.

You can also override a setting without editing code: add an `AURA_` environment variable to the service. Run `systemctl --user edit aura` and add:
```ini
[Service]
Environment=AURA_USER_NAME=Toluwani
Environment=AURA_HUD_OPACITY=0.25
```

### The HUD (the glow)

| Setting | Default | Effect |
|---|---|---|
| `HUD_OPACITY` | `0.35` | Glow strength: 0.15 is a whisper, 1.0 is very bold |
| `HUD_HEIGHT` | `110` | How many pixels of the screen bottom the glow can use. Smaller means shorter crests. |
| `HUD_PILL_OPACITY` | `0.55` | Darkness of the status pill's background |
| `HUD_ENABLED` | `True` | `False` turns the HUD off entirely |

Preview changes without restarting AURA by running `python -m ui.orb`, which cycles through every state for about 15 s. Colours per state are in `LOOKS` at the top of `ui/orb.py`, and the "thinking" words are in `THINKING_WORDS`.

### Voice and hearing

| Setting | Default | Effect |
|---|---|---|
| `USER_NAME` | "" | What she calls you |
| `TTS_VOICE` | `af_bella` | Kokoro voice (others: `af_heart`, `af_nicole`, `bf_emma`, `am_adam`, …) |
| `TTS_SPEED` | `1.05` | Speaking speed |
| `WAKEWORD_THRESHOLD` | `0.5` | Lower means she wakes more easily, but also wakes by accident more often |
| `VAD_THRESHOLD` | `0.5` | How sure she must be that sound is speech. Raise it in noisy rooms. |
| `VAD_END_SILENCE_MS` | `800` | Pause length that ends your turn. Raise it if she cuts you off. |
| `FOLLOW_UP_WINDOW` / `CHECK_IN_WINDOW` | `20` / `20` | Seconds of silence before "Still there?" and before sleeping |
| `ECHO_TAIL_MS` | `350` | How long she ignores the mic after speaking, so she doesn't hear herself |

**Tuning the wake word:** run `systemctl --user stop aura`, then `python main.py --tune-wakeword`. Say "Aura, wake up" five times, press Ctrl+C, and it prints a suggested threshold.

### Brain

| Setting | Default | Effect |
|---|---|---|
| `OLLAMA_MODEL` | `gemma4:e4b` | Fast, fits on the GPU. `qwen3.6:35b-a3b` is smarter but about 10× slower. |
| `OLLAMA_THINK` | `False` | `True` makes her reason first: better answers, but seconds of silence |
| `HISTORY_TURNS` | `20` | How many past exchanges she remembers within a conversation |

Her **personality** is the `PERSONA` text at the top of `core/agent.py`. Edit it freely; it's plain English.

### What she remembers
Long-term facts are in `data/memory.json`. You can read or edit it by hand, or just say "remember…" or "forget…". Past conversations are saved in `data/sessions/`.

---

## 4. Working on the code by hand

```bash
cd ~/Documents/Projects/AURA
systemctl --user stop aura          # 1. stop the background copy
source myenv/bin/activate           # 2. use AURA's Python environment

python main.py --text               # 3a. chat by typing: fastest way to test prompts and tools
python main.py                      # 3b. full voice + HUD in this terminal (Ctrl+C to quit)
python main.py --no-greet -v        #     start asleep, with debug logging

python -m unittest discover -s tests -t .   # 4. run the tests (offline, safe)
python doctor.py                             #    check Ollama, Kokoro, SearXNG, mic…

systemctl --user start aura         # 5. hand her back to systemd when done
```

### Where things are

| To change… | Edit |
|---|---|
| Personality, greeting, goodbye phrases, confirmation rules | `core/agent.py` (`PERSONA`, `greet()`, `FAREWELL`, `YES`/`NO`) |
| Add or change abilities (tools) | `core/tools.py`, see "Adding a tool" in the README |
| Conversation flow (check-in, sleep, error handling) | `main.py` → `AuraAssistant.converse()` |
| Wake word, speech detection, echo guard | `voice/audio.py` |
| Speech-to-text | `voice/Speech2Text.py` |
| Her voice and playback | `voice/Text2Speech.py` |
| The glow | `ui/orb.py` |
| Settings | `core/config.py` |

### Safe habits
- Commit before big edits: `git add -A && git commit -m "before my changes"`. To throw your edits away: `git checkout -- .`
- Test new tools in `--text` mode first, where nothing is spoken.
- Tools must **return** error text, not raise. Anything destructive needs `risk=CONFIRM`.

---

## 5. Troubleshooting

First look at the log: `journalctl --user -u aura -n 100`, or open `data/aura.log`.

| Problem | Fix |
|---|---|
| She never wakes | `--tune-wakeword` and lower `WAKEWORD_THRESHOLD`; check the mic with `pactl get-default-source` |
| She wakes by accident | Raise `WAKEWORD_THRESHOLD` |
| She doesn't go to sleep on "good night" | Make sure the sentence is short; check the log for what Whisper heard (`You: …`) |
| She cuts you off | Raise `VAD_END_SILENCE_MS` to 1200 |
| She responds to the TV or games | Put her to sleep, use a headset, or raise `VAD_THRESHOLD` to 0.7 |
| She hears herself / loops | Use headphones or raise `ECHO_TAIL_MS` |
| First reply takes 10–20 s | Ollama swapped her model out for another one (Open WebUI). See ROADMAP "Known issues". |
| Red glow, "Kokoro TTS is not reachable" | `docker start kokoro` |
| Red glow, "Ollama is not reachable" | `sudo systemctl start ollama` |
| HUD missing | Check `HUD_ENABLED`; run `python -m ui.orb` to test it alone |
| Everything is weird | `python doctor.py` |

---

## 6. Undoing everything

The original pre-agent AURA is preserved on the `main` branch and the `pre-agentic` tag.
```bash
scripts/install-service.sh --remove   # first! main has no service file
git checkout main
```
