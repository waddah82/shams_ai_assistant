import frappe

from shams_ai_assistant.shams_ai_assistant.doctype.ai_provider.ai_provider import (
    build_system_prompt,
)


STANDARD_PROVIDERS = [
    {
        "provider_name": "OpenAI",
        "provider_type": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    },
    {
        "provider_name": "Anthropic",
        "provider_type": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "api_version": "2023-06-01",
        "default_model": "claude-3-5-sonnet-latest",
    },
    {
        "provider_name": "Google Gemini",
        "provider_type": "Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "default_model": "gemini-2.0-flash",
    },
    {
        "provider_name": "Mistral",
        "provider_type": "Mistral",
        "base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-small-latest",
    },
    {
        "provider_name": "Ollama",
        "provider_type": "Ollama",
        "base_url": "http://127.0.0.1:11434",
        "default_model": "llama3.1",
        "verify_ssl": 0,
    },
    {
        "provider_name": "OpenRouter",
        "provider_type": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o-mini",
    },
    {
        "provider_name": "Azure OpenAI",
        "provider_type": "Azure OpenAI",
        "base_url": "",
        "default_model": "deployment-name",
    },
    {
        "provider_name": "OpenAI Compatible",
        "provider_type": "OpenAI Compatible",
        "base_url": "",
        "default_model": "model-name",
    },
    {
        "provider_name": "Custom Provider",
        "provider_type": "Custom",
        "base_url": "",
        "default_model": "model-name",
    },
]


def sync_standard_providers():
    """Create one editable AI Provider record for each supported provider type.

    Existing records are never overwritten. This keeps API keys, models, URLs,
    enabled state, tool mode, and administrator customizations intact.
    """
    if not frappe.db.exists("DocType", "AI Provider"):
        return

    existing_types = set(
        frappe.get_all("AI Provider", pluck="provider_type")
    )

    for provider in STANDARD_PROVIDERS:
        if provider["provider_type"] in existing_types:
            continue

        values = {
            "doctype": "AI Provider",
            "enabled": 0,
            "is_default": 0,
            "request_timeout": 120,
            "verify_ssl": 1,
            "temperature": 0.2,
            "max_output_tokens": 2048,
            "tool_mode": "Auto",
            "native_mcp_source": "Custom MCP Server",
            "native_mcp_fallback": 1,
            "auto_update_system_prompt": 1,
            "system_prompt": build_system_prompt("Auto", "Custom MCP Server"),
            **provider,
        }
        frappe.get_doc(values).insert(ignore_permissions=True)


def execute():
    sync_standard_providers()
