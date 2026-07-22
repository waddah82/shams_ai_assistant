from __future__ import annotations
import frappe

READ_TOOLS = {
    "get_current_document": "Read the document currently open in ERPNext",
    "get_document": "Read an ERPNext document by DocType and name",
    "list_documents": "List permitted ERPNext documents",
}

def get_current_document(context):
    dt=context.get("doctype"); name=context.get("docname")
    if not dt or not name: return {"error":"No document is currently open"}
    return get_document(dt, name)

def get_document(doctype, name):
    frappe.has_permission(doctype, "read", throw=True)
    doc=frappe.get_doc(doctype, name)
    doc.check_permission("read")
    data=doc.as_dict(no_nulls=True)
    meta=frappe.get_meta(doctype)
    hidden={f.fieldname for f in meta.fields if f.fieldtype in {"Password"}}
    return {k:v for k,v in data.items() if k not in hidden}

def list_documents(doctype, fields=None, filters=None, limit=20):
    frappe.has_permission(doctype, "read", throw=True)
    fields=fields or ["name","modified"]
    return frappe.get_list(doctype, fields=fields, filters=filters or {}, limit_page_length=min(int(limit or 20),100), order_by="modified desc")
