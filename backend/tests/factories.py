"""Plain helper functions for building test fixtures -- no factory_boy needed
at this scope, just thin wrappers that remove boilerplate from test bodies."""

import uuid

from sqlalchemy.orm import Session

from app import auth, models


def make_org(db: Session, name: str = "Test Org") -> models.Organization:
    org = models.Organization(name=name, deployment_mode="cloud")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def make_user(
    db: Session,
    org: models.Organization,
    email: str | None = None,
    password: str = "test-password-123",
    role: str = "admin",
    name: str = "Test User",
) -> models.User:
    if email is None:
        email = f"{uuid.uuid4().hex}@example.com"
    user = models.User(
        organization_id=org.id,
        name=name,
        email=email,
        role=role,
        password_hash=auth.hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(client, email: str, password: str) -> None:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text


def make_framework(db: Session, name: str = "Test Framework", version: str = "1.0") -> models.Framework:
    framework = models.Framework(
        name=name,
        version=version,
        status="approved",
        source_doc_ref="test-fixture",
    )
    db.add(framework)
    db.commit()
    db.refresh(framework)
    return framework


def make_requirement(
    db: Session, framework: models.Framework, ref_code: str = "1.1", title: str = "Test Requirement"
) -> models.Requirement:
    requirement = models.Requirement(
        framework_id=framework.id,
        ref_code=ref_code,
        title=title,
        description="Test requirement description",
    )
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return requirement


def make_control(db: Session, requirement: models.Requirement, description: str = "Test control") -> models.Control:
    control = models.Control(
        requirement_id=requirement.id,
        description=description,
        testing_procedure="Test procedure",
    )
    db.add(control)
    db.commit()
    db.refresh(control)
    return control


def make_gap(
    db: Session,
    control: models.Control,
    org: models.Organization,
    severity: str = "high",
    status: str = "open",
) -> models.Gap:
    gap = models.Gap(
        control_id=control.id,
        organization_id=org.id,
        severity=severity,
        description="Test gap",
        recommended_action="Do the thing",
        status=status,
    )
    db.add(gap)
    db.commit()
    db.refresh(gap)
    return gap


def make_org_with_gap(db: Session, status: str = "open"):
    """Convenience combinator: builds an org + framework + requirement +
    control + gap in one call for tests that just need "an org with an
    actionable gap" and don't care about the framework details."""
    org = make_org(db)
    framework = make_framework(db)
    requirement = make_requirement(db, framework)
    control = make_control(db, requirement)
    gap = make_gap(db, control, org, status=status)
    return org, control, gap
