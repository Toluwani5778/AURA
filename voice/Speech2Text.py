"""Speech-to-text with Faster Whisper. The model loads lazily on first use."""

import logging
import re
import threading

import numpy as np

from core.config import WHISPER_COMPUTE_TYPE, WHISPER_DEVICE, WHISPER_MODEL_SIZE

log = logging.getLogger("aura.stt")
_model = None
_lock = threading.Lock()

# Whisper invents these on silence / noise.
HALLUCINATIONS = {"thank you", "thanks for watching", "you", "bye", ".", "thank you for watching",
                  "subtitles by the amara.org community"}


def _preload_pip_cuda_libs():
    """CTranslate2 needs libcublas, which pip installs outside the linker path."""
    import ctypes
    import glob
    import os
    import site
    for base in site.getsitepackages():
        for lib in sorted(glob.glob(os.path.join(base, "nvidia", "*", "lib", "lib*.so.*"))):
            try:
                ctypes.CDLL(lib, mode=ctypes.RTLD_GLOBAL)
            except OSError:
                pass


def _load(device, compute_type):
    from faster_whisper import WhisperModel
    try:  # offline first: at boot the network may not be up yet
        return WhisperModel(WHISPER_MODEL_SIZE, device=device, compute_type=compute_type,
                            local_files_only=True)
    except Exception:
        return WhisperModel(WHISPER_MODEL_SIZE, device=device, compute_type=compute_type)


def get_model():
    """Load Whisper, proving the GPU path works before trusting it."""
    global _model
    with _lock:
        if _model is None:
            if WHISPER_DEVICE == "cuda":
                try:
                    _preload_pip_cuda_libs()
                    model = _load("cuda", WHISPER_COMPUTE_TYPE)
                    list(model.transcribe(np.zeros(16000, dtype=np.float32), language="en")[0])
                    _model = model
                    log.info("Whisper %s on GPU", WHISPER_MODEL_SIZE)
                except Exception as error:  # CUDA libs missing, VRAM full, ...
                    log.warning("Whisper GPU unavailable (%s); using CPU", error)
            if _model is None:
                _model = _load("cpu", "int8")
                log.info("Whisper %s on CPU", WHISPER_MODEL_SIZE)
    return _model


def transcribe(audio, initial_prompt="AURA, Konsole, Firefox, VS Code, Fedora.") -> str:
    """Transcribe float32 16 kHz mono audio, or a path to an audio file."""
    try:
        segments, _info = get_model().transcribe(
            audio, beam_size=5, language="en", vad_filter=isinstance(audio, str),
            condition_on_previous_text=False, initial_prompt=initial_prompt,
        )
        text = " ".join(s.text.strip() for s in segments if s.no_speech_prob < 0.6).strip()
    except Exception as error:
        log.error("Transcription failed: %s", error)
        return ""
    if re.sub(r"[^a-z ]", "", text.lower()).strip() in HALLUCINATIONS:
        return ""
    return text


def transcribe_audio(audio_path=None, audio: np.ndarray = None) -> str:
    """Backwards-compatible wrapper."""
    return transcribe(audio_path if audio_path else audio)
