import pyaudio
import numpy as np
import openwakeword
import soundfile as sf
import time
from core.config import (
    WAKEWORD_PRETRAINED, WAKEWORD_CUSTOM, WAKEWORD_CUSTOM_PATH,
    WAKEWORD_THRESHOLD, SLEEP_WAKEWORD_THRESHOLD,
    AUDIO_FORMAT, AUDIO_CHANNELS, AUDIO_RATE, AUDIO_FRAMES_PER_BUFFER,
    USE_CUSTOM_MODEL
)

openwakeword.utils.download_models()

# AUDIO_PATH = "resources/audio/Input/seb.wav"  # path to the audio file

def get_wakeword_config():
    """Get wakeword configuration based on settings"""
    if USE_CUSTOM_MODEL:
        return WAKEWORD_CUSTOM_PATH, WAKEWORD_CUSTOM
    else:
        return WAKEWORD_PRETRAINED, WAKEWORD_PRETRAINED

def Wakeup_agent(mod=None, wakeword=None, threshold=WAKEWORD_THRESHOLD):
    """
    Wake word detection agent
    Returns: True if wake word detected, False otherwise
    """
    if mod is None or wakeword is None:
        mod, wakeword = get_wakeword_config()
    
    model = openwakeword.Model(
        wakeword_models=[mod],
        inference_framework="onnx"
    )

    pa = pyaudio.PyAudio()

    # Open a stream to capture audio from the microphone
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=1280,
    )

    print(f"🎤 Listening for wake word: '{wakeword}'...")

    while True:
        audio = np.frombuffer(
            stream.read(1280, exception_on_overflow=False),
            dtype=np.int16,
        )

        prediction = model.predict(audio)
        score = float(prediction[wakeword])

        if score > threshold:
            stream.stop_stream()
            stream.close()
            print(f"✅ Wake word detected! Confidence: {score:.3f}")
            return True


def listen_for_sleep_word(stream, sleep_word="good night aura", threshold=SLEEP_WAKEWORD_THRESHOLD):
    """
    Listen for sleep word during an active session
    Returns: True if sleep word detected, False if listening should continue
    """
    try:
        # Use the pretrained hey_mycroft model to detect speech
        model = openwakeword.Model(
            wakeword_models=["hey_mycroft"],
            inference_framework="onnx"
        )
        
        audio = np.frombuffer(
            stream.read(1280, exception_on_overflow=False),
            dtype=np.int16,
        )
        
        prediction = model.predict(audio)
        score = float(prediction["hey_mycroft"])
        
        # If speech detected with high confidence, it might be the sleep word
        if score > threshold:
            return True
    except Exception as e:
        print(f"Warning in sleep word detection: {e}")
    
    return False