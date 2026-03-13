import os
from typing import Optional, Tuple

from azure.identity import ClientSecretCredential

# Microsoft Graph API endpoint (shared across all modules)
GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"


_cached_credential: Optional[ClientSecretCredential] = None
_cached_credential_key: Optional[tuple] = None


def _get_credential() -> Optional[ClientSecretCredential]:
    """Return a cached ClientSecretCredential, creating one if env vars changed."""
    global _cached_credential, _cached_credential_key
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    client_id = os.environ.get("AZURE_CLIENT_ID")
    client_secret = os.environ.get("AZURE_CLIENT_SECRET")

    if not all([tenant_id, client_id, client_secret]):
        return None

    key = (tenant_id, client_id, client_secret)
    if _cached_credential is not None and _cached_credential_key == key:
        return _cached_credential

    _cached_credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )
    _cached_credential_key = key
    return _cached_credential


def get_access_token() -> Optional[str]:
    """Acquire an application (app-only) access token for Microsoft Graph.

    Returns None if credentials are not configured.
    The underlying ClientSecretCredential is cached so its internal MSAL token
    cache is preserved across calls, avoiding redundant AAD round-trips.
    """
    credential = _get_credential()
    if credential is None:
        return None

    token = credential.get_token("https://graph.microsoft.com/.default")
    return token.token


def _get_agent_user_id() -> str:
    """Return the configured agent user id if available, else empty string."""
    return os.environ.get("AGENT_USER_ID", "").strip()


def _get_token_and_base_for_me(
    delegated_scopes: str = "",
    delegated_user: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Return (delegated_token, '/me') or (None, None) if unavailable.

    Uses agent_auth_manager.get_agent_token to obtain a delegated token with the
    provided scopes. When scopes are omitted, the manager default is used.
    """
    try:
        from agent_auth_manager import get_agent_token  # local import to avoid cycles
        token = (
            get_agent_token(delegated_scopes, delegated_user=delegated_user)
            if delegated_scopes
            else get_agent_token(delegated_user=delegated_user)
        )
        if token:
            return token, "/me"
    except ValueError:
        raise
    except Exception:
        return None, None
    return None, None


def build_json_headers(token: str) -> dict:
    """Standard JSON headers with Authorization."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


