"""Registry of configurable integration vendors.

Each vendor module (m365.py, nessus.py, palo_alto.py, burp.py) implements the
IntegrationDefinition interface below and registers an instance here. This is
what makes "configure via chat" generic: the chat agent (and the REST API)
just ask the registry for a type's config schema, store whatever fields come
back, and call test_connection/collect_evidence — no per-vendor code in the
chat agent or routers.
"""

from dataclasses import dataclass
from typing import Callable


@dataclass
class ConfigField:
    key: str
    label: str
    type: str  # "text" | "secret" | "url"
    help_text: str = ""
    required: bool = True


@dataclass
class IntegrationDefinition:
    type: str  # vendor key, e.g. "m365", "nessus"
    display_name: str
    adapter_type: str  # broad category for Action routing: ad|edr|m365|vuln_scanner|cloud|itsm
    fields: list[ConfigField]
    permissions_help: str
    test_connection: Callable[[dict], dict]  # config -> {"success": bool, "message": str}
    collect_evidence: Callable[[dict], dict] | None = None  # config -> extracted_facts dict

    def missing_required_fields(self, config: dict) -> list[str]:
        return [f.key for f in self.fields if f.required and not config.get(f.key)]


_REGISTRY: dict[str, IntegrationDefinition] = {}


def register(definition: IntegrationDefinition) -> None:
    _REGISTRY[definition.type] = definition


def get(integration_type: str) -> IntegrationDefinition:
    if integration_type not in _REGISTRY:
        raise KeyError(f"Unknown integration type '{integration_type}'")
    return _REGISTRY[integration_type]


def list_all() -> list[IntegrationDefinition]:
    return list(_REGISTRY.values())
