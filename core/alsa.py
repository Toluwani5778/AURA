"""Helpers for silencing non-fatal ALSA diagnostics."""

import ctypes
from contextlib import contextmanager


_ERROR_HANDLER = ctypes.CFUNCTYPE(
    None,
    ctypes.c_char_p,
    ctypes.c_int,
    ctypes.c_char_p,
    ctypes.c_int,
    ctypes.c_char_p,
)


def _ignore_alsa_error(filename, line, function, err, fmt):
    """Ignore diagnostics emitted by ALSA's native library."""


_error_handler = _ERROR_HANDLER(_ignore_alsa_error)
_asound = None


def silence_alsa_errors():
    """Install the ALSA error callback for the lifetime of this process."""
    global _asound

    if _asound is not None:
        return

    try:
        _asound = ctypes.cdll.LoadLibrary("libasound.so.2")
        _asound.snd_lib_error_set_handler(_error_handler)
    except OSError:
        _asound = False


@contextmanager
def suppress_alsa_errors():
    """Temporarily silence ALSA diagnostics around an audio operation."""
    silence_alsa_errors()
    yield