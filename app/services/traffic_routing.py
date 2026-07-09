"""
Maryland Real-Time Traffic Routing Service.

Feature: High-Value Feature #1
Purpose: Calculate true commute times using real-time I-695/I-495 traffic data.

Improvements over basic haversine distance:
- Real-time traffic conditions
- Rush hour predictions
- Maryland-specific highway patterns
- Time-of-day routing
"""

import logging
from datetime import datetime, time, timezone
from typing import Dict, Optional, Tuple
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)


class TrafficRoutingService:
    """
    Real-time traffic routing for Maryland healthcare staffing.
    
    Uses Google Maps Distance Matrix API to calculate accurate
    commute times considering:
    - Current traffic conditions
    - Historical traffic patterns
    - Rush hour delays (I-695/I-495)
    - Time-of-day routing
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.enabled = getattr(settings, "TRAFFIC_ROUTING_ENABLED", True)
        self.api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", None)
        self.dry_run = getattr(settings, "TRAFFIC_ROUTING_DRY_RUN", True)
        
        if not self.api_key and not self.dry_run:
            logger.warning("[TRAFFIC] No Google Maps API key configured")
    
    async def calculate_commute_time(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        departure_time: Optional[datetime] = None
    ) -> Dict:
        """
        Calculate commute time with real-time traffic.
        
        Args:
            origin_lat: Provider's current latitude
            origin_lng: Provider's current longitude
            dest_lat: Facility latitude
            dest_lng: Facility longitude
            departure_time: When the provider would depart (for prediction)
        
        Returns:
            {
                "distance_miles": float,
                "duration_minutes": float,
                "duration_in_traffic_minutes": float,
                "traffic_delay_minutes": float,
                "traffic_level": str (LIGHT/MODERATE/HEAVY),
                "suggested_departure": datetime
            }
        """
        if not self.enabled:
            return self._fallback_haversine(origin_lat, origin_lng, dest_lat, dest_lng)
        
        if self.dry_run or not self.api_key:
            return self._mock_traffic_data(origin_lat, origin_lng, dest_lat, dest_lng, departure_time)
        
        try:
            return await self._fetch_google_maps_data(
                origin_lat, origin_lng, dest_lat, dest_lng, departure_time
            )
        except Exception as e:
            logger.error(f"[TRAFFIC] Google Maps API error: {e}")
            return self._fallback_haversine(origin_lat, origin_lng, dest_lat, dest_lng)
    
    async def _fetch_google_maps_data(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        departure_time: Optional[datetime]
    ) -> Dict:
        """Fetch real-time traffic data from Google Maps Distance Matrix API."""
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        
        params = {
            "origins": f"{origin_lat},{origin_lng}",
            "destinations": f"{dest_lat},{dest_lng}",
            "key": self.api_key,
            "mode": "driving",
            "departure_time": "now" if not departure_time else int(departure_time.timestamp()),
            "traffic_model": "best_guess"  # or "pessimistic" for safety
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        if data["status"] != "OK":
            raise Exception(f"Google Maps API error: {data.get('error_message')}")
        
        element = data["rows"][0]["elements"][0]
        
        if element["status"] != "OK":
            raise Exception(f"Route not found: {element['status']}")
        
        # Extract data
        distance_meters = element["distance"]["value"]
        duration_seconds = element["duration"]["value"]
        duration_in_traffic_seconds = element.get("duration_in_traffic", {}).get("value", duration_seconds)
        
        distance_miles = distance_meters / 1609.34
        duration_minutes = duration_seconds / 60
        duration_in_traffic_minutes = duration_in_traffic_seconds / 60
        traffic_delay_minutes = duration_in_traffic_minutes - duration_minutes
        
        # Determine traffic level
        if traffic_delay_minutes < 5:
            traffic_level = "LIGHT"
        elif traffic_delay_minutes < 15:
            traffic_level = "MODERATE"
        else:
            traffic_level = "HEAVY"
        
        # Calculate suggested departure time (work backwards from shift start)
        suggested_departure = None
        if departure_time:
            buffer_minutes = 15  # Safety buffer
            total_commute = duration_in_traffic_minutes + buffer_minutes
            suggested_departure = departure_time
        
        logger.info(
            f"[TRAFFIC] Route: {distance_miles:.1f} mi, "
            f"{duration_in_traffic_minutes:.0f} min (traffic), "
            f"+{traffic_delay_minutes:.0f} min delay ({traffic_level})"
        )
        
        return {
            "distance_miles": round(distance_miles, 2),
            "duration_minutes": round(duration_minutes, 1),
            "duration_in_traffic_minutes": round(duration_in_traffic_minutes, 1),
            "traffic_delay_minutes": round(traffic_delay_minutes, 1),
            "traffic_level": traffic_level,
            "suggested_departure": suggested_departure,
            "api_source": "google_maps"
        }
    
    def _mock_traffic_data(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        departure_time: Optional[datetime]
    ) -> Dict:
        """Generate mock traffic data for testing."""
        # Calculate base haversine distance
        base_data = self._fallback_haversine(origin_lat, origin_lng, dest_lat, dest_lng)
        
        # Add simulated traffic based on time of day
        now = departure_time or datetime.now(timezone.utc)
        hour = now.hour
        
        # Rush hour multipliers (Maryland I-695/I-495 patterns)
        if 7 <= hour < 9 or 16 <= hour < 19:
            # Morning/evening rush hour
            traffic_multiplier = 1.5
            traffic_level = "HEAVY"
            traffic_delay = base_data["duration_minutes"] * 0.5
        elif 9 <= hour < 16:
            # Mid-day moderate traffic
            traffic_multiplier = 1.2
            traffic_level = "MODERATE"
            traffic_delay = base_data["duration_minutes"] * 0.2
        else:
            # Night/early morning
            traffic_multiplier = 1.0
            traffic_level = "LIGHT"
            traffic_delay = 0
        
        duration_in_traffic = base_data["duration_minutes"] * traffic_multiplier
        
        logger.info(
            f"[TRAFFIC] MOCK: {base_data['distance_miles']:.1f} mi, "
            f"{duration_in_traffic:.0f} min ({traffic_level})"
        )
        
        return {
            "distance_miles": base_data["distance_miles"],
            "duration_minutes": base_data["duration_minutes"],
            "duration_in_traffic_minutes": round(duration_in_traffic, 1),
            "traffic_delay_minutes": round(traffic_delay, 1),
            "traffic_level": traffic_level,
            "suggested_departure": departure_time,
            "api_source": "mock"
        }
    
    def _fallback_haversine(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float
    ) -> Dict:
        """Fallback to basic haversine distance calculation."""
        from app.services.geo_matching import haversine_distance
        
        distance_miles = haversine_distance(origin_lat, origin_lng, dest_lat, dest_lng)
        
        # Rough estimate: 30 mph average speed
        duration_minutes = (distance_miles / 30.0) * 60.0
        
        return {
            "distance_miles": round(distance_miles, 2),
            "duration_minutes": round(duration_minutes, 1),
            "duration_in_traffic_minutes": round(duration_minutes, 1),
            "traffic_delay_minutes": 0,
            "traffic_level": "UNKNOWN",
            "suggested_departure": None,
            "api_source": "haversine_fallback"
        }
    
    def is_rush_hour(self, dt: Optional[datetime] = None) -> bool:
        """Check if given time is Maryland rush hour."""
        dt = dt or datetime.now(timezone.utc)
        hour = dt.hour
        
        # Morning rush: 7-9 AM
        # Evening rush: 4-7 PM
        return (7 <= hour < 9) or (16 <= hour < 19)
    
    def get_rush_hour_multiplier(self, dt: Optional[datetime] = None) -> float:
        """Get traffic multiplier for rush hour."""
        dt = dt or datetime.now(timezone.utc)
        hour = dt.hour
        
        if 7 <= hour < 9 or 16 <= hour < 19:
            return 1.5  # 50% longer during rush hour
        elif 9 <= hour < 16:
            return 1.2  # 20% longer mid-day
        else:
            return 1.0  # Normal time off-peak
    
    async def calculate_commute_for_shift(
        self,
        provider_id: UUID,
        shift_id: UUID
    ) -> Optional[Dict]:
        """
        Calculate commute time for a specific provider-shift pair.
        
        Args:
            provider_id: Provider UUID
            shift_id: Shift UUID
        
        Returns:
            Commute data dict or None if data unavailable
        """
        from app.models import MarylandProvider, OfferCareJobOffer, MarylandFacility
        from sqlalchemy import select
        
        try:
            # Get provider location
            stmt = select(MarylandProvider).where(MarylandProvider.provider_id == provider_id)
            result = await self.db.execute(stmt)
            provider = result.scalar_one_or_none()
            
            if not provider or not provider.latitude or not provider.longitude:
                logger.warning(f"[TRAFFIC] Provider {provider_id} has no location data")
                return None
            
            # Get shift/facility location
            stmt = select(OfferCareJobOffer, MarylandFacility).join(
                MarylandFacility, OfferCareJobOffer.facility_id == MarylandFacility.facility_id
            ).where(OfferCareJobOffer.offer_id == shift_id)
            
            result = await self.db.execute(stmt)
            row = result.first()
            
            if not row:
                logger.warning(f"[TRAFFIC] Shift {shift_id} not found")
                return None
            
            shift, facility = row
            
            if not facility.latitude or not facility.longitude:
                logger.warning(f"[TRAFFIC] Facility has no location data")
                return None
            
            # Calculate commute with shift start time
            return await self.calculate_commute_time(
                origin_lat=provider.latitude,
                origin_lng=provider.longitude,
                dest_lat=facility.latitude,
                dest_lng=facility.longitude,
                departure_time=shift.shift_start
            )
            
        except Exception as e:
            logger.error(f"[TRAFFIC] Error calculating commute: {e}")
            return None


# Convenience functions
async def get_commute_time(
    db: Session,
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    departure_time: Optional[datetime] = None
) -> Dict:
    """Convenience function to get commute time."""
    service = TrafficRoutingService(db)
    return await service.calculate_commute_time(
        origin_lat, origin_lng, dest_lat, dest_lng, departure_time
    )
