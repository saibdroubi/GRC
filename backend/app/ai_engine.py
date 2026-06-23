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
