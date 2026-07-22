import frappe
from frappe import _
from frappe.utils import today, add_days
from shams_ai_assistant.usage import limits_for

def _assert_manager():
    if "System Manager" not in frappe.get_roles(frappe.session.user): frappe.throw(_("System Manager role required."), frappe.PermissionError)

@frappe.whitelist()
def get_summary_stats():
    _assert_manager(); d=today(); since=add_days(d,-7)
    q=lambda sql,args=(): frappe.db.sql(sql,args)[0][0] or 0
    return {"conversations_7d":int(q("SELECT COUNT(*) FROM `tabAI Conversation` WHERE creation >= %s",(since,))),
      "messages_today":int(q("SELECT COUNT(*) FROM `tabAI Message` WHERE DATE(creation)=%s",(d,))),
      "tokens_today":int(q("SELECT COALESCE(SUM(total_tokens),0) FROM `tabAI Token Usage` WHERE usage_date=%s AND request_status='Success'",(d,))),
      "tool_calls_7d":int(q("SELECT COALESCE(SUM(tool_calls),0) FROM `tabAI Token Usage` WHERE creation >= %s",(since,))),
      "active_users_7d":int(q("SELECT COUNT(DISTINCT user) FROM `tabAI Token Usage` WHERE creation >= %s",(since,))),
      "failed_7d":int(q("SELECT COUNT(*) FROM `tabAI Token Usage` WHERE creation >= %s AND request_status='Failed'",(since,)))}

@frappe.whitelist()
def get_user_usage():
    _assert_manager(); d=today(); month=d[:7]
    rows=frappe.db.sql("""SELECT user,SUM(CASE WHEN usage_date=%s THEN total_tokens ELSE 0 END) daily_tokens,SUM(CASE WHEN usage_month=%s THEN total_tokens ELSE 0 END) monthly_tokens,COUNT(*) requests FROM `tabAI Token Usage` WHERE request_status='Success' AND usage_month=%s GROUP BY user ORDER BY monthly_tokens DESC""",(d,month,month),as_dict=True)
    for r in rows:
      lim=limits_for(r.user); r.update(daily_limit=lim.daily,monthly_limit=lim.monthly,unlimited=lim.unlimited,daily_tokens=int(r.daily_tokens or 0),monthly_tokens=int(r.monthly_tokens or 0),requests=int(r.requests or 0))
    return rows

@frappe.whitelist()
def get_daily_usage(days=14):
    _assert_manager(); since=add_days(today(),-int(days)+1)
    return frappe.db.sql("SELECT usage_date,SUM(input_tokens) input_tokens,SUM(output_tokens) output_tokens,SUM(total_tokens) total_tokens FROM `tabAI Token Usage` WHERE usage_date >= %s AND request_status='Success' GROUP BY usage_date ORDER BY usage_date",(since,),as_dict=True)

@frappe.whitelist()
def get_top_models(days=7):
    _assert_manager(); since=add_days(today(),-int(days))
    return frappe.db.sql("SELECT provider,model,SUM(total_tokens) tokens,COUNT(*) requests FROM `tabAI Token Usage` WHERE creation >= %s AND request_status='Success' GROUP BY provider,model ORDER BY tokens DESC LIMIT 15",(since,),as_dict=True)
