"""
VettedCare.ai VMS (Vendor Management System) Integration

Unified shift ingest pipeline with concurrency guards and stress testing.
Supports ShiftWise, Fieldglass, and custom facility VMS feeds.
"""

from app.services.vms.ingest_pipeline import VMSIngestPipeline, VMSPayload, VMSIngestResult

__all__ = ["VMSIngestPipeline", "VMSPayload", "VMSIngestResult"]
