"""Read-only Microsoft 365 / Entra ID (Graph API) evidence collector.

First-pass scope, per docs/ARCHITECTURE.md §2.6: app-only (client credentials)
auth against Microsoft Graph, read-only. Currently collects Conditional
Access policies and evaluates whether MFA is enforced org-wide, which is the
signal PCI DSS-style control 8.3 (strong/multi-factor authentication) cares
about. No write/remediation calls are made by this module.

Required Entra ID app registration permission (application, admin-consented):
  Policy.Read.All
"""

import time

import httpx

from app.config import settings

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

_token_cache: dict[str, object] = {"access_token": None, "expires_at": 0}


class M365NotConfigured(Exception):
    pass


class M365RequestError(Exception):
    pass


def _require_config() -> None:
    if not (settings.m365_tenant_id and settings.m365_client_id and settings.m365_client_secret):
        raise M365NotConfigured(
            "M365 integration is not configured. Set M365_TENANT_ID, M365_CLIENT_ID, "
            "and M365_CLIENT_SECRET in backend/.env."
        )


def get_access_token() -> str:
    _require_config()

    if _token_cache["access_token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]  # type: ignore[return-value]

    token_url = f"https://login.microsoftonline.com/{settings.m365_tenant_id}/oauth2/v2.0/token"
    response = httpx.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": settings.m365_client_id,
            "client_secret": settings.m365_client_secret,
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=15,
    )
    if response.status_code != 200:
        raise M365RequestError(f"Failed to obtain Graph token: {response.status_code} {response.text}")

    data = response.json()
    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"] = time.time() + data.get("expires_in", 3600)
    return data["access_token"]


def list_conditional_access_policies() -> list[dict]:
    token = get_access_token()
    response = httpx.get(
        f"{GRAPH_BASE}/identity/conditionalAccess/policies",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if response.status_code != 200:
        raise M365RequestError(
            f"Graph request failed: {response.status_code} {response.text}"
        )
    return response.json().get("value", [])


def _policy_enforces_mfa_for_all(policy: dict) -> bool:
    if policy.get("state") != "enabled":
        return False
    users = policy.get("conditions", {}).get("users", {}) or {}
    if "All" not in (users.get("includeUsers") or []):
        return False
    controls = policy.get("grantControls", {}) or {}
    return "mfa" in (controls.get("builtInControls") or [])


def evaluate_mfa_enforcement() -> dict:
    """Pull live Conditional Access policies and judge whether MFA is
    enforced for all users. Returns a dict shaped like the manual
    extracted_facts payload the /evidence endpoint already accepts."""
    policies = list_conditional_access_policies()

    enforcing = [p for p in policies if _policy_enforces_mfa_for_all(p)]
    enabled_mfa_policies = [
        p
        for p in policies
        if p.get("state") == "enabled" and "mfa" in (p.get("grantControls", {}).get("builtInControls") or [])
    ]

    if enforcing:
        status = "met"
        notes = (
            f"Conditional Access policy '{enforcing[0].get('displayName')}' enforces MFA for all users."
        )
    elif enabled_mfa_policies:
        status = "partial"
        names = ", ".join(p.get("displayName", "unnamed") for p in enabled_mfa_policies)
        notes = f"MFA is enforced by Conditional Access for a subset of users/apps only ({names}), not org-wide."
    else:
        status = "not_met"
        notes = "No enabled Conditional Access policy enforces MFA for all users."

    return {
        "status": status,
        "notes": notes,
        "source": "m365_conditional_access",
        "policy_count": len(policies),
        "policy_names": [p.get("displayName") for p in policies],
    }
