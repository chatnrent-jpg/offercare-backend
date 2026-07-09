"""
Geo-Fenced Reliability Tracking Service.

Feature: High-Value Feature #2
Purpose: Track provider location 60 minutes before shift start.
         Alert if provider is still at home 15 minutes before shift.

Core Functionality:
- Monitor provider location in real-time
- Geo-fence facility location (500m radius)
- Detect "still at home" providers
- Trigger automated backup dispatch
- Update reliability scores
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.services.wave_match_dispatcher import WaveMatchDispatcher

logger = logging.getLogger(__name__)


class GeofenceReliabilityService:
    """
    Real-time location tracking for shift reliability.
    
    Monitors provider locations before shifts:
    - 60 minutes before: Start monitoring
    - 15 minutes before: Alert if still at home
    - Trigger backup dispatch if needed
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.enabled = getattr(settings, "GEOFENCE_ENABLED", True)
        self.monitoring_window_minutes = 60  # Start monitoring 60 min before
        self.alert_threshold_minutes = 15    # Alert if home at 15 min before
        self.home_radius_meters = 500        # Consider "at home" within 500m
        
    async def check_provider_location(
        self,
        provider_id: UUID,
        shift_id: UUID,
        current_lat: float,
        current_lng: float
    ) -> Dict:
        """
        Check if provider is on-time based on current location.
        
        Args:
            provider_id: Provider UUID
            shift_id: Shift UUID
            current_lat: Provider's current latitude
            current_lng: Provider's current longitude
        
        Returns:
            {
                "status": "ON_TRACK" | "AT_RISK" | "EMERGENCY",
                "minutes_until_shift": int,
                "distance_from_facility_miles": float,
                "estimated_late_minutes": float,
                "backup_dispatched": bool,
                "alert_sent": bool
            }
        """
        from app.models import OfferCareJobOffer, MarylandProvider, MarylandFacility
        from app.services.traffic_routing import TrafficRoutingService
        
        if not self.enabled:
            return {"status": "DISABLED"}
        
        try:
            # Get shift details
            stmt = select(OfferCareJobOffer, MarylandFacility).join(
                MarylandFacility, OfferCareJobOffer.facility_id == MarylandFacility.facility_id
            ).where(OfferCareJobOffer.offer_id == shift_id)
            
            result = await self.db.execute(stmt)
            row = result.first()
            
            if not row:
                logger.warning(f"[GEOFENCE] Shift {shift_id} not found")
                return {"status": "ERROR", "reason": "Shift not found"}
            
            shift, facility = row
            
            # Calculate time until shift
            now = datetime.now(timezone.utc)
            minutes_until_shift = (shift.shift_start - now).total_seconds() / 60
            
            # Only monitor within window
            if minutes_until_shift > self.monitoring_window_minutes:
                return {
                    "status": "NOT_YET_MONITORED",
                    "minutes_until_shift": round(minutes_until_shift)
                }
            
            # Get provider's home location
            stmt = select(MarylandProvider).where(MarylandProvider.provider_id == provider_id)
            result = await self.db.execute(stmt)
            provider = result.scalar_one_or_none()
            
            if not provider:
                return {"status": "ERROR", "reason": "Provider not found"}
            
            # Check if still at home
            is_at_home = self._is_at_location(
                current_lat, current_lng,
                provider.latitude, provider.longitude,
                self.home_radius_meters
            )
            
            # Calculate commute time from current location
            traffic_service = TrafficRoutingService(self.db)
            commute = await traffic_service.calculate_commute_time(
                origin_lat=current_lat,
                origin_lng=current_lng,
                dest_lat=facility.latitude,
                dest_lng=facility.longitude,
                departure_time=now
            )
            
            distance_miles = commute["distance_miles"]
            commute_minutes = commute["duration_in_traffic_minutes"]
            
            # Determine status
            buffer_minutes = 10  # Expect 10 min early arrival
            time_needed = commute_minutes + buffer_minutes
            estimated_late_minutes = max(0, time_needed - minutes_until_shift)
            
            backup_dispatched = False
            alert_sent = False
            
            if is_at_home and minutes_until_shift <= self.alert_threshold_minutes:
                # EMERGENCY: Still at home 15 min before shift
                status = "EMERGENCY"
                alert_sent = await self._send_alert(provider_id, shift_id, "STILL_AT_HOME")
                backup_dispatched = await self._trigger_backup(shift_id)
                
                logger.warning(
                    f"[GEOFENCE] EMERGENCY: Provider {provider_id} still at home "
                    f"{minutes_until_shift:.0f} min before shift"
                )
                
            elif estimated_late_minutes > 5:
                # AT_RISK: May arrive late
                status = "AT_RISK"
                alert_sent = await self._send_alert(provider_id, shift_id, "AT_RISK")
                
                logger.warning(
                    f"[GEOFENCE] AT_RISK: Provider {provider_id} may be "
                    f"{estimated_late_minutes:.0f} min late"
                )
                
            else:
                # ON_TRACK: Should arrive on time
                status = "ON_TRACK"
                logger.info(
                    f"[GEOFENCE] ON_TRACK: Provider {provider_id} "
                    f"{distance_miles:.1f} mi away, {minutes_until_shift:.0f} min before shift"
                )
            
            return {
                "status": status,
                "minutes_until_shift": round(minutes_until_shift, 1),
                "distance_from_facility_miles": distance_miles,
                "estimated_late_minutes": round(estimated_late_minutes, 1),
                "backup_dispatched": backup_dispatched,
                "alert_sent": alert_sent,
                "is_at_home": is_at_home,
                "commute_minutes": commute_minutes
            }
            
        except Exception as e:
            logger.error(f"[GEOFENCE] Error checking location: {e}")
            return {"status": "ERROR", "reason": str(e)}
    
    def _is_at_location(
        self,
        lat1: float, lng1: float,
        lat2: float, lng2: float,
        radius_meters: float
    ) -> bool:
        """Check if two coordinates are within radius."""
        from app.services.geo_matching import haversine_distance
        
        distance_miles = haversine_distance(lat1, lng1, lat2, lng2)
        distance_meters = distance_miles * 1609.34
        
        return distance_meters <= radius_meters
    
    async def _send_alert(
        self,
        provider_id: UUID,
        shift_id: UUID,
        alert_type: str
    ) -> bool:
        """Send SMS alert to provider about location concern."""
        from app.services.sms import send_sms
        from app.models import MarylandProvider
        
        try:
            stmt = select(MarylandProvider).where(MarylandProvider.provider_id == provider_id)
            result = await self.db.execute(stmt)
            provider = result.scalar_one_or_none()
            
            if not provider:
                return False
            
            if alert_type == "STILL_AT_HOME":
                message = (
                    f"⚠️ Your shift starts in 15 minutes and we haven't detected you leaving home. "
                    f"Reply OMWCONFIRM if you're on the way, or reply CANCEL if you need to cancel."
                )
            elif alert_type == "AT_RISK":
                message = (
                    f"⚠️ Based on your current location, you may arrive late to your shift. "
                    f"Reply OK if you're on the way, or reply HELP for assistance."
                )
            else:
                message = f"⚠️ Location check alert for upcoming shift."
            
            send_sms(provider.phone_number, message)
            logger.info(f"[GEOFENCE] Sent {alert_type} alert to provider {provider_id}")
            return True
            
        except Exception as e:
            logger.error(f"[GEOFENCE] Error sending alert: {e}")
            return False
    
    async def _trigger_backup(self, shift_id: UUID) -> bool:
        """Trigger emergency backup dispatch."""
        try:
            dispatcher = WaveMatchDispatcher(self.db)
            await dispatcher.trigger_wave_dispatch(
                job_offer_id=shift_id,
                priority="EMERGENCY",
                reason="Provider geofence alert - still at home"
            )
            
            logger.info(f"[GEOFENCE] Triggered backup dispatch for shift {shift_id}")
            return True
            
        except Exception as e:
            logger.error(f"[GEOFENCE] Error triggering backup: {e}")
            return False
    
    async def monitor_active_shifts(self) -> List[Dict]:
        """
        Monitor all shifts starting in the next 60 minutes.
        
        This should be called by a background scheduler (Celery)
        every 5 minutes to check all upcoming shifts.
        
        Returns:
            List of monitoring results
        """
        from app.models import OfferCareJobOffer, MarylandProvider
        
        try:
            now = datetime.now(timezone.utc)
            monitoring_window_end = now + timedelta(minutes=self.monitoring_window_minutes)
            
            # Find all shifts starting in next 60 minutes
            stmt = select(OfferCareJobOffer).where(
                OfferCareJobOffer.shift_start >= now,
                OfferCareJobOffer.shift_start <= monitoring_window_end,
                OfferCareJobOffer.status == "CONFIRMED"
            )
            
            result = await self.db.execute(stmt)
            upcoming_shifts = result.scalars().all()
            
            logger.info(f"[GEOFENCE] Monitoring {len(upcoming_shifts)} upcoming shifts")
            
            results = []
            for shift in upcoming_shifts:
                # Get provider's current location
                stmt = select(MarylandProvider).where(
                    MarylandProvider.provider_id == shift.provider_id
                )
                result = await self.db.execute(stmt)
                provider = result.scalar_one_or_none()
                
                if not provider or not provider.latitude or not provider.longitude:
                    continue
                
                # Check location (using last known location as current)
                check = await self.check_provider_location(
                    provider_id=provider.provider_id,
                    shift_id=shift.offer_id,
                    current_lat=provider.latitude,
                    current_lng=provider.longitude
                )
                
                results.append({
                    "shift_id": shift.offer_id,
                    "provider_id": provider.provider_id,
                    "check": check
                })
            
            return results
            
        except Exception as e:
            logger.error(f"[GEOFENCE] Error monitoring active shifts: {e}")
            return []


# API endpoint for mobile app to update location
async def update_provider_location(
    db: Session,
    provider_id: UUID,
    latitude: float,
    longitude: float
) -> Dict:
    """
    Update provider's current location from mobile app.
    
    This should be called by the mobile app when:
    - Provider has an upcoming shift (within 60 min)
    - Background location update fires
    - Provider manually checks in
    """
    from app.models import MarylandProvider
    from sqlalchemy import update as sql_update
    
    try:
        # Update provider location
        stmt = sql_update(MarylandProvider).where(
            MarylandProvider.provider_id == provider_id
        ).values(
            latitude=latitude,
            longitude=longitude,
            location_updated_at=datetime.now(timezone.utc)
        )
        
        await db.execute(stmt)
        await db.commit()
        
        logger.info(f"[GEOFENCE] Updated location for provider {provider_id}")
        
        # Check all upcoming shifts for this provider
        service = GeofenceReliabilityService(db)
        from app.models import OfferCareJobOffer
        
        now = datetime.now(timezone.utc)
        monitoring_window_end = now + timedelta(minutes=60)
        
        stmt = select(OfferCareJobOffer).where(
            OfferCareJobOffer.provider_id == provider_id,
            OfferCareJobOffer.shift_start >= now,
            OfferCareJobOffer.shift_start <= monitoring_window_end,
            OfferCareJobOffer.status == "CONFIRMED"
        )
        
        result = await db.execute(stmt)
        upcoming_shifts = result.scalars().all()
        
        checks = []
        for shift in upcoming_shifts:
            check = await service.check_provider_location(
                provider_id=provider_id,
                shift_id=shift.offer_id,
                current_lat=latitude,
                current_lng=longitude
            )
            checks.append(check)
        
        return {
            "success": True,
            "shifts_checked": len(checks),
            "checks": checks
        }
        
    except Exception as e:
        logger.error(f"[GEOFENCE] Error updating location: {e}")
        return {"success": False, "error": str(e)}
