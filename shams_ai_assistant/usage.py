from __future__ import annotations
import json
import frappe
from frappe import _
from frappe.utils import today, now_datetime


def _settings():
    try:
        return frappe.get_cached_doc("AI Assistant Settings")
    except Exception:
        return frappe._dict(default_daily_token_limit=100000, default_monthly_token_limit=2000000, quota_warning_percent=80)


def normalize_usage(raw):
    raw = raw or {}
    input_tokens = int(raw.get("prompt_tokens") or raw.get("input_tokens") or raw.get("promptTokenCount") or 0)
    output_tokens = int(raw.get("completion_tokens") or raw.get("output_tokens") or raw.get("candidatesTokenCount") or 0)
    total_tokens = int(raw.get("total_tokens") or raw.get("totalTokenCount") or (input_tokens + output_tokens))
    return {"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": total_tokens}


def limits_for(user):
    s = _settings()
    result = frappe._dict(daily=int(getattr(s,"default_daily_token_limit",0) or 0), monthly=int(getattr(s,"default_monthly_token_limit",0) or 0), unlimited=False, block=True)
    name = frappe.db.get_value("AI User Quota", {"user": user, "enabled": 1}, "name")
    if name:
        q = frappe.get_cached_doc("AI User Quota", name)
        if q.unlimited:
            result.unlimited = True; result.daily = 0; result.monthly = 0
        else:
            if int(q.daily_token_limit or 0) > 0: result.daily = int(q.daily_token_limit)
            if int(q.monthly_token_limit or 0) > 0: result.monthly = int(q.monthly_token_limit)
        result.block = bool(q.block_when_exceeded)
    return result


def usage_totals(user):
    d = today(); month = d[:7]
    daily = frappe.db.sql("SELECT COALESCE(SUM(total_tokens),0) FROM `tabAI Token Usage` WHERE user=%s AND usage_date=%s AND request_status='Success'", (user,d))[0][0] or 0
    monthly = frappe.db.sql("SELECT COALESCE(SUM(total_tokens),0) FROM `tabAI Token Usage` WHERE user=%s AND usage_month=%s AND request_status='Success'", (user,month))[0][0] or 0
    return frappe._dict(daily=int(daily), monthly=int(monthly))


def quota_status(user=None):
    user = user or frappe.session.user
    lim = limits_for(user); used = usage_totals(user)
    daily_remaining = None if lim.unlimited or not lim.daily else max(0, lim.daily-used.daily)
    monthly_remaining = None if lim.unlimited or not lim.monthly else max(0, lim.monthly-used.monthly)
    return frappe._dict(allowed=lim.unlimited or not ((lim.daily and used.daily >= lim.daily) or (lim.monthly and used.monthly >= lim.monthly)), limits=lim, used=used, daily_remaining=daily_remaining, monthly_remaining=monthly_remaining)


def check_quota(user=None):
    user = user or frappe.session.user
    lim = limits_for(user); used = usage_totals(user)
    if lim.unlimited: return frappe._dict(allowed=True, limits=lim, used=used)
    daily_exceeded = lim.daily > 0 and used.daily >= lim.daily
    monthly_exceeded = lim.monthly > 0 and used.monthly >= lim.monthly
    allowed = not ((daily_exceeded or monthly_exceeded) and lim.block)
    if not allowed:
        period = _("daily") if daily_exceeded else _("monthly")
        limit = lim.daily if daily_exceeded else lim.monthly
        consumed = used.daily if daily_exceeded else used.monthly
        frappe.throw(_("Your {0} AI token quota has been reached ({1} of {2} tokens). Contact the System Manager.").format(period, consumed, limit), frappe.PermissionError)
    return frappe._dict(allowed=True, limits=lim, used=used)


def log_usage(*, user, conversation=None, provider=None, model=None, raw_usage=None, tool_calls=0, status="Success", response_time_ms=0):
    n = normalize_usage(raw_usage)
    d = today()
    doc = frappe.get_doc({"doctype":"AI Token Usage","user":user,"conversation":conversation,"provider":provider,"model":model,
        "input_tokens":n["input_tokens"],"output_tokens":n["output_tokens"],"total_tokens":n["total_tokens"],"tool_calls":int(tool_calls or 0),
        "request_status":status,"response_time_ms":int(response_time_ms or 0),"usage_date":d,"usage_month":d[:7],"raw_usage":json.dumps(raw_usage or {},default=str)})
    doc.insert(ignore_permissions=True)
    return n
