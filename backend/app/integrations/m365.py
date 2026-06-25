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

from app.integrations.registry import ConfigField, IntegrationDefinition, register

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Token cache keyed by tenant_id — fine for a single-process dev/small
# deployment; a multi-worker deployment would want this in Postgres/Redis
# instead, same caveat as any other in-memory cache here.
_token_cache: dict[str, dict] = {}


class M365RequestError(Exception):
    pass


def _get_access_token(config: dict) -> str:
    tenant_id = config["tenant_id"]
    cached = _token_cache.get(tenant_id)
    if cached and time.time() < cached["expires_at"] - 60:
        return cached["access_token"]

    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    response = httpx.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=15,
    )
    if response.status_code != 200:
        raise M365RequestError(f"Failed to obtain Graph token: {response.status_code} {response.text}")

    data = response.json()
    _token_cache[tenant_id] = {
        "access_token": data["access_token"],
        "expires_at": time.time() + data.get("expires_in", 3600),
    }
    return data["access_token"]


def _list_conditional_access_policies(config: dict) -> list[dict]:
    token = _get_access_token(config)
    response = httpx.get(
        f"{GRAPH_BASE}/identity/conditionalAccess/policies",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if response.status_code != 200:
        raise M365RequestError(f"Graph request failed: {response.status_code} {response.text}")
    return response.json().get("value", [])


def _policy_enforces_mfa_for_all(policy: dict) -> bool:
    if policy.get("state") != "enabled":
        return False
    users = policy.get("conditions", {}).get("users", {}) or {}
    if "All" not in (users.get("includeUsers") or []):
        return False
    controls = policy.get("grantControls", {}) or {}
    return "mfa" in (controls.get("builtInControls") or [])


def test_connection(config: dict) -> dict:
    try:
        _get_access_token(config)
        return {"success": True, "message": "Obtained a Graph access token successfully."}
    except M365RequestError as e:
        return {"success": False, "message": str(e)}


def collect_evidence(config: dict) -> dict:
    """Pull live Conditional Access policies and judge whether MFA is
    enforced for all users. Returns a dict shaped like the manual
    extracted_facts payload the /evidence endpoint already accepts."""
    policies = _list_conditional_access_policies(config)

    enforcing = [p for p in policies if _policy_enforces_mfa_for_all(p)]
    enabled_mfa_policies = [
        p
        for p in policies
        if p.get("state") == "enabled" and "mfa" in (p.get("grantControls", {}).get("builtInControls") or [])
    ]

    if enforcing:
        status = "met"
        notes = f"Conditional Access policy '{enforcing[0].get('displayName')}' enforces MFA for all users."
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


register(
    IntegrationDefinition(
        type="m365",
        display_name="Microsoft 365 / Entra ID",
        adapter_type="m365",
        fields=[
            ConfigField("tenant_id", "Tenant ID", "text", "Entra ID directory (tenant) ID"),
            ConfigField("client_id", "Client ID", "text", "App registration's application (client) ID"),
            ConfigField("client_secret", "Client secret", "secret", "App registration client secret value"),
        ],
        permissions_help=(
            "Entra ID app registration needs the application permission Policy.Read.All, "
            "admin-consented. Azure portal -> Entra ID -> App registrations -> your app -> "
            "API permissions -> Add a permission -> Microsoft Graph -> Application permissions."
        ),
        test_connection=test_connection,
        collect_evidence=collect_evidence,
    )
)
