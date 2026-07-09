"""
PBJ Reporting Engine — CMS Payroll-Based Journal Compliance

Sprint: VCAI-TIER3-SPRINT-2026-07-07
Purpose: Automated CMS-compliant staffing reports for nursing homes.

PBJ Requirements (Federal):
- Daily staffing hours by credential type (RN, LPN, CNA, GNA)
- Staff-to-resident ratios
- Weekend/weekday breakdown
- Contract vs. W-2 employee designation
- Submitted to CMS quarterly

Format: CSV or XML per CMS specifications
"""

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import PBJReportExport


@dataclass
class PBJRecord:
    """Single PBJ staffing record."""
    facility_cms_id: str
    work_date: date
    credential_type: str
    hours_worked: float
    employee_type: str  # CONTRACT or W2


class PBJReportingEngine:
    """
    CMS PBJ reporting engine.
    
    Main entry points:
    - generate_pbj_report(facility_id, start_date, end_date)
    - auto_export_monthly_reports()
    """
    
    def __init__(self, db: Optional[AsyncSession] = None):
        """Initialize with optional database session."""
        self.db = db
        self._should_close_db = db is None
    
    async def __aenter__(self):
        """Async context manager entry."""
        if self.db is None:
            self.db = AsyncSessionLocal()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._should_close_db and self.db:
            await self.db.close()
    
    async def generate_pbj_report(
        self,
        facility_id: UUID,
        start_date: date,
        end_date: date,
        cms_provider_id: str
    ) -> UUID:
        """
        Generate PBJ report for facility.
        
        Args:
            facility_id: Facility UUID
            start_date: Report period start
            end_date: Report period end
            cms_provider_id: CMS provider number (6-digit)
        
        Returns:
            PBJ export record ID
        """
        if not settings.PBJ_REPORTING_ENABLED:
            raise Exception("PBJ reporting is disabled")
        
        # Fetch shift data for period
        records = await self._fetch_shift_records(facility_id, start_date, end_date)
        
        # Generate CSV export
        csv_content = self._generate_pbj_csv(records, cms_provider_id)
        
        # Save export file to disk
        import os
        from pathlib import Path
        
        # Create exports directory if it doesn't exist
        exports_dir = Path("exports/pbj")
        exports_dir.mkdir(parents=True, exist_ok=True)
        
        file_name = f"pbj_{facility_id}_{start_date}_{end_date}.csv"
        file_path = str(exports_dir / file_name)
        
        # Write CSV content to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(csv_content)
        
        # Create export record
        export_record = PBJReportExport(
            facility_id=facility_id,
            report_period_start=str(start_date),
            report_period_end=str(end_date),
            cms_provider_id=cms_provider_id,
            total_hours_worked=Decimal(str(sum(r.hours_worked for r in records))),
            total_shifts_reported=str(len(records)),
            export_format=settings.PBJ_EXPORT_FORMAT,
            export_file_path=file_path,
            export_status="COMPLETED"
        )
        self.db.add(export_record)
        await self.db.commit()
        await self.db.refresh(export_record)
        
        print(f"[PBJ] Generated report for facility {facility_id}: {len(records)} records, {sum(r.hours_worked for r in records):.1f} hours")
        
        return export_record.id
    
    async def _fetch_shift_records(
        self,
        facility_id: UUID,
        start_date: date,
        end_date: date
    ) -> List[PBJRecord]:
        """Fetch completed shifts for period."""
        from app.models import ClinicalPlacementLedger, OfferCareJobOffer, MarylandProvider
        from sqlalchemy import select, and_
        from datetime import datetime, timezone
        
        # Query completed placements for facility in date range
        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        
        stmt = (
            select(ClinicalPlacementLedger, OfferCareJobOffer, MarylandProvider)
            .join(OfferCareJobOffer, ClinicalPlacementLedger.offer_id == OfferCareJobOffer.offer_id)
            .join(MarylandProvider, ClinicalPlacementLedger.provider_id == MarylandProvider.provider_id)
            .where(
                and_(
                    OfferCareJobOffer.facility_id == facility_id,
                    ClinicalPlacementLedger.outbound_payload_timestamp >= start_dt,
                    ClinicalPlacementLedger.outbound_payload_timestamp <= end_dt
                )
            )
        )
        
        result = await self.db.execute(stmt)
        rows = result.all()
        
        records = []
        for placement, offer, provider in rows:
            # Calculate hours worked
            hours_worked = 8.0  # Default
            if offer.shift_start and offer.shift_end:
                duration = offer.shift_end - offer.shift_start
                hours_worked = duration.total_seconds() / 3600.0
            
            # Map credential type to PBJ job code
            job_code = "01110"  # Default: Registered Nurse
            if provider.credential_type == "CNA":
                job_code = "01400"  # Nursing Aide
            elif provider.credential_type == "LPN":
                job_code = "01120"  # Licensed Practical Nurse
            elif provider.credential_type == "GNA":
                job_code = "01410"  # Geriatric Nursing Aide
            
            records.append(PBJRecord(
                work_date=placement.outbound_payload_timestamp.date() if placement.outbound_payload_timestamp else start_date,
                job_code=job_code,
                hours_worked=hours_worked,
                employee_name=f"{provider.first_name} {provider.last_name}",
                employee_id=str(provider.provider_id),
                pay_type="HOURLY"
            ))
        
        # If no real data found, return mock for development/testing
        if not records and settings.PBJ_REPORTING_MOCK_WHEN_EMPTY:
            return self._generate_mock_pbj_records(start_date, end_date)
        
        return records
    
    def _generate_mock_pbj_records(self, start_date: date, end_date: date) -> List[PBJRecord]:
        """Generate mock PBJ records for testing."""
        records = []
        current_date = start_date
        
        while current_date <= end_date:
            # 3 CNAs per day
            for _ in range(3):
                records.append(PBJRecord(
                    facility_cms_id="123456",
                    work_date=current_date,
                    credential_type="CNA",
                    hours_worked=8.0,
                    employee_type="CONTRACT"
                ))
            
            # 1 LPN per day
            records.append(PBJRecord(
                facility_cms_id="123456",
                work_date=current_date,
                credential_type="LPN",
                hours_worked=8.0,
                employee_type="CONTRACT"
            ))
            
            current_date += timedelta(days=1)
        
        return records
    
    def _generate_pbj_csv(self, records: List[PBJRecord], cms_provider_id: str) -> str:
        """
        Generate CMS-compliant PBJ CSV.
        
        CSV Format (simplified):
        CMS_Provider_ID,Work_Date,Job_Title,Hours_Worked,Employee_Type
        """
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "CMS_Provider_ID",
            "Work_Date",
            "Job_Title",
            "Hours_Worked",
            "Employee_Type"
        ])
        
        # Data rows
        for record in records:
            writer.writerow([
                cms_provider_id,
                record.work_date.strftime("%Y-%m-%d"),
                record.credential_type,
                f"{record.hours_worked:.2f}",
                record.employee_type
            ])
        
        return output.getvalue()


# Convenience function
async def export_pbj_report(
    facility_id: UUID,
    start_date: date,
    end_date: date,
    cms_provider_id: str
) -> UUID:
    """Export PBJ report (convenience wrapper)."""
    async with PBJReportingEngine() as engine:
        return await engine.generate_pbj_report(
            facility_id, start_date, end_date, cms_provider_id
        )
