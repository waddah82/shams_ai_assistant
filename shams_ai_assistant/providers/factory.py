from .openai_compatible import OpenAICompatibleProvider
from .anthropic import AnthropicProvider
from .gemini import GeminiProvider
from .ollama import OllamaProvider
from .mistral import MistralProvider


def get_provider(config):
    kind = (config.provider_type or "").strip().lower()
    if kind in {"openai", "openrouter", "azure openai", "openai compatible", "custom"}:
        return OpenAICompatibleProvider(config)
    if kind == "anthropic":
        return AnthropicProvider(config)
    if kind == "gemini":
        return GeminiProvider(config)
    if kind == "ollama":
        return OllamaProvider(config)
    if kind == "mistral":
        return MistralProvider(config)
    raise ValueError(f"Unsupported provider type: {config.provider_type}")
