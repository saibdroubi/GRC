"""Real framework ingestion: PDF/text upload -> Claude extraction -> a draft
Framework an admin reviews and approves.

This module never contains or fabricates standard text. It only extracts
structured Requirement/Control records from whatever document the customer
uploads (their own licensed/downloaded copy of the standard) -- the prompt
explicitly forbids inferring or adding anything not present in the source
text, which is the whole point: app/seed.py's hand-written sample exists
only for development and must be replaced by a real ingested document
before any customer-facing compliance scoring happens against it.
"""

import io
import json
import uuid

import anthropic
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.errors import NotFoundError, ValidationError

MODEL = "claude-sonnet-4-6"
MAX_CHARS_PER_CHUNK = 12000


class FrameworkIngestionNotConfigured(Exception):
    pass


def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def chunk_text(text: str, max_chars: int = MAX_CHARS_PER_CHUNK) -> list[str]:
    paragraphs = text.split("\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        if current_len + len(para) > max_chars and current:
            chunks.append("\n".join(current))
            current, current_len = [], 0
        current.append(para)
        current_len += len(para) + 1

    if current:
        chunks.append("\n".join(current))
    return chunks


def _get_client() -> anthropic.Anthropic:
    if not settings.anthropic_api_key:
        raise FrameworkIngestionNotConfigured(
            "Framework ingestion needs ANTHROPIC_API_KEY set in backend/.env."
        )
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def extract_requirements_with_claude(chunk: str) -> list[dict]:
    """Ask Claude to extract ONLY requirements/controls explicitly present in
    this chunk of text -- never to infer, summarize generically, or add
    anything not literally stated."""
    prompt = f"""You are extracting structured data from an official compliance framework document. \
Extract ONLY requirements that are explicitly and literally present in the text below. \
Do not infer, summarize generically, add commentary, or invent anything not in the text. \
If this chunk contains no clearly identifiable requirements (e.g. it's a cover page, table of \
contents, glossary, or appendix), return an empty list.

For each requirement found, extract its reference code exactly as written (e.g. "3.2.1"), its \
title, its description (verbatim or near-verbatim from the text), and any sub-controls/testing \
procedures explicitly listed under it.

Text:
---
{chunk}
---

Respond with ONLY a JSON array, no other text:
[{{"ref_code": "...", "title": "...", "description": "...", "controls": [{{"description": "...", "testing_procedure": "..."}}]}}]"""

    client = _get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return []


def ingest_framework_document(
    db: Session,
    name: str,
    version: str,
    file_bytes: bytes,
    is_pdf: bool,
) -> models.Framework:
    text = extract_text_from_pdf(file_bytes) if is_pdf else file_bytes.decode("utf-8", errors="replace")
    chunks = chunk_text(text)

    framework = models.Framework(
        name=name,
        version=version,
        status="draft",
        source_doc_ref=f"Ingested from uploaded document ({len(chunks)} chunk(s) processed)",
    )
    db.add(framework)
    db.flush()

    seen_ref_codes: set[str] = set()
    requirement_count = 0
    control_count = 0

    for chunk in chunks:
        extracted = extract_requirements_with_claude(chunk)
        for req in extracted:
            ref_code = req.get("ref_code")
            if not ref_code or ref_code in seen_ref_codes:
                continue
            seen_ref_codes.add(ref_code)

            requirement = models.Requirement(
                framework_id=framework.id,
                ref_code=ref_code,
                title=req.get("title", ""),
                description=req.get("description", ""),
            )
            db.add(requirement)
            db.flush()
            requirement_count += 1

            for control in req.get("controls", []):
                db.add(
                    models.Control(
                        requirement_id=requirement.id,
                        description=control.get("description", ""),
                        testing_procedure=control.get("testing_procedure"),
                    )
                )
                control_count += 1

    db.commit()
    db.refresh(framework)
    return framework, requirement_count, control_count


def approve_framework(db: Session, framework_id: uuid.UUID) -> models.Framework:
    framework = db.get(models.Framework, framework_id)
    if framework is None:
        raise NotFoundError("Framework not found")
    if framework.status != "draft":
        raise ValidationError("Only a draft framework can be approved")
    framework.status = "approved"
    db.commit()
    db.refresh(framework)
    return framework
