import os

from app.config import Settings


def configure_langsmith(settings: Settings) -> bool:
    enabled = settings.langsmith_enabled
    os.environ["LANGSMITH_TRACING"] = "true" if enabled else "false"
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    else:
        os.environ.pop("LANGSMITH_API_KEY", None)
    if settings.langsmith_endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    else:
        os.environ.pop("LANGSMITH_ENDPOINT", None)
    if settings.langsmith_workspace_id:
        os.environ["LANGSMITH_WORKSPACE_ID"] = settings.langsmith_workspace_id
    else:
        os.environ.pop("LANGSMITH_WORKSPACE_ID", None)
    return enabled
