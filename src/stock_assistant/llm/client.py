from __future__ import annotations

import re

import requests

from ..config import Settings


class LLMUnavailable(RuntimeError):
    """Raised when the configured local LLM is not reachable."""


class OllamaClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model
        self.timeout = settings.request_timeout

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
        except requests.RequestException:
            return False
        return True

    def chat(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LLMUnavailable(f"Ollama 不可用或模型响应超时：{exc}") from exc

        data = response.json()
        content = data.get("message", {}).get("content", "")
        if not content:
            raise LLMUnavailable("Ollama 返回为空。")
        return strip_thinking(content).strip()


def strip_thinking(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()

