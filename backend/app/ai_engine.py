import json

import anthropic

from app.config import settings
from app import models

MODEL = "claude-sonnet-4-6"

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def analyze_evidence_against_control(
    evidence: models.Evidence, control: models.Control
) -> tuple[str, float, str]:
    """Ask Claude whether the given evidence satisfies the given control.

    Returns (status, confidence, rationale). status is one of
    met | partial | not_met | not_applicable.
    """
    prompt = f"""You are a compliance analyst. Decide whether the evidence below satisfies the control.

Control: {control.description}
Testing procedure: {control.testing_procedure or "N/A"}

Evidence (extracted facts): {json.dumps(evidence.extracted_facts)}
Evidence type: {evidence.evidence_type}

Respond with ONLY a JSON object: {{"status": "met|partial|not_met|not_applicable", "confidence": 0.0-1.0, "rationale": "one or two sentences"}}"""

    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text
    data = json.loads(text)
    return data["status"], float(data["confidence"]), data["rationale"]


VALID_ADAPTER_TYPES = {"ad", "edr", "m365", "vuln_scanner", "cloud", "itsm"}

_HEURISTIC_RULES = [
    (("multi-factor", "mfa", "conditional access"), "m365", "enforce_mfa_policy"),
    (("vulnerability scan", "patch"), "vuln_scanner", "trigger_scan"),
    (("audit log", "logging"), "cloud", "enable_audit_logging"),
    (("endpoint", "malware", "edr"), "edr", "isolate_or_remediate_host"),
    (("account", "password", "directory"), "ad", "enforce_account_policy"),
]


def _heuristic_remediation(control: models.Control) -> tuple[str, str, dict]:
    text = control.description.lower()
    for keywords, adapter_type, action_type in _HEURISTIC_RULES:
        if any(k in text for k in keywords):
            return adapter_type, action_type, {"control_id": str(control.id)}
    return "itsm", "create_remediation_ticket", {"control_id": str(control.id)}


def propose_remediation(gap: models.Gap, control: models.Control) -> tuple[str, str, dict, str]:
    """Propose a remediation action for an open gap.

    Returns (adapter_type, action_type, parameters, rationale). Uses Claude when an
    API key is configured, falling back to a keyword heuristic over the control text
    otherwise (e.g. local/offline dev, or before a key has been provisioned).
    """
    if not settings.anthropic_api_key:
        adapter_type, action_type, parameters = _heuristic_remediation(control)
        return adapter_type, action_type, parameters, (
            f"Heuristic match on control text -> {adapter_type}.{action_type} "
            "(no ANTHROPIC_API_KEY configured; set one for AI-generated proposals)."
        )

    prompt = f"""You are a compliance remediation planner. Given the gap and control below, propose ONE
concrete remediation action.

Control: {control.description}
Gap: {gap.description}

Valid adapter_type values: {sorted(VALID_ADAPTER_TYPES)}

Respond with ONLY a JSON object:
{{"adapter_type": "...", "action_type": "short_snake_case_name", "parameters": {{}}, "rationale": "one sentence"}}"""

    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    data = json.loads(response.content[0].text)
    adapter_type = data["adapter_type"] if data["adapter_type"] in VALID_ADAPTER_TYPES else "itsm"
    return adapter_type, data["action_type"], data.get("parameters", {}), data["rationale"]
