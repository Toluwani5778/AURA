# AURA Next Steps

## Purpose

This document is the ongoing roadmap for evolving AURA from a working voice assistant into a persistent desktop AI system on Fedora.

The current foundation already includes:

- Wakeword detection with OpenWakeWord
- Faster Whisper speech-to-text
- Ollama-backed responses
- Kokoro text-to-speech
- Session conversation memory
- Timeout handling and sleep behavior
- A skills framework
- Basic task execution for applications and system controls
- Safe test workflow with mocked external services
- ALSA diagnostic suppression

Future sessions should use this file as the handoff point. Update the status and notes as each stage is implemented.

---

## Guiding Architecture

The long-term architecture should separate the system into these layers:

```text
Fedora Desktop
    |
    +-- AURA HUD
    |
    +-- Conversation Engine
           |
           +-- Wakeword Detection
           +-- Audio Input and VAD
           +-- Speech-to-Text
           +-- Ollama Reasoning
           +-- Tool Registry
           +-- Memory
           +-- Permission System
           +-- Response Generation
           +-- Text-to-Speech
```

The HUD must subscribe to AURA state and events. It should not own assistant logic.

The core engine should publish states such as:

```text
SLEEPING
WAKING
LISTENING
PROCESSING
THINKING
EXECUTING
SPEAKING
ERROR
```

The interface should react to those states without directly controlling the conversation engine.

---

## Current Baseline

### Verified

- AURA can wake from the configured wakeword.
- AURA can transcribe spoken input.
- AURA can answer through Ollama.
- AURA can synthesize and play spoken responses.
- Skills can respond to greetings, time, jokes, and capability requests.
- Basic application launching works.
- Sessions are saved when the session ends.
- ALSA startup diagnostics are suppressed in Python and during `aplay` playback.
- The safe test workflow has previously passed all six tests.

### Known Issues To Address

- The current conversation loop still uses fixed-duration recording rather than voice activity detection.
- The wakeword/sleep implementation and transcribed sleep commands need to be clearly separated.
- Tool routing is currently based largely on keyword classification rather than LLM tool calling.
- The assistant may repeat spoken output or print duplicate response messages; investigate the current `main.py` and TTS flow before changing behavior.
- Some generic phrases may match the wrong skill. For example, application requests should not be captured by the capabilities skill.
- Startup and shutdown are not yet managed by a user-level systemd service.
- There is no HUD state/event contract yet.
- There is no explicit permission layer for dangerous operations.
- There is no long-term memory, vision pipeline, web-search tool, or developer mode.

---

# Implementation Roadmap

## Stage 1: Stabilize the Existing Assistant

### Goals

Make the current assistant predictable before adding major features.

### Tasks

- Review and refactor `main.py` around an explicit conversation state machine.
- Define one source of truth for assistant states.
- Ensure each response is spoken exactly once.
- Ensure each user message is saved exactly once.
- Ensure audio streams are closed on normal exit, errors, and `Ctrl+C`.
- Ensure `PyAudio.terminate()` is called during shutdown.
- Ensure sessions are saved exactly once.
- Fix skill priority and matching conflicts.
- Add tests for:
  - Wakeword to session transition
  - Listening to processing transition
  - Processing to speaking transition
  - Speaking back to listening
  - Sleep command
  - Keyboard interruption
  - Audio initialization failure

### Completion Criteria

- The assistant can run for a complete session without duplicated responses.
- A normal shutdown and an interrupted shutdown both clean up resources.
- State transitions are observable and testable.

### Status

- [x] Complete

### Verified Work

- Added an explicit `AURAState` lifecycle model and wired it into `main.py`.
- Added synchronous lifecycle events for wakeword detection, transcripts, tools, responses, errors, interruption, and session end.
- Removed duplicate response printing and made default skill registration idempotent.
- Added pre-action announcement and session persistence for reboot, shutdown, and suspend.
- Added cleanup coverage for streams, `PyAudio.terminate()`, interruption, sleep phrases, and session finalization.
- Added focused regression tests in `test_stage1_stage2.py`.
- Existing safe workflow remains green with 6/6 tests passing.

---

## Stage 2: Build the AURA State and Event Layer

### Goals

Create the contract that the HUD and future services will consume.

### Suggested Files

```text
core/
    state.py       # AURAState enum and state data
    events.py      # Event names and event publisher
```

### Suggested State Model

```python
class AURAState(Enum):
    SLEEPING = "sleeping"
    WAKING = "waking"
    LISTENING = "listening"
    PROCESSING = "processing"
    THINKING = "thinking"
    EXECUTING = "executing"
    SPEAKING = "speaking"
    ERROR = "error"
```

### Tasks

- [x] Add a state enum.
- [x] Add a small synchronous event publisher or observer interface.
- [x] Publish state changes from the conversation engine.
- [x] Publish useful events such as wakeword, transcript, tool, response, and error events.
- [x] Keep the event layer dependency-light so it can be used by both the HUD and tests.

### Completion Criteria

- The engine can report every meaningful lifecycle transition.
- A test subscriber can observe the complete state sequence.
- The HUD can be added without changing assistant behavior.

### Status

- [x] Complete

### Current Implementation

- `core/state.py` defines the shared `AURAState` enum.
- `core/events.py` defines `AURAEvent` and `EventPublisher`.
- `AuraAssistant` accepts an event publisher and emits lifecycle updates.
- The engine is ready for a HUD subscriber without coupling UI code to assistant logic.

### Next Task

- Begin Stage 3 with a PyQt6 HUD that subscribes to `EventPublisher`.

---

## Stage 3: Build the Floating HUD

### Goals

Create a small, persistent, state-driven visual presence for AURA.

### Technology

- PyQt6
- Frameless transparent top-level window
- Always-on-top behavior where appropriate
- Custom `QPainter` rendering
- Qt property/timer animations

### Suggested Files

```text
ui/
    orb.py
    animations.py
    waveform.py
```

### Status

- [ ] In progress

### Current Implementation

- `ui/orb.py` contains a transparent, frameless, always-on-top PyQt6 orb.
- The orb subscribes to `EventPublisher` through a Qt signal for thread-safe updates.
- Colors and animation behavior currently reflect sleeping, listening, thinking, executing, speaking, waking, and error states.
- `main.py` runs the assistant loop beside the Qt event loop so the HUD remains responsive.

### Next Task

- Add a compact state label or tooltip for development diagnostics.
- Verify placement and behavior on the live Fedora desktop.
- Then add richer animations and audio-reactive waveform behavior.

### Visual States

- `SLEEPING`: dim, minimal dot or very small orb
- `WAKING`: expanding ring
- `LISTENING`: active ring and subtle microphone motion
- `THINKING`: rotating or orbiting particles
- `EXECUTING`: progress or horizontal activity line
- `SPEAKING`: pulsing orb and waveform
- `ERROR`: restrained red/orange warning state

### Tasks

- Create a transparent HUD window.
- Position it consistently in the top-right area of the desktop.
- Keep the HUD compact and unobtrusive.
- Connect the HUD to the state/event layer.
- Add a development mode that displays the current state and last event.
- Ensure the HUD can be disabled in configuration.
- Test on the current Fedora desktop and screen scaling.

### Completion Criteria

- The orb appears without a background rectangle.
- State changes visibly alter the animation.
- The HUD does not block normal desktop interaction.
- The assistant remains functional if the HUD fails.

### Status

- [ ] Not started

---

## Stage 4: Add User-Level systemd Integration

### Goals

Run AURA as a managed user service after graphical login.

### Suggested Files

```text
system/
    aura.service
```

### Service Requirements

- Start after the graphical user session is available.
- Use the project virtual environment's Python executable.
- Use the absolute project path.
- Write useful logs to the user journal.
- Restart on unexpected failure with a controlled delay.
- Stop cleanly when the user session ends.
- Do not start before audio and desktop services are ready.

### Tasks

- Add a user-level service file.
- Add setup instructions for copying or linking it into `~/.config/systemd/user/`.
- Add commands for:
  - Start
  - Stop
  - Restart
  - Enable
  - Status
  - Journal inspection
- Add a configuration switch for startup greeting.
- Add a configuration switch for startup system report.
- Make startup initialization report clear progress in the journal.

### Completion Criteria

```text
systemctl --user status aura
```

shows an active service, and:

```text
journalctl --user -u aura
```

shows meaningful startup and shutdown events.

### Status

- [ ] Not started

---

## Stage 5: Improve Continuous Conversation

### Goals

Replace the current fixed recording cycle with a natural conversation state machine.

### Target Flow

```text
SLEEPING
    |
    | wakeword
    v
WAKING
    v
LISTENING
    |
    | speech complete
    v
PROCESSING
    v
THINKING or EXECUTING
    v
SPEAKING
    v
LISTENING
    |
    | inactivity policy
    v
SLEEPING
```

### Timeout Policy

Use different time windows for different interaction states:

- Short pause: wait for a possible follow-up.
- Medium pause: mark the conversation as fading.
- Longer pause: move to standby.
- Existing long timeout: ask whether the user is still present.
- Repeated timeout: return to sleep.

Keep all values configurable.

### Tasks

- Separate wakeword listening from active conversation listening.
- Keep the microphone stream reusable where safe.
- Return to listening immediately after TTS completes.
- Add interruption handling while AURA is speaking.
- Detect explicit sleep phrases from transcription.
- Preserve context across follow-up commands.
- Add tests for multiple consecutive commands without another wakeword.

### Completion Criteria

The user can issue several related commands after one wakeword and AURA remains engaged until the configured inactivity policy puts it to sleep.

### Status

- [ ] Not started

---

## Stage 6: Add Voice Activity Detection

### Goals

Stop relying on a fixed 10-second or 30-second recording window.

### Target Flow

```text
Microphone
    v
Voice activity detection
    v
Speech begins
    v
Capture audio
    v
Short silence detected
    v
Send utterance to Whisper
```

### Tasks

- Select and add a suitable VAD implementation.
- Define speech-start and speech-end thresholds.
- Add configurable pre-roll and trailing silence.
- Handle noisy rooms and short utterances.
- Retain a fixed maximum utterance duration as a safety limit.
- Add mocked audio tests for speech, silence, and noise.

### Completion Criteria

AURA begins processing shortly after the user finishes speaking without waiting for a fixed recording timeout.

### Status

- [ ] Not started

---

## Stage 7: Create a Proper Tool Registry

### Goals

Evolve the existing skills framework into a structured, permission-aware tool system.

### Suggested Organization

```text
skills/
    system/
        shutdown
        restart
        lock
        sleep
        volume
    applications/
        firefox
        vscode
        spotify
        terminal
    linux/
        processes
        services
        packages
        network
    files/
        search
        open
        move
        organize
    development/
        git
        docker
        vscode
        terminals
    intelligence/
        web_search
        vision
        memory
```

### Tool Contract

Each tool should declare:

- Name
- Description
- Input schema
- Risk level
- Whether confirmation is required
- Execution method
- Result format

### Risk Levels

- `SAFE`: execute immediately, such as opening an application.
- `MODERATE`: explain the action and request confirmation where appropriate.
- `DANGEROUS`: require explicit confirmation.
- `CRITICAL`: require explicit confirmation and possibly a second safety check.

### Completion Criteria

Adding a tool should require creating the tool, registering it, and exposing its description to the reasoning layer without modifying the central conversation loop.

### Status

- [ ] Not started

---

## Stage 8: Add LLM Tool Calling

### Goals

Move from keyword-only routing toward structured tool selection by Ollama.

### Target Flow

```text
User request
    v
Ollama chooses response or tool call
    v
Permission check
    v
Tool execution
    v
Tool result
    v
Ollama creates natural response
```

### Tasks

- Confirm the selected Ollama model's tool-calling support.
- Define JSON-compatible tool schemas.
- Add a tool-call parser with strict validation.
- Reject malformed, unknown, or unauthorized tool calls.
- Return tool results to Ollama for final phrasing.
- Keep deterministic local routing as a fallback.
- Log every tool call and result.

### Completion Criteria

Natural language requests such as opening an application or querying system status route through a validated tool interface rather than a growing collection of string checks.

### Status

- [ ] Not started

---

## Stage 9: Add System Awareness Tools

### Goals

Ensure AURA uses real system data instead of allowing the LLM to guess.

### Initial Tools

- CPU usage
- RAM usage
- GPU usage
- GPU temperature
- VRAM usage
- Disk usage
- Network status
- Running processes
- System uptime
- Battery status

### Safety Rules

- Read-only tools can execute automatically.
- Tool output should include timestamps and units.
- Missing hardware or commands should produce a clear unavailable result.
- Do not expose secrets, tokens, or private file contents by default.

### Completion Criteria

For system questions, AURA reports measured values and identifies the source instead of presenting invented data.

### Status

- [ ] Not started

---

## Stage 10: Add Long-Term and Episodic Memory

### Memory Types

### Short-Term Memory

Current conversation context and recent tool results.

### Long-Term Memory

Stable preferences and facts, such as:

- Preferred browser
- Preferred IDE
- AURA project directory
- Preferred voice
- Preferred wakeword
- User's name

### Episodic Memory

Important past events, such as:

- Work completed on a project
- Major configuration changes
- Important decisions

### Tasks

- Define what is safe to remember.
- Add explicit user control to inspect, edit, and delete memories.
- Store structured records rather than raw unbounded conversations.
- Add retrieval by relevance and recency.
- Avoid saving secrets and sensitive data.
- Add tests for persistence, retrieval, deletion, and isolation.

### Completion Criteria

AURA can use useful persistent preferences while the user retains clear control over stored information.

### Status

- [ ] Not started

---

## Stage 11: Add Barge-In and Audio-Reactive Output

### Barge-In

While AURA is speaking, the microphone should detect an interruption such as:

- "Stop"
- "Cancel"
- "Actually, never mind"
- A new wakeword, if configured

The current audio playback should stop promptly and the state should return to listening or sleeping.

### Audio-Reactive HUD

Analyze the TTS audio amplitude and publish audio-level events so the HUD waveform reflects actual speech rather than random animation.

### Tasks

- Make TTS playback interruptible.
- Run playback and interruption detection concurrently.
- Add cancellation tokens or an equivalent stop signal.
- Avoid microphone feedback from AURA's own voice.
- Publish normalized amplitude values.
- Add tests for interruption and cancellation.

### Completion Criteria

The user can interrupt a long spoken response naturally, and the orb reacts to actual AURA audio.

### Status

- [ ] Not started

---

## Stage 12: Add Vision, Web, and Developer Tools

### Vision

Possible requests:

- Read the screen
- Explain a terminal error
- Identify what is displayed

Requirements:

- Explicit screenshot capture
- User-visible privacy indicator
- Configurable image model
- No capture while disabled

### Web Access

Add an actual web-search tool for current information. AURA must distinguish searched facts from model knowledge and report when a search was performed.

### Developer Mode

Developer tools may include:

- Git status and diff summaries
- Test execution
- Docker status and lifecycle commands
- VS Code project actions
- Python commands
- Fedora and systemd diagnostics
- Terminal command execution through a strict permission layer

Dangerous developer commands must require confirmation and should be logged.

### Completion Criteria

Each capability is an independently registered tool with permissions, tests, and clear failure reporting.

### Status

- [ ] Not started

---

# Safety and Privacy Requirements

These requirements apply to every future stage.

- Never execute destructive commands without explicit confirmation.
- Require confirmation for `sudo`, `rm`, disk operations, firewall changes, package removal, and similar actions.
- Prefer allowlisted commands and structured arguments over arbitrary shell strings.
- Keep secrets out of prompts, logs, and memory.
- Make screenshots and persistent memory opt-in or clearly controllable.
- Log tool calls with redaction where needed.
- Keep the safe mock workflow working as features are added.
- Provide a dry-run mode for tools wherever practical.
- Keep UI failure independent from assistant-engine failure.

---

# Testing Strategy

Every stage should add focused tests before expanding scope.

## Required Test Layers

### Unit Tests

Test state transitions, tool schemas, permission checks, parsers, and memory operations.

### Integration Tests

Use mocks for Ollama, Kokoro, PyAudio, OpenWakeWord, subprocesses, systemd, and desktop APIs.

### Safe Workflow Tests

Keep `test_workflow.py` safe to run on the real workstation. It must not:

- Launch applications
- Change volume
- Shut down or restart the computer
- Modify files outside test data
- Make external service calls unless explicitly mocked

### Manual Tests

Document manual checks for:

- Real microphone input
- Real speaker playback
- HUD placement
- Desktop startup
- Service restart
- Barge-in behavior

---

# Suggested Session Handoff Format

At the end of each future implementation session, update this file with:

```text
## Session YYYY-MM-DD

Completed:
- ...

Files changed:
- ...

Validation:
- ...

Known issues:
- ...

Next recommended task:
- ...
```

Also update the relevant stage's `Status` checkbox and keep the smallest unfinished task clearly identified.

---

# Recommended Immediate Next Task

Start with **Stage 1: Stabilize the Existing Assistant**.

Before adding the HUD or systemd service, inspect the current `main.py`, `core/skills.py`, and voice modules to:

1. Remove duplicate response handling.
2. Define explicit assistant states.
3. Centralize cleanup.
4. Fix incorrect skill matching such as application requests being handled by the capabilities skill.
5. Add focused tests for the conversation lifecycle.

After Stage 1 is stable, implement the state/event layer and then connect the HUD to it.
