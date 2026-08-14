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