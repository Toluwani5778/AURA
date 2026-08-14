"""
Session Manager Module
Handles conversation context, memory, and session state for AURA
"""

from datetime import datetime
from typing import List, Dict, Any
import json
import os

class Message:
    """Represents a single message in the conversation"""
    def __init__(self, role: str, content: str, timestamp: float = None):
        self.role = role  # "user" or "assistant"
        self.content = content
        self.timestamp = timestamp or datetime.now().timestamp()
    
    def to_dict(self):
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp
        }


class SessionManager:
    """Manages conversation context and session state"""
    
    def __init__(self, session_name: str = None):
        self.session_name = session_name or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.messages: List[Message] = []
        self.conversation_context = ""
        self.session_start_time = datetime.now().timestamp()
        self.last_interaction_time = self.session_start_time
        self.timeout_count = 0
        self.is_active = False
        
    def add_message(self, role: str, content: str):
        """Add a message to the conversation history"""
        message = Message(role, content)
        self.messages.append(message)
        self.last_interaction_time = message.timestamp
        self._update_context()
        
    def get_context_for_llm(self) -> str:
        """
        Prepare conversation context for LLM
        Returns a formatted string suitable for the LLM prompt
        """
        if not self.messages:
            return "This is the start of the conversation."
        
        context_lines = []
        context_lines.append("Conversation history:")
        context_lines.append("-" * 40)
        
        for msg in self.messages[-10:]:  # Keep last 10 messages for context
            role_display = "USER" if msg.role == "user" else "AURA"
            context_lines.append(f"{role_display}: {msg.content}")
        
        context_lines.append("-" * 40)
        return "\n".join(context_lines)
    
    def _update_context(self):
        """Update the internal conversation context string"""
        self.conversation_context = self.get_context_for_llm()
    
    def get_session_duration(self) -> float:
        """Get session duration in seconds"""
        return datetime.now().timestamp() - self.session_start_time
    
    def get_idle_time(self) -> float:
        """Get time since last interaction in seconds"""
        return datetime.now().timestamp() - self.last_interaction_time
    
    def increment_timeout_count(self):
        """Increment timeout counter"""
        self.timeout_count += 1
    
    def reset_timeout_count(self):
        """Reset timeout counter after user interaction"""
        self.timeout_count = 0
    
    def should_force_sleep(self, max_timeouts: int = 2) -> bool:
        """Check if session should force sleep (too many timeouts)"""
        return self.timeout_count >= max_timeouts
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get a summary of the session"""
        return {
            "session_name": self.session_name,
            "duration_seconds": self.get_session_duration(),
            "message_count": len(self.messages),
            "timeout_count": self.timeout_count,
            "last_interaction": self.last_interaction_time,
            "is_active": self.is_active
        }
    
    def save_session(self, filepath: str = None):
        """Save session history to a JSON file"""
        if filepath is None:
            filepath = f"data/sessions/{self.session_name}.json"
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        session_data = {
            "session_name": self.session_name,
            "session_start": datetime.fromtimestamp(self.session_start_time).isoformat(),
            "session_duration": self.get_session_duration(),
            "messages": [msg.to_dict() for msg in self.messages],
            "summary": self.get_session_summary()
        }
        
        with open(filepath, "w") as f:
            json.dump(session_data, f, indent=2)
        
        print(f"Session saved to {filepath}")
    
    def end_session(self):
        """End the current session"""
        self.is_active = False
        self.save_session()
