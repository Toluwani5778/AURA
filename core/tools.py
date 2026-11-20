"""AURA's tools: the actions the LLM may choose to take.

Add a tool by decorating a function with @tool. The docstring becomes the
description the model sees; `params` is a JSON-schema "properties" dict.
Tools return a short plain-text result that is fed back to the model.

risk="confirm" tools are never executed directly: the agent asks the user
first and only runs them after a spoken "yes" (enforced in code, not prompt).
"""

import configparser
import datetime as dt
import difflib
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional
from urllib.parse import quote_plus

import requests

from core.config import SEARXNG_URL

log = logging.getLogger("aura.tools")

SAFE, CONFIRM = "safe", "confirm"


@dataclass
class Tool:
    name: str
    description: str
    func: Callable[..., str]
    params: Dict[str, dict] = field(default_factory=dict)
    required: tuple = ()
    risk: str = SAFE

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.params,
                    "required": list(self.required),
                },
            },
        }


class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Tool] = {}

    def register(self, tool_obj: Tool) -> None:
        self.tools[tool_obj.name] = tool_obj

    def get(self, name: str) -> Optional[Tool]:
        return self.tools.get(name)

    def schemas(self) -> list:
        return [t.schema() for t in self.tools.values()]

    def run(self, name: str, args: dict) -> str:
        tool_obj = self.tools.get(name)
        if tool_obj is None:
            return f"Error: unknown tool '{name}'."
        allowed = set(tool_obj.params)
        clean = {k: v for k, v in (args or {}).items() if k in allowed}
        try:
            return str(tool_obj.func(**clean))
        except Exception as error:  # a broken tool must never kill the loop
            log.exception("Tool %s failed", name)
            return f"Error running {name}: {error}"


registry = ToolRegistry()


def tool(params=None, required=(), risk=SAFE, name=None):
    def wrap(func):
        registry.register(Tool(
            name=name or func.__name__,
            description=" ".join((func.__doc__ or "").split()),
            func=func,
            params=params or {},
            required=tuple(required),
            risk=risk,
        ))
        return func
    return wrap


def _str(description):
    return {"type": "string", "description": description}


def _run(cmd, timeout=10) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def _spawn(cmd) -> None:
    subprocess.Popen(
        cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, start_new_session=True,
    )


# ---------------------------------------------------------------------------
# Applications (discovered from installed .desktop files, incl. Flatpak)
# ---------------------------------------------------------------------------

ALIASES = {
    "console": "konsole", "terminal": "konsole", "shell": "konsole",
    "mozilla": "firefox", "browser": "firefox", "web browser": "firefox",
    "vs code": "visual studio code", "vscode": "visual studio code", "code": "visual studio code",
    "files": "dolphin", "file manager": "dolphin", "explorer": "dolphin",
    "obs": "obs studio", "notes": "sticky", "settings": "system settings",
}


@dataclass
class DesktopApp:
    desktop_id: str
    name: str
    exec_line: str
    flatpak_id: str = ""

    @property
    def process_name(self) -> str:
        if self.flatpak_id:
            match = re.search(r"--command=(\S+)", self.exec_line)
            return match.group(1) if match else ""
        first = self.exec_line.split()[0] if self.exec_line else ""
        return os.path.basename(first)


def _desktop_dirs():
    dirs = [Path.home() / ".local/share/applications",
            Path.home() / ".local/share/flatpak/exports/share/applications",
            Path("/var/lib/flatpak/exports/share/applications")]
    for base in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":"):
        dirs.append(Path(base) / "applications")
    return dirs


_app_cache: Optional[Dict[str, DesktopApp]] = None


def installed_apps() -> Dict[str, DesktopApp]:
    """Map lowercase display name -> app, for launchable GUI apps."""
    global _app_cache
    if _app_cache is not None:
        return _app_cache
    apps: Dict[str, DesktopApp] = {}
    for directory in _desktop_dirs():
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.desktop")):
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(path, encoding="utf-8")
                entry = parser["Desktop Entry"]
            except (configparser.Error, KeyError, UnicodeDecodeError):
                continue
            if entry.get("NoDisplay", "false").lower() == "true" or entry.get("Type") != "Application":
                continue
            name = entry.get("Name", "").strip()
            if not name or name.lower() in apps:
                continue
            exec_line = entry.get("Exec", "")
            flatpak = entry.get("X-Flatpak", "")
            apps[name.lower()] = DesktopApp(path.stem, name, exec_line, flatpak)
    _app_cache = apps
    return apps


def find_app(query: str) -> Optional[DesktopApp]:
    q = query.lower().strip()
    q = re.sub(r"^(the|my)\s+", "", q)
    q = re.sub(r"\s+(app|application|program)$", "", q)
    q = ALIASES.get(q, q)
    apps = installed_apps()
    if q in apps:
        return apps[q]
    for app in apps.values():
        if q == app.desktop_id.lower() or q == app.process_name.lower() or q in app.desktop_id.lower().split("."):
            return app
    for key, app in apps.items():
        if q in key.split() or key.startswith(q):
            return app
    close = difflib.get_close_matches(q, list(apps), n=1, cutoff=0.6)
    return apps[close[0]] if close else None


@tool(params={"name": _str("App name as the user said it, e.g. 'firefox', 'console', 'vs code'")},
      required=["name"])
def open_app(name: str) -> str:
    """Launch an installed desktop application."""
    app = find_app(name)
    if not app:
        return f"No installed app matches '{name}'. Use list_apps to see what is installed."
    _spawn(["gtk-launch", app.desktop_id])
    return f"Launched {app.name}."


@tool(params={"name": _str("App name, e.g. 'firefox'")}, required=["name"])
def close_app(name: str) -> str:
    """Close a running desktop application."""
    app = find_app(name)
    if not app:
        return f"No installed app matches '{name}'."
    if app.flatpak_id:
        result = _run(["flatpak", "kill", app.flatpak_id])
    else:
        proc = app.process_name
        if not proc:
            return f"I don't know which process belongs to {app.name}."
        result = _run(["pkill", "-x", proc])
        if result.returncode == 1:
            result = _run(["pkill", "-f", proc])
    if result.returncode == 0:
        return f"Closed {app.name}."
    return f"{app.name} doesn't appear to be running."


@tool()
def list_apps() -> str:
    """List the desktop applications installed on this computer."""
    return ", ".join(sorted(a.name for a in installed_apps().values()))


# ---------------------------------------------------------------------------
# Web
# ---------------------------------------------------------------------------

@tool(params={"query": _str("What to look up")}, required=["query"])
def web_search(query: str) -> str:
    """Search the internet (private SearXNG) and return the top results so you can
    answer questions about current events, facts, weather, prices, etc."""
    try:
        response = requests.get(f"{SEARXNG_URL}/search",
                                params={"q": query, "format": "json"}, timeout=10)
        response.raise_for_status()
        results = response.json().get("results", [])[:5]
    except (requests.RequestException, ValueError) as error:
        return f"Search failed: {error}"
    if not results:
        return "No results."
    return "\n".join(f"- {r.get('title', '')}: {r.get('content', '')[:300]} ({r.get('url', '')})"
                     for r in results)


@tool(params={"target": _str("A URL, a site name like 'youtube', or search terms")},
      required=["target"])
def open_in_browser(target: str) -> str:
    """Open a website, or show a web search, in the user's browser."""
    t = target.strip()
    if re.match(r"^https?://", t):
        url = t
    elif re.match(r"^[\w-]+(\.[\w-]+)+(/\S*)?$", t):
        url = "https://" + t
    elif re.fullmatch(r"[a-zA-Z]+", t) and t.lower() in {
            "youtube", "gmail", "github", "reddit", "netflix", "twitter", "amazon", "wikipedia"}:
        url = f"https://www.{t.lower()}.com" if t.lower() != "wikipedia" else "https://wikipedia.org"
    else:
        url = "https://duckduckgo.com/?q=" + quote_plus(t)
    _spawn(["xdg-open", url])
    return f"Opened {url}."


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

@tool()
def get_datetime() -> str:
    """Get the current local date and time."""
    return dt.datetime.now().strftime("%A, %B %d %Y, %I:%M %p")


@tool(params={
    "action": {"type": "string", "enum": ["up", "down", "set", "mute", "unmute"]},
    "percent": {"type": "integer", "description": "Target volume for 'set', or step for up/down (default 10)"},
}, required=["action"])
def volume(action: str, percent: int = None) -> str:
    """Change the speaker volume."""
    sink = "@DEFAULT_AUDIO_SINK@"
    if action == "mute":
        _run(["wpctl", "set-mute", sink, "1"])
    elif action == "unmute":
        _run(["wpctl", "set-mute", sink, "0"])
    elif action == "set":
        level = max(0, min(int(percent if percent is not None else 50), 150))
        _run(["wpctl", "set-volume", sink, f"{level}%"])
    else:
        step = int(percent or 10)
        _run(["wpctl", "set-volume", "-l", "1.5", sink, f"{step}%{'+' if action == 'up' else '-'}"])
    current = _run(["wpctl", "get-volume", sink]).stdout.strip()
    return f"Done. {current}"


@tool(params={"action": {"type": "string", "enum": ["play", "pause", "play-pause", "next", "previous"]}},
      required=["action"])
def media(action: str) -> str:
    """Control whatever media player is playing (Spotify, browser video, etc.)."""
    if not shutil.which("playerctl"):
        return "playerctl is not installed (sudo dnf install playerctl)."
    result = _run(["playerctl", action])
    return "Done." if result.returncode == 0 else (result.stderr.strip() or "No player is running.")


@tool()
def lock_screen() -> str:
    """Lock the screen."""
    _run(["loginctl", "lock-session"])
    return "Screen locked."


POWER_COMMANDS = {
    "shutdown": ["systemctl", "poweroff"],
    "reboot": ["systemctl", "reboot"],
    "suspend": ["systemctl", "suspend"],
    "logout": ["loginctl", "terminate-user", os.environ.get("USER", "")],
}


@tool(params={"action": {"type": "string", "enum": list(POWER_COMMANDS)}},
      required=["action"], risk=CONFIRM)
def power(action: str) -> str:
    """Shut down, reboot, suspend or log out of the computer."""
    command = POWER_COMMANDS.get(action)
    if not command:
        return f"Unknown power action {action}."
    _spawn(command)
    return f"{action.capitalize()} started."


@tool()
def system_status() -> str:
    """Report CPU load, memory, GPU, disk usage and uptime."""
    parts = []
    load1, _, _ = os.getloadavg()
    parts.append(f"CPU load {load1:.1f} on {os.cpu_count()} cores")
    meminfo = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
    total = int(meminfo["MemTotal"].split()[0]) / 1048576
    avail = int(meminfo["MemAvailable"].split()[0]) / 1048576
    parts.append(f"RAM {total - avail:.1f} of {total:.1f} GB used")
    if shutil.which("nvidia-smi"):
        gpu = _run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                    "--format=csv,noheader,nounits"]).stdout.strip()
        if gpu:
            util, used, tot, temp = [x.strip() for x in gpu.split(",")]
            parts.append(f"GPU {util}% busy, {int(used) / 1024:.1f} of {int(tot) / 1024:.1f} GB VRAM, {temp}°C")
    disk = shutil.disk_usage(str(Path.home()))
    parts.append(f"home disk {disk.used / 1e9:.0f} of {disk.total / 1e9:.0f} GB used")
    uptime = float(Path("/proc/uptime").read_text().split()[0])
    parts.append(f"up {int(uptime // 3600)}h {int(uptime % 3600 // 60)}m")
    return "; ".join(parts)


WEATHER_CODES = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "foggy", 48: "foggy",
                 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain",
                 65: "heavy rain", 66: "freezing rain", 67: "freezing rain", 71: "light snow", 73: "snow",
                 75: "heavy snow", 77: "snow grains", 80: "rain showers", 81: "rain showers",
                 82: "violent rain showers", 85: "snow showers", 86: "heavy snow showers",
                 95: "thunderstorms", 96: "thunderstorms with hail", 99: "thunderstorms with hail"}


@tool(params={"location": _str("City name, e.g. 'Toronto'. Use the user's home city from memory if not given.")},
      required=["location"])
def weather(location: str) -> str:
    """Current weather and the next 3 days' forecast for a city."""
    try:
        geo = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                           params={"name": location.split(",")[0].strip(), "count": 1}, timeout=8).json()
        place = (geo.get("results") or [None])[0]
        if not place:
            return f"I couldn't find a place called {location}."
        data = requests.get("https://api.open-meteo.com/v1/forecast", timeout=8, params={
            "latitude": place["latitude"], "longitude": place["longitude"], "timezone": "auto",
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "forecast_days": 3,
        }).json()
    except (requests.RequestException, ValueError) as error:
        return f"Weather lookup failed: {error}"
    cur, daily = data["current"], data["daily"]
    lines = [f"{place['name']}, {place.get('admin1', '')}: now {cur['temperature_2m']:.0f}°C "
             f"(feels {cur['apparent_temperature']:.0f}°C), {WEATHER_CODES.get(cur['weather_code'], 'unknown')}, "
             f"wind {cur['wind_speed_10m']:.0f} km/h."]
    for i, day in enumerate(daily["time"]):
        label = ["Today", "Tomorrow", day][min(i, 2)]
        lines.append(f"{label}: {WEATHER_CODES.get(daily['weather_code'][i], '')}, high {daily['temperature_2m_max'][i]:.0f}, "
                     f"low {daily['temperature_2m_min'][i]:.0f}, {daily['precipitation_probability_max'][i]}% chance of rain.")
    return " ".join(lines)


@tool(params={"question": _str("What the user wants to know about their screen")}, required=["question"])
def look_at_screen(question: str) -> str:
    """Take a screenshot and look at it to answer a question about what's on the
    user's screen (an error message, a window, a chart). Only when the user asks."""
    import base64
    import tempfile
    from core.config import OLLAMA_HOST, OLLAMA_KEEP_ALIVE, VISION_MODEL
    import time
    path = os.path.join(tempfile.gettempdir(), "aura-screen.png")
    if os.path.exists(path):
        os.remove(path)
    _run(["spectacle", "-b", "-n", "-f", "-o", path], timeout=15)
    for _ in range(50):  # spectacle may hand off to a running instance and return early
        if os.path.exists(path) and os.path.getsize(path) > 0:
            break
        time.sleep(0.1)
    else:
        return "I couldn't capture the screen."
    time.sleep(0.2)
    try:
        image = base64.b64encode(Path(path).read_bytes()).decode()
        response = requests.post(f"{OLLAMA_HOST}/api/chat", timeout=120, json={
            "model": VISION_MODEL, "stream": False, "think": False, "keep_alive": OLLAMA_KEEP_ALIVE,
            "messages": [{"role": "user", "images": [image],
                          "content": f"This is a screenshot of my desktop. {question} "
                                     "Answer concisely and specifically, quoting any key text."}],
        })
        response.raise_for_status()
        return response.json()["message"]["content"]
    except (requests.RequestException, KeyError, ValueError) as error:
        return f"Screen analysis failed: {error}"
    finally:
        os.remove(path)
