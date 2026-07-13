"""One-click Maryland COMAR audit packet generator."""

from __future__ import annotations

import io
import json
import zipfile
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import LicenseVerificationLog, MarylandProvider
from app.services.compliance_monitor import build_provider_compliance_status


def build_provider_audit_packet(db: Session, provider_id: UUID) -> bytes:
    provider = db.query(MarylandProvider).filter(MarylandProvider.provider_id == provider_id).first()
    if provider is None:
        raise ValueError("provider_not_found")

    status = build_provider_compliance_status(db, provider_id)
    history = (
        db.query(LicenseVerificationLog)
        .filter(LicenseVerificationLog.provider_id == provider_id)
        .order_by(LicenseVerificationLog.created_at.asc())
        .all()
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("compliance_status.json", json.dumps(status, indent=2))
        archive.writestr(
            "verification_history.json",
            json.dumps(
                [
                    {
                        "event_type": row.event_type,
                        "check_result": row.check_result,
                        "notes": row.notes,
                        "reviewer": row.reviewer,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    }
                    for row in history
                ],
                indent=2,
            ),
        )
        archive.writestr(
            "README.txt",
            "\n".join(
                [
                    "VettedMe Maryland COMAR Audit Packet",
                    f"Worker: {provider.full_name}",
                    f"License: {provider.md_license_number}",
                    f"Dispatch status: {provider.dispatch_status}",
                    "",
                    "Includes automated MBON, OIG LEIE, and Maryland judiciary screening history.",
                ]
            ),
        )
    return buffer.getvalue()
