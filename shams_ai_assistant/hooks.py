app_name = "shams_ai_assistant"
app_title = "Shams AI Assistant"
app_publisher = "Shams Solutions"
app_description = "Multi-provider AI assistant for ERPNext"
app_email = "support@shams.local"
app_license = "MIT"

app_include_js = ["/assets/shams_ai_assistant/js/assistant.js"]
app_include_css = ["/assets/shams_ai_assistant/css/assistant.css"]

permission_query_conditions = {
    "AI Conversation": "shams_ai_assistant.permissions.conversation_query",
    "AI Message": "shams_ai_assistant.permissions.message_query",
}

has_permission = {
    "AI Conversation": "shams_ai_assistant.permissions.conversation_permission",
    "AI Message": "shams_ai_assistant.permissions.message_permission",
}

# Seed/synchronize standard AI tools only after DocType model synchronization.
after_install = "shams_ai_assistant.install.after_install"
after_migrate = "shams_ai_assistant.install.after_migrate"
