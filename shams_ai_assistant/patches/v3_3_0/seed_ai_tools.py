import frappe

TOOLS=[
("list_documents","List Documents","List permitted documents from an allowed Frappe DocType using filters, fields, ordering and pagination.","Documents","Read","shams_ai_assistant.tooling.local_handlers.list_documents",[("doctype","string",1),("fields","array",0),("filters","object",0),("or_filters","object",0),("order_by","string",0),("limit","integer",0),("start","integer",0)]),
("count_documents","Count Documents","Count permitted documents in an allowed Frappe DocType.","Documents","Read","shams_ai_assistant.tooling.local_handlers.count_documents",[("doctype","string",1),("filters","object",0)]),
("get_document","Get Document","Read one permitted Frappe document by DocType and name.","Documents","Read","shams_ai_assistant.tooling.local_handlers.get_document",[("doctype","string",1),("name","string",1),("fields","array",0)]),
("get_doctype_info","Get DocType Info","Return safe field metadata for an allowed DocType.","Metadata","Read","shams_ai_assistant.tooling.local_handlers.get_doctype_info",[("doctype","string",1)]),
("search_link","Search Link","Search permitted Link values in an allowed DocType.","Metadata","Read","shams_ai_assistant.tooling.local_handlers.search_link",[("doctype","string",1),("text","string",0),("limit","integer",0)]),
("create_document","Create Document","Create a permitted Frappe document.","Documents","Create","shams_ai_assistant.tooling.local_handlers.create_document",[("doctype","string",1),("values","object",1)]),
("update_document","Update Document","Update permitted fields of an existing Frappe document.","Documents","Update","shams_ai_assistant.tooling.local_handlers.update_document",[("doctype","string",1),("name","string",1),("values","object",1)]),
("submit_document","Submit Document","Submit a permitted submittable Frappe document.","Documents","Submit","shams_ai_assistant.tooling.local_handlers.submit_document",[("doctype","string",1),("name","string",1)]),
("cancel_document","Cancel Document","Cancel a permitted submitted Frappe document.","Documents","Cancel","shams_ai_assistant.tooling.local_handlers.cancel_document",[("doctype","string",1),("name","string",1)]),
("delete_document","Delete Document","Delete a permitted draft Frappe document. Disabled by default.","Documents","Delete","shams_ai_assistant.tooling.local_handlers.delete_document",[("doctype","string",1),("name","string",1)]),
("amend_document","Amend Document","Create a draft amendment from a cancelled document.","Documents","Create","shams_ai_assistant.tooling.local_handlers.amend_document",[("doctype","string",1),("name","string",1)]),
("list_reports","List Reports","List reports available to the current user.","Reports","Read","shams_ai_assistant.tooling.local_handlers.list_reports",[("reference_doctype","string",0),("limit","integer",0)]),
("get_report_requirements","Get Report Requirements","Read report metadata and requirements.","Reports","Read","shams_ai_assistant.tooling.local_handlers.get_report_requirements",[("report_name","string",1)]),
("run_report","Run Report","Run a permitted Frappe report using supplied filters.","Reports","Read","shams_ai_assistant.tooling.local_handlers.run_report",[("report_name","string",1),("filters","object",0),("limit","integer",0)]),
("get_pending_approvals","Get Pending Approvals","List workflow actions pending for the current user.","Workflow","Read","shams_ai_assistant.tooling.local_handlers.get_pending_approvals",[("doctype","string",0),("limit","integer",0)]),
("get_workflow_actions","Get Workflow Actions","List workflow actions currently available for a document.","Workflow","Read","shams_ai_assistant.tooling.local_handlers.get_workflow_actions",[("doctype","string",1),("name","string",1)]),
("apply_workflow_action","Apply Workflow Action","Apply a permitted workflow action to a document.","Workflow","Update","shams_ai_assistant.tooling.local_handlers.apply_workflow_action",[("doctype","string",1),("name","string",1),("action","string",1)]),
("get_my_recent_activity","Get My Recent Activity","List the current user's recent ERPNext activity.","Activity","Read","shams_ai_assistant.tooling.local_handlers.get_my_recent_activity",[("limit","integer",0)]),
]

WRITE={"create_document","update_document","submit_document","cancel_document","delete_document","amend_document","apply_workflow_action"}

def execute():
    for i,(name,label,desc,cat,op,handler,params) in enumerate(TOOLS,1):
        if frappe.db.exists("AI Tool",name): continue
        doc=frappe.get_doc({"doctype":"AI Tool","tool_name":name,"tool_label":label,"description":desc,"enabled":0 if name=="delete_document" else 1,"is_standard":1,"category":cat,"operation":op,"handler_method":handler,"read_only":0 if name in WRITE else 1,"requires_confirmation":1 if name in WRITE else 0,"apply_user_permissions":1,"priority":i*10,"maximum_rows":50})
        for pname,ptype,reqd in params:
            doc.append("parameters",{"parameter_name":pname,"parameter_type":ptype,"required":reqd,"description":pname.replace('_',' ').title()})
        doc.insert(ignore_permissions=True)

    # Preserve the former MCP Mode when upgrading from v3.2.x.
    try:
        columns=frappe.db.get_table_columns("AI Provider")
        if "mcp_mode" in columns and "tool_mode" in columns:
            mapping={
                "Native Remote MCP":"Native MCP",
                "Application Managed MCP":"Application MCP",
                "Disabled":"Disabled",
                "Auto":"Auto",
            }
            for row in frappe.db.sql("select name, mcp_mode, tool_mode from `tabAI Provider`",as_dict=True):
                if row.mcp_mode and (not row.tool_mode or row.tool_mode=="Auto"):
                    frappe.db.set_value("AI Provider",row.name,"tool_mode",mapping.get(row.mcp_mode,"Auto"),update_modified=False)
    except Exception:
        frappe.log_error(frappe.get_traceback(),"Shams AI tool mode migration")
