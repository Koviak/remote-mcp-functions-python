import os
from typing import Optional, Tuple

from azure.identity import ClientSecretCredential


# Microsoft Graph API endpoint (shared across all modules)
GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"


def get_access_token() -> Optional[str]:
    """Acquire an application (app-only) access token for Microsoft Graph.

    Returns None if credentials are not configured.
    """
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    client_id = os.environ.get("AZURE_CLIENT_ID")
    client_secret = os.environ.get("AZURE_CLIENT_SECRET")

    if not all([tenant_id, client_id, client_secret]):
        return None

    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )

    token = credential.get_token("https://graph.microsoft.com/.default")
    return token.token


def _get_agent_user_id() -> str:
    """Return the configured agent user id if available, else empty string."""
    return os.environ.get("AGENT_USER_ID", "").strip()


def _get_token_and_base_for_me(delegated_scopes: str = "") -> Tuple[Optional[str], Optional[str]]:
    """Return (delegated_token, '/me') or (None, None) if unavailable.

    Uses agent_auth_manager.get_agent_token to obtain a delegated token with the
    provided scopes. When scopes are omitted, the manager default is used.
    """
    try:
        from agent_auth_manager import get_agent_token  # local import to avoid cycles
        token = get_agent_token(delegated_scopes) if delegated_scopes else get_agent_token()
        if token:
            return token, "/me"
    except Exception:
        return None, None
    return None, None


def build_json_headers(token: str) -> dict:
    """Standard JSON headers with Authorization."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


