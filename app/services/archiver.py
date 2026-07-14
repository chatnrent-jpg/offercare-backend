import json
import os
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.models import HealthcareCredential

logger = logging.getLogger("ComplianceArchiver")

class LegalComplianceArchiver:
    def __init__(self, db: Session):
        self.db = db
        self.archive_directory = "var/compliance_archive_cold"
        os.makedirs(self.archive_directory, exist_ok=True)

    def execute_cold_storage_rotation(self) -> dict:
        """
        Locates old verification rows, serializes them into immutable JSON arrays,
        and saves them onto the system file layers to satisfy 7-year records retention laws.
        """
        # Define historical timeline threshold (e.g., look for checks over 7 years old)
        seven_years_ago = datetime.now(timezone.utc) - timedelta(days=7 * 365)
        
        # Query logs matching archiving criteria
        historical_records = self.db.query(HealthcareCredential).filter(
            HealthcareCredential.last_verified_at <= seven_years_ago
        ).all()
        
        if not historical_records:
            return {"archived_count": 0, "status": "NO_STALE_DATA"}

        archive_payload = []
        for record in historical_records:
            archive_payload.append({
                "record_id": record.id,
                "worker_name": record.professional_name,
                "license_identity": f"{record.license_type}-{record.license_number}",
                "final_known_status": record.status,
                "verified_timestamp": record.last_verified_at.isoformat() if record.last_verified_at else None
            })

        # Securely build target archive filename
        timestamp_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        target_file = os.path.join(self.archive_directory, f"ohcq_audit_manifest_{timestamp_slug}.json")

        with open(target_file, "w") as storage_file:
            json.dump(archive_payload, storage_file, indent=2)

        logger.info(f"Successfully archived {len(archive_payload)} rows to path: {target_file}")
        
        # In a full data lifecycle routine, you could safely remove these rows from the hot operational DB here.
        return {
            "archived_count": len(archive_payload),
            "archive_destination": target_file,
            "retention_policy_enforced": "7_YEAR_MANDATE"
        }
