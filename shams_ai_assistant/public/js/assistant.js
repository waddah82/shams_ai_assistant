(() => {
  "use strict";

  if (window.__shams_ai_assistant_bootstrapped) return;
  window.__shams_ai_assistant_bootstrapped = true;

  const state = {
    open: false,
    conversation: null,
    providers: [],
    provider: null,
    mcpServers: [],
    mcpServer: null,
    mounted: false,
  };

  const esc = (value = "") => String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));

  const byId = (id) => document.getElementById(id);
  const messages = () => byId("shams-ai-messages");

  function getContext() {
    const route = window.frappe?.get_route ? frappe.get_route() : [];
    return {
      route,
      doctype: route[0] === "Form" ? route[1] : null,
      docname: route[0] === "Form" ? route[2] : null,
    };
  }

  function iconMarkup() {
    return `
      <svg viewBox="0 0 64 64" aria-hidden="true" focusable="false">
        <path d="M32 5c2.5 10.7 8.3 16.5 19 19-10.7 2.5-16.5 8.3-19 19-2.5-10.7-8.3-16.5-19-19C23.7 21.5 29.5 15.7 32 5Z" fill="currentColor"/>
        <circle cx="48" cy="46" r="7" fill="currentColor" opacity=".72"/>
      </svg>`;
  }

  function panelMarkup() {
    return `
      <button id="shams-ai-button" type="button" title="Shams AI Assistant" aria-label="فتح مساعد شمس">
        ${iconMarkup()}
        <span class="shams-ai-button-label">AI</span>
      </button>
      <div id="shams-ai-backdrop" aria-hidden="true"></div>
      <aside id="shams-ai-panel" dir="rtl" aria-label="Shams AI Assistant">
        <header class="shams-ai-header">
          <div class="shams-ai-brand">
            <span class="shams-ai-logo">${iconMarkup()}</span>
            <div><b>Shams AI</b><small id="shams-ai-model">مساعد ERPNext</small></div>
          </div>
          <button id="shams-ai-close" type="button" aria-label="إغلاق">×</button>
        </header>
        <div class="shams-ai-toolbar">
          <select id="shams-ai-provider" aria-label="مزود الذكاء"></select>
          <select id="shams-ai-mcp" aria-label="خادم MCP"><option value="">بدون MCP</option></select>
          <button id="shams-ai-new" type="button">محادثة جديدة</button>
        </div>
        <main id="shams-ai-messages">
          <div class="shams-ai-welcome">
            <span class="shams-ai-welcome-icon">${iconMarkup()}</span>
            <b>مرحبًا بك في Shams AI</b>
            <span>اختر المزود ثم اكتب سؤالك. استخدم <code>/current</code> لقراءة المستند المفتوح.</span>
          </div>
        </main>
        <footer class="shams-ai-composer">
          <textarea id="shams-ai-input" rows="1" placeholder="اكتب رسالتك..." aria-label="نص الرسالة"></textarea>
          <button id="shams-ai-send" type="button">إرسال</button>
        </footer>
      </aside>`;
  }

  function mount() {
    if (!document.body || byId("shams-ai-button")) return;
    document.body.insertAdjacentHTML("beforeend", panelMarkup());
    state.mounted = true;

    byId("shams-ai-button").addEventListener("click", () => setOpen(true));
    byId("shams-ai-close").addEventListener("click", () => setOpen(false));
    byId("shams-ai-backdrop").addEventListener("click", () => setOpen(false));
    byId("shams-ai-new").addEventListener("click", newConversation);
    byId("shams-ai-send").addEventListener("click", send);
    byId("shams-ai-provider").addEventListener("change", (event) => {
      state.provider = event.target.value;
      updateModel();
    });
    byId("shams-ai-input").addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        send();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && state.open) setOpen(false);
    });

    loadProviders();
    loadMCPServers();
  }

  function setOpen(open) {
    state.open = Boolean(open);
    byId("shams-ai-panel")?.classList.toggle("open", state.open);
    byId("shams-ai-backdrop")?.classList.toggle("open", state.open);
    byId("shams-ai-button")?.classList.toggle("panel-open", state.open);
    document.documentElement.classList.toggle("shams-ai-open", state.open);
    if (state.open) setTimeout(() => byId("shams-ai-input")?.focus(), 120);
  }

  function newConversation() {
    state.conversation = null;
    messages().innerHTML = `
      <div class="shams-ai-welcome">
        <span class="shams-ai-welcome-icon">${iconMarkup()}</span>
        <b>محادثة جديدة</b><span>كيف يمكنني مساعدتك؟</span>
      </div>`;
    byId("shams-ai-input")?.focus();
  }

  function addMessage(role, text) {
    messages()?.querySelector(".shams-ai-welcome")?.remove();
    messages()?.insertAdjacentHTML("beforeend", `
      <div class="shams-ai-msg ${role}"><div>${esc(text).replace(/\n/g, "<br>")}</div></div>`);
    messages().scrollTop = messages().scrollHeight;
  }

  function updateModel() {
    const provider = state.providers.find((item) => item.name === state.provider);
    const label = byId("shams-ai-model");
    if (label) label.textContent = provider
      ? `${provider.provider_type} · ${provider.default_model}`
      : "لا يوجد مزود مفعّل";
  }

  async function loadProviders() {
    const select = byId("shams-ai-provider");
    if (!window.frappe?.call) {
      select.innerHTML = '<option value="">ERPNext غير جاهز</option>';
      return;
    }
    try {
      const response = await frappe.call("shams_ai_assistant.api.chat.list_providers");
      state.providers = response.message || [];
      select.innerHTML = state.providers.length
        ? state.providers.map((provider) => `<option value="${esc(provider.name)}">${esc(provider.provider_name)} — ${esc(provider.default_model)}</option>`).join("")
        : '<option value="">لا يوجد مزود مفعّل</option>';
      state.provider = (state.providers.find((provider) => provider.is_default) || state.providers[0] || {}).name || null;
      if (state.provider) select.value = state.provider;
      updateModel();
    } catch (error) {
      console.error("Shams AI provider loading failed", error);
      addMessage("assistant", "تعذر تحميل مزودات الذكاء. أنشئ مزودًا مفعّلًا من AI Provider.");
    }
  }

  async function loadMCPServers() {
    const select = byId("shams-ai-mcp");
    if (!select || !window.frappe?.call) return;
    try {
      const response = await frappe.call("shams_ai_assistant.api.mcp.list_servers");
      state.mcpServers = response.message || [];
      select.innerHTML = '<option value="">بدون MCP</option>' + state.mcpServers.map((server) => `<option value="${esc(server.name)}">MCP: ${esc(server.server_name)}</option>`).join("");
      state.mcpServer = (state.mcpServers.find((server) => server.is_default) || {}).name || "";
      select.value = state.mcpServer;
      select.addEventListener("change", (event) => { state.mcpServer = event.target.value; });
    } catch (error) {
      console.warn("Shams AI MCP loading failed", error);
    }
  }

  async function send() {
    const input = byId("shams-ai-input");
    const text = input?.value.trim();
    if (!text) return;
    if (!state.provider) {
      frappe?.msgprint?.("لا يوجد AI Provider مفعّل.");
      return;
    }

    input.value = "";
    addMessage("user", text);
    const button = byId("shams-ai-send");
    button.disabled = true;
    button.textContent = "...";

    try {
      const response = await frappe.call({
        method: "shams_ai_assistant.api.chat.send",
        args: {
          message: text,
          conversation: state.conversation,
          provider: state.provider,
          context: JSON.stringify(getContext()),
          mcp_server: state.mcpServer || null,
        },
        freeze: false,
      });
      state.conversation = response.message.conversation;
      addMessage("assistant", response.message.answer);
    } catch (error) {
      const message = error?.message || error?.exc || "حدث خطأ أثناء الاتصال بالمزود.";
      addMessage("assistant", message);
    } finally {
      button.disabled = false;
      button.textContent = "إرسال";
      input?.focus();
    }
  }

  function bootstrap() {
    mount();
    // Frappe Desk is a single-page application. Recreate the button if another script removes it.
    window.setInterval(() => {
      if (document.body && !byId("shams-ai-button")) mount();
    }, 3000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrap, { once: true });
  } else {
    bootstrap();
  }
  window.addEventListener("load", mount, { once: true });
})();
