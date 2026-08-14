"""
AURA Skills Framework
Extensible framework for adding custom skills and capabilities
"""

from abc import ABC, abstractmethod
from typing import Dict, Tuple, Optional, List
import inspect


class AuraSkill(ABC):
    """
    Base class for AURA skills
    Subclass this to create custom capabilities
    """
    
    # Metadata about the skill
    name: str = "Unnamed Skill"
    description: str = "No description"
    keywords: List[str] = []  # Keywords that trigger this skill
    
    def __init__(self):
        """Initialize the skill"""
        pass
    
    @abstractmethod
    def can_handle(self, user_input: str) -> bool:
        """
        Determine if this skill can handle the user input
        
        Args:
            user_input: The transcribed user input
        
        Returns:
            bool: True if this skill can handle it
        """
        pass
    
    @abstractmethod
    def execute(self, user_input: str) -> Tuple[bool, str]:
        """
        Execute the skill
        
        Args:
            user_input: The transcribed user input
        
        Returns:
            Tuple of (success, response_text)
        """
        pass
    
    def get_info(self) -> Dict:
        """Get information about this skill"""
        return {
            "name": self.name,
            "description": self.description,
            "keywords": self.keywords,
            "class": self.__class__.__name__
        }


class SkillRegistry:
    """Registry for managing AURA skills"""
    
    def __init__(self):
        self.skills: List[AuraSkill] = []
    
    def register(self, skill: AuraSkill) -> None:
        """Register a new skill"""
        self.skills.append(skill)
        print(f"✅ Registered skill: {skill.name}")
    
    def unregister(self, skill_name: str) -> bool:
        """Unregister a skill by name"""
        for i, skill in enumerate(self.skills):
            if skill.name == skill_name:
                self.skills.pop(i)
                print(f"❌ Unregistered skill: {skill_name}")
                return True
        return False
    
    def find_skill(self, user_input: str) -> Optional[AuraSkill]:
        """Find a skill that can handle the user input"""
        for skill in self.skills:
            if skill.can_handle(user_input):
                return skill
        return None
    
    def execute(self, user_input: str) -> Tuple[bool, str, Optional[AuraSkill]]:
        """
        Find and execute a skill for the user input
        
        Returns:
            Tuple of (success, response, skill_used)
        """
        skill = self.find_skill(user_input)
        if skill:
            success, response = skill.execute(user_input)
            return success, response, skill
        return False, None, None
    
    def list_skills(self) -> List[Dict]:
        """List all registered skills"""
        return [skill.get_info() for skill in self.skills]


# ============================================================================
# Example Custom Skills
# ============================================================================

class GreetingSkill(AuraSkill):
    """Handles greeting and farewell interactions"""
    
    name = "Greeting"
    description = "Handles hello, goodbye, and basic greetings"
    keywords = ["hello", "hi", "hey", "goodbye", "bye", "farewell"]
    
    def can_handle(self, user_input: str) -> bool:
        user_lower = user_input.lower()
        return any(kw in user_lower for kw in self.keywords)
    
    def execute(self, user_input: str) -> Tuple[bool, str]:
        user_lower = user_input.lower()
        
        if any(kw in user_lower for kw in ["goodbye", "bye", "farewell"]):
            return True, "Goodbye! It was nice talking to you. See you soon!"
        
        else:  # hello, hi, hey
            return True, "Hey there! I'm AURA, your personal AI assistant. How can I help?"


class TimeSkill(AuraSkill):
    """Handles time and date queries"""
    
    name = "Time"
    description = "Provides current time and date information"
    keywords = ["time", "date", "what time", "what's the time"]
    
    def can_handle(self, user_input: str) -> bool:
        user_lower = user_input.lower()
        return any(kw in user_lower for kw in self.keywords)
    
    def execute(self, user_input: str) -> Tuple[bool, str]:
        from datetime import datetime
        
        now = datetime.now()
        time_str = now.strftime("%I:%M %p")
        date_str = now.strftime("%A, %B %d, %Y")
        
        return True, f"It's {time_str} on {date_str}."


class JokeSkill(AuraSkill):
    """Tells jokes"""
    
    name = "Joke"
    description = "Tells a random joke"
    keywords = ["joke", "tell me a joke", "make me laugh", "something funny"]
    
    def can_handle(self, user_input: str) -> bool:
        user_lower = user_input.lower()
        return any(kw in user_lower for kw in self.keywords)
    
    def execute(self, user_input: str) -> Tuple[bool, str]:
        jokes = [
            "Why did the programmer quit his job? Because he didn't get arrays.",
            "Why do Python programmers wear glasses? Because they don't C#.",
            "How many programmers does it take to change a light bulb? None, that's a hardware problem!",
            "Why was the programmer sad? Because he had problems.",
        ]
        
        import random
        return True, random.choice(jokes)


class CapabilitiesSkill(AuraSkill):
    """Describes what AURA can do"""
    
    name = "Capabilities"
    description = "Describes LUCY's capabilities"
    keywords = ["capabilities", "can you", "what can you", "what can i ask", "help"]
    
    def can_handle(self, user_input: str) -> bool:
        user_lower = user_input.lower()
        return any(kw in user_lower for kw in self.keywords)
    
    def execute(self, user_input: str) -> Tuple[bool, str]:
        capabilities = """
I'm AURA, and I can help you with:
- Answering questions and having conversations
- Controlling your PC (shutdown, restart, lock screen)
- Controlling volume and brightness
- Opening and closing applications
- Telling you the time and date
- Telling jokes and having fun
- Remembering conversation context within sessions

You can also ask me to do almost anything, and I'll try my best to help!
        """
        return True, capabilities.strip()


# ============================================================================
# Global Registry Instance
# ============================================================================

global_skill_registry = SkillRegistry()

# Register default skills
def initialize_default_skills():
    """Initialize AURA with default skills"""
    global_skill_registry.register(GreetingSkill())
    global_skill_registry.register(TimeSkill())
    global_skill_registry.register(JokeSkill())
    global_skill_registry.register(CapabilitiesSkill())
    print(f"\n✅ Initialized {len(global_skill_registry.skills)} default skills\n")
