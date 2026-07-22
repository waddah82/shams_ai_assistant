from __future__ import annotations
import json, time
import frappe
from frappe import _
from shams_ai_assistant.providers.factory import get_provider
from shams_ai_assistant.tooling import ToolManager
from shams_ai_assistant.usage import check_quota, quota_status, log_usage

DEFAULT_SYSTEM = """You are Shams AI Assistant inside ERPNext. Answer in the user's language. Never invent ERP data. Respect Frappe permissions. Use available tools when ERPNext or external-system data is required. For data changes, explain the proposed action and request explicit approval; do not claim a change was made unless a tool result confirms it."""


def _provider(name=None):
    if name:
        doc=frappe.get_doc("AI Provider", name)
    else:
        name=frappe.db.get_value("AI Provider", {"enabled":1,"is_default":1}, "name") or frappe.db.get_value("AI Provider", {"enabled":1}, "name")
        if not name: frappe.throw(_("No enabled AI Provider is configured."))
        doc=frappe.get_doc("AI Provider", name)
    if not doc.enabled: frappe.throw(_("The selected AI Provider is disabled."))
    return doc


def _messages(conversation, limit=None):
    if limit is None:
        try: limit=int(frappe.get_cached_value("AI Assistant Settings",None,"max_history_messages") or 20)
        except Exception: limit=20
    rows=frappe.get_all("AI Message",filters={"conversation":conversation},fields=["role","content","creation"],order_by="creation desc",limit_page_length=limit)
    rows.reverse()
    return [{"role":r.role,"content":r.content} for r in rows if r.role in {"user","assistant"}]


def _save_message(conversation, role, content, provider=None, model=None, raw=None):
    return frappe.get_doc({"doctype":"AI Message","conversation":conversation,"role":role,"content":content,"provider":provider,"model":model,"raw_response":json.dumps(raw,default=str) if raw else None}).insert(ignore_permissions=True)


def _context_note(context):
    if not context: return ""
    clean={k:context.get(k) for k in ("route","doctype","docname") if context.get(k)}
    return "\nCurrent ERPNext page context (not document contents): "+json.dumps(clean,ensure_ascii=False)


def _merge_usage(total, current):
    for key,value in (current or {}).items():
        if isinstance(value,(int,float)): total[key]=total.get(key,0)+value


def _tool_result_message(call, result):
    return {
        "role":"user",
        "content":"Tool result for %s:\n%s" % (call.get("name"),json.dumps(result,ensure_ascii=False,default=str)),
    }


@frappe.whitelist()
def send(message, conversation=None, provider=None, context=None, mcp_server=None, approved_tool=None):
    if frappe.session.user=="Guest": frappe.throw(_("Login required"),frappe.PermissionError)
    if isinstance(context,str): context=json.loads(context or "{}")
    if isinstance(approved_tool,str): approved_tool=json.loads(approved_tool or "{}")
    message=(message or "").strip()
    if not message: frappe.throw(_("Message is required."))
    user=frappe.session.user; check_quota(user); started=time.monotonic(); config=_provider(provider)
    if not conversation:
        conv=frappe.get_doc({"doctype":"AI Conversation","title":message[:80],"provider":config.name,"model":config.default_model,"route_context":json.dumps(context or {},ensure_ascii=False)}).insert(ignore_permissions=True)
        conversation=conv.name
    else:
        conv=frappe.get_doc("AI Conversation",conversation); conv.check_permission("read")
    _save_message(conversation,"user",message,config.name,config.default_model)
    system=(config.system_prompt or DEFAULT_SYSTEM)+_context_note(context)
    history=_messages(conversation)
    try:
        provider_client=get_provider(config)
        manager=ToolManager(config,provider_client,message=message,mcp_server=mcp_server,conversation=conversation)
        total_usage={}; tool_call_count=0
        try: max_steps=int(frappe.get_cached_value("AI Assistant Settings",None,"max_tool_steps") or 6)
        except Exception: max_steps=6

        # Explicitly approved pending call can be replayed without asking the model again.
        if approved_tool:
            manager.provider_tools()
            result=manager.execute(approved_tool.get("name"),approved_tool.get("arguments") or {},approved=True)
            history.append(_tool_result_message(approved_tool,result))

        if manager.uses_native_mcp:
            local_tools=manager.local_schemas() if manager.uses_local else []
            native=manager.native_definition()
            result=None
            for _step in range(max_steps):
                result=provider_client.chat_native_mcp(history,system,native,local_tools=local_tools)
                _merge_usage(total_usage,result.usage)
                if not result.tool_calls: break
                for call in result.tool_calls:
                    tool_call_count+=1
                    tool_result=manager.execute(call.get("name"),call.get("arguments") or {},approved=False)
                    if isinstance(tool_result,dict) and tool_result.get("approval_required"):
                        answer=_("Approval is required before running tool: {0}").format(call.get("name"))
                        _save_message(conversation,"assistant",answer,config.name,config.default_model,tool_result)
                        return {"conversation":conversation,"answer":answer,"provider":config.name,"model":config.default_model,"tool_mode":manager.mode,"approval_required":True,"approval":tool_result}
                    history.append(_tool_result_message(call,tool_result))
            else:
                raise RuntimeError(f"Tool execution exceeded the maximum of {max_steps} steps.")
        else:
            tools=manager.provider_tools(); result=None
            working_history=list(history)
            for _step in range(max_steps):
                result=provider_client.chat(working_history,system,tools=tools)
                _merge_usage(total_usage,result.usage)
                if not result.tool_calls: break
                raw_message=(((result.raw.get("choices") or [{}])[0] or {}).get("message") or {})
                working_history.append({"role":"assistant","content":raw_message.get("content") or "","tool_calls":raw_message.get("tool_calls") or [c.get("raw") for c in result.tool_calls]})
                for call in result.tool_calls:
                    tool_call_count+=1
                    tool_result=manager.execute(call.get("name"),call.get("arguments") or {},approved=False)
                    if isinstance(tool_result,dict) and tool_result.get("approval_required"):
                        answer=_("Approval is required before running tool: {0}").format(call.get("name"))
                        _save_message(conversation,"assistant",answer,config.name,config.default_model,tool_result)
                        return {"conversation":conversation,"answer":answer,"provider":config.name,"model":config.default_model,"tool_mode":manager.mode,"approval_required":True,"approval":tool_result}
                    working_history.append({"role":"tool","tool_call_id":call.get("id"),"name":call.get("name"),"content":json.dumps(tool_result,ensure_ascii=False,default=str)})
            else:
                raise RuntimeError(f"Tool execution exceeded the maximum of {max_steps} steps.")

        answer=(result.text if result else "") or _("The provider returned an empty response after tool execution.")
        _save_message(conversation,"assistant",answer,config.name,config.default_model,result.raw if result else None)
        frappe.db.set_value("AI Conversation",conversation,{"provider":config.name,"model":config.default_model,"last_activity":frappe.utils.now()})
        normalized=log_usage(user=user,conversation=conversation,provider=config.name,model=config.default_model,raw_usage=total_usage or (result.usage if result else {}),tool_calls=tool_call_count,status="Success",response_time_ms=int((time.monotonic()-started)*1000))
        return {"conversation":conversation,"answer":answer,"provider":config.name,"model":config.default_model,"tool_mode":manager.mode,"usage":normalized,"quota":quota_status(user)}
    except Exception as exc:
        try: log_usage(user=user,conversation=conversation,provider=config.name,model=config.default_model,status="Failed",response_time_ms=int((time.monotonic()-started)*1000))
        except Exception: pass
        frappe.log_error(frappe.get_traceback(),"Shams AI Provider Error")
        _save_message(conversation,"assistant",f"Error: {exc}",config.name,config.default_model)
        frappe.throw(_("AI provider request failed: {0}").format(str(exc)))


@frappe.whitelist()
def list_conversations():
    return frappe.get_list("AI Conversation",fields=["name","title","provider","model","last_activity","modified"],order_by="modified desc",limit_page_length=50)


@frappe.whitelist()
def get_messages(conversation):
    doc=frappe.get_doc("AI Conversation",conversation); doc.check_permission("read")
    return frappe.get_list("AI Message",filters={"conversation":conversation},fields=["name","role","content","creation","provider","model"],order_by="creation asc",limit_page_length=200)


@frappe.whitelist()
def list_providers():
    return frappe.get_all("AI Provider",filters={"enabled":1},fields=["name","provider_name","provider_type","default_model","is_default","tool_mode"],order_by="is_default desc, provider_name asc")
