"""Thin streaming client for Ollama's /api/chat endpoint."""

import json
import logging
import time
from typing import Iterator

import requests

from core.config import (
    OLLAMA_HOST, OLLAMA_KEEP_ALIVE, OLLAMA_MODEL, OLLAMA_NUM_CTX, OLLAMA_THINK,
)

log = logging.getLogger("aura.llm")


class OllamaClient:
    def __init__(self, host=OLLAMA_HOST, model=OLLAMA_MODEL):
        self.host = host.rstrip("/")
        self.model = model

    def is_up(self) -> bool:
        try:
            return requests.get(f"{self.host}/api/tags", timeout=2).ok
        except requests.RequestException:
            return False

    def wait_until_ready(self, timeout=120) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_up():
                return True
            time.sleep(2)
        return False

    def warm(self) -> None:
        """Load the model into VRAM now so the first reply isn't a cold start."""
        try:
            requests.post(
                f"{self.host}/api/chat",
                json={"model": self.model, "messages": [], "keep_alive": OLLAMA_KEEP_ALIVE},
                timeout=120,
            )
        except requests.RequestException as error:
            log.warning("Could not warm %s: %s", self.model, error)

    def chat_stream(self, messages, tools=None) -> Iterator[dict]:
        """Yield streamed chunks: {"content": str} and/or {"tool_calls": [...]}."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "think": OLLAMA_THINK,
            "keep_alive": OLLAMA_KEEP_ALIVE,
            "options": {"num_ctx": OLLAMA_NUM_CTX, "temperature": 0.6},
        }
        if tools:
            payload["tools"] = tools
        with requests.post(
            f"{self.host}/api/chat", json=payload, stream=True, timeout=(5, 120)
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if "error" in chunk:
                    raise RuntimeError(chunk["error"])
                message = chunk.get("message", {})
                yield {
                    "content": message.get("content", ""),
                    "tool_calls": message.get("tool_calls") or [],
                    "done": chunk.get("done", False),
                }
