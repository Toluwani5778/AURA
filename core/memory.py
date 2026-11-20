"""Session transcripts and long-term memory for AURA."""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import List

from core.config import MEMORY_FILE, SESSIONS_DIR
from core.tools import tool

log = logging.getLogger("aura.memory")


class SessionLog:
    """Records one conversation (wake -> sleep) and saves it exactly once."""

    def __init__(self, directory: Path = SESSIONS_DIR):
        self.started = datetime.now()
        self.name = f"session_{self.started:%Y%m%d_%H%M%S}"
        self.path = Path(directory) / f"{self.name}.json"
        self.messages: List[dict] = []
        self.saved = False

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content,
                              "time": datetime.now().isoformat(timespec="seconds")})

    def save(self) -> None:
        if self.saved or not self.messages:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "session": self.name,
            "started": self.started.isoformat(timespec="seconds"),
            "ended": datetime.now().isoformat(timespec="seconds"),
            "messages": self.messages,
        }, indent=2))
        self.saved = True
        log.info("Session saved to %s", self.path)


class LongTermMemory:
    """Durable facts about the user, injected into every system prompt."""

    def __init__(self, path: Path = MEMORY_FILE):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.facts: List[dict] = []
        if self.path.exists():
            try:
                self.facts = json.loads(self.path.read_text()).get("facts", [])
            except (OSError, ValueError):
                log.warning("Could not read %s; starting empty", self.path)

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"facts": self.facts}, indent=2))

    def add(self, fact: str) -> str:
        fact = fact.strip()
        with self._lock:
            if any(f["fact"].lower() == fact.lower() for f in self.facts):
                return "I already knew that."
            self.facts.append({"fact": fact, "added": datetime.now().isoformat(timespec="seconds")})
            self._save()
        return f"Remembered: {fact}"

    def forget(self, about: str) -> str:
        about = about.lower().strip()
        with self._lock:
            before = len(self.facts)
            self.facts = [f for f in self.facts if about not in f["fact"].lower()]
            removed = before - len(self.facts)
            self._save()
        return f"Forgot {removed} item(s)." if removed else "I had nothing stored about that."

    def as_prompt(self) -> str:
        if not self.facts:
            return ""
        return "Things you know about the user:\n" + "\n".join(f"- {f['fact']}" for f in self.facts)


memory = LongTermMemory()


@tool(params={"fact": {"type": "string", "description": "A short fact, preference or reminder about the user"}},
      required=["fact"])
def remember(fact: str) -> str:
    """Store something about the user permanently (preferences, names, projects,
    routines). Use when the user says 'remember...' or shares a lasting preference."""
    return memory.add(fact)


@tool(params={"about": {"type": "string", "description": "Words identifying what to forget"}},
      required=["about"])
def forget(about: str) -> str:
    """Delete stored memories matching some words, when the user asks you to forget."""
    return memory.forget(about)
