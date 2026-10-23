from __future__ import annotations

import re

import requests

from ..config import Settings


class LLMUnavailable(RuntimeError):
    """Raised when the configured LLM is not reachable."""


class OllamaClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.ollama_base_url.strip().rstrip("/")
        self.model = settings.ollama_model
        self.timeout = settings.request_timeout

    def check(self) -> None:
        """Check transport, response schema and exact installed model name."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=min(5, self.timeout))
            response.raise_for_status()
            data = response.json()
            models = data["models"]
            if not isinstance(models, list) or any(not isinstance(m, dict) for m in models):
                raise ValueError("models 必须是对象列表")
            names = {m.get("name") for m in models if isinstance(m.get("name"), str)}
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            raise LLMUnavailable("Ollama 检测失败：检查 SSH 隧道、Windows Ollama 和 /api/tags 响应。") from exc
        if self.model not in names:
            raise LLMUnavailable(f"Ollama 未安装模型 {self.model}；请在 Windows 执行 ollama list / ollama pull。")

    def is_available(self) -> bool:
        try:
            self.check()
        except LLMUnavailable:
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

        try:
            data = response.json()
            content = data["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("content 必须是字符串")
            content = strip_thinking(content).strip()
            if not content:
                raise ValueError("正文为空")
        except (ValueError, KeyError, TypeError) as exc:
            raise LLMUnavailable("Ollama 返回无效或正文为空。") from exc
        return content


def strip_thinking(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()

