from __future__ import annotations
import json
import frappe
from frappe import _
from shams_ai_assistant.mcp import list_tools as _list_tools, call_tool as _call_tool


@frappe.whitelist()
def list_servers():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)
    return frappe.get_all("AI MCP Server", filters={"enabled": 1}, fields=["name", "server_name", "transport", "is_default", "require_approval"], order_by="is_default desc, server_name asc")


@frappe.whitelist()
def list_tools(server=None):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)
    return _list_tools(server)


@frappe.whitelist()
def call_tool(server, tool_name, arguments=None, approved=0):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)
    if isinstance(arguments, str):
        arguments = json.loads(arguments or "{}")
    return _call_tool(server, tool_name, arguments or {}, bool(int(approved or 0)))
