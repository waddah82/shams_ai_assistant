from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import json
import requests

@dataclass
class ProviderResponse:
    text: str
    raw: dict[str, Any]
    usage: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

class BaseProvider(ABC):
    def __init__(self, config):
        self.config = config
        self.timeout = int(config.request_timeout or 120)

    @abstractmethod
    def chat(self, messages, system_prompt="", tools=None) -> ProviderResponse:
        raise NotImplementedError

    def supports_function_tools(self) -> bool:
        return False

    def supports_native_mcp(self) -> bool:
        return False

    def chat_native_mcp(self, messages, system_prompt="", native_mcp=None, local_tools=None) -> ProviderResponse:
        raise RuntimeError(f"{self.__class__.__name__} does not support native Remote MCP.")

    def post(self, url, *, headers=None, json=None):
        response = requests.post(url, headers=headers or {}, json=json, timeout=self.timeout, verify=bool(self.config.verify_ssl))
        if not response.ok:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:2000]}")
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(f"Provider returned non-JSON data: {response.text[:1000]}") from exc

    @staticmethod
    def text_from_content(content: Any) -> str:
        if content is None: return ""
        if isinstance(content, str): return content.strip()
        if isinstance(content, (int, float, bool)): return str(content)
        if isinstance(content, list):
            return "".join(BaseProvider.text_from_content(x) for x in content).strip()
        if isinstance(content, dict):
            for key in ("text", "output_text", "content", "value"):
                if key in content:
                    value = BaseProvider.text_from_content(content.get(key))
                    if value: return value
            return ""
        return str(content).strip()

    @classmethod
    def extract_chat_text(cls, data):
        text = cls.text_from_content(data.get("output_text"))
        if text: return text
        choices = data.get("choices") or []
        if choices:
            choice = choices[0] or {}; message = choice.get("message") or {}
            for candidate in (message.get("content"), message.get("reasoning_content"), choice.get("text"), choice.get("content")):
                text = cls.text_from_content(candidate)
                if text: return text
        for item in data.get("output") or []:
            text = cls.text_from_content(item.get("content") if isinstance(item, dict) else item)
            if text: return text
        return ""

    @staticmethod
    def extract_tool_calls(data):
        choices = data.get("choices") or []
        if not choices: return []
        raw_calls = ((choices[0] or {}).get("message") or {}).get("tool_calls") or []
        calls = []
        for call in raw_calls:
            fn = call.get("function") or {}
            args = fn.get("arguments") or "{}"
            try:
                args = json.loads(args) if isinstance(args, str) else (args or {})
            except Exception:
                args = {"_raw": args}
            calls.append({"id": call.get("id"), "name": fn.get("name"), "arguments": args, "raw": call})
        return calls

    @staticmethod
    def empty_response_reason(data):
        choices = data.get("choices") or []
        if choices:
            choice = choices[0] or {}; finish_reason = choice.get("finish_reason")
            if finish_reason: return f"The model returned no text (finish_reason={finish_reason})."
        if data.get("promptFeedback"):
            return "The provider blocked the prompt: " + json.dumps(data.get("promptFeedback"), ensure_ascii=False, default=str)[:800]
        return "The provider returned a valid response but no readable text was found."
