"""
AURA - Personal AI Assistant
Main application loop with wakeword detection, conversation management, and timeouts
"""

import pyaudio
import numpy as np
import time
import threading
from core.llm import ask_VA
from core.memory import SessionManager
from core.task_executor import TaskExecutor
from core.skills import global_skill_registry, initialize_default_skills
from voice.Text2Speech import speak, play_audio
from voice.Speech2Text import transcribe_audio
from voice.Wakeup import Wakeup_agent, listen_for_sleep_word
from core.config import (
    SESSION_TIMEOUT, MAX_TIMEOUTS, SLEEP_WAKEWORD, 
    AUDIO_FORMAT, AUDIO_CHANNELS, AUDIO_RATE, AUDIO_FRAMES_PER_BUFFER
)


class AuraAssistant:
    """Main AURA Assistant Class"""
    
    def __init__(self):
        self.session = None
        self.audio_stream = None
        self.running = False
        self.audio_thread = None
        self.pa = pyaudio.PyAudio()
    
    def _get_audio_stream(self):
        """Get or create audio stream"""
        if self.audio_stream is None:
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
            print(f"🎙️ AURA: {text[:100]}...")  # Print first 100 chars
            audio_file = speak(text)
            play_audio(audio_file)
        except Exception as e:
            print(f"❌ Error in speech synthesis: {e}")
    
    def listen_for_command(self, timeout=30):
        """
        Listen for user voice input using live stream transcription
        Returns: (user_text, timeout_occurred)
        """
        try:
            stream = self._get_audio_stream()
            user_input = transcribe_audio(stream=stream, duration=timeout)
            
            if user_input:
                return user_input, False
            else:
                return None, True
        
        except Exception as e:
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
        if transcribed_text:
            sleep_word_lower = SLEEP_WAKEWORD.lower()
            if sleep_word_lower in transcribed_text.lower():
                return True
        return False
    
    def run_session(self):
        """Run an active AURA session"""
        self.session = SessionManager()
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
                    user_input, timeout_occurred = self.listen_for_command(timeout=30)
                    
                    if timeout_occurred or not user_input:
                        print("⚠️ No input detected, continuing to listen...")
                        continue
                    
                    # Reset timeout counter on successful input
                    self.session.reset_timeout_count()
                    last_interaction_time = time.time()
                    
                    # Check for sleep word
                    if self.check_for_sleep_word(user_input):
                        print(f"User said sleep word: '{user_input}'")
                        self.speak_response("Good night! I'll be here if you need me. Sleep well!")
                        break
                    
                    print(f"👤 User: {user_input}")
                    self.session.add_message("user", user_input)
                    
                    # Try to match a skill first
                    skill_success, skill_response, skill_used = global_skill_registry.execute(user_input)
                    
                    if skill_success and skill_response:
                        # Skill handled it
                        final_response = skill_response
                        print(f"💡 Skill '{skill_used.name}' used")
                    else:
                        # Fall back to LLM
                        context = self.session.get_context_for_llm()
                        llm_response = ask_VA(user_input, context)
                        
                        # Try to execute tasks based on LLM response
                        task_success, task_response = TaskExecutor.execute(user_input, llm_response)
                        final_response = task_response if task_success else llm_response
                    
                    print(f"🎙️ AURA: {final_response[:100]}...")
                    self.session.add_message("assistant", final_response)
                    
                    # Speak the response
                    self.speak_response(final_response)
                    
                except Exception as e:
                    print(f"❌ Error during interaction: {e}")
                    continue
        
        except KeyboardInterrupt:
            print("\n⚠️ Session interrupted by user")
        
        finally:
            self.end_session()
    
    def end_session(self):
        """End the current session and save history"""
        if self.session:
            self.session.end_session()
            summary = self.session.get_session_summary()
            print("\n" + "="*50)
            print("📊 Session Summary:")
            print(f"   Duration: {summary['duration_seconds']:.1f} seconds")
            print(f"   Messages: {summary['message_count']}")
            print(f"   Timeouts: {summary['timeout_count']}")
            print("="*50 + "\n")
        
        self.running = False
        
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
    
    assistant = AuraAssistant()
    assistant.running = True
    
    try:
        while assistant.running:
            print("👂 Waiting for wake word...")
            
            # Wait for wake word
            if Wakeup_agent():
                print("✅ Wake word detected!")
                
                # Run the main session
                assistant.run_session()
            
            # Ask if user wants to continue
            print("\n❓ Say the wake word again to start a new session, or exit the program.")
    
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down AURA...")
    
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("Goodbye! 👋\n")


if __name__ == "__main__":
    main()