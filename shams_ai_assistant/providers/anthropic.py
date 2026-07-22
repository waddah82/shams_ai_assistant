from .base import BaseProvider, ProviderResponse


class AnthropicProvider(BaseProvider):
    def chat(self, messages, system_prompt="", tools=None):
        base = (self.config.base_url or "https://api.anthropic.com/v1").rstrip("/")
        key = self.config.get_password("api_key", raise_exception=False) or ""
        if not key:
            raise RuntimeError("Anthropic API Key is not configured.")

        headers = {
            "x-api-key": key,
            "anthropic-version": self.config.api_version or "2023-06-01",
            "content-type": "application/json",
            "accept": "application/json",
        }
        payload = {
            "model": self.config.default_model,
            "max_tokens": int(self.config.max_output_tokens or 2048),
            "messages": messages,
        }
        if system_prompt:
            payload["system"] = system_prompt

        data = self.post(f"{base}/messages", headers=headers, json=payload)
        text = self.text_from_content(data.get("content") or [])
        if not text:
            stop_reason = data.get("stop_reason")
            suffix = f" (stop_reason={stop_reason})" if stop_reason else ""
            raise RuntimeError("Anthropic returned no readable text" + suffix + ".")
        return ProviderResponse(text=text, raw=data, usage=data.get("usage"))
