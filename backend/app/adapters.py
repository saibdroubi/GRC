"""Integration adapter execution stubs.

Per docs/ARCHITECTURE.md §2.6, each adapter_type should be backed by a real
client against the target system (Entra ID/Graph, AD/LDAP, EDR API, vuln
scanner API, cloud provider API, ITSM API), looked up via the org's
IntegrationConnection config. None of those are wired up yet, so every
adapter here is a simulated executor: it always succeeds and returns a
canned result, so the full propose -> approve -> execute -> evidence loop
can be exercised end-to-end before any real integration exists. Replace
each function's body with a real API call when that adapter is built.
"""

from app import models


def _simulate(action: models.Action, message: str) -> dict:
    return {"success": True, "simulated": True, "message": message}


def execute_ad(action: models.Action) -> dict:
    return _simulate(action, f"[simulated] AD action '{action.action_type}' applied.")


def execute_edr(action: models.Action) -> dict:
    return _simulate(action, f"[simulated] EDR action '{action.action_type}' applied.")


def execute_m365(action: models.Action) -> dict:
    return _simulate(action, f"[simulated] M365/Graph action '{action.action_type}' applied.")


def execute_vuln_scanner(action: models.Action) -> dict:
    return _simulate(action, f"[simulated] Vulnerability scanner action '{action.action_type}' applied.")


def execute_cloud(action: models.Action) -> dict:
    return _simulate(action, f"[simulated] Cloud config action '{action.action_type}' applied.")


def execute_itsm(action: models.Action) -> dict:
    return _simulate(action, f"[simulated] ITSM action '{action.action_type}' applied (e.g. ticket created).")


EXECUTORS = {
    "ad": execute_ad,
    "edr": execute_edr,
    "m365": execute_m365,
    "vuln_scanner": execute_vuln_scanner,
    "cloud": execute_cloud,
    "itsm": execute_itsm,
}


def execute_action(action: models.Action) -> dict:
    executor = EXECUTORS[action.adapter_type]
    return executor(action)
