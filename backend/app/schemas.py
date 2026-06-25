import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FrameworkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    version: str
    status: str


class RequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ref_code: str
    title: str
    description: str


class ControlOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requirement_id: uuid.UUID
    description: str
    testing_procedure: str | None = None


class EvidenceIn(BaseModel):
    organization_id: uuid.UUID
    evidence_type: str
    control_hints: list[str] = []
    extracted_facts: dict = {}
    raw_ref: str | None = None


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    evidence_type: str
    collected_at: datetime
    control_hints: list[str]
    extracted_facts: dict


class GapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    control_id: uuid.UUID
    organization_id: uuid.UUID
    severity: str
    description: str
    recommended_action: str | None = None
    status: str


class ControlScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    control_id: uuid.UUID
    organization_id: uuid.UUID
    status: str
    confidence: float
    last_evaluated_at: datetime


class ControlWithStatusOut(BaseModel):
    id: uuid.UUID
    ref_code: str
    requirement_title: str
    description: str
    status: str
    confidence: float
    gap_id: uuid.UUID | None = None
    gap_severity: str | None = None
    gap_status: str | None = None
    gap_description: str | None = None


class ActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    gap_id: uuid.UUID
    adapter_type: str
    action_type: str
    parameters: dict
    status: str
    proposed_by: str
    approved_by_user_id: uuid.UUID | None = None
    executed_at: datetime | None = None
    result: dict


class FrameworkScoreOut(BaseModel):
    framework_id: uuid.UUID
    framework_name: str
    framework_version: str
    total_controls: int
    met: int
    partial: int
    not_met: int
    not_applicable: int
    unscored: int
    score_pct: float


class ChatSessionIn(BaseModel):
    organization_id: uuid.UUID
    user_id: uuid.UUID


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime


class ChatMessageIn(BaseModel):
    content: str


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    tool_calls: dict
    created_at: datetime
