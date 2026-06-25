"""Read-only Nessus / Tenable.io vulnerability scan evidence collector.

Works against Tenable.io and Nessus Manager, which share the same
X-ApiKeys access/secret key auth model and /scans REST surface. Pulls the
most recently completed scan and summarizes severity counts, mapped to a
vulnerability-scanning control (e.g. the sample 11.3 control).
"""

from datetime import datetime, timezone

import httpx

from app.integrations.registry import ConfigField, IntegrationDefinition, register


class NessusRequestError(Exception):
    pass


def _headers(config: dict) -> dict:
    return {
        "X-ApiKeys": f"accessKey={config['access_key']}; secretKey={config['secret_key']}",
    }


def _list_scans(config: dict) -> list[dict]:
    response = httpx.get(
        f"{config['base_url'].rstrip('/')}/scans",
        headers=_headers(config),
        timeout=15,
    )
    if response.status_code != 200:
        raise NessusRequestError(f"Nessus request failed: {response.status_code} {response.text}")
    return response.json().get("scans") or []


def _get_scan_detail(config: dict, scan_id: int) -> dict:
    response = httpx.get(
        f"{config['base_url'].rstrip('/')}/scans/{scan_id}",
        headers=_headers(config),
        timeout=15,
    )
    if response.status_code != 200:
        raise NessusRequestError(f"Nessus request failed: {response.status_code} {response.text}")
    return response.json()


def test_connection(config: dict) -> dict:
    try:
        scans = _list_scans(config)
        return {"success": True, "message": f"Connected; {len(scans)} scan(s) visible."}
    except NessusRequestError as e:
        return {"success": False, "message": str(e)}


def collect_evidence(config: dict) -> dict:
    scans = _list_scans(config)
    completed = [s for s in scans if s.get("status") == "completed"]
    if not completed:
        return {
            "status": "not_met",
            "notes": "No completed vulnerability scan found in Nessus/Tenable.",
            "source": "nessus",
        }

    latest = max(completed, key=lambda s: s.get("last_modification_date", 0))
    detail = _get_scan_detail(config, latest["id"])

    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for host in detail.get("hosts", []):
        for severity in counts:
            counts[severity] += host.get(severity, 0) or 0

    scan_age_days = None
    last_modified = latest.get("last_modification_date")
    if last_modified:
        scan_age_days = (
            datetime.now(timezone.utc) - datetime.fromtimestamp(last_modified, tz=timezone.utc)
        ).days

    stale = scan_age_days is not None and scan_age_days > 100

    if counts["critical"] > 0:
        status = "not_met"
    elif counts["high"] > 0 or stale:
        status = "partial"
    else:
        status = "met"

    notes = (
        f"Most recent completed scan '{latest.get('name')}' "
        f"({scan_age_days if scan_age_days is not None else '?'} days old): "
        f"{counts['critical']} critical, {counts['high']} high, "
        f"{counts['medium']} medium, {counts['low']} low findings."
    )
    if stale:
        notes += " Scan is older than 100 days."

    return {
        "status": status,
        "notes": notes,
        "source": "nessus",
        "scan_id": latest.get("id"),
        "severity_counts": counts,
    }


register(
    IntegrationDefinition(
        type="nessus",
        display_name="Nessus / Tenable.io",
        adapter_type="vuln_scanner",
        fields=[
            ConfigField("base_url", "API base URL", "url", "e.g. https://cloud.tenable.com"),
            ConfigField("access_key", "Access key", "secret"),
            ConfigField("secret_key", "Secret key", "secret"),
        ],
        permissions_help=(
            "Generate an API access key/secret key pair under My Account -> API Keys "
            "(Tenable.io) or Settings -> My Account (Nessus Manager). Read-only scan "
            "access is sufficient."
        ),
        test_connection=test_connection,
        collect_evidence=collect_evidence,
    )
)
