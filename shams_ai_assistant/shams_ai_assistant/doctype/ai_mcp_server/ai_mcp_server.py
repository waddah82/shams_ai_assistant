from __future__ import annotations
import frappe
from frappe.model.document import Document


class AIMCPServer(Document):
    def validate(self):
        if self.is_default and self.enabled:
            frappe.db.set_value(
                "AI MCP Server",
                {"name": ["!=", self.name]},
                "is_default",
                0,
                update_modified=False,
            )
