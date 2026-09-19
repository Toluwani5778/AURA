"""Small dependency-free event layer for AURA state and lifecycle updates."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from core.state import AURAState


@dataclass(frozen=True)
class AURAEvent:
    """A lifecycle event delivered to subscribers synchronously."""

    name: str
    state: Optional[AURAState] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


EventHandler = Callable[[AURAEvent], None]


class EventPublisher:
    """Publish events to in-process subscribers."""

    def __init__(self) -> None:
        self._subscribers: List[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> None:
        if handler not in self._subscribers:
            self._subscribers.append(handler)

    def unsubscribe(self, handler: EventHandler) -> None:
        if handler in self._subscribers:
            self._subscribers.remove(handler)

    def publish(
        self,
        name: str,
        state: Optional[AURAState] = None,
        **data: Any,
    ) -> AURAEvent:
        event = AURAEvent(name=name, state=state, data=data)
        for handler in tuple(self._subscribers):
            handler(event)
        return event
