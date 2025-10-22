from __future__ import annotations
import requests, json, os

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

def generate_once(model: str, prompt: str, temp: float = 0.2) -> str:
    url = f"{OLLAMA_HOST}/api/generate"
    payload = {"model": model, "prompt": prompt, "options": {"temperature": temp}, "stream": False}
    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data.get("response", "").strip()
