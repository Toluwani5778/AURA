# Creating Custom AURA Skills 🎘

AURA has an extensible skills framework that makes it easy to add custom capabilities. This guide shows you how to create and register your own skills.

## Skill Architecture

A **Skill** is a Python class that:

1. Extends the `AuraSkill` base class
2. Implements `can_handle()` to detect if it should process user input
3. Implements `execute()` to perform the action and return a response

## Basic Skill Template

```python
from core.skills import AuraSkill
from typing import Tuple

class MyCustomSkill(AuraSkill):
    # Metadata
    name = "My Custom Skill"
    description = "Does something awesome"
    keywords = ["keyword1", "keyword2", "trigger phrase"]

    def can_handle(self, user_input: str) -> bool:
        """Return True if this skill should handle the input"""
        user_lower = user_input.lower()
        return any(kw in user_lower for kw in self.keywords)

    def execute(self, user_input: str) -> Tuple[bool, str]:
        """Execute the skill and return (success, response_text)"""
        # Your implementation here
        return True, "Response to the user"
```

## Example 1: Weather Skill

```python
from core.skills import AuraSkill
from typing import Tuple

class WeatherSkill(AuraSkill):
    name = "Weather"
    description = "Provides weather information"
    keywords = ["weather", "forecast", "temperature", "rain", "sunny"]

    def can_handle(self, user_input: str) -> bool:
        user_lower = user_input.lower()
        return any(kw in user_lower for kw in self.keywords)

    def execute(self, user_input: str) -> Tuple[bool, str]:
        # In real implementation, fetch from weather API
        # For now, return a sample response
        return True, "It's 72 degrees and sunny today!"
```

**Register it in `main.py`:**

```python
from my_skills import WeatherSkill

initialize_default_skills()
global_skill_registry.register(WeatherSkill())
```

## Example 2: Reminder Skill

```python
from core.skills import AuraSkill
from typing import Tuple
from datetime import datetime, timedelta

class ReminderSkill(AuraSkill):
    name = "Reminder"
    description = "Sets reminders and alarms"
    keywords = ["remind", "alarm", "set reminder", "remember"]

    def __init__(self):
        super().__init__()
        self.reminders = {}  # Store reminders in memory

    def can_handle(self, user_input: str) -> bool:
        user_lower = user_input.lower()
        return any(kw in user_lower for kw in self.keywords)

    def execute(self, user_input: str) -> Tuple[bool, str]:
        user_lower = user_input.lower()

        # Example: "Remind me in 5 minutes"
        if "in" in user_lower:
            # Parse time and message
            # Create reminder
            return True, "I'll remind you in 5 minutes!"

        return False, "I didn't understand the reminder request"
```

## Example 3: Music Control Skill

```python
from core.skills import AuraSkill
from typing import Tuple
import subprocess

class MusicSkill(AuraSkill):
    name = "Music"
    description = "Controls music playback"
    keywords = ["play", "music", "spotify", "pause", "stop", "next track"]

    def can_handle(self, user_input: str) -> bool:
        user_lower = user_input.lower()
        return any(kw in user_lower for kw in self.keywords)

    def execute(self, user_input: str) -> Tuple[bool, str]:
        user_lower = user_input.lower()

        try:
            if "play" in user_lower:
                subprocess.run(["playerctl", "play"], check=False)
                return True, "Music is now playing"

            elif "pause" in user_lower or "stop" in user_lower:
                subprocess.run(["playerctl", "pause"], check=False)
                return True, "Music paused"

            elif "next" in user_lower:
                subprocess.run(["playerctl", "next"], check=False)
                return True, "Next track"

            return False, "Music command not recognized"

        except Exception as e:
            return False, f"Error controlling music: {str(e)}"
```

## How Skills Are Processed

1. User says something
2. AURA checks each registered skill's `can_handle()` method
3. First skill that returns `True` is selected
4. The skill's `execute()` method is called
5. If no skill matches, AURA falls back to the LLM for general conversation

## Best Practices

### ✅ DO:

- Keep skills focused on one task
- Use descriptive keyword lists
- Handle exceptions gracefully
- Return a user-friendly message
- Test thoroughly before deploying

### ❌ DON'T:

- Overlap keywords with other skills (first match wins)
- Make `can_handle()` too broad
- Block for long periods (no sleep loops)
- Return empty strings
- Raise unhandled exceptions

## Advanced: Skill with State

```python
from core.skills import AuraSkill
from typing import Tuple

class CounterSkill(AuraSkill):
    name = "Counter"
    description = "Maintains a counter"
    keywords = ["count", "increment", "counter"]

    def __init__(self):
        super().__init__()
        self.counter = 0  # Persistent state

    def can_handle(self, user_input: str) -> bool:
        user_lower = user_input.lower()
        return any(kw in user_lower for kw in self.keywords)

    def execute(self, user_input: str) -> Tuple[bool, str]:
        user_lower = user_input.lower()

        if "reset" in user_lower:
            self.counter = 0
            return True, "Counter reset to zero"

        else:
            self.counter += 1
            return True, f"Counter is now {self.counter}"
```

## Accessing Session Context

If you need conversation context or session info:

```python
from core.skills import AuraSkill

class ContextAwareSkill(AuraSkill):
    name = "Context"
    description = "Uses session context"
    keywords = ["last", "previous", "remember"]

    def __init__(self, session_manager=None):
        super().__init__()
        self.session_manager = session_manager

    def execute(self, user_input: str) -> Tuple[bool, str]:
        # Access conversation history
        if self.session_manager:
            context = self.session_manager.get_context_for_llm()
            # Use context to provide smarter responses
            return True, "Response using context"

        return False, "No session context available"
```

## Registering Custom Skills

Add your skills to `main.py`:

```python
from core.skills import initialize_default_skills, global_skill_registry
from my_skills import WeatherSkill, ReminderSkill, MusicSkill

def main():
    # Initialize default skills
    initialize_default_skills()

    # Add your custom skills
    global_skill_registry.register(WeatherSkill())
    global_skill_registry.register(ReminderSkill())
    global_skill_registry.register(MusicSkill())

    # Rest of main...
```

## Listing Registered Skills

```python
# Show all skills
skills = global_skill_registry.list_skills()
for skill_info in skills:
    print(f"Skill: {skill_info['name']}")
    print(f"  Description: {skill_info['description']}")
    print(f"  Keywords: {skill_info['keywords']}")
```

## Testing Your Skill

Create a test script:

```python
from core.skills import AuraSkill
from my_skills import MyCustomSkill

# Test the skill directly
skill = MyCustomSkill()

# Test detection
print(skill.can_handle("test input with keyword1"))  # Should be True
print(skill.can_handle("unrelated input"))           # Should be False

# Test execution
success, response = skill.execute("input with keyword1")
print(f"Success: {success}")
print(f"Response: {response}")
```

## Common Use Cases

### API Integration

```python
class NewsSkill(AuraSkill):
    def execute(self, user_input: str) -> Tuple[bool, str]:
        import requests
        # Fetch from news API
        response = requests.get("https://api.example.com/news")
        return True, f"Latest news: {response.json()['headline']}"
```

### File Operations

```python
class FileSkill(AuraSkill):
    def execute(self, user_input: str) -> Tuple[bool, str]:
        # Read/write files
        with open("notes.txt", "a") as f:
            f.write(user_input + "\n")
        return True, "Note saved"
```

### System Integration

```python
class SystemSkill(AuraSkill):
    def execute(self, user_input: str) -> Tuple[bool, str]:
        import subprocess
        result = subprocess.run(["cmd"], capture_output=True, text=True)
        return True, result.stdout
```

## Troubleshooting

**Skill not being called?**

- Check `can_handle()` method - add debug prints
- Verify keywords match actual user input (case-insensitive)
- Ensure skill is registered before `main()` runs

**Response not spoken?**

- Return tuple as `(bool, str)` not just `str`
- Ensure response is not empty string
- Check if skill is returning `True` for success

**Unexpected behavior?**

- Test skill independently first
- Add logging/prints to `execute()` method
- Check for keyword conflicts with other skills

---

Happy skill building! 🚀
