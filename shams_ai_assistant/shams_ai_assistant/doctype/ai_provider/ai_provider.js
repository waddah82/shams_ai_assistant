frappe.ui.form.on("AI Provider", {
  refresh(frm) {
    frm.trigger("set_provider_defaults");
  },

  provider_type(frm) {
    frm.trigger("set_provider_defaults");
  },

  tool_mode(frm) {
    frm.trigger("update_system_prompt_for_mode");
  },

  native_mcp_source(frm) {
    if (["Native MCP", "Local + Native MCP", "Auto"].includes(frm.doc.tool_mode)) {
      frm.trigger("update_system_prompt_for_mode");
    }
  },

  auto_update_system_prompt(frm) {
    if (frm.doc.auto_update_system_prompt) {
      frm.trigger("update_system_prompt_for_mode");
    }
  },

  set_provider_defaults(frm) {
    const defaults = {
      "OpenAI": {
        base_url: "https://api.openai.com/v1",
        default_model: "gpt-4o-mini",
      },
      "Anthropic": {
        base_url: "https://api.anthropic.com/v1",
        api_version: "2023-06-01",
        default_model: "claude-3-5-sonnet-latest",
      },
      "Gemini": {
        base_url: "https://generativelanguage.googleapis.com/v1beta",
        default_model: "gemini-2.0-flash",
      },
      "Mistral": {
        base_url: "https://api.mistral.ai/v1",
        default_model: "mistral-small-latest",
      },
      "Ollama": {
        base_url: "http://127.0.0.1:11434",
        default_model: "llama3.1",
      },
      "OpenRouter": {
        base_url: "https://openrouter.ai/api/v1",
        default_model: "openai/gpt-4o-mini",
      },
      "Azure OpenAI": {
        default_model: "deployment-name",
      },
      "OpenAI Compatible": {
        default_model: "model-name",
      },
      "Custom": {
        default_model: "model-name",
      },
    };

    const value = defaults[frm.doc.provider_type];
    if (!value) return;

    if (value.base_url && !frm.doc.base_url) {
      frm.set_value("base_url", value.base_url);
    }
    if (value.api_version && !frm.doc.api_version) {
      frm.set_value("api_version", value.api_version);
    }
    if (value.default_model && !frm.doc.default_model) {
      frm.set_value("default_model", value.default_model);
    }
  },

  update_system_prompt_for_mode(frm) {
    if (!frm.doc.auto_update_system_prompt) return;

    frappe.call({
      method: "shams_ai_assistant.shams_ai_assistant.doctype.ai_provider.ai_provider.get_mode_system_prompt",
      args: {
        tool_mode: frm.doc.tool_mode || "Auto",
        native_mcp_source: frm.doc.native_mcp_source || "Custom MCP Server",
      },
      callback(r) {
        if (r.message) {
          frm.set_value("system_prompt", r.message);
        }
      },
    });
  },
});
