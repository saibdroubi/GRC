"""Burp Suite Enterprise Edition integration — scaffolded.

Connection setup and status checks work today. Evidence collection (pulling
scan results and mapping them to specific controls) is intentionally not
implemented yet, same reasoning as app/integrations/palo_alto.py.

TODO: implement collect_evidence() against the Enterprise REST API's scan
issues endpoint once the control mapping for web-app vuln findings is
defined.
"""

import httpx

from app.integrations.registry import ConfigField, IntegrationDefinition, register


def test_connection(config: dict) -> dict:
    try:
        response = httpx.get(
            f"{config['base_url'].rstrip('/')}/api/v1/scans",
            headers={"Authorization": config["api_key"]},
            timeout=15,
            params={"size": 1},
        )
    except httpx.HTTPError as e:
        return {"success": False, "message": f"Connection failed: {e}"}

    if response.status_code not in (200, 401, 403):
        return {"success": False, "message": f"Unexpected response: {response.status_code}"}
    if response.status_code != 200:
        return {"success": False, "message": f"API key rejected: {response.status_code}"}
    return {"success": True, "message": "Burp Suite Enterprise API key accepted."}


register(
    IntegrationDefinition(
        type="burp",
        display_name="Burp Suite Enterprise",
        adapter_type="vuln_scanner",
        fields=[
            ConfigField("base_url", "Enterprise server URL", "url", "e.g. https://burp.yourcompany.com"),
            ConfigField("api_key", "API key", "secret", "Generate under Enterprise -> API"),
        ],
        permissions_help="Generate an API key in Burp Suite Enterprise under the API settings page.",
        test_connection=test_connection,
        collect_evidence=None,
    )
)
