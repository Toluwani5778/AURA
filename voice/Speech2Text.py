"""
Speech-to-Text Module
Handles audio transcription using Faster Whisper
"""

import numpy as np
import pyaudio
from faster_whisper import WhisperModel
from core.config import (
    WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE,
    AUDIO_RATE, AUDIO_FRAMES_PER_BUFFER, AUDIO_CHANNELS
)

# Initialize the model once
model = WhisperModel(
    WHISPER_MODEL_SIZE,
    device=WHISPER_DEVICE,
    compute_type=WHISPER_COMPUTE_TYPE
)


def transcribe_audio(audio_path=None, stream=None, duration=10):
    """
    Transcribe audio from either a file or a live stream
    
    Args:
        audio_path: Path to audio file (optional)
        stream: PyAudio stream object for live recording (optional)
        duration: Duration to record in seconds (only used if stream provided)
    
    Returns:
        str: Transcribed text
    """
    if audio_path:
        # Transcribe from file
        return _transcribe_file(audio_path)
    elif stream:
        # Transcribe from live stream
        return _transcribe_stream(stream, duration)
    else:
        raise ValueError("Either audio_path or stream must be provided")


def _transcribe_file(audio_path):
    """Transcribe audio from a file"""
    try:
        segments, info = model.transcribe(
            audio_path,
            vad_filter=True,
            vad_parameters={"threshold": 0.5, "min_silence_duration_ms": 500},
            beam_size=5
        )

        print(f"Detected language '{info.language}' with probability {info.language_probability:.2f}")

        texts = []
        for segment in segments:
            print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
            texts.append(segment.text)

        result_text = " ".join(texts)
        return result_text

    except Exception as e:
        print(f"Error transcribing file: {e}")
        return ""


def _transcribe_stream(stream, duration=10):
    """
    Transcribe audio from a live PyAudio stream
    
    Args:
        stream: PyAudio stream object
        duration: Duration to record in seconds
    
    Returns:
        str: Transcribed text
    """
    try:
        print(f"🎤 Recording audio for {duration} seconds...")
        
        frames = []
        frames_per_second = AUDIO_RATE // AUDIO_FRAMES_PER_BUFFER
        num_frames = frames_per_second * duration
        
        for _ in range(num_frames):
            try:
                data = stream.read(AUDIO_FRAMES_PER_BUFFER, exception_on_overflow=False)
                frames.append(np.frombuffer(data, dtype=np.int16))
            except Exception as e:
                print(f"Warning: Error reading audio frame: {e}")
                continue
        
        if not frames:
            print("No audio frames captured")
            return ""
        
        # Combine all frames into single audio array
        audio_data = np.concatenate(frames)
        
        print("✅ Recording complete. Transcribing...")
        
        # Transcribe the recorded audio
        segments, info = model.transcribe(
            audio_data.astype(np.float32) / 32768.0,  # Normalize audio
            vad_filter=True,
            vad_parameters={"threshold": 0.5, "min_silence_duration_ms": 500},
            beam_size=5
        )

        print(f"Detected language '{info.language}' with probability {info.language_probability:.2f}")

        texts = []
        for segment in segments:
            print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
            texts.append(segment.text)

        result_text = " ".join(texts).strip()
        return result_text

    except Exception as e:
        print(f"Error transcribing stream: {e}")
        return ""



