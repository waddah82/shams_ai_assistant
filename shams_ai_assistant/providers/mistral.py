from .base import BaseProvider, ProviderResponse

class MistralProvider(BaseProvider):
    def supports_function_tools(self) -> bool:
        """Mistral Chat Completions accepts OpenAI-style function tools."""
        return True

    def chat(self, messages, system_prompt="", tools=None):
        base=(self.config.base_url or "https://api.mistral.ai/v1").rstrip("/")
        api_key=self.config.get_password("api_key", raise_exception=False) or ""
        if not api_key: raise RuntimeError("Mistral API Key is not configured.")
        payload_messages=[]
        if system_prompt: payload_messages.append({"role":"system","content":system_prompt})
        payload_messages.extend(messages)
        payload={"model":self.config.default_model,"messages":payload_messages,"temperature":float(self.config.temperature or 0.2)}
        if tools:
            payload["tools"]=tools; payload["tool_choice"]="auto"
        if self.config.max_output_tokens: payload["max_tokens"]=int(self.config.max_output_tokens)
        data=self.post(f"{base}/chat/completions",headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json","Accept":"application/json"},json=payload)
        text=self.extract_chat_text(data); calls=self.extract_tool_calls(data)
        if not text and not calls: raise RuntimeError(self.empty_response_reason(data))
        return ProviderResponse(text=text,raw=data,usage=data.get("usage"),tool_calls=calls)
