"""Palo Alto Networks firewall (PAN-OS XML API) integration — scaffolded.

Connection setup and status checks work today. Evidence collection (mapping
firewall rule-base/config posture to specific controls) is intentionally not
implemented yet — which controls a firewall rule review should satisfy
depends on the framework and the customer's network segmentation, and
deserves its own design pass rather than a guessed mapping.

TODO: implement collect_evidence() once that mapping is defined — likely
pulling the security rulebase (`<show><running><security-policy>` or the
config API) and evaluating rules against whatever control(s) it's wired to.
"""

import httpx

from app.integrations.registry import ConfigField, IntegrationDefinition, register


class PaloAltoRequestError(Exception):
    pass


def test_connection(config: dict) -> dict:
    try:
        response = httpx.get(
            f"{config['base_url'].rstrip('/')}/api/",
            params={
                "type": "op",
                "cmd": "<show><system><info></info></system></show>",
                "key": config["api_key"],
            },
            timeout=15,
        )
    except httpx.HTTPError as e:
        return {"success": False, "message": f"Connection failed: {e}"}

    if response.status_code != 200 or "<response status=\"success\"" not in response.text:
        return {"success": False, "message": f"PAN-OS API request failed: {response.status_code}"}
    return {"success": True, "message": "PAN-OS API key accepted."}


register(
    IntegrationDefinition(
        type="palo_alto",
        display_name="Palo Alto Networks Firewall",
        adapter_type="cloud",
        fields=[
            ConfigField("base_url", "Firewall URL", "url", "e.g. https://10.0.0.1"),
            ConfigField("api_key", "API key", "secret", "Generate via <firewall>/api/?type=keygen"),
        ],
        permissions_help=(
            "Generate a PAN-OS API key for a read-only admin account: "
            "GET https://<firewall>/api/?type=keygen&user=...&password=..."
        ),
        test_connection=test_connection,
        collect_evidence=None,
    )
)
