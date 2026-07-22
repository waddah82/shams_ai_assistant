# Shams AI Assistant 3.0.0

Multi-provider AI assistant for Frappe/ERPNext v15 and v16 with a floating Desk chat, OpenAI, Anthropic Claude, Google Gemini, Mistral, Ollama, OpenRouter, Azure OpenAI, OpenAI-compatible providers, and local/remote MCP server configuration.

## Install from Git

```bash
cd ~/frappe-bench
bench get-app https://YOUR-GIT-SERVER/shams-ai-assistant.git --branch main
bench --site YOUR-SITE install-app shams_ai_assistant
bench build --app shams_ai_assistant
bench --site YOUR-SITE migrate
bench --site YOUR-SITE clear-cache
bench restart
```

## Install from a local Git repository

```bash
cd ~/frappe-bench
bench get-app file:///absolute/path/shams_ai_assistant
bench --site YOUR-SITE install-app shams_ai_assistant
bench build --app shams_ai_assistant
bench --site YOUR-SITE migrate
bench restart
```

Configure **AI Provider** and optionally **AI MCP Server** from Desk.
