import frappe

def _esc(value):
    return frappe.db.escape(value)

def conversation_query(user=None):
    user = user or frappe.session.user
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return ""
    return f"`tabAI Conversation`.`owner` = {_esc(user)}"

def message_query(user=None):
    user = user or frappe.session.user
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return ""
    return f"`tabAI Message`.`owner` = {_esc(user)}"

def conversation_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    return user == "Administrator" or "System Manager" in frappe.get_roles(user) or doc.owner == user

def message_permission(doc, user=None, permission_type=None):
    return conversation_permission(doc, user, permission_type)
