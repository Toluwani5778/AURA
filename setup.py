#!/usr/bin/env python3
"""
AURA Setup and Verification Script
Checks all dependencies and external services before running
"""

import subprocess
import sys
import os
import json
from pathlib import Path
import requests
import time

class AuraSetup:
    """Setup and verification tool for AURA"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.data_dir = self.project_root / "data"
        self.sessions_dir = self.data_dir / "sessions"
        self.resources_dir = self.project_root / "resources"
        self.audio_input_dir = self.resources_dir / "audio" / "Input"
        self.audio_output_dir = self.resources_dir / "audio" / "Output"
        
        self.checks_passed = 0
        self.checks_failed = 0
    
    def print_header(self, text):
        """Print a section header"""
        print("\n" + "="*60)
        print(f"  {text}")
        print("="*60)
    
    def print_check(self, name, status, message=""):
        """Print a check result"""
        symbol = "✅" if status else "❌"
        print(f"{symbol} {name}")
        if message:
            print(f"   {message}")
        
        if status:
            self.checks_passed += 1
        else:
            self.checks_failed += 1
    
    def run_command(self, cmd, shell=False):
        """Run a shell command and return success status"""
        try:
            result = subprocess.run(
                cmd,
                shell=shell,
                capture_output=True,
                timeout=5,
                text=True
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)
    
    def check_python_version(self):
        """Check Python version"""
        self.print_header("🐍 Python Version")
        try:
            version = sys.version_info
            required_version = (3, 10)
            
            if version >= required_version:
                self.print_check(
                    f"Python {version.major}.{version.minor}",
                    True,
                    f"Required: >= {required_version[0]}.{required_version[1]}"
                )
            else:
                self.print_check(
                    f"Python {version.major}.{version.minor}",
                    False,
                    f"Required: >= {required_version[0]}.{required_version[1]}"
                )
        except Exception as e:
            self.print_check("Python version", False, str(e))
    
    def check_python_packages(self):
        """Check required Python packages"""
        self.print_header("📦 Python Dependencies")
        
        required_packages = {
            "pyaudio": "PyAudio",
            "numpy": "NumPy",
            "requests": "Requests",
            "faster_whisper": "Faster Whisper",
            "openwakeword": "OpenWakeWord",
            "soundfile": "SoundFile",
        }
        
        for package_name, display_name in required_packages.items():
            try:
                __import__(package_name)
                self.print_check(display_name, True)
            except ImportError:
                self.print_check(
                    display_name,
                    False,
                    f"Install with: pip install {package_name}"
                )
    
    def check_ollama(self):
        """Check Ollama connection"""
        self.print_header("🦙 Ollama LLM Server")
        
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            
            if response.status_code == 200:
                models = response.json().get("models", [])
                if models:
                    model_names = [m.get("name", "unknown") for m in models]
                    self.print_check(
                        "Ollama Connection",
                        True,
                        f"Found models: {', '.join(model_names[:3])}"
                    )
                else:
                    self.print_check(
                        "Ollama Connection",
                        False,
                        "No models installed. Run: ollama pull qwen3.6:latest"
                    )
            else:
                self.print_check("Ollama Connection", False, "Invalid response")
        
        except requests.exceptions.ConnectionError:
            self.print_check(
                "Ollama Connection",
                False,
                "Cannot connect to http://localhost:11434\n"
                "   Start Ollama: ollama serve"
            )
        except Exception as e:
            self.print_check("Ollama Connection", False, str(e))
    
    def check_kokoro_tts(self):
        """Check Kokoro TTS service"""
        self.print_header("🎙️ Kokoro TTS Server")
        
        try:
            response = requests.get("http://localhost:8880/docs", timeout=2)
            self.print_check(
                "Kokoro Connection",
                response.status_code == 200,
                "http://localhost:8880"
            )
        except requests.exceptions.ConnectionError:
            self.print_check(
                "Kokoro Connection",
                False,
                "Cannot connect to http://localhost:8880\n"
                "   Start Kokoro: python3 server.py (from Kokoro-82M repo)"
            )
        except Exception as e:
            self.print_check("Kokoro Connection", False, str(e))
    
    def check_audio_devices(self):
        """Check audio input/output devices"""
        self.print_header("🔊 Audio Devices")
        
        try:
            import pyaudio
            pa = pyaudio.PyAudio()
            
            # Check for input devices
            input_devices = 0
            output_devices = 0
            
            for i in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(i)
                if info["maxInputChannels"] > 0:
                    input_devices += 1
                if info["maxOutputChannels"] > 0:
                    output_devices += 1
            
            pa.terminate()
            
            self.print_check(
                f"Input Devices",
                input_devices > 0,
                f"Found {input_devices} microphone(s)"
            )
            self.print_check(
                f"Output Devices",
                output_devices > 0,
                f"Found {output_devices} speaker(s)"
            )
        except Exception as e:
            self.print_check("Audio Devices", False, str(e))
    
    def check_directories(self):
        """Create and check required directories"""
        self.print_header("📁 Directory Structure")
        
        directories = {
            self.data_dir: "Data directory",
            self.sessions_dir: "Sessions directory",
            self.audio_input_dir: "Audio input directory",
            self.audio_output_dir: "Audio output directory",
        }
        
        for directory, name in directories.items():
            try:
                directory.mkdir(parents=True, exist_ok=True)
                self.print_check(name, True, str(directory))
            except Exception as e:
                self.print_check(name, False, str(e))
    
    def check_configuration(self):
        """Check configuration file"""
        self.print_header("⚙️ Configuration")
        
        config_path = self.project_root / "core" / "config.py"
        try:
            self.print_check("Config file exists", config_path.exists(), str(config_path))
        except Exception as e:
            self.print_check("Config file", False, str(e))
    
    def print_summary(self):
        """Print summary of checks"""
        self.print_header("📊 Summary")
        
        total = self.checks_passed + self.checks_failed
        print(f"\n✅ Passed: {self.checks_passed}/{total}")
        print(f"❌ Failed: {self.checks_failed}/{total}\n")
        
        if self.checks_failed == 0:
            print("🎉 All checks passed! Ready to run AURA.\n")
            print("Start AURA with: python main.py\n")
            return True
        else:
            print("⚠️  Please fix the issues above before running AURA.\n")
            return False
    
    def run_all_checks(self):
        """Run all setup checks"""
        print("\n" + "🌟 "*30)
        print("AURA Setup & Verification Tool".center(60))
        print("🌟 "*30)
        
        self.check_python_version()
        self.check_python_packages()
        self.check_directories()
        self.check_configuration()
        self.check_ollama()
        self.check_kokoro_tts()
        self.check_audio_devices()
        
        return self.print_summary()


def main():
    """Main entry point"""
    setup = AuraSetup()
    success = setup.run_all_checks()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
