"""
Task Execution Framework
Handles different types of tasks AURA can perform (PC control, app opening, Q&A, etc.)
"""

import subprocess
import re
from typing import Any, Dict, Tuple, Optional
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

    ACTION_COMMANDS = {
        "reboot": ["systemctl", "reboot"],
        "shutdown": ["systemctl", "poweroff"],
        "suspend": ["systemctl", "suspend"],
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
    def may_be_action_request(user_input: str) -> bool:
        """Identify language that is worth sending to the action planner."""
        action_words = {
            "open", "launch", "start", "close", "quit", "kill", "stop",
            "restart", "reboot", "shutdown", "power", "turn", "suspend",
            "sleep", "lock", "increase", "decrease", "raise", "lower", "mute",
        }
        words = set(re.findall(r"\b[\w']+\b", user_input.lower()))
        return bool(words & action_words) or TaskExecutor.classify_task(user_input) in {
            TaskType.PC_CONTROL,
            TaskType.APP_CONTROL,
        }
    
    @staticmethod
    def execute(user_input: str, llm_response: str = "") -> Tuple[bool, str]:
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
    def execute_plan(plan: Dict[str, Any]) -> Tuple[bool, str]:
        """Execute one validated action selected by AURA's planner."""
        action = plan.get("action")
        app = plan.get("app")

        if action in TaskExecutor.ACTION_COMMANDS:
            return TaskExecutor._run_system_action(action)
        if action == "lock":
            return TaskExecutor._run_command(["loginctl", "lock-session"], "Locking the screen.")
        if action in {"volume_up", "volume_down", "volume_mute"}:
            commands = {
                "volume_up": ["amixer", "set", "Master", "5%+"],
                "volume_down": ["amixer", "set", "Master", "5%-"],
                "volume_mute": ["amixer", "set", "Master", "toggle"],
            }
            messages = {
                "volume_up": "Volume increased.",
                "volume_down": "Volume decreased.",
                "volume_mute": "Mute toggled.",
            }
            return TaskExecutor._run_command(commands[action], messages[action])
        if action == "open_app" and app:
            return TaskExecutor._open_application(app)
        if action == "close_app" and app:
            return TaskExecutor._close_application(app)

        return False, "No safe action was selected."

    @staticmethod
    def _run_system_action(action: str) -> Tuple[bool, str]:
        """Try a native system action, then provide an interactive sudo fallback."""
        command = TaskExecutor.ACTION_COMMANDS[action]

        try:
            result = subprocess.run(command, check=False, capture_output=True, text=True)
            if result.returncode == 0:
                return True, f"{action.capitalize()} command accepted."
        except OSError:
            result = None

        sudo_command = "sudo " + " ".join(command)
        try:
            # --hold keeps the terminal visible so sudo prompts and failures are
            # not lost when Konsole exits its command shell.
            subprocess.Popen([
                "konsole",
                "--hold",
                "-e",
                "bash",
                "-lc",
                f"{sudo_command}; status=$?; echo; echo 'Command exited with status:' $status; read -r -p 'Press Enter to close...'",
            ])
            return True, f"Opening Konsole to run {sudo_command}. Enter your password there if prompted."
        except OSError as error:
            return False, f"I could not run {action}: Konsole is unavailable ({error})."

    @staticmethod
    def _run_command(command: list[str], response: str) -> Tuple[bool, str]:
        try:
            result = subprocess.run(command, check=False)
            if result.returncode == 0:
                return True, response
            return False, f"The command {' '.join(command)} was rejected (exit code {result.returncode})."
        except OSError as error:
            return False, f"Could not run {' '.join(command)}: {error}"

    @staticmethod
    def _open_application(app: str) -> Tuple[bool, str]:
        app_command = TaskExecutor.APP_COMMANDS.get(app.lower())
        if not app_command:
            return False, f"I do not have a safe launcher for {app}."
        try:
            subprocess.Popen([app_command])
            return True, f"Opening {app}."
        except OSError as error:
            return False, f"Could not open {app}: {error}"

    @staticmethod
    def _close_application(app: str) -> Tuple[bool, str]:
        app_command = TaskExecutor.APP_COMMANDS.get(app.lower())
        if not app_command:
            return False, f"I do not have a safe closer for {app}."
        try:
            subprocess.run(["pkill", app_command], check=False)
            return True, f"Closing {app}."
        except OSError as error:
            return False, f"Could not close {app}: {error}"
    
    @staticmethod
    def _handle_pc_control(user_input: str) -> Tuple[bool, str]:
        """Handle PC control tasks"""
        user_lower = user_input.lower()
        
        try:
            if any(keyword in user_lower for keyword in ["shutdown", "power off", "turn off"]):
                return TaskExecutor._run_system_action("shutdown")
            if any(keyword in user_lower for keyword in ["restart", "reboot"]):
                return TaskExecutor._run_system_action("reboot")
            if any(keyword in user_lower for keyword in ["sleep", "suspend"]):
                return TaskExecutor._run_system_action("suspend")
            
            # Commands that don't need sudo
            if any(kw in user_lower for kw in ["lock", "screen lock"]):
                return TaskExecutor._run_command(["loginctl", "lock-session"], "Locking the screen.")
            
            elif "volume" in user_lower:
                if "up" in user_lower or "increase" in user_lower:
                    return TaskExecutor._run_command(["amixer", "set", "Master", "5%+"], "Volume increased.")
                elif "down" in user_lower or "decrease" in user_lower:
                    return TaskExecutor._run_command(["amixer", "set", "Master", "5%-"], "Volume decreased.")
                elif "mute" in user_lower:
                    return TaskExecutor._run_command(["amixer", "set", "Master", "toggle"], "Mute toggled.")
            
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
                        return TaskExecutor._close_application(app_name)
                    else:
                        # Open the application
                        return TaskExecutor._open_application(app_name)
            
            return False, "Application not recognized."
        
        except Exception as e:
            return False, f"Error launching application: {str(e)}"
