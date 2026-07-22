import frappe
from frappe import _
from frappe.model.document import Document


PROMPT_COMMON = """You are Shams AI Assistant integrated with ERPNext.
Use only the tools made available for the selected integration mode.
Never invent ERPNext records, values, or successful operations.
Respect the current user's ERPNext permissions and allowed DocTypes.
For create, update, submit, cancel, delete, amend, or workflow actions, obtain explicit user confirmation before execution unless the application has already recorded that confirmation.
After every tool call, explain the result accurately and do not claim success unless the tool response confirms it."""


def build_system_prompt(tool_mode: str | None, native_mcp_source: str | None = None) -> str:
    mode = tool_mode or "Auto"
    native_source = native_mcp_source or "Custom MCP Server"

    mode_instructions = {
        "Disabled": """No ERPNext tools are available in this mode.
Answer general questions only. When ERPNext data or an ERPNext operation is required, clearly state that tools are disabled and ask the user to enable an appropriate Tool Mode.""",
        "Local Tools": """ERPNext access is available through the application's local function tools.
Always use the available local tools whenever ERPNext data is required.
Do not use or claim to use MCP in this mode.""",
        "Application MCP": """ERPNext access is available through the application's managed MCP client.
Always use the application-managed MCP tools whenever ERPNext data is required.
Do not use local tools or provider-native MCP unless they are explicitly supplied.""",
        "Native MCP": f"""ERPNext access is available through provider-native MCP using: {native_source}.
Always use the provider-native MCP tools whenever ERPNext data is required.
Do not claim access through local tools or application-managed MCP unless fallback tools are actually supplied.""",
        "Local + Application MCP": """ERPNext access is available through both local function tools and the application's managed MCP client.
Prefer local tools for standard ERPNext document, report, and workflow operations.
Use application-managed MCP when it provides a required capability that is not available locally.""",
        "Local + Native MCP": f"""ERPNext access is available through local function tools and provider-native MCP using: {native_source}.
Prefer local tools for standard ERPNext document, report, and workflow operations.
Use provider-native MCP when it provides a required capability that is not available locally.""",
        "Auto": """The application automatically selects the safest supported tool integration for the active provider and model.
Use only the tools actually supplied in the current request.
Do not assume that local tools, application-managed MCP, or native MCP are available unless they are present.""",
    }

    return f"{PROMPT_COMMON}\n\nIntegration mode: {mode}\n{mode_instructions.get(mode, mode_instructions['Auto'])}"


@frappe.whitelist()
def get_mode_system_prompt(tool_mode=None, native_mcp_source=None):
    """Return the standard prompt for instant form updates."""
    return build_system_prompt(tool_mode, native_mcp_source)


class AIProvider(Document):
    def validate(self):
        if self.is_default and self.enabled:
            frappe.db.set_value(
                "AI Provider",
                {"name": ["!=", self.name]},
                "is_default",
                0,
            )

        if getattr(self, "auto_update_system_prompt", 1):
            previous = None
            if not self.is_new():
                try:
                    previous = self.get_doc_before_save()
                except Exception:
                    previous = None

            mode_changed = not previous or previous.tool_mode != self.tool_mode
            source_changed = (
                not previous
                or previous.native_mcp_source != self.native_mcp_source
            )

            if not self.system_prompt or mode_changed or source_changed:
                self.system_prompt = build_system_prompt(
                    self.tool_mode,
                    self.native_mcp_source,
                )
