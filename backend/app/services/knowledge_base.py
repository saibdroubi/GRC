import uuid

import anthropic
from sqlalchemy.orm import Session

from app import embeddings, models
from app.config import settings

REFORMAT_MODEL = "claude-sonnet-4-6"


def _reformat_with_claude(title: str, content: str) -> str:
    """Optional cleanup pass: turn raw/messy input into clearly structured
    text before it's embedded and stored. Best-effort -- if Claude isn't
    configured or the call fails, store the content as-is rather than block
    ingestion on an enhancement step."""
    if not settings.anthropic_api_key:
        return content
    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=REFORMAT_MODEL,
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Clean up and clearly structure the following note for storage in a "
                        "security/compliance knowledge base. Preserve every fact; do not add "
                        "anything not present in the source. Title: "
                        f"{title}\n\n{content}"
                    ),
                }
            ],
        )
        return response.content[0].text
    except Exception:
        return content


def ingest_document(
    db: Session,
    organization_id: uuid.UUID,
    title: str,
    content: str,
    reformat: bool = False,
    source_type: str = "document",
    source_ref: str | None = None,
    metadata: dict | None = None,
) -> models.KnowledgeBaseEntry:
    final_content = _reformat_with_claude(title, content) if reformat else content
    embedding = embeddings.embed_text(final_content)

    entry = models.KnowledgeBaseEntry(
        organization_id=organization_id,
        source_type=source_type,
        source_ref=source_ref,
        title=title,
        content=final_content,
        embedding=embedding,
        metadata_=metadata or {},
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def ingest_from_evidence(db: Session, evidence: models.Evidence) -> None:
    """Deterministic, no-LLM-call distillation of a piece of evidence into a
    knowledge base entry -- runs on every evidence submission/integration
    sync so the knowledge base grows automatically, with no dependency on
    any API key being configured."""
    facts = evidence.extracted_facts or {}
    status = facts.get("status", "unknown")
    notes = facts.get("notes", "")
    source = facts.get("source", evidence.evidence_type)

    control_refs = ", ".join(evidence.control_hints) if evidence.control_hints else "no linked control"
    title = f"Evidence ({source}) — status: {status}"
    content = (
        f"Collected at {evidence.collected_at} via {source}.\n"
        f"Linked control(s): {control_refs}.\n"
        f"Status: {status}.\n"
        f"Notes: {notes}"
    )

    entry = models.KnowledgeBaseEntry(
        organization_id=evidence.organization_id,
        source_type="integration_sync" if evidence.connection_id else "evidence",
        source_ref=str(evidence.id),
        title=title,
        content=content,
        embedding=embeddings.embed_text(content),
        metadata_={"evidence_id": str(evidence.id), "control_hints": evidence.control_hints},
    )
    db.add(entry)
    db.flush()


def search(db: Session, organization_id: uuid.UUID, query: str, top_k: int = 5) -> list[models.KnowledgeBaseEntry]:
    query_embedding = embeddings.embed_text(query)

    base_query = db.query(models.KnowledgeBaseEntry).filter_by(organization_id=organization_id)

    if query_embedding is not None:
        return (
            base_query.filter(models.KnowledgeBaseEntry.embedding.isnot(None))
            .order_by(models.KnowledgeBaseEntry.embedding.cosine_distance(query_embedding))
            .limit(top_k)
            .all()
        )

    like = f"%{query}%"
    return (
        base_query.filter(
            models.KnowledgeBaseEntry.content.ilike(like) | models.KnowledgeBaseEntry.title.ilike(like)
        )
        .order_by(models.KnowledgeBaseEntry.created_at.desc())
        .limit(top_k)
        .all()
    )
