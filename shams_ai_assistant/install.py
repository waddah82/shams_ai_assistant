from shams_ai_assistant.setup.standard_providers import sync_standard_providers
from shams_ai_assistant.setup.standard_tools import sync_standard_tools


def _sync_standard_records():
    sync_standard_tools()
    sync_standard_providers()


def after_install():
    _sync_standard_records()


def after_migrate():
    _sync_standard_records()
