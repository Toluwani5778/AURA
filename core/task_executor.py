"""
Task Execution Framework
Handles different types of tasks AURA can perform (PC control, app opening, Q&A, etc.)
"""

import subprocess
import re
from typing import Tuple, Optional
from enum import Enum


class TaskType(Enum):
    """Types of tasks AURA can perform"""
    PC_CONTROL = "pc_control"          # Shutdown, restart, sleep, etc.
    APP_CONTROL = "app_control"         # Open/close applications
    INFORMATION = "information"         # Answer questions
    GENERAL = "general"                 # General conversation
    UNKNOWN = "unknown"


class TaskExecutor:
    """Executes different types of tasks based on user requests"""
    
    # Map of application names to executable commands
    APP_COMMANDS = {
        "firefox": "firefox",
        "chrome": "google-chrome",
        "chromium": "chromium-browser",
        "vscode": "code",
        "code": "code",
        "vs code": "code",
        "terminal": "gnome-terminal",
        "konsole": "konsole",
        "spotify": "spotify",
        "vlc": "vlc",
        "blender": "blender",
        "gimp": "gimp",
        "thunderbird": "thunderbird",
        "email": "thunderbird",
        "nautilus": "nautilus",
        "files": "nautilus",
    }
    
    # PC control keywords
    PC_CONTROL_KEYWORDS = {
        "shutdown": "shutdown",
        "power off": "shutdown",
        "turn off": "shutdown",
        "restart": "restart",
        "reboot": "restart",
        "sleep": "sleep",
        "suspend": "sleep",
        "lock": "lock",
        "screen lock": "lock",
        "brightness": "brightness",
        "volume": "volume",
    }
    
    @staticmethod
    def classify_task(user_input: str) -> TaskType:
        """
        Classify the type of task based on user input
        
        Args:
            user_input: The user's voice input
        
        Returns:
            TaskType: The classified task type
        """
        user_lower = user_input.lower()
        
        # Check for PC control
        for keyword in TaskExecutor.PC_CONTROL_KEYWORDS:
            if keyword in user_lower:
                return TaskType.PC_CONTROL
        
        # Check for app control
        for app_name in TaskExecutor.APP_COMMANDS:
            if app_name in user_lower:
                return TaskType.APP_CONTROL
        
        # Check for information queries
        info_keywords = ["tell me", "what is", "who is", "how", "when", "where", "why", "weather", "time", "date"]
        if any(keyword in user_lower for keyword in info_keywords):
            return TaskType.INFORMATION
        
        # Default to general conversation
        return TaskType.GENERAL
    
    @staticmethod
    def execute(user_input: str, llm_response: str) -> Tuple[bool, str]:
        """
        Execute a task based on user input
        
        Args:
            user_input: The user's original input
            llm_response: The LLM's response suggesting what to do
        
        Returns:
            Tuple of (success, message)
        """
        task_type = TaskExecutor.classify_task(user_input)
        
        try:
            if task_type == TaskType.PC_CONTROL:
                return TaskExecutor._handle_pc_control(user_input)
            
            elif task_type == TaskType.APP_CONTROL:
                return TaskExecutor._handle_app_control(user_input)
            
            elif task_type == TaskType.INFORMATION:
                # Information tasks are handled by LLM, no execution needed
                return True, llm_response
            
            else:
                # General conversation
                return True, llm_response
        
        except Exception as e:
            return False, f"I encountered an error: {str(e)}"
    
    @staticmethod
    def _handle_pc_control(user_input: str) -> Tuple[bool, str]:
        """Handle PC control tasks"""
        user_lower = user_input.lower()
        
        try:
            # Commands that need sudo (shown in konsole)
            sudo_commands = {
                "shutdown": "systemctl poweroff",
                "power off": "systemctl poweroff",
                "turn off": "systemctl poweroff",
                "restart": "systemctl reboot",
                "reboot": "systemctl reboot",
                "sleep": "systemctl suspend",
                "suspend": "systemctl suspend",
            }
            
            # Check for sudo-required commands first
            for keyword, command in sudo_commands.items():
                if keyword in user_lower:
                    # Open konsole with the command ready for user to execute with sudo
                    konsole_cmd = f"konsole -e 'echo Running: sudo {command}; sudo {command}'"
                    subprocess.Popen(konsole_cmd, shell=True)
                    return True, f"Opening console to execute: sudo {command}. Please confirm with your sudo password."
            
            # Commands that don't need sudo
            if any(kw in user_lower for kw in ["lock", "screen lock"]):
                subprocess.run(["loginctl", "lock-session"], check=False)
                return True, "Locking the screen."
            
            elif "volume" in user_lower:
                if "up" in user_lower or "increase" in user_lower:
                    subprocess.run(["amixer", "set", "Master", "5%+"], check=False)
                    return True, "Volume increased."
                elif "down" in user_lower or "decrease" in user_lower:
                    subprocess.run(["amixer", "set", "Master", "5%-"], check=False)
                    return True, "Volume decreased."
                elif "mute" in user_lower:
                    subprocess.run(["amixer", "set", "Master", "toggle"], check=False)
                    return True, "Mute toggled."
            
            elif "brightness" in user_lower:
                # Brightness adjustment (requires xrandr or similar)
                if "up" in user_lower or "increase" in user_lower:
                    subprocess.run(["xrandr", "--output", "HDMI-1", "--brightness", "1.2"], check=False)
                    return True, "Brightness increased."
                elif "down" in user_lower or "decrease" in user_lower:
                    subprocess.run(["xrandr", "--output", "HDMI-1", "--brightness", "0.8"], check=False)
                    return True, "Brightness decreased."
            
            return False, "PC control command not recognized."
        
        except Exception as e:
            return False, f"Error executing PC control: {str(e)}"
    
    @staticmethod
    def _handle_app_control(user_input: str) -> Tuple[bool, str]:
        """Handle application control tasks"""
        user_lower = user_input.lower()
        
        try:
            # Find which app to open/close
            for app_name, app_command in TaskExecutor.APP_COMMANDS.items():
                if app_name in user_lower:
                    if "close" in user_lower or "quit" in user_lower:
                        subprocess.run(["pkill", app_command], check=False)
                        return True, f"Closing {app_name}."
                    else:
                        # Open the application
                        subprocess.Popen([app_command])
                        return True, f"Opening {app_name}."
            
            return False, "Application not recognized."
        
        except Exception as e:
            return False, f"Error launching application: {str(e)}"
