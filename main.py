"""
AURA - Personal AI Assistant
Main application loop with wakeword detection, conversation management, and timeouts
"""

import pyaudio
import numpy as np
import time
import threading
import re
from PyQt6.QtWidgets import QApplication
from core.alsa import silence_alsa_errors, suppress_alsa_errors
from core.llm import ask_VA, plan_action
from core.memory import SessionManager
from core.events import EventPublisher
from core.state import AURAState
from core.task_executor import TaskExecutor
from core.skills import global_skill_registry, initialize_default_skills
from voice.Text2Speech import speak, play_audio
from voice.Speech2Text import transcribe_audio
from voice.Wakeup import Wakeup_agent, listen_for_sleep_word
from core.config import (
    SESSION_TIMEOUT, MAX_TIMEOUTS, SLEEP_WAKEWORD, 
    AUDIO_FORMAT, AUDIO_CHANNELS, AUDIO_RATE, AUDIO_FRAMES_PER_BUFFER
)
from ui.orb import AuraHUD

silence_alsa_errors()


class AuraAssistant:
    """Main AURA Assistant Class"""
    
    def __init__(self, event_publisher=None):
        self.session = None
        self.audio_stream = None
        self.running = False
        self.audio_thread = None
        self.state = AURAState.SLEEPING
        self.events = event_publisher or EventPublisher()
        self.session_saved = False
        with suppress_alsa_errors():
            self.pa = pyaudio.PyAudio()

    def set_state(self, state: AURAState, **data):
        """Update the shared state and notify observers."""
        self.state = state
        self.events.publish("state_changed", state=state, **data)

    def emit(self, name: str, **data):
        """Publish a lifecycle event without changing assistant state."""
        return self.events.publish(name, state=self.state, **data)
    
    def _get_audio_stream(self):
        """Get or create audio stream"""
        if self.audio_stream is None:
            with suppress_alsa_errors():
                self.audio_stream = self.pa.open(
                    format=pyaudio.paInt16,
                    channels=AUDIO_CHANNELS,
                    rate=AUDIO_RATE,
                    input=True,
                    frames_per_buffer=AUDIO_FRAMES_PER_BUFFER,
                )
        return self.audio_stream
        
    def speak_response(self, text):
        """Generate speech and play audio response"""
        try:
            self.set_state(AURAState.SPEAKING, text=text)
            self.emit("response_started", text=text)
            print(f"🎙️ AURA: {text[:100]}...")  # Print first 100 chars
            audio_file = speak(text)
            play_audio(audio_file)
            self.emit("response_completed", text=text)
        except Exception as e:
            self.set_state(AURAState.ERROR, error=str(e))
            self.emit("error", error=str(e), operation="speech")
            print(f"❌ Error in speech synthesis: {e}")
    
    def listen_for_command(self, timeout=30):
        """
        Listen for user voice input using live stream transcription
        Returns: (user_text, timeout_occurred)
        """
        try:
            self.set_state(AURAState.LISTENING)
            stream = self._get_audio_stream()
            user_input = transcribe_audio(stream=stream, duration=timeout)
            
            if user_input:
                self.emit("transcript_received", text=user_input)
                return user_input, False
            else:
                return None, True
        
        except Exception as e:
            self.set_state(AURAState.ERROR, error=str(e))
            self.emit("error", error=str(e), operation="transcription")
            print(f"❌ Error during transcription: {e}")
            return None, True
    
    def handle_timeout(self):
        """Handle timeout scenario - ask if user is still there"""
        self.session.increment_timeout_count()
        
        if self.session.should_force_sleep(MAX_TIMEOUTS):
            print("😴 Timeout limit reached. Going to sleep...")
            self.speak_response("I haven't heard from you in a while. I'm going to rest now. Wake me up anytime!")
            return True  # Signal to end session
        
        print("⏰ Session timeout triggered")
        self.speak_response(f"I haven't heard from you in {SESSION_TIMEOUT} seconds. Are you still there?")
        return False  # Continue session
    
    def check_for_sleep_word(self, transcribed_text):
        """Check if the transcribed text contains sleep word"""
        if not transcribed_text:
            return False

        normalized_input = re.sub(r"[^a-z0-9']+", " ", transcribed_text.lower()).strip()
        normalized_input = re.sub(r"\s+", " ", normalized_input)
        sleep_phrases = {
            SLEEP_WAKEWORD.lower(),
            "good night aura",
            "good night aurora",
            "goodnight aura",
            "goodnight aurora",
            "good night",
            "goodnight",
        }
        return any(phrase in normalized_input for phrase in sleep_phrases)
    
    def run_session(self):
        """Run an active AURA session"""
        self.set_state(AURAState.WAKING)
        self.session = SessionManager()
        self.session_saved = False
        self.session.is_active = True
        
        print("\n" + "="*50)
        print("🚀 AURA Session Started!")
        print("="*50 + "\n")
        
        # Greeting
        greeting = "Hi there! I'm AURA, your personal AI assistant. How can I help you today?"
        self.speak_response(greeting)
        self.session.add_message("assistant", greeting)
        
        last_interaction_time = time.time()
        
        try:
            while self.running and self.session.is_active:
                # Check for timeout
                current_time = time.time()
                idle_time = current_time - last_interaction_time
                
                if idle_time > SESSION_TIMEOUT:
                    should_sleep = self.handle_timeout()
                    if should_sleep:
                        break
                    last_interaction_time = current_time  # Reset timer
                
                # Listen for user input
                try:
                    user_input, timeout_occurred = self.listen_for_command(timeout=10)
                    
                    if timeout_occurred or not user_input:
                        print("⚠️ No input detected, continuing to listen...")
                        continue
                    
                    # Reset timeout counter on successful input
                    self.session.reset_timeout_count()
                    last_interaction_time = time.time()
                    
                    # Check for sleep word
                    if self.check_for_sleep_word(user_input):
                        print(f"User said sleep word: '{user_input}'")
                        sleep_response = "Good night! I'll be here if you need me. Sleep well!"
                        self.session.add_message("user", user_input)
                        self.session.add_message("assistant", sleep_response)
                        self.speak_response(sleep_response)
                        break
                    
                    print(f"👤 User: {user_input}")
                    self.session.add_message("user", user_input)
                    self.set_state(AURAState.PROCESSING, text=user_input)
                    
                    task_type = TaskExecutor.classify_task(user_input)
                    context = self.session.get_context_for_llm()
                    action_plan = {"action": "none", "app": None}
                    if TaskExecutor.may_be_action_request(user_input):
                        self.set_state(AURAState.THINKING, text=user_input)
                        action_plan = plan_action(user_input, context)
                        if action_plan["action"] == "none":
                            action_plan = TaskExecutor.extract_search_request(user_input) or action_plan

                    # Direct actions are deterministic and should happen before
                    # an LLM response, while conversation remains model-driven.
                    if action_plan["action"] != "none":
                        self.emit("tool_started", action=action_plan["action"], app=action_plan.get("app"))
                        if action_plan["action"] in {"reboot", "shutdown", "suspend"}:
                            notice = f"I'm preparing to {action_plan['action']} the computer now. I'll save this session first."
                            self.session.add_message("assistant", notice)
                            self.speak_response(notice)
                            self.session.is_active = False
                            self.session.save_session()
                            self.session_saved = True
                        self.set_state(AURAState.EXECUTING, action=action_plan["action"])
                        task_success, task_response = TaskExecutor.execute_plan(action_plan)
                        self.emit("tool_completed", action=action_plan["action"], success=task_success)
                        if task_success:
                            final_response = task_response
                        else:
                            final_response = ask_VA(user_input, context)
                    elif task_type.value in {"pc_control", "app_control"}:
                        task_success, task_response = TaskExecutor.execute(user_input)
                        if task_success:
                            final_response = task_response
                        else:
                            final_response = ask_VA(user_input, context)
                    else:
                        # Narrow utility skills may answer immediately. Anything
                        # ambiguous, contextual, or conversational goes to Ollama.
                        skill_success, skill_response, skill_used = global_skill_registry.execute(
                            user_input,
                            excluded_names={"Capabilities"},
                        )

                        if skill_success and skill_response:
                            final_response = skill_response
                            print(f"💡 Skill '{skill_used.name}' used")
                        else:
                            final_response = ask_VA(user_input, context)
                    
                    self.session.add_message("assistant", final_response)
                    
                    # Speak the response
                    self.speak_response(final_response)
                    
                except Exception as e:
                    self.set_state(AURAState.ERROR, error=str(e))
                    self.emit("error", error=str(e), operation="interaction")
                    print(f"❌ Error during interaction: {e}")
                    continue
        
        except KeyboardInterrupt:
            print("\n⚠️ Session interrupted by user")
            self.emit("session_interrupted")
        
        finally:
            self.end_session()
    
    def end_session(self):
        """End the current session and save history"""
        if self.session:
            if not self.session_saved:
                self.session.end_session()
                self.session_saved = True
            else:
                self.session.is_active = False
            self.emit("session_ended", session_name=self.session.session_name)
            summary = self.session.get_session_summary()
            print("\n" + "="*50)
            print("📊 Session Summary:")
            print(f"   Duration: {summary['duration_seconds']:.1f} seconds")
            print(f"   Messages: {summary['message_count']}")
            print(f"   Timeouts: {summary['timeout_count']}")
            print("="*50 + "\n")
        
        self.running = False
        self.set_state(AURAState.SLEEPING)
        
        # Cleanup audio resources
        if self.audio_stream:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
        self.pa.terminate()


def main():
    """Main application entry point"""
    print("\n" + "🌟 "*20)
    print("Welcome to AURA - Adaptive Utility & Reasoning Assistant")
    print("🌟 "*20 + "\n")
    
    # Initialize skills framework
    initialize_default_skills()
    
    app = QApplication.instance() or QApplication([])
    hud = AuraHUD()
    hud.place_top_right()
    hud.show()

    assistant = AuraAssistant(event_publisher=EventPublisher())
    assistant.events.subscribe(hud.receive_event)
    assistant.running = True

    def assistant_loop():
        try:
            while assistant.running:
                print("👂 Waiting for wake word...")
                assistant.set_state(AURAState.WAKING)

                if Wakeup_agent():
                    assistant.emit("wakeword_detected")
                    print("✅ Wake word detected!")
                    assistant.run_session()
                else:
                    assistant.set_state(AURAState.SLEEPING)

                print("\n❓ Say the wake word again to start a new session, or exit the program.")
        except KeyboardInterrupt:
            print("\n\n👋 Shutting down AURA...")
        except Exception as error:
            assistant.set_state(AURAState.ERROR, error=str(error))
            assistant.emit("error", error=str(error), operation="main_loop")
            print(f"\n❌ Fatal error: {error}")
        finally:
            assistant.running = False
            print("Goodbye! 👋\n")

    worker = threading.Thread(target=assistant_loop, name="aura-assistant", daemon=True)
    worker.start()
    app.aboutToQuit.connect(lambda: setattr(assistant, "running", False))
    app.exec()


if __name__ == "__main__":
    main()