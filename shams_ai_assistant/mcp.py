from __future__ import annotations
import json
from typing import Any
import requests
import frappe
from frappe import _


def _password(doc, fieldname: str) -> str:
    try:
        return doc.get_password(fieldname, raise_exception=False) or ""
    except Exception:
        return ""


def _headers(server) -> dict[str, str]:
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    auth_type = (server.authentication_type or "None").strip()
    value = _password(server, "authorization_value").strip()
    if not value or auth_type == "None":
        return headers
    if auth_type == "Bearer Token":
        headers["Authorization"] = value if value.lower().startswith("bearer ") else f"Bearer {value}"
    elif auth_type == "Frappe Token":
        headers["Authorization"] = value if value.lower().startswith("token ") else f"token {value}"
    elif auth_type == "Basic Auth":
        headers["Authorization"] = value if value.lower().startswith("basic ") else f"Basic {value}"
    elif auth_type == "Custom Header":
        headers[(server.custom_header_name or "Authorization").strip()] = value
    return headers


def _parse_response(response: requests.Response) -> dict[str, Any]:
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        for line in response.text.splitlines():
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload and payload != "[DONE]":
                    return json.loads(payload)
        return {}
    return response.json()


def rpc(server, method: str, params: dict | None = None) -> dict[str, Any]:
    payload = {"jsonrpc": "2.0", "id": frappe.generate_hash(length=12), "method": method, "params": params or {}}
    response = requests.post(
        server.server_url,
        headers=_headers(server),
        json=payload,
        timeout=int(server.request_timeout or 60),
        verify=bool(server.verify_ssl),
    )
    data = _parse_response(response)
    if data.get("error"):
        err = data["error"]
        raise RuntimeError(err.get("message") if isinstance(err, dict) else str(err))
    return data.get("result", data)


def get_server(name: str | None = None):
    if name:
        server = frappe.get_doc("AI MCP Server", name)
    else:
        server_name = frappe.db.get_value("AI MCP Server", {"enabled": 1, "is_default": 1}, "name") or frappe.db.get_value("AI MCP Server", {"enabled": 1}, "name")
        if not server_name:
            frappe.throw(_("No enabled MCP server is configured."))
        server = frappe.get_doc("AI MCP Server", server_name)
    if not server.enabled:
        frappe.throw(_("The selected MCP server is disabled."))
    return server


def list_tools(server_name: str | None = None, force_refresh: bool = False) -> list[dict[str, Any]]:
    server = get_server(server_name)
    cache_key = f"shams_ai:mcp_tools:{server.name}:{server.modified}"
    tools = None if force_refresh else frappe.cache().get_value(cache_key)
    if tools is None:
        result = rpc(server, "tools/list")
        tools = result.get("tools", []) if isinstance(result, dict) else []
        try:
            minutes = int(frappe.get_cached_value("AI Assistant Settings", None, "mcp_tools_cache_minutes") or 30)
        except Exception:
            minutes = 30
        frappe.cache().set_value(cache_key, tools, expires_in_sec=max(60, minutes * 60))
    allowed = {x.strip() for x in (server.allowed_tools or "").replace(",", "\n").splitlines() if x.strip()}
    return [tool for tool in tools if not allowed or tool.get("name") in allowed]


def call_tool(server_name: str, tool_name: str, arguments: dict | None = None, approved: bool = False):
    server = get_server(server_name)
    allowed_names = {tool.get("name") for tool in list_tools(server.name)}
    if tool_name not in allowed_names:
        frappe.throw(_("Tool is not allowed or not exposed by the MCP server."), frappe.PermissionError)
    patterns = [x.strip().lower() for x in (server.tool_name_patterns or "").splitlines() if x.strip()]
    sensitive = any(pattern in tool_name.lower() for pattern in patterns)
    if server.require_approval and sensitive and not approved:
        return {"approval_required": True, "server": server.name, "tool": tool_name, "arguments": arguments or {}}
    return rpc(server, "tools/call", {"name": tool_name, "arguments": arguments or {}})


def native_mcp_config(server_name: str | None = None, connector_id: str | None = None) -> dict[str, Any]:
    """Return a provider-safe Remote MCP definition without exposing internal fields."""
    server = get_server(server_name)
    label = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in (server.server_name or server.name).lower()).strip("_") or "shams_mcp"
    allowed = [x.strip() for x in (server.allowed_tools or "").replace(",", "\n").splitlines() if x.strip()]
    headers = _headers(server)
    headers.pop("Content-Type", None)
    headers.pop("Accept", None)
    result = {
        "server_label": label,
        "allowed_tools": allowed,
        "require_approval": "never",
    }
    if connector_id:
        result["connector_id"] = connector_id.strip()
        auth = headers.get("Authorization")
        if auth:
            result["authorization"] = auth.removeprefix("Bearer ").strip()
    else:
        result["server_url"] = server.server_url
        result["headers"] = headers
    return result
