"""Shared lifecycle state for the AURA engine and user interface."""

from enum import Enum


class AURAState(Enum):
    """Observable states of the assistant lifecycle."""

    SLEEPING = "sleeping"
    WAKING = "waking"
    LISTENING = "listening"
    PROCESSING = "processing"
    THINKING = "thinking"
    EXECUTING = "executing"
    SPEAKING = "speaking"
    ERROR = "error"
