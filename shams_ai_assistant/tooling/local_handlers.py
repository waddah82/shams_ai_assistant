from __future__ import annotations
import json
import frappe
from frappe import _
from frappe.utils import cint
from frappe.model.workflow import apply_workflow
from .decorators import ai_tool_handler


def _lines(value):
    return {x.strip() for x in (value or "").splitlines() if x.strip()}


def _rule(tool, doctype, operation):
    rows = list(tool.get("allowed_doctypes") or [])
    if not rows:
        return None
    row = next((r for r in rows if r.reference_doctype == doctype), None)
    if not row:
        frappe.throw(_("DocType {0} is not allowed for tool {1}.").format(doctype, tool.tool_name), frappe.PermissionError)
    field = {
        "read": "allow_read", "create": "allow_create", "update": "allow_update",
        "submit": "allow_submit", "cancel": "allow_cancel", "delete": "allow_delete",
    }.get(operation)
    if field and not cint(row.get(field)):
        frappe.throw(_("Operation {0} is not allowed for DocType {1}.").format(operation, doctype), frappe.PermissionError)
    return row


def _safe_fields(tool, doctype, requested, operation="read"):
    rule = _rule(tool, doctype, operation)
    meta = frappe.get_meta(doctype)
    blocked = {f.fieldname for f in meta.fields if f.fieldtype == "Password"}
    if rule:
        blocked |= _lines(rule.blocked_fields)
        allowed = _lines(rule.allowed_fields)
    else:
        allowed = set()
    requested = requested or ["name"]
    result=[]
    for field in requested:
        base = str(field).split(" as ",1)[0].strip().split(".")[-1]
        if base in blocked:
            continue
        if allowed and base not in allowed and base != "name":
            continue
        result.append(field)
    return result or ["name"]


def _check_permission(doctype, ptype, name=None):
    frappe.has_permission(doctype, ptype=ptype, doc=name, throw=True)


@ai_tool_handler
def list_documents(tool, doctype, fields=None, filters=None, or_filters=None, order_by=None, limit=20, start=0):
    _check_permission(doctype, "read")
    rule = _rule(tool, doctype, "read")
    maximum = cint((rule and rule.maximum_rows) or tool.maximum_rows or 50)
    return frappe.get_list(
        doctype,
        fields=_safe_fields(tool, doctype, fields, "read"),
        filters=filters or {},
        or_filters=or_filters or {},
        order_by=order_by or "modified desc",
        start=max(cint(start), 0),
        page_length=min(max(cint(limit) or 20, 1), maximum or 50),
    )


@ai_tool_handler
def count_documents(tool, doctype, filters=None):
    _check_permission(doctype, "read")
    _rule(tool, doctype, "read")
    return {"doctype": doctype, "count": frappe.db.count(doctype, filters=filters or {})}


@ai_tool_handler
def get_document(tool, doctype, name, fields=None):
    _check_permission(doctype, "read", name)
    _rule(tool, doctype, "read")
    doc=frappe.get_doc(doctype, name)
    doc.check_permission("read")
    data=doc.as_dict(no_nulls=True)
    if fields:
        safe=set(_safe_fields(tool, doctype, fields, "read")) | {"doctype","name"}
        data={k:v for k,v in data.items() if k in safe}
    else:
        meta=frappe.get_meta(doctype)
        hidden={f.fieldname for f in meta.fields if f.fieldtype == "Password"}
        data={k:v for k,v in data.items() if k not in hidden}
    return data


@ai_tool_handler
def get_doctype_info(tool, doctype):
    _check_permission(doctype, "read")
    _rule(tool, doctype, "read")
    meta=frappe.get_meta(doctype)
    fields=[]
    for f in meta.fields:
        if f.fieldtype in {"Section Break","Column Break","Tab Break","HTML","Button","Password"}:
            continue
        fields.append({"fieldname":f.fieldname,"label":f.label,"fieldtype":f.fieldtype,"options":f.options,"required":bool(f.reqd),"read_only":bool(f.read_only)})
    return {"doctype":doctype,"is_submittable":bool(meta.is_submittable),"fields":fields}


@ai_tool_handler
def search_link(tool, doctype, text="", limit=20):
    _check_permission(doctype, "read")
    _rule(tool, doctype, "read")
    meta=frappe.get_meta(doctype)
    title=meta.title_field or "name"
    fields=["name"] + ([title] if title != "name" else [])
    filters={}
    or_filters=[]
    if text:
        or_filters=[[doctype,"name","like",f"%{text}%"]]
        if title != "name": or_filters.append([doctype,title,"like",f"%{text}%"])
    return frappe.get_list(doctype, fields=fields, filters=filters, or_filters=or_filters, page_length=min(max(cint(limit) or 20,1),50), order_by="modified desc")


def _write_doc(tool, doctype, operation, name=None, values=None):
    _rule(tool, doctype, operation)
    _check_permission(doctype, operation if operation != "update" else "write", name)
    values=values or {}
    allowed=_safe_fields(tool, doctype, list(values), operation)
    safe={k:v for k,v in values.items() if k in allowed}
    if operation == "create":
        doc=frappe.get_doc({"doctype":doctype, **safe}); doc.insert()
    else:
        doc=frappe.get_doc(doctype,name); doc.check_permission("write")
        doc.update(safe); doc.save()
    return doc.as_dict(no_nulls=True)


@ai_tool_handler
def create_document(tool, doctype, values): return _write_doc(tool,doctype,"create",values=values)

@ai_tool_handler
def update_document(tool, doctype, name, values): return _write_doc(tool,doctype,"update",name=name,values=values)

@ai_tool_handler
def submit_document(tool, doctype, name):
    _rule(tool,doctype,"submit"); doc=frappe.get_doc(doctype,name); doc.check_permission("submit"); doc.submit(); return doc.as_dict(no_nulls=True)

@ai_tool_handler
def cancel_document(tool, doctype, name):
    _rule(tool,doctype,"cancel"); doc=frappe.get_doc(doctype,name); doc.check_permission("cancel"); doc.cancel(); return doc.as_dict(no_nulls=True)

@ai_tool_handler
def delete_document(tool, doctype, name):
    _rule(tool,doctype,"delete"); _check_permission(doctype,"delete",name); frappe.delete_doc(doctype,name); return {"deleted":True,"doctype":doctype,"name":name}

@ai_tool_handler
def amend_document(tool, doctype, name):
    _rule(tool,doctype,"create"); original=frappe.get_doc(doctype,name); original.check_permission("read")
    amended=frappe.copy_doc(original); amended.amended_from=original.name; amended.docstatus=0; amended.name=None; amended.insert(); return amended.as_dict(no_nulls=True)

@ai_tool_handler
def list_reports(tool, reference_doctype=None, limit=50):
    filters={"disabled":0}
    if reference_doctype: filters["ref_doctype"]=reference_doctype
    return frappe.get_list("Report",filters=filters,fields=["name","report_name","ref_doctype","report_type","is_standard"],page_length=min(max(cint(limit) or 50,1),100),order_by="report_name asc")

@ai_tool_handler
def get_report_requirements(tool, report_name):
    report=frappe.get_doc("Report",report_name); report.check_permission("read")
    return {"name":report.name,"report_name":report.report_name,"ref_doctype":report.ref_doctype,"report_type":report.report_type,"filters":json.loads(report.json or "{}") if report.report_type=="Report Builder" and report.json else []}

@ai_tool_handler
def run_report(tool, report_name, filters=None, limit=100):
    report=frappe.get_doc("Report",report_name); report.check_permission("read")
    from frappe.desk.query_report import run
    result=run(report_name,filters=filters or {},ignore_prepared_report=True)
    if isinstance(result,dict) and isinstance(result.get("result"),list): result["result"]=result["result"][:min(max(cint(limit) or 100,1),500)]
    return result

@ai_tool_handler
def get_pending_approvals(tool, doctype=None, limit=50):
    filters={"status":"Open","reference_doctype":["is","set"]}
    if doctype: filters["reference_doctype"]=doctype
    return frappe.get_list("Workflow Action",filters=filters,fields=["name","reference_doctype","reference_name","workflow_state","status","creation"],page_length=min(max(cint(limit) or 50,1),100),order_by="creation desc")

@ai_tool_handler
def get_workflow_actions(tool, doctype, name):
    doc=frappe.get_doc(doctype,name); doc.check_permission("read")
    from frappe.model.workflow import get_transitions
    return [{"action":x.action,"next_state":x.next_state,"allowed":x.allowed} for x in get_transitions(doc)]

@ai_tool_handler
def apply_workflow_action(tool, doctype, name, action):
    _rule(tool,doctype,"update"); doc=frappe.get_doc(doctype,name); doc.check_permission("write"); result=apply_workflow(doc,action); return result.as_dict(no_nulls=True)

@ai_tool_handler
def get_my_recent_activity(tool, limit=20):
    return frappe.get_list("Activity Log",filters={"user":frappe.session.user},fields=["subject","operation","reference_doctype","reference_name","creation"],page_length=min(max(cint(limit) or 20,1),100),order_by="creation desc")
