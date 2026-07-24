from __future__ import annotations
import base64
import re
import frappe
from .base import BaseProvider, ProviderResponse


_CACHE_PREFIX = "opencode_session:"


class OpenCodeProvider(BaseProvider):
    """Provider for OpenCode AI server with ERPNext context injection.

    Session IDs are persisted in Frappe cache keyed by (provider, conversation)
    so that multi-turn conversations maintain context across API calls.
    """

    KEYWORD_DOCTYPES = {
        "invoice": ["Sales Invoice", "Purchase Invoice"],
        "faktur": ["Sales Invoice", "Purchase Invoice"],
        "بيع": ["Sales Invoice"],
        "شراء": ["Purchase Invoice"],
        "sales invoice": ["Sales Invoice"],
        "purchase invoice": ["Purchase Invoice"],
        "عميل": ["Customer"],
        "customer": ["Customer"],
        "منتج": ["Item"],
        "item": ["Item"],
        "بضاعة": ["Item"],
        "طلب": ["Sales Order", "Purchase Order"],
        "order": ["Sales Order", "Purchase Order"],
        "أوامر": ["Sales Order", "Purchase Order"],
        "فاتورة": ["Sales Invoice", "Purchase Invoice"],
        "مورد": ["Supplier"],
        "supplier": ["Supplier"],
        "دفعة": ["Payment Entry"],
        "payment": ["Payment Entry"],
        "سند": ["Payment Entry"],
        "مبلغ": ["Payment Entry"],
        "account": ["Account"],
        "حساب": ["Account"],
        "جرد": ["Stock Entry"],
        "stock": ["Stock Entry", "Stock Ledger Entry"],
        "مخزون": ["Stock Entry", "Stock Ledger Entry"],
        "مبيعات": ["Sales Invoice", "Sales Order"],
        "مشتريات": ["Purchase Invoice", "Purchase Order"],
        "إيراد": ["Sales Invoice"],
        "revenue": ["Sales Invoice"],
        "عمولة": ["Sales Invoice"],
        "profit": ["Sales Invoice", "Purchase Invoice"],
        "ربح": ["Sales Invoice", "Purchase Invoice"],
        "إجمالي": ["Sales Invoice", "Purchase Invoice"],
        "total": ["Sales Invoice", "Purchase Invoice"],
        "قائمة": ["Sales Invoice", "Customer", "Item"],
        "list": ["Sales Invoice", "Customer", "Item"],
        "أحدث": ["Sales Invoice", "Customer", "Item"],
        "recent": ["Sales Invoice", "Customer", "Item"],
        "آخر": ["Sales Invoice", "Customer", "Item"],
        "last": ["Sales Invoice", "Customer", "Item"],
        "كمية": ["Sales Invoice", "Purchase Invoice"],
        "quantity": ["Sales Invoice", "Purchase Invoice"],
        "عدد": ["Sales Invoice", "Purchase Invoice", "Customer", "Item"],
        "count": ["Sales Invoice", "Purchase Invoice"],
        "عملية": ["Journal Entry"],
        "transaction": ["Journal Entry", "Payment Entry"],
    }

    def _auth_header(self) -> str:
        password = self.config.get_password("api_key", raise_exception=False) or ""
        credentials = base64.b64encode(f"opencode:{password}".encode()).decode()
        return f"Basic {credentials}"

    def _base_url(self) -> str:
        return (self.config.base_url or "http://localhost:4096").rstrip("/")

    def _headers(self):
        return {
            "Authorization": self._auth_header(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _cache_key(self, conversation: str) -> str:
        return f"{_CACHE_PREFIX}{self.config.name}:{conversation}"

    def _get_session_id(self, conversation: str) -> str | None:
        if not conversation:
            return None
        return frappe.cache().get_value(self._cache_key(conversation))

    def _set_session_id(self, conversation: str, session_id: str):
        if conversation:
            frappe.cache().set_value(self._cache_key(conversation), session_id, expires_in_sec=86400)

    def supports_function_tools(self) -> bool:
        return True

    def supports_native_mcp(self) -> bool:
        return False

    def chat(self, messages, system_prompt="", tools=None, conversation=None) -> ProviderResponse:
        base = self._base_url()
        headers = self._headers()

        # Reuse session for the same conversation
        session_id = self._get_session_id(conversation)
        if not session_id:
            session_resp = self.post(f"{base}/session", headers=headers, json={})
            session_id = session_resp["id"]
            self._set_session_id(conversation, session_id)

        # Get the user's latest message
        user_message = ""
        if messages:
            last = messages[-1]
            user_message = last.get("content", "")

        # Pre-fetch ERPNext context
        erpnext_context = self._fetch_erpnext_context(user_message, messages)

        # Build the prompt
        text = self._build_message_text(messages, system_prompt, erpnext_context)

        payload = {"parts": [{"type": "text", "text": text}]}
        data = self.post(
            f"{base}/session/{session_id}/message",
            headers=headers,
            json=payload,
        )

        parts = data.get("parts") or []
        answer = self._extract_text(parts)
        usage_raw = (data.get("info") or {}).get("tokens") or {}
        usage = {
            "prompt_tokens": usage_raw.get("input"),
            "completion_tokens": usage_raw.get("output"),
            "total_tokens": usage_raw.get("total"),
        }

        if not answer:
            raise RuntimeError("OpenCode returned no text in response.")

        return ProviderResponse(text=answer, raw=data, usage=usage, tool_calls=[])

    def _fetch_erpnext_context(self, user_message: str, messages: list) -> str:
        if not user_message:
            return ""

        message_lower = user_message.lower()
        doctypes_to_fetch = set()

        for keyword, doctypes in self.KEYWORD_DOCTYPES.items():
            if keyword in message_lower:
                doctypes_to_fetch.update(doctypes)

        if not doctypes_to_fetch:
            return ""

        context_parts = []
        for doctype in list(doctypes_to_fetch)[:3]:
            try:
                data = self._fetch_doctype_data(doctype, user_message)
                if data:
                    context_parts.append(f"--- {doctype} Data ---\n{data}")
            except Exception:
                pass

        return "\n\n".join(context_parts)

    def _fetch_doctype_data(self, doctype: str, user_message: str) -> str:
        try:
            if not frappe.has_permission(doctype, "read"):
                return ""

            filters = {}
            limit = 5

            last_match = re.search(r"(?:last|آخر|أحدث)\s+(\d+)", user_message)
            if last_match:
                limit = min(int(last_match.group(1)), 20)

            fields = ["name", "modified"]

            if doctype == "Sales Invoice":
                fields.extend(["customer", "grand_total", "status", "posting_date"])
            elif doctype == "Purchase Invoice":
                fields.extend(["supplier", "grand_total", "status", "posting_date"])
            elif doctype == "Customer":
                fields.extend(["customer_name", "customer_group", "territory"])
            elif doctype == "Item":
                fields.extend(["item_name", "item_group", "stock_uom"])
            elif doctype == "Sales Order":
                fields.extend(["customer", "grand_total", "status", "transaction_date"])
            elif doctype == "Purchase Order":
                fields.extend(["supplier", "grand_total", "status", "transaction_date"])
            elif doctype == "Payment Entry":
                fields.extend(["party", "party_type", "paid_amount", "posting_date"])
            elif doctype == "Account":
                fields.extend(["account_name", "account_type", "root_type"])

            data = frappe.get_list(
                doctype,
                fields=fields,
                filters=filters,
                order_by="modified desc",
                limit_page_length=limit,
            )

            if not data:
                return f"No {doctype} records found."

            lines = []
            for row in data:
                parts = [f"Name: {row.get('name', 'N/A')}"]
                for key, value in row.items():
                    if key != "name" and value is not None:
                        parts.append(f"{key}: {value}")
                lines.append(" | ".join(parts))

            return "\n".join(lines)

        except Exception as e:
            return f"Error fetching {doctype}: {str(e)}"

    @staticmethod
    def _build_message_text(messages, system_prompt="", erpnext_context="") -> str:
        parts = []
        if system_prompt:
            parts.append(f"System: {system_prompt}")

        if erpnext_context:
            parts.append(f"\n[ERPNext Data Available]\n{erpnext_context}\n[End of ERPNext Data]")

        if messages:
            last = messages[-1]
            role = last.get("role", "user")
            content = last.get("content", "")
            if role == "user":
                parts.append(content)
            else:
                parts.append(f"{role}: {content}")

        return "\n\n".join(parts)

    @staticmethod
    def _extract_text(parts: list) -> str:
        texts = []
        for part in parts:
            if isinstance(part, dict) and part.get("type") == "text":
                t = part.get("text", "")
                if t:
                    texts.append(t)
        return "\n".join(texts)
