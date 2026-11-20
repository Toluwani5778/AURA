"""Health check: `python doctor.py` verifies everything AURA depends on."""

import os
import shutil
import sys

import requests

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from core.config import OLLAMA_HOST, OLLAMA_MODEL, SEARXNG_URL, TTS_API_URL, WAKEWORD_MODEL_PATH  # noqa: E402

ok = True


def check(name, passed, hint=""):
    global ok
    ok &= bool(passed)
    print(f"  {'✅' if passed else '❌'} {name}" + (f"  → {hint}" if hint and not passed else ""))


def get(url, **kw):
    try:
        return requests.get(url, timeout=3, **kw)
    except requests.RequestException:
        return None


print("AURA doctor\n")
check(f"Python {sys.version.split()[0]} (3.10+)", sys.version_info >= (3, 10))
for mod in ("pyaudio", "faster_whisper", "openwakeword", "PyQt6", "requests", "numpy"):
    try:
        __import__(mod)
        check(f"python package {mod}", True)
    except ImportError:
        check(f"python package {mod}", False, "pip install -r requirements.txt")

tags = get(f"{OLLAMA_HOST}/api/tags")
check("Ollama running", tags is not None and tags.ok, "systemctl start ollama")
if tags is not None and tags.ok:
    names = [m["name"] for m in tags.json().get("models", [])]
    check(f"model {OLLAMA_MODEL} pulled", OLLAMA_MODEL in names, f"ollama pull {OLLAMA_MODEL}")
voices = get(f"{TTS_API_URL}/v1/audio/voices")
check("Kokoro TTS container", voices is not None and voices.ok, "docker start kokoro")
search = get(f"{SEARXNG_URL}/search", params={"q": "test", "format": "json"})
check("SearXNG (web_search tool)", search is not None and search.ok,
      "docker start searxng; enable 'json' under search.formats in settings.yml")
check("wake word model", os.path.exists(WAKEWORD_MODEL_PATH), WAKEWORD_MODEL_PATH)
for tool, why in (("wpctl", "volume"), ("gtk-launch", "opening apps"), ("xdg-open", "browser"),
                  ("pw-play", "audio playback"), ("playerctl", "media control (optional)")):
    check(f"{tool} ({why})", shutil.which(tool), f"sudo dnf install {tool}")
try:
    import pyaudio
    pa = pyaudio.PyAudio()
    inputs = [pa.get_device_info_by_index(i)["name"] for i in range(pa.get_device_count())
              if pa.get_device_info_by_index(i)["maxInputChannels"] > 0]
    pa.terminate()
    check(f"microphone ({len(inputs)} input devices)", inputs)
except Exception as error:  # noqa: BLE001
    check("microphone", False, str(error))

print("\nAll good!" if ok else "\nSome checks failed (optional ones can be ignored).")
