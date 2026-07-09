"""
EHR Integration Gateway — MatrixCare/PointClickCare Deep Hooks

Sprint: VCAI-TIER3-SPRINT-2026-07-07
Purpose: Bidirectional shift sync with facility EHR systems for deep lock-in.

Supported EHR Systems:
- MatrixCare (SNF/ALF market leader)
- PointClickCare (Long-term care leader)
- Generic REST API (for other systems)

Sync Flow:
1. EHR → VettedCare (INBOUND):
   - Facility posts shift in their EHR
   - VettedCare polls EHR API every 15 minutes
   - Auto-creates shift in VettedCare
   - Triggers wave dispatch

2. VettedCare → EHR (OUTBOUND):
   - Nurse accepts shift in VettedCare
   - VettedCare pushes confirmation to EHR
   - EHR marks shift as filled
   - Nurse details sync to EHR

Benefits:
- Zero double-entry for facilities
- Real-time shift status sync
- Deep integration = hard to leave
- Automatic nurse credentialing sync
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import EHRIntegrationConfig, EHRShiftSyncLog


@dataclass
class SyncResult:
    """Result of EHR sync operation."""
    success: bool
    shifts_synced: int
    errors: List[str]


class EHRIntegrationGateway:
    """
    EHR integration gateway for deep facility hooks.
    
    Main entry points:
    - sync_inbound_shifts(facility_id) - Pull shifts from EHR
    - sync_outbound_confirmation(shift_id) - Push confirmation to EHR
    - configure_integration(facility_id, ehr_system, credentials)
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
    
    async def sync_inbound_shifts(self, facility_id: UUID) -> SyncResult:
        """
        Sync shifts from EHR → VettedCare.
        
        Polls facility's EHR system for new open shifts.
        Auto-creates shifts in VettedCare and triggers dispatch.
        
        Args:
            facility_id: Facility UUID
        
        Returns:
            SyncResult with count of shifts synced
        """
        if not settings.EHR_INTEGRATION_ENABLED:
            return SyncResult(success=False, shifts_synced=0, errors=["EHR integration disabled"])
        
        # Get facility EHR config
        config = await self._get_ehr_config(facility_id)
        if not config or config.sync_enabled != "1":
            return SyncResult(success=False, shifts_synced=0, errors=["EHR integration not configured"])
        
        try:
            # Fetch open shifts from EHR
            ehr_shifts = await self._fetch_ehr_shifts(config)
            
            shifts_synced = 0
            errors = []
            
            for ehr_shift in ehr_shifts:
                try:
                    # Create shift in VettedCare
                    shift_id = await self._create_shift_from_ehr(facility_id, ehr_shift)
                    
                    # Log successful sync
                    await self._log_sync(
                        facility_id=facility_id,
                        ehr_system=config.ehr_system,
                        shift_id=shift_id,
                        ehr_shift_id=ehr_shift.get("id"),
                        sync_direction="INBOUND",
                        sync_status="SUCCESS",
                        shift_data=ehr_shift
                    )
                    
                    shifts_synced += 1
                    
                    # Trigger wave dispatch for new shift if enabled
                    if settings.WAVE_DISPATCH_ENABLED:
                        try:
                            from app.services.wave_match_dispatcher import WaveMatchDispatcher
                            
                            wave_dispatcher = WaveMatchDispatcher(self.db)
                            await wave_dispatcher.trigger_wave_dispatch(
                                shift_id=shift_id,
                                facility_id=facility_id,
                                auto_dispatch=True
                            )
                            print(f"[EHR] Triggered wave dispatch for shift {shift_id}")
                        except Exception as dispatch_error:
                            print(f"[EHR] Failed to trigger wave dispatch: {dispatch_error}")
                    
                except Exception as e:
                    errors.append(f"Failed to sync shift {ehr_shift.get('id')}: {str(e)}")
            
            # Update last sync time
            config.last_sync_at = datetime.utcnow()
            await self.db.commit()
            
            print(f"[EHR] Synced {shifts_synced} shifts from {config.ehr_system} for facility {facility_id}")
            
            return SyncResult(
                success=True,
                shifts_synced=shifts_synced,
                errors=errors
            )
            
        except Exception as e:
            return SyncResult(
                success=False,
                shifts_synced=0,
                errors=[str(e)]
            )
    
    async def sync_outbound_confirmation(
        self,
        shift_id: UUID,
        facility_id: UUID,
        provider_id: UUID,
        provider_details: Dict
    ) -> bool:
        """
        Sync shift confirmation from VettedCare → EHR.
        
        When nurse accepts shift, push confirmation to EHR.
        
        Args:
            shift_id: VettedCare shift UUID
            facility_id: Facility UUID
            provider_id: Provider UUID
            provider_details: Provider credentials/info
        
        Returns:
            True if sync successful
        """
        if not settings.EHR_INTEGRATION_ENABLED:
            return False
        
        config = await self._get_ehr_config(facility_id)
        if not config or config.sync_enabled != "1":
            return False
        
        try:
            # Get EHR shift ID from offer record
            from app.models import OfferCareJobOffer
            from sqlalchemy import select
            
            stmt = select(OfferCareJobOffer).where(OfferCareJobOffer.offer_id == shift_id)
            result = await self.db.execute(stmt)
            offer = result.scalar_one_or_none()
            
            ehr_shift_id = offer.ehr_external_id if offer else None
            
            # Push confirmation to EHR
            success = await self._push_confirmation_to_ehr(
                config, shift_id, provider_details
            )
            
            # Log sync
            await self._log_sync(
                facility_id=facility_id,
                ehr_system=config.ehr_system,
                shift_id=shift_id,
                ehr_shift_id=ehr_shift_id,
                sync_direction="OUTBOUND",
                sync_status="SUCCESS" if success else "FAILED",
                shift_data={"provider_id": str(provider_id)}
            )
            
            print(f"[EHR] Pushed confirmation to {config.ehr_system} for shift {shift_id}")
            
            return success
            
        except Exception as e:
            print(f"[EHR ERROR] Failed to push confirmation: {e}")
            return False
    
    async def configure_integration(
        self,
        facility_id: UUID,
        ehr_system: str,
        api_endpoint: str,
        api_key: str,
        ehr_facility_id: str
    ) -> UUID:
        """
        Configure EHR integration for facility.
        
        Args:
            facility_id: Facility UUID
            ehr_system: MATRIXCARE, POINTCLICKCARE, GENERIC
            api_endpoint: EHR API base URL
            api_key: EHR API key
            ehr_facility_id: Facility ID in EHR system
        
        Returns:
            Integration config ID
        """
        # Check if config exists
        config = await self._get_ehr_config(facility_id)
        
        if config:
            # Update existing
            config.ehr_system = ehr_system
            config.ehr_api_endpoint = api_endpoint
            config.ehr_api_key = api_key
            config.ehr_facility_id = ehr_facility_id
            config.sync_enabled = "1"
        else:
            # Create new
            config = EHRIntegrationConfig(
                facility_id=facility_id,
                ehr_system=ehr_system,
                ehr_api_endpoint=api_endpoint,
                ehr_api_key=api_key,
                ehr_facility_id=ehr_facility_id
            )
            self.db.add(config)
        
        await self.db.commit()
        await self.db.refresh(config)
        
        print(f"[EHR] Configured {ehr_system} integration for facility {facility_id}")
        
        return config.id
    
    async def _get_ehr_config(self, facility_id: UUID) -> Optional[EHRIntegrationConfig]:
        """Get EHR config for facility."""
        stmt = select(EHRIntegrationConfig).where(
            EHRIntegrationConfig.facility_id == facility_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def _fetch_ehr_shifts(self, config: EHRIntegrationConfig) -> List[Dict]:
        """
        Fetch open shifts from EHR system.
        
        Returns list of shift dictionaries from EHR.
        """
        if settings.EHR_DRY_RUN:
            # Return mock shifts
            return self._generate_mock_ehr_shifts(config)
        
        # Real EHR API integration
        if config.ehr_system == "MATRIXCARE":
            return await self._fetch_matrixcare_shifts(config)
        elif config.ehr_system == "POINTCLICKCARE":
            return await self._fetch_pointclickcare_shifts(config)
        else:
            return await self._fetch_generic_ehr_shifts(config)
    
    def _generate_mock_ehr_shifts(self, config: EHRIntegrationConfig) -> List[Dict]:
        """Generate mock EHR shifts for testing."""
        return [
            {
                "id": "EHR-SHIFT-001",
                "credential_type": "CNA",
                "shift_date": "2026-07-08",
                "start_time": "07:00",
                "end_time": "15:00",
                "hourly_rate": 28.00,
                "notes": "Floor 2 - Med/Surg"
            },
            {
                "id": "EHR-SHIFT-002",
                "credential_type": "LPN",
                "shift_date": "2026-07-08",
                "start_time": "15:00",
                "end_time": "23:00",
                "hourly_rate": 38.00,
                "notes": "Floor 3 - Skilled Nursing"
            }
        ]
    
    async def _fetch_matrixcare_shifts(self, config: EHRIntegrationConfig) -> List[Dict]:
        """Fetch shifts from MatrixCare API."""
        import httpx
        
        if not config.ehr_api_endpoint or not config.ehr_api_key:
            print("[EHR] MatrixCare credentials not configured")
            return []
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{config.ehr_api_endpoint}/api/staffing/openShifts",
                    headers={
                        "Authorization": f"Bearer {config.ehr_api_key}",
                        "Content-Type": "application/json",
                        "X-Facility-ID": config.ehr_facility_id or ""
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                return data.get("shifts", [])
                
        except Exception as e:
            print(f"[EHR] MatrixCare API error: {e}")
            return []
    
    async def _fetch_pointclickcare_shifts(self, config: EHRIntegrationConfig) -> List[Dict]:
        """Fetch shifts from PointClickCare API."""
        import httpx
        
        if not config.ehr_api_endpoint or not config.ehr_api_key:
            print("[EHR] PointClickCare credentials not configured")
            return []
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{config.ehr_api_endpoint}/scheduling/v1/openings",
                    headers={
                        "X-API-Key": config.ehr_api_key,
                        "X-Organization-ID": config.ehr_facility_id or "",
                        "Accept": "application/json"
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                return data.get("openings", [])
                
        except Exception as e:
            print(f"[EHR] PointClickCare API error: {e}")
            return []
    
    async def _fetch_generic_ehr_shifts(self, config: EHRIntegrationConfig) -> List[Dict]:
        """Fetch shifts from generic REST API."""
        import httpx
        
        if not config.ehr_api_endpoint:
            print("[EHR] Generic EHR endpoint not configured")
            return []
        
        try:
            headers = {"Accept": "application/json"}
            if config.ehr_api_key:
                headers["Authorization"] = f"Bearer {config.ehr_api_key}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{config.ehr_api_endpoint}/shifts/open",
                    headers=headers
                )
                response.raise_for_status()
                
                data = response.json()
                # Handle both array and object responses
                if isinstance(data, list):
                    return data
                return data.get("shifts", data.get("data", []))
                
        except Exception as e:
            print(f"[EHR] Generic EHR API error: {e}")
            return []
    
    async def _create_shift_from_ehr(self, facility_id: UUID, ehr_shift: Dict) -> UUID:
        """Create shift in VettedCare from EHR data."""
        from app.models import OfferCareJobOffer
        from datetime import datetime
        from uuid import uuid4
        
        # Parse EHR shift data
        shift_start = ehr_shift.get("start_time")
        shift_end = ehr_shift.get("end_time")
        
        # Convert to datetime if strings
        if isinstance(shift_start, str):
            shift_start = datetime.fromisoformat(shift_start.replace('Z', '+00:00'))
        if isinstance(shift_end, str):
            shift_end = datetime.fromisoformat(shift_end.replace('Z', '+00:00'))
        
        # Map EHR role to credential type
        role = ehr_shift.get("role", "CNA").upper()
        credential_type = "CNA"
        if "LPN" in role or "LVN" in role:
            credential_type = "LPN"
        elif "RN" in role:
            credential_type = "RN"
        elif "GNA" in role:
            credential_type = "GNA"
        
        # Create offer
        offer = OfferCareJobOffer(
            offer_id=uuid4(),
            facility_id=facility_id,
            credential_type=credential_type,
            shift_start=shift_start,
            shift_end=shift_end,
            hourly_pay_rate=ehr_shift.get("hourly_rate", 30.0),
            shift_role=ehr_shift.get("role", "CNA"),
            ehr_external_id=ehr_shift.get("id"),
            offer_status="OPEN"
        )
        
        self.db.add(offer)
        await self.db.commit()
        await self.db.refresh(offer)
        
        return offer.offer_id
    
    async def _push_confirmation_to_ehr(
        self,
        config: EHRIntegrationConfig,
        shift_id: UUID,
        provider_details: Dict
    ) -> bool:
        """Push shift confirmation to EHR."""
        if settings.EHR_DRY_RUN:
            print(f"[EHR] DRY RUN: Would push confirmation for shift {shift_id}")
            return True
        
        import httpx
        
        if not config.ehr_api_endpoint or not config.ehr_api_key:
            print("[EHR] Cannot push confirmation - credentials not configured")
            return False
        
        try:
            confirmation_data = {
                "shift_id": str(shift_id),
                "provider_name": f"{provider_details.get('first_name')} {provider_details.get('last_name')}",
                "provider_license": provider_details.get("license_number"),
                "provider_phone": provider_details.get("phone"),
                "status": "CONFIRMED"
            }
            
            endpoint = f"{config.ehr_api_endpoint}/shifts/{shift_id}/confirm"
            if config.ehr_system == "MATRIXCARE":
                endpoint = f"{config.ehr_api_endpoint}/api/staffing/confirmations"
            elif config.ehr_system == "POINTCLICKCARE":
                endpoint = f"{config.ehr_api_endpoint}/scheduling/v1/assignments"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    endpoint,
                    json=confirmation_data,
                    headers={
                        "Authorization": f"Bearer {config.ehr_api_key}",
                        "Content-Type": "application/json"
                    }
                )
                response.raise_for_status()
                
                print(f"[EHR] Successfully pushed confirmation to {config.ehr_system}")
                return True
                
        except Exception as e:
            print(f"[EHR] Failed to push confirmation: {e}")
            return False
    
    async def _log_sync(
        self,
        facility_id: UUID,
        ehr_system: str,
        shift_id: Optional[UUID],
        ehr_shift_id: Optional[str],
        sync_direction: str,
        sync_status: str,
        shift_data: Dict
    ):
        """Log sync operation."""
        log = EHRShiftSyncLog(
            facility_id=facility_id,
            ehr_system=ehr_system,
            shift_id=shift_id,
            ehr_shift_id=ehr_shift_id,
            sync_direction=sync_direction,
            sync_status=sync_status,
            shift_data=json.dumps(shift_data)
        )
        self.db.add(log)
        await self.db.commit()


# Convenience functions
async def sync_facility_shifts(facility_id: UUID) -> SyncResult:
    """Sync shifts for facility (convenience wrapper)."""
    async with EHRIntegrationGateway() as gateway:
        return await gateway.sync_inbound_shifts(facility_id)
