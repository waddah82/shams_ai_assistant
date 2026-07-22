import frappe

@frappe.whitelist()
def status():
    providers=frappe.get_all("AI Provider", fields=["name","provider_type","default_model","enabled","is_default"])
    return {"app":"shams_ai_assistant","version":"2.0.0","user":frappe.session.user,"providers":providers,"assets":{"js":"/assets/shams_ai_assistant/js/assistant.js","css":"/assets/shams_ai_assistant/css/assistant.css"}}
