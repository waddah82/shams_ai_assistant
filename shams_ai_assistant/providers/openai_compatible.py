from __future__ import annotations
import re
from .base import BaseProvider, ProviderResponse


class OpenAICompatibleProvider(BaseProvider):
    def _headers(self):
        api_key=self.config.get_password("api_key", raise_exception=False) or ""
        headers={"Content-Type":"application/json","Accept":"application/json"}
        if api_key: headers["Authorization"]=f"Bearer {api_key}"
        return headers

    def supports_function_tools(self) -> bool:
        return True

    def supports_native_mcp(self) -> bool:
        # OpenAI Responses API supports Remote MCP. Generic compatible endpoints,
        # OpenRouter and Azure are not assumed to support the same contract.
        return (self.config.provider_type or "").strip().lower() == "openai"

    def chat(self, messages, system_prompt="", tools=None):
        base=(self.config.base_url or "https://api.openai.com/v1").rstrip("/")
        payload_messages=[]
        if system_prompt: payload_messages.append({"role":"system","content":system_prompt})
        payload_messages.extend(messages)
        model=(self.config.default_model or "").strip()
        payload={"model":model,"messages":payload_messages}
        if tools:
            payload["tools"]=tools
            payload["tool_choice"]="auto"
        lowered=model.lower(); reasoning=lowered.startswith(("gpt-5","o1","o3","o4"))
        if not reasoning: payload["temperature"]=float(self.config.temperature or 0.2)
        if self.config.max_output_tokens:
            payload["max_completion_tokens" if reasoning else "max_tokens"]=int(self.config.max_output_tokens)
        data=self.post(f"{base}/chat/completions",headers=self._headers(),json=payload)
        text=self.extract_chat_text(data); calls=self.extract_tool_calls(data)
        if not text and not calls: raise RuntimeError(self.empty_response_reason(data))
        return ProviderResponse(text=text,raw=data,usage=data.get("usage"),tool_calls=calls)

    def chat_native_mcp(self, messages, system_prompt="", native_mcp=None, local_tools=None):
        if not self.supports_native_mcp():
            return super().chat_native_mcp(messages, system_prompt, native_mcp, local_tools)
        native_mcp = native_mcp or {}
        base=(self.config.base_url or "https://api.openai.com/v1").rstrip("/")
        model=(self.config.default_model or "").strip()
        input_messages=[]
        for item in messages:
            role=item.get("role")
            if role not in {"user","assistant"}: continue
            input_messages.append({"role":role,"content":item.get("content") or ""})
        tool={"type":"mcp","server_label":native_mcp.get("server_label") or "shams_mcp"}
        if native_mcp.get("connector_id"):
            tool["connector_id"]=native_mcp["connector_id"]
            if native_mcp.get("authorization"):
                tool["authorization"]=native_mcp["authorization"]
        else:
            tool["server_url"]=native_mcp.get("server_url")
            if native_mcp.get("headers"): tool["headers"]=native_mcp["headers"]
        if native_mcp.get("allowed_tools"):
            tool["allowed_tools"]=native_mcp["allowed_tools"]
        tool["require_approval"] = native_mcp.get("require_approval", "never")
        response_tools=[]
        for item in local_tools or []:
            fn=(item or {}).get("function") or {}
            response_tools.append({"type":"function","name":fn.get("name"),"description":fn.get("description") or "","parameters":fn.get("parameters") or {"type":"object","properties":{}}})
        response_tools.append(tool)
        payload={"model":model,"input":input_messages,"tools":response_tools}
        if system_prompt: payload["instructions"]=system_prompt
        if self.config.max_output_tokens: payload["max_output_tokens"]=int(self.config.max_output_tokens)
        data=self.post(f"{base}/responses",headers=self._headers(),json=payload)
        text=self.text_from_content(data.get("output_text"))
        if not text:
            chunks=[]
            for item in data.get("output") or []:
                if not isinstance(item,dict): continue
                if item.get("type") == "message":
                    chunks.append(self.text_from_content(item.get("content")))
            text="".join(x for x in chunks if x).strip()
        calls=[]
        for item in data.get("output") or []:
            if not isinstance(item,dict) or item.get("type") != "function_call":
                continue
            args=item.get("arguments") or "{}"
            try:
                import json as _json
                args=_json.loads(args) if isinstance(args,str) else (args or {})
            except Exception:
                args={"_raw":args}
            calls.append({"id":item.get("call_id") or item.get("id"),"name":item.get("name"),"arguments":args,"raw":item})
        if not text and not calls: raise RuntimeError(self.empty_response_reason(data))
        usage=data.get("usage") or {}
        return ProviderResponse(text=text,raw=data,usage=usage,tool_calls=calls)
