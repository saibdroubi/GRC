"""Chat agent: lets an admin do via prompt anything the dashboard/API can do.

Wraps the same service-layer functions the REST routers call (app/services/*)
as Anthropic tool-use tools, so chat and the dashboard never drift out of
sync. run_chat_turn is always called with the authenticated current_user
(app/api/chat.py resolves it via app.auth.get_current_user and verifies the
session belongs to them before this module ever runs) — three hard
guardrails enforced here in code, not just by prompting:

1. organization_id and the approving/acting user's identity always come from
   that authenticated current_user, never an LLM-supplied tool parameter —
   the model cannot query/act on a different org or impersonate another user.
2. Every mutating tool is gated by the same role requirements as its REST
   equivalent (_TOOL_ROLE_REQUIREMENTS, checked via app.permissions) — chat
   cannot do anything a viewer/analyst couldn't do through the dashboard.

Within those, the system prompt is what stops the model from calling
approve/reject unless the human's latest message actually asked for it.
"""

import json
import uuid

import anthropic
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.errors import ForbiddenError, NotFoundError, ValidationError
from app.evidence_pipeline import record_evidence
from app.permissions import ADMIN_ROLES, WRITE_ROLES, require_role
from app.serialization import to_jsonable
from app.services import actions as actions_service
from app.services import frameworks as frameworks_service
from app.services import gaps as gaps_service
from app.services import integrations as integrations_service
from app.services import knowledge_base as kb_service

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are the GRC platform's operating assistant. You can read and act on \
frameworks, controls, gaps, remediation actions, evidence, and integrations through your tools \
— the same data and operations the web dashboard exposes.

Hard rules:
- Never call approve_action or reject_action unless the human's most recent message explicitly \
approves or rejects that specific proposal. If they haven't, propose first and ask.
- When the human asks to connect/integrate a new system (e.g. "let's integrate Office 365", \
"connect our Nessus scanner"), act as a setup wizard: call list_integration_types and/or \
get_integration_status to see what's already there, then ask for the specific missing required \
fields (one or a few at a time, not a giant form dump), call configure_integration as each is \
provided, and once nothing is missing call test_integration_connection and report the result \
plainly (success or the exact error). Always mention what permissions/credentials are needed \
up front if get_integration_status hasn't already been called.
- Be transparent about where information comes from (which control, which integration, AI \
heuristic vs configured AI analysis) — never present a guess as a verified fact.
- If a tool returns is_error, explain the problem in plain language; don't retry blindly.
- Use search_knowledge_base when answering questions that might be informed by past evidence, \
syncs, or notes you don't already have in this conversation. Only call save_to_knowledge_base \
when the human explicitly asks you to remember/save something — never silently log every message.

Be concise. This is an admin operating a compliance program, not a chat companion."""


class ChatNotConfigured(Exception):
    pass


def _get_client() -> anthropic.Anthropic:
    if not settings.anthropic_api_key:
        raise ChatNotConfigured(
            "Chat is not configured. Set ANTHROPIC_API_KEY in backend/.env to enable it."
        )
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


# --- Tool definitions (Anthropic tool-use schema) -----------------------

TOOL_DEFINITIONS = [
    {
        "name": "list_frameworks",
        "description": "List all compliance frameworks (e.g. PCI DSS) known to the system.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_framework_score",
        "description": "Get the rolled-up compliance score for a framework: met/partial/not_met/n-a/unscored counts and a percentage.",
        "input_schema": {
            "type": "object",
            "properties": {"framework_id": {"type": "string"}},
            "required": ["framework_id"],
        },
    },
    {
        "name": "list_controls_with_status",
        "description": "List every control in a framework with its current status, confidence, and any open gap.",
        "input_schema": {
            "type": "object",
            "properties": {"framework_id": {"type": "string"}},
            "required": ["framework_id"],
        },
    },
    {
        "name": "list_gaps",
        "description": "List compliance gaps, optionally filtered by status (open, in_progress, remediated, risk_accepted).",
        "input_schema": {
            "type": "object",
            "properties": {"status": {"type": "string"}},
        },
    },
    {
        "name": "update_gap_status",
        "description": "Change a gap's status directly (e.g. mark in_progress or risk_accepted).",
        "input_schema": {
            "type": "object",
            "properties": {
                "gap_id": {"type": "string"},
                "new_status": {
                    "type": "string",
                    "enum": ["open", "in_progress", "remediated", "risk_accepted"],
                },
            },
            "required": ["gap_id", "new_status"],
        },
    },
    {
        "name": "submit_evidence",
        "description": "Manually record evidence against a control (e.g. the admin states a fact directly in chat).",
        "input_schema": {
            "type": "object",
            "properties": {
                "control_id": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["met", "partial", "not_met", "not_applicable"],
                },
                "notes": {"type": "string"},
            },
            "required": ["control_id", "status", "notes"],
        },
    },
    {
        "name": "propose_action",
        "description": "Have the AI engine propose a remediation action for an open/in_progress gap. Lands in pending_approval — does not execute anything.",
        "input_schema": {
            "type": "object",
            "properties": {"gap_id": {"type": "string"}},
            "required": ["gap_id"],
        },
    },
    {
        "name": "approve_action",
        "description": "Approve a pending remediation action, causing it to execute immediately. Only call this if the human just explicitly approved it.",
        "input_schema": {
            "type": "object",
            "properties": {"action_id": {"type": "string"}},
            "required": ["action_id"],
        },
    },
    {
        "name": "reject_action",
        "description": "Reject a pending remediation action. Only call this if the human just explicitly rejected it.",
        "input_schema": {
            "type": "object",
            "properties": {"action_id": {"type": "string"}},
            "required": ["action_id"],
        },
    },
    {
        "name": "list_integration_types",
        "description": "List every integration vendor type the platform supports, its required config fields, and what permissions it needs.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_integration_status",
        "description": "Get one integration's configuration/connection status for this org, including which required fields are still missing.",
        "input_schema": {
            "type": "object",
            "properties": {"integration_type": {"type": "string"}},
            "required": ["integration_type"],
        },
    },
    {
        "name": "configure_integration",
        "description": "Store one or more config field values for an integration (merges with whatever's already saved). Use this to collect credentials/fields one at a time during setup.",
        "input_schema": {
            "type": "object",
            "properties": {
                "integration_type": {"type": "string"},
                "config": {
                    "type": "object",
                    "description": "Field key -> value, e.g. {\"tenant_id\": \"...\"}",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["integration_type", "config"],
        },
    },
    {
        "name": "test_integration_connection",
        "description": "Test the stored credentials for an integration against the live vendor API and report success/failure.",
        "input_schema": {
            "type": "object",
            "properties": {"integration_type": {"type": "string"}},
            "required": ["integration_type"],
        },
    },
    {
        "name": "sync_integration_evidence",
        "description": "Pull live evidence from a configured integration and record it against a control.",
        "input_schema": {
            "type": "object",
            "properties": {
                "integration_type": {"type": "string"},
                "control_id": {"type": "string"},
            },
            "required": ["integration_type", "control_id"],
        },
    },
    {
        "name": "search_knowledge_base",
        "description": "Search this org's accumulated knowledge base (facts distilled from evidence, integration syncs, and saved notes) for relevant context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "save_to_knowledge_base",
        "description": "Explicitly save a fact/note the human asked you to remember into the knowledge base. Only call this when the human clearly asked you to remember/save something, not for every message.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["title", "content"],
        },
    },
]


# Mirrors the REST routers' role gates exactly (app/api/*.py) -- this is the
# part of the "chat can't bypass RBAC" guarantee that lives in code, not the
# system prompt.
_TOOL_ROLE_REQUIREMENTS = {
    "update_gap_status": WRITE_ROLES,
    "submit_evidence": WRITE_ROLES,
    "propose_action": WRITE_ROLES,
    "approve_action": ADMIN_ROLES,
    "reject_action": ADMIN_ROLES,
    "configure_integration": ADMIN_ROLES,
    "test_integration_connection": ADMIN_ROLES,
    "sync_integration_evidence": ADMIN_ROLES,
    "save_to_knowledge_base": WRITE_ROLES,
}


def _dispatch(db: Session, actor: models.User, name: str, tool_input: dict):
    org_id = actor.organization_id

    required_roles = _TOOL_ROLE_REQUIREMENTS.get(name)
    if required_roles is not None:
        require_role(actor, required_roles)

    if name == "list_frameworks":
        return frameworks_service.list_frameworks(db)
    if name == "get_framework_score":
        return frameworks_service.get_framework_score(
            db, uuid.UUID(tool_input["framework_id"]), org_id
        )
    if name == "list_controls_with_status":
        return frameworks_service.list_controls_with_status(
            db, uuid.UUID(tool_input["framework_id"]), org_id
        )
    if name == "list_gaps":
        return gaps_service.list_gaps(db, org_id, tool_input.get("status"))
    if name == "update_gap_status":
        return gaps_service.update_gap_status(
            db, org_id, uuid.UUID(tool_input["gap_id"]), tool_input["new_status"]
        )
    if name == "submit_evidence":
        return record_evidence(
            db,
            organization_id=org_id,
            evidence_type="document",
            control_hints=[tool_input["control_id"]],
            extracted_facts={"status": tool_input["status"], "notes": tool_input["notes"]},
        )
    if name == "propose_action":
        return actions_service.propose_action(db, org_id, uuid.UUID(tool_input["gap_id"]))
    if name == "approve_action":
        return actions_service.approve_action(
            db, org_id, uuid.UUID(tool_input["action_id"]), actor.id
        )
    if name == "reject_action":
        return actions_service.reject_action(
            db, org_id, uuid.UUID(tool_input["action_id"]), actor.id
        )
    if name == "list_integration_types":
        return integrations_service.list_types()
    if name == "get_integration_status":
        return integrations_service.get_status(db, org_id, tool_input["integration_type"])
    if name == "configure_integration":
        return integrations_service.update_connection_config(
            db, org_id, tool_input["integration_type"], tool_input["config"]
        )
    if name == "test_integration_connection":
        return integrations_service.test_connection(db, org_id, tool_input["integration_type"])
    if name == "sync_integration_evidence":
        return integrations_service.sync_evidence(
            db, org_id, tool_input["integration_type"], uuid.UUID(tool_input["control_id"])
        )
    if name == "search_knowledge_base":
        return kb_service.search(db, org_id, tool_input["query"], tool_input.get("top_k", 5))
    if name == "save_to_knowledge_base":
        return kb_service.ingest_document(
            db,
            org_id,
            title=tool_input["title"],
            content=tool_input["content"],
            source_type="chat",
        )

    raise ValidationError(f"Unknown tool '{name}'")


def _run_tool(db: Session, actor: models.User, name: str, tool_input: dict) -> tuple[str, bool]:
    try:
        result = _dispatch(db, actor, name, tool_input)
        return json.dumps(to_jsonable(result)), False
    except (NotFoundError, ValidationError, ForbiddenError) as e:
        return str(e), True
    except Exception as e:  # vendor/integration errors, etc.
        return f"Unexpected error: {e}", True


def _load_history(db: Session, session_id: uuid.UUID) -> list[models.ChatMessage]:
    return (
        db.query(models.ChatMessage)
        .filter_by(session_id=session_id)
        .order_by(models.ChatMessage.created_at)
        .all()
    )


def _history_to_anthropic_messages(history: list[models.ChatMessage]) -> list[dict]:
    """Reconstruct the Anthropic messages list (including tool_use/tool_result
    blocks) from persisted ChatMessage rows, so a new run_chat_turn call
    continues the conversation instead of starting blind each time."""
    messages: list[dict] = []
    i = 0
    while i < len(history):
        m = history[i]
        if m.role == "user":
            messages.append({"role": "user", "content": m.content})
            i += 1
        elif m.role == "assistant":
            tool_uses = (m.tool_calls or {}).get("tool_uses", [])
            content_blocks = []
            if m.content:
                content_blocks.append({"type": "text", "text": m.content})
            for t in tool_uses:
                content_blocks.append(
                    {"type": "tool_use", "id": t["id"], "name": t["name"], "input": t["input"]}
                )
            messages.append({"role": "assistant", "content": content_blocks or m.content})
            i += 1
            if tool_uses:
                tool_results = []
                for _ in tool_uses:
                    tm = history[i]
                    tc = tm.tool_calls or {}
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tc.get("tool_use_id"),
                            "content": tm.content,
                            "is_error": tc.get("is_error", False),
                        }
                    )
                    i += 1
                messages.append({"role": "user", "content": tool_results})
        else:
            i += 1  # "tool" rows are consumed above; shouldn't appear standalone
    return messages


def _save_message(db: Session, session_id: uuid.UUID, role: str, content: str, tool_calls: dict | None = None):
    msg = models.ChatMessage(
        session_id=session_id, role=role, content=content, tool_calls=tool_calls or {}
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def run_chat_turn(
    db: Session, session_id: uuid.UUID, user_message: str, current_user: models.User
) -> models.ChatMessage:
    client = _get_client()  # raises ChatNotConfigured before we touch the DB if unset

    anthropic_messages = _history_to_anthropic_messages(_load_history(db, session_id))
    anthropic_messages.append({"role": "user", "content": user_message})
    _save_message(db, session_id, "user", user_message)

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=anthropic_messages,
        )

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b.text for b in response.content if b.type == "text"]

        if not tool_uses:
            final_text = "\n".join(text_blocks).strip()
            return _save_message(db, session_id, "assistant", final_text)

        anthropic_messages.append({"role": "assistant", "content": response.content})
        _save_message(
            db,
            session_id,
            "assistant",
            "\n".join(text_blocks).strip(),
            tool_calls={"tool_uses": [{"id": t.id, "name": t.name, "input": t.input} for t in tool_uses]},
        )

        tool_results = []
        for t in tool_uses:
            result_text, is_error = _run_tool(db, current_user, t.name, t.input)
            _save_message(
                db,
                session_id,
                "tool",
                result_text,
                tool_calls={"tool_use_id": t.id, "name": t.name, "is_error": is_error},
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": t.id,
                    "content": result_text,
                    "is_error": is_error,
                }
            )

        anthropic_messages.append({"role": "user", "content": tool_results})
