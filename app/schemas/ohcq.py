from pydantic import BaseModel, Field
from typing import Dict, Any
from datetime import datetime

class OHCQAuditExportRequest(BaseModel):
    facility_id: str = Field(..., description="Target facility UUID for the OHCQ inspection review")
    start_date: str = Field(..., description="Historical timeline filter window start (YYYY-MM-DD)")
    end_date: str = Field(..., description="Historical timeline filter window end (YYYY-MM-DD)")

class OHCQAuditResponse(BaseModel):
    ledger_id: str = Field(..., description="Unique generated tracking ID for this audit ledger footprint")
    merkle_root_hash: str = Field(..., description="The SHA-256 Merkle-tree root hash chaining this historical state record")
    cryptographic_signature: str = Field(..., description="Secure system sign-off verifying data integrity")
    exported_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp recording when data left the secure boundary")
    metadata_summary: Dict[str, Any] = Field(..., description="Calculated statistics regarding matching records extracted")
