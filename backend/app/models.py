import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

EMBEDDING_DIM = 1024  # Voyage AI voyage-3 output dimension


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String, nullable=False)
    deployment_mode: Mapped[str] = mapped_column(
        Enum("on_prem", "cloud", name="deployment_mode"), default="cloud"
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    users: Mapped[list["User"]] = relationship(back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    role: Mapped[str] = mapped_column(
        Enum("admin", "analyst", "owner", "viewer", name="user_role"), default="viewer"
    )

    organization: Mapped["Organization"] = relationship(back_populates="users")


class Framework(Base):
    __tablename__ = "frameworks"
    __table_args__ = (UniqueConstraint("name", "version"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    source_doc_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("draft", "approved", "superseded", name="framework_status"), default="draft"
    )

    requirements: Mapped[list["Requirement"]] = relationship(back_populates="framework")


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[uuid.UUID] = uuid_pk()
    framework_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("frameworks.id"))
    parent_requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requirements.id"), nullable=True
    )
    ref_code: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    framework: Mapped["Framework"] = relationship(back_populates="requirements")
    controls: Mapped[list["Control"]] = relationship(back_populates="requirement")


class Control(Base):
    __tablename__ = "controls"

    id: Mapped[uuid.UUID] = uuid_pk()
    requirement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("requirements.id"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    testing_procedure: Mapped[str | None] = mapped_column(Text, nullable=True)
    applicability_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    requirement: Mapped["Requirement"] = relationship(back_populates="controls")


class IntegrationConnection(Base):
    __tablename__ = "integration_connections"
    __table_args__ = (UniqueConstraint("organization_id", "integration_type"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    # Specific vendor, e.g. "m365" | "nessus" | "palo_alto" | "burp" — drives
    # which IntegrationDefinition in app/integrations/registry.py applies.
    integration_type: Mapped[str] = mapped_column(String, nullable=False)
    # Broad category used for Action routing in app/adapters.py.
    adapter_type: Mapped[str] = mapped_column(
        Enum("ad", "edr", "m365", "vuln_scanner", "cloud", "itsm", name="adapter_type")
    )
    # Fernet-encrypted JSON blob (see app/crypto.py) — never stored plaintext.
    config_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("active", "error", "disabled", name="connection_status"), default="active"
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("integration_connections.id"), nullable=True
    )
    control_hints: Mapped[list[str]] = mapped_column(JSON, default=list)
    raw_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(server_default=func.now())
    evidence_type: Mapped[str] = mapped_column(
        Enum("config", "log", "screenshot", "api_response", "document", name="evidence_type")
    )
    checksum: Mapped[str | None] = mapped_column(String, nullable=True)
    extracted_facts: Mapped[dict] = mapped_column(JSON, default=dict)

    findings: Mapped[list["Finding"]] = relationship(back_populates="evidence")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = uuid_pk()
    control_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("controls.id"))
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence.id"))
    status: Mapped[str] = mapped_column(
        Enum("met", "partial", "not_met", "not_applicable", name="finding_status")
    )
    confidence: Mapped[float] = mapped_column(default=0.0)
    ai_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("findings.id"), nullable=True
    )

    evidence: Mapped["Evidence"] = relationship(back_populates="findings")


class ControlScore(Base):
    __tablename__ = "control_scores"
    __table_args__ = (UniqueConstraint("control_id", "organization_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    control_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("controls.id"))
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    status: Mapped[str] = mapped_column(
        Enum("met", "partial", "not_met", "not_applicable", name="control_score_status")
    )
    confidence: Mapped[float] = mapped_column(default=0.0)
    last_evaluated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Gap(Base):
    __tablename__ = "gaps"

    id: Mapped[uuid.UUID] = uuid_pk()
    control_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("controls.id"))
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    severity: Mapped[str] = mapped_column(
        Enum("critical", "high", "medium", "low", name="gap_severity")
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("open", "in_progress", "remediated", "risk_accepted", name="gap_status"),
        default="open",
    )
    linked_finding_ids: Mapped[list[str]] = mapped_column(JSON, default=list)

    actions: Mapped[list["Action"]] = relationship(back_populates="gap")


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[uuid.UUID] = uuid_pk()
    gap_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gaps.id"))
    adapter_type: Mapped[str] = mapped_column(
        Enum("ad", "edr", "m365", "vuln_scanner", "cloud", "itsm", name="action_adapter_type")
    )
    action_type: Mapped[str] = mapped_column(String, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(
        Enum(
            "proposed",
            "pending_approval",
            "approved",
            "executing",
            "completed",
            "failed",
            "rejected",
            name="action_status",
        ),
        default="proposed",
    )
    proposed_by: Mapped[str] = mapped_column(Enum("ai", "user", name="proposed_by"))
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    executed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)

    gap: Mapped["Gap"] = relationship(back_populates="actions")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    actor: Mapped[str] = mapped_column(Enum("user", "ai_agent", name="audit_actor"))
    action: Mapped[str] = mapped_column(String, nullable=False)
    target_type: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_sessions.id"))
    role: Mapped[str] = mapped_column(Enum("user", "assistant", "tool", name="chat_role"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
