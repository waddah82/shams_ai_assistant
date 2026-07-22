from .base import BaseProvider, ProviderResponse


class GeminiProvider(BaseProvider):
    def chat(self, messages, system_prompt="", tools=None):
        base = (self.config.base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        key = self.config.get_password("api_key", raise_exception=False) or ""
        if not key:
            raise RuntimeError("Gemini API Key is not configured.")

        contents = []
        for message in messages:
            role = "model" if message.get("role") == "assistant" else "user"
            contents.append({
                "role": role,
                "parts": [{"text": message.get("content", "")}],
            })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": float(self.config.temperature or 0.2),
                "maxOutputTokens": int(self.config.max_output_tokens or 2048),
            },
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        data = self.post(
            f"{base}/models/{self.config.default_model}:generateContent?key={key}",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            json=payload,
        )
        candidates = data.get("candidates") or []
        parts = (candidates[0].get("content") or {}).get("parts", []) if candidates else []
        text = self.text_from_content(parts)
        if not text:
            raise RuntimeError(self.empty_response_reason(data))
        return ProviderResponse(text=text, raw=data, usage=data.get("usageMetadata"))
