import json
import requests
from core.config import OLLAMA_URL, OLLAMA_MODEL, SYSTEM_PROMPT

def ask_VA(prompt, context=""):
    """
    Query the LLM with a prompt and optional conversation context
    
    Args:
        prompt: The user's current input/question
        context: Previous conversation context for memory
    
    Returns:
        str: The LLM's response
    """
    # Combine system prompt, context, and current prompt
    full_prompt = f"{SYSTEM_PROMPT}\n\n{context}\n\nUser: {prompt}\n\nAURA:"
    
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": full_prompt,
            "stream": False
        }
    )
    
    return response.json()["response"].strip()


def plan_action(prompt, context=""):
    """Return a validated allowlisted action inferred by Ollama."""
    planner_prompt = f"""You are AURA's action planner. Infer the user's immediate intent from the latest request and context.
Return JSON only with exactly these keys: action, app, query, browser.
Allowed action values: none, reboot, shutdown, suspend, lock, volume_up, volume_down, volume_mute, open_app, close_app, search_web.
For open_app or close_app, app must be one of: firefox, chrome, chromium, vscode, terminal, konsole, spotify, vlc, blender, gimp, thunderbird, nautilus.
For search_web, query must contain the requested search terms and browser must be firefox, google, or duckduckgo.
Use action none for conversation, questions, praise, thanks, or unclear requests.
Only select reboot, shutdown, or suspend when the user clearly asks for that operation.
Never return shell commands, explanations, markdown, or extra keys.

{context}
Latest user request: {prompt}"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": planner_prompt,
                "format": "json",
                "stream": False,
            },
            timeout=30,
        )
        plan = json.loads(response.json().get("response", "{}"))
    except (OSError, ValueError, KeyError, requests.RequestException):
        return {"action": "none", "app": None, "query": "", "browser": "firefox"}

    allowed_actions = {
        "none", "reboot", "shutdown", "suspend", "lock",
        "volume_up", "volume_down", "volume_mute", "open_app", "close_app", "search_web",
    }
    allowed_apps = {
        "firefox", "chrome", "chromium", "vscode", "terminal", "konsole",
        "spotify", "vlc", "blender", "gimp", "thunderbird", "nautilus",
    }
    action = plan.get("action")
    app = plan.get("app")
    if action not in allowed_actions:
        return {"action": "none", "app": None, "query": "", "browser": "firefox"}
    if action in {"open_app", "close_app"} and app not in allowed_apps:
        return {"action": "none", "app": None, "query": "", "browser": "firefox"}
    browser = plan.get("browser", "firefox")
    query = plan.get("query", "")
    if action == "search_web" and (browser not in {"firefox", "google", "duckduckgo"} or not str(query).strip()):
        return {"action": "none", "app": None, "query": "", "browser": "firefox"}
    return {"action": action, "app": app, "query": query, "browser": browser}