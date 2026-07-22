from __future__ import annotations
import json, time
import frappe
from frappe import _
from shams_ai_assistant.mcp import list_tools as mcp_list_tools, call_tool as mcp_call_tool, native_mcp_config

MODES={
    "disabled":"disabled",
    "local tools":"local",
    "application mcp":"application_mcp",
    "native mcp":"native_mcp",
    "local + application mcp":"local_application_mcp",
    "local + native mcp":"local_native_mcp",
    "auto":"auto",
}

class ToolManager:
    def __init__(self, provider_config, provider_client, message="", mcp_server=None, conversation=None):
        self.config=provider_config; self.provider=provider_client; self.message=message or ""; self.mcp_server=mcp_server; self.conversation=conversation
        self.mode=self.resolve_mode()
        self.local_docs={}
        self.managed_mcp_names=set()

    def resolve_mode(self):
        requested=MODES.get((self.config.get("tool_mode") or self.config.get("mcp_mode") or "Auto").strip().lower(),"auto")
        has_local=bool(frappe.db.exists("AI Tool",{"enabled":1}))
        has_mcp=bool(self.mcp_server)
        native=bool(has_mcp and self.provider.supports_native_mcp())
        function_tools=bool(getattr(self.provider,"supports_function_tools",lambda: True)())
        fallback=bool(self.config.get("native_mcp_fallback"))
        if requested=="auto":
            if has_local and native: return "local_native_mcp"
            if native: return "native_mcp"
            if has_local and has_mcp and function_tools: return "local_application_mcp"
            if has_mcp and function_tools: return "application_mcp"
            if has_local and function_tools: return "local"
            return "disabled"
        if requested in {"native_mcp","local_native_mcp"} and not native:
            if fallback:
                return "local_application_mcp" if requested.startswith("local") and function_tools else "application_mcp"
            frappe.throw(_("The selected provider/model does not support Native MCP."))
        if requested in {"application_mcp","local_application_mcp","local"} and not function_tools:
            frappe.throw(_("The selected provider/model does not support function tools."))
        if "mcp" in requested and not has_mcp:
            return "local" if requested.startswith("local") and has_local else "disabled"
        return requested

    @property
    def uses_local(self): return self.mode in {"local","local_application_mcp","local_native_mcp"}
    @property
    def uses_managed_mcp(self): return self.mode in {"application_mcp","local_application_mcp"}
    @property
    def uses_native_mcp(self): return self.mode in {"native_mcp","local_native_mcp"}

    def _roles_allowed(self,tool):
        roles={r.role for r in tool.allowed_roles or []}
        return not roles or bool(roles.intersection(frappe.get_roles()))

    def local_schemas(self):
        names=frappe.get_all("AI Tool",filters={"enabled":1},pluck="name",order_by="priority asc, modified desc")
        docs=[]
        for name in names:
            tool=frappe.get_cached_doc("AI Tool",name)
            if self._roles_allowed(tool): docs.append(tool)
        docs=self._select(docs, lambda x: f"{x.tool_name} {x.tool_label} {x.description}")
        result=[]
        for tool in docs:
            public_name=f"local__{tool.tool_name}"
            self.local_docs[public_name]=tool
            props={}; required=[]
            for row in tool.parameters or []:
                spec={"type":row.parameter_type or "string","description":row.description or ""}
                if row.options: spec["enum"]=[x.strip() for x in row.options.splitlines() if x.strip()]
                if row.parameter_type=="array": spec["items"]={"type":row.items_type or "string"}
                if row.default_value not in (None,""):
                    try: spec["default"]=json.loads(row.default_value)
                    except Exception: spec["default"]=row.default_value
                props[row.parameter_name]=spec
                if row.required: required.append(row.parameter_name)
            result.append({"type":"function","function":{"name":public_name,"description":tool.description,"parameters":{"type":"object","properties":props,"required":required,"additionalProperties":False}}})
        return result

    def managed_mcp_schemas(self):
        raw=mcp_list_tools(self.mcp_server)
        selected=self._select(raw,lambda x:f"{x.get('name','')} {x.get('description','')}")
        out=[]
        for tool in selected:
            public=f"mcp__{tool.get('name')}"; self.managed_mcp_names.add(public)
            out.append({"type":"function","function":{"name":public,"description":tool.get("description") or "","parameters":tool.get("inputSchema") or {"type":"object","properties":{}}}})
        return out

    def _select(self,items,text_fn):
        try:
            settings=frappe.get_cached_doc("AI Assistant Settings"); enabled=bool(settings.enable_tool_filtering); maximum=int(settings.max_tools_per_request or 12)
        except Exception: enabled,maximum=True,12
        words={w.lower() for w in __import__('re').findall(r"[\w-]+",self.message) if len(w)>2}
        ranked=[]
        for item in items:
            text=text_fn(item).lower(); score=sum(3 if w in text.split()[0] else 1 for w in words if w in text); ranked.append((score,item))
        ranked.sort(key=lambda x:x[0],reverse=True)
        return [x[1] for x in (ranked[:maximum] if enabled and len(ranked)>maximum else ranked)]

    def provider_tools(self):
        tools=[]
        if self.uses_local: tools += self.local_schemas()
        if self.uses_managed_mcp: tools += self.managed_mcp_schemas()
        return tools

    def native_definition(self):
        if not self.uses_native_mcp: return None
        connector=(self.config.get("connector_id") or "").strip() if self.config.get("native_mcp_source")=="Provider Connector" else None
        return native_mcp_config(self.mcp_server,connector_id=connector)

    def execute(self,name,args,approved=False):
        started=time.monotonic(); source="Local"; status="Success"; result=None; error=None
        try:
            if name in self.local_docs:
                tool=self.local_docs[name]
                if tool.requires_confirmation and not approved:
                    result={"approval_required":True,"source":"local","name":name,"tool":tool.tool_name,"arguments":args}
                    status="Approval Required"; return result
                method=frappe.get_attr(tool.handler_method)
                if not getattr(method,"is_shams_ai_tool",False): frappe.throw(_("Unsafe or unregistered tool handler."))
                result=method(tool=tool,**(args or {}))
            elif name in self.managed_mcp_names:
                source="Application MCP"; result=mcp_call_tool(self.mcp_server,name.removeprefix("mcp__"),args or {},approved=approved)
                if isinstance(result,dict) and result.get("approval_required"):
                    result.setdefault("name",name); result.setdefault("arguments",args or {})
                    status="Approval Required"
            else: frappe.throw(_("Unknown tool: {0}").format(name))
            return result
        except Exception as exc:
            status="Failed"; error=str(exc); raise
        finally:
            try:
                frappe.get_doc({"doctype":"AI Tool Execution Log","user":frappe.session.user,"conversation":self.conversation,"source":source,"tool_name":name,"mcp_server":self.mcp_server if source!="Local" else None,"arguments":json.dumps(args,ensure_ascii=False,default=str),"result":json.dumps(result,ensure_ascii=False,default=str) if result is not None else None,"status":status,"duration_ms":int((time.monotonic()-started)*1000),"error":error}).insert(ignore_permissions=True)
            except Exception: pass
