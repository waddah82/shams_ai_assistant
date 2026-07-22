from .base import BaseProvider, ProviderResponse


class OllamaProvider(BaseProvider):
    def chat(self, messages, system_prompt="", tools=None):
        base = (self.config.base_url or "http://127.0.0.1:11434").rstrip("/")
        payload_messages = []
        if system_prompt:
            payload_messages.append({"role": "system", "content": system_prompt})
        payload_messages.extend(messages)

        data = self.post(
            f"{base}/api/chat",
            json={
                "model": self.config.default_model,
                "messages": payload_messages,
                "stream": False,
                "options": {"temperature": float(self.config.temperature or 0.2)},
            },
        )
        text = self.text_from_content((data.get("message") or {}).get("content"))
        if not text:
            raise RuntimeError(self.empty_response_reason(data))
        return ProviderResponse(
            text=text,
            raw=data,
            usage={
                "prompt_eval_count": data.get("prompt_eval_count"),
                "eval_count": data.get("eval_count"),
            },
        )
