"""Seed a development organization plus a small, illustrative subset of
PCI DSS-style requirements/controls.

IMPORTANT: the requirement text below is a hand-written sample for
development/testing only. It is NOT the verified, current PCI DSS standard
text and must be replaced by the real Framework Library ingestion pipeline
(see docs/ARCHITECTURE.md §2.1) before any real compliance scoring is done
against it.
"""

from app.database import SessionLocal
from app import models


def run() -> None:
    db = SessionLocal()
    try:
        org = models.Organization(name="Dev Org", deployment_mode="cloud")
        db.add(org)

        framework = models.Framework(
            name="PCI DSS",
            version="4.0.1-sample",
            status="draft",
            source_doc_ref="manual sample, not verified against official text",
        )
        db.add(framework)
        db.flush()

        sample_requirements = [
            (
                "8.3",
                "Strong Authentication",
                "Strong authentication for users and administrators is established "
                "and managed.",
                [
                    (
                        "Multi-factor authentication is implemented for all access into "
                        "the cardholder data environment.",
                        "Review MFA configuration for all CDE access paths.",
                    ),
                ],
            ),
            (
                "11.3",
                "Vulnerability Scanning",
                "External and internal vulnerabilities are regularly identified, "
                "prioritized, and addressed.",
                [
                    (
                        "Internal vulnerability scans are performed at least quarterly "
                        "and after significant changes.",
                        "Review most recent internal scan reports and remediation evidence.",
                    ),
                ],
            ),
            (
                "10.2",
                "Audit Logging",
                "Audit logs are implemented to support the detection of anomalies "
                "and suspicious activity.",
                [
                    (
                        "Audit logs are enabled for all system components and "
                        "cardholder data access.",
                        "Review logging configuration on in-scope systems.",
                    ),
                ],
            ),
        ]

        for ref_code, title, description, controls in sample_requirements:
            req = models.Requirement(
                framework_id=framework.id,
                ref_code=ref_code,
                title=title,
                description=description,
            )
            db.add(req)
            db.flush()
            for control_desc, testing_procedure in controls:
                db.add(
                    models.Control(
                        requirement_id=req.id,
                        description=control_desc,
                        testing_procedure=testing_procedure,
                    )
                )

        db.commit()
        print(f"Seeded organization {org.id} and framework {framework.id} ({framework.name} {framework.version})")
    finally:
        db.close()


if __name__ == "__main__":
    run()
