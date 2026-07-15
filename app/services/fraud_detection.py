"""
VettedMe AI Fraud Detection Engine

Detects:
- Deepfake biometrics
- Document forgery
- Anomalous verification patterns
- Credential stuffing attacks
- Identity theft
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import numpy as np
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# ==================== RISK SCORING ====================

@dataclass
class FraudRiskScore:
    """Fraud risk assessment result"""
    risk_level: str  # "low", "medium", "high", "critical"
    risk_score: int  # 0-100
    flags: List[str]
    indicators: Dict[str, Any]
    recommended_action: str
    timestamp: datetime


class FraudDetectionEngine:
    """AI-powered fraud detection system"""
    
    def __init__(self, db: Session):
        self.db = db
        self.risk_weights = {
            "biometric_anomaly": 40,
            "document_forgery": 50,
            "velocity_anomaly": 30,
            "geolocation_anomaly": 20,
            "device_fingerprint": 15,
            "behavioral_pattern": 25,
        }
    
    async def analyze_verification_request(
        self,
        passport_id: str,
        request_data: Dict[str, Any]
    ) -> FraudRiskScore:
        """
        Comprehensive fraud analysis
        
        Checks:
        1. Biometric liveness (deepfake detection)
        2. Document authenticity (forgery detection)
        3. Velocity checks (too many verifications)
        4. Geolocation anomalies
        5. Device fingerprinting
        6. Behavioral patterns
        """
        flags = []
        risk_score = 0
        indicators = {}
        
        # 1. Biometric Anomaly Detection
        biometric_risk = await self._check_biometric_anomalies(passport_id, request_data)
        if biometric_risk > 0.5:
            flags.append("BIOMETRIC_ANOMALY")
            risk_score += self.risk_weights["biometric_anomaly"]
            indicators["biometric_risk"] = biometric_risk
        
        # 2. Document Forgery Detection
        if "document_image" in request_data:
            forgery_risk = await self._detect_document_forgery(request_data["document_image"])
            if forgery_risk > 0.5:
                flags.append("DOCUMENT_FORGERY")
                risk_score += self.risk_weights["document_forgery"]
                indicators["forgery_risk"] = forgery_risk
        
        # 3. Velocity Anomaly Detection
        velocity_risk = await self._check_velocity_anomalies(passport_id)
        if velocity_risk > 0.5:
            flags.append("VELOCITY_ANOMALY")
            risk_score += self.risk_weights["velocity_anomaly"]
            indicators["velocity_risk"] = velocity_risk
        
        # 4. Geolocation Anomaly Detection
        if "ip_address" in request_data:
            geo_risk = await self._check_geolocation_anomalies(passport_id, request_data["ip_address"])
            if geo_risk > 0.5:
                flags.append("GEOLOCATION_ANOMALY")
                risk_score += self.risk_weights["geolocation_anomaly"]
                indicators["geo_risk"] = geo_risk
        
        # 5. Device Fingerprint Analysis
        if "device_fingerprint" in request_data:
            device_risk = await self._check_device_fingerprint(passport_id, request_data["device_fingerprint"])
            if device_risk > 0.5:
                flags.append("DEVICE_FINGERPRINT_MISMATCH")
                risk_score += self.risk_weights["device_fingerprint"]
                indicators["device_risk"] = device_risk
        
        # 6. Behavioral Pattern Analysis
        behavior_risk = await self._analyze_behavioral_patterns(passport_id, request_data)
        if behavior_risk > 0.5:
            flags.append("BEHAVIORAL_ANOMALY")
            risk_score += self.risk_weights["behavioral_pattern"]
            indicators["behavior_risk"] = behavior_risk
        
        # Normalize risk score (0-100)
        max_possible_score = sum(self.risk_weights.values())
        normalized_score = min(100, int((risk_score / max_possible_score) * 100))
        
        # Determine risk level
        if normalized_score >= 80:
            risk_level = "critical"
            action = "BLOCK_VERIFICATION"
        elif normalized_score >= 60:
            risk_level = "high"
            action = "MANUAL_REVIEW_REQUIRED"
        elif normalized_score >= 30:
            risk_level = "medium"
            action = "ENHANCED_VERIFICATION"
        else:
            risk_level = "low"
            action = "PROCEED"
        
        return FraudRiskScore(
            risk_level=risk_level,
            risk_score=normalized_score,
            flags=flags,
            indicators=indicators,
            recommended_action=action,
            timestamp=datetime.now()
        )
    
    async def _check_biometric_anomalies(self, passport_id: str, request_data: Dict) -> float:
        """
        Detect deepfakes and biometric anomalies
        
        Checks:
        - Liveness detection (eye movement, head rotation)
        - Face embedding consistency
        - Image metadata forensics
        """
        risk = 0.0
        
        # Check if biometric data exists
        if "biometric_data" not in request_data:
            return 0.0
        
        # Liveness check (mock - in production, use FaceTec or AWS Rekognition)
        liveness_score = request_data.get("liveness_score", 1.0)
        if liveness_score < 0.7:
            risk += 0.4
        
        # Face embedding consistency check
        # Compare current embedding with enrolled embedding
        enrolled_embedding = await self._get_enrolled_embedding(passport_id)
        current_embedding = request_data.get("face_embedding", [])
        
        if enrolled_embedding and current_embedding:
            similarity = self._cosine_similarity(enrolled_embedding, current_embedding)
            if similarity < 0.85:
                risk += 0.6
        
        return min(1.0, risk)
    
    async def _detect_document_forgery(self, document_image: bytes) -> float:
        """
        Detect forged documents using AI
        
        Checks:
        - Font inconsistencies
        - Copy-move detection
        - Metadata analysis
        - Microprint verification
        - Hologram presence
        """
        risk = 0.0
        
        # Mock implementation - in production, use:
        # - AWS Textract for OCR + validation
        # - Computer vision models for forgery detection
        # - EXIF metadata analysis
        
        # Placeholder logic
        # In real implementation: send to ML model for analysis
        forgery_indicators = self._analyze_document_features(document_image)
        
        if forgery_indicators.get("font_inconsistency", False):
            risk += 0.3
        if forgery_indicators.get("copy_move_detected", False):
            risk += 0.5
        if forgery_indicators.get("metadata_stripped", False):
            risk += 0.2
        
        return min(1.0, risk)
    
    async def _check_velocity_anomalies(self, passport_id: str) -> float:
        """
        Detect abnormal verification velocity
        
        Flags:
        - >10 verifications in 1 hour
        - >50 verifications in 24 hours
        - Sudden spike from 0 to 20+ in minutes
        """
        risk = 0.0
        
        # Count verifications in last hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_verifications = self.db.execute(
            """
            SELECT COUNT(*) FROM verification_logs
            WHERE passport_id = :passport_id AND verified_at > :since
            """,
            {"passport_id": passport_id, "since": one_hour_ago}
        ).scalar() or 0
        
        if recent_verifications > 20:
            risk = 1.0
        elif recent_verifications > 10:
            risk = 0.7
        elif recent_verifications > 5:
            risk = 0.3
        
        return risk
    
    async def _check_geolocation_anomalies(self, passport_id: str, ip_address: str) -> float:
        """
        Detect impossible travel scenarios
        
        Flags:
        - Verification in NYC at 9am, then Tokyo at 9:05am (impossible)
        - Rapid country switching
        - VPN/Tor usage (high risk)
        """
        risk = 0.0
        
        # Get last verification location
        last_location = await self._get_last_verification_location(passport_id)
        current_location = await self._geolocate_ip(ip_address)
        
        if last_location and current_location:
            distance_km = self._calculate_distance(last_location, current_location)
            time_diff_hours = self._get_time_since_last_verification(passport_id)
            
            # Check for impossible travel
            # Max travel speed: 900 km/h (commercial airplane)
            max_possible_distance = time_diff_hours * 900
            
            if distance_km > max_possible_distance:
                risk = 1.0  # Impossible travel detected
        
        # Check for VPN/Tor
        if await self._is_vpn_or_tor(ip_address):
            risk = max(risk, 0.5)
        
        return risk
    
    async def _check_device_fingerprint(self, passport_id: str, fingerprint: str) -> float:
        """
        Check device fingerprint consistency
        
        Flags:
        - New device never seen before
        - Device fingerprint changed suddenly
        - Device associated with fraud in the past
        """
        risk = 0.0
        
        # Check if device is known
        known_devices = await self._get_known_devices(passport_id)
        
        if fingerprint not in known_devices:
            if len(known_devices) > 0:
                # New device for existing user
                risk = 0.3
            else:
                # First time user (normal)
                risk = 0.0
        
        # Check device blacklist
        if await self._is_device_blacklisted(fingerprint):
            risk = 1.0
        
        return risk
    
    async def _analyze_behavioral_patterns(self, passport_id: str, request_data: Dict) -> float:
        """
        Analyze user behavior patterns
        
        Checks:
        - Typing speed/patterns
        - Mouse movement
        - Time of day (unusual hours)
        - Verification cadence
        """
        risk = 0.0
        
        # Check time of day
        current_hour = datetime.now().hour
        if current_hour >= 2 and current_hour <= 5:
            # Verifications at 2am-5am are suspicious
            risk += 0.2
        
        # Check typical verification pattern
        typical_hour = await self._get_typical_verification_hour(passport_id)
        if typical_hour and abs(current_hour - typical_hour) > 8:
            risk += 0.3
        
        return min(1.0, risk)
    
    # ==================== HELPER METHODS ====================
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        if not vec1 or not vec2:
            return 0.0
        
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
    
    def _analyze_document_features(self, image: bytes) -> Dict[str, bool]:
        """Analyze document for forgery indicators (mock)"""
        # In production: use ML model
        return {
            "font_inconsistency": False,
            "copy_move_detected": False,
            "metadata_stripped": False,
        }
    
    async def _get_enrolled_embedding(self, passport_id: str) -> Optional[List[float]]:
        """Get enrolled face embedding from database"""
        # Mock - in production, query from biometric_data table
        return None
    
    async def _get_last_verification_location(self, passport_id: str) -> Optional[Dict]:
        """Get location of last verification"""
        # Mock implementation
        return None
    
    async def _geolocate_ip(self, ip_address: str) -> Dict:
        """Geolocate IP address"""
        # In production: use MaxMind GeoIP2 or IPinfo
        return {"latitude": 0.0, "longitude": 0.0, "country": "US"}
    
    def _calculate_distance(self, loc1: Dict, loc2: Dict) -> float:
        """Calculate distance between two locations (km)"""
        # Haversine formula
        lat1, lon1 = loc1["latitude"], loc1["longitude"]
        lat2, lon2 = loc2["latitude"], loc2["longitude"]
        
        R = 6371  # Earth's radius in km
        
        dlat = np.radians(lat2 - lat1)
        dlon = np.radians(lon2 - lon1)
        
        a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
        
        return R * c
    
    def _get_time_since_last_verification(self, passport_id: str) -> float:
        """Get hours since last verification"""
        # Mock implementation
        return 24.0
    
    async def _is_vpn_or_tor(self, ip_address: str) -> bool:
        """Check if IP is from VPN or Tor"""
        # In production: use IPQualityScore API or similar
        return False
    
    async def _get_known_devices(self, passport_id: str) -> List[str]:
        """Get list of known device fingerprints"""
        # Mock implementation
        return []
    
    async def _is_device_blacklisted(self, fingerprint: str) -> bool:
        """Check if device is blacklisted"""
        # Mock implementation
        return False
    
    async def _get_typical_verification_hour(self, passport_id: str) -> Optional[int]:
        """Get typical hour of day for verifications"""
        # Mock implementation
        return None


# ==================== REAL-TIME ALERTING ====================

class FraudAlertService:
    """Real-time fraud alerting to security team"""
    
    def __init__(self):
        self.slack_webhook = os.getenv("SLACK_SECURITY_WEBHOOK")
        self.pagerduty_key = os.getenv("PAGERDUTY_API_KEY")
    
    async def send_alert(self, risk_score: FraudRiskScore, passport_id: str):
        """Send alert to security team"""
        if risk_score.risk_level in ["high", "critical"]:
            # Send to Slack
            await self._send_slack_alert(risk_score, passport_id)
            
            # Page security team for critical
            if risk_score.risk_level == "critical":
                await self._page_security_team(risk_score, passport_id)
    
    async def _send_slack_alert(self, risk_score: FraudRiskScore, passport_id: str):
        """Send Slack notification"""
        message = f"""
🚨 **FRAUD ALERT** 🚨

**Risk Level**: {risk_score.risk_level.upper()}
**Risk Score**: {risk_score.risk_score}/100
**Passport ID**: {passport_id}
**Flags**: {', '.join(risk_score.flags)}
**Recommended Action**: {risk_score.recommended_action}

**Indicators**:
{json.dumps(risk_score.indicators, indent=2)}

Time: {risk_score.timestamp.isoformat()}
        """
        # Send to Slack (mock)
        logger.warning(f"FRAUD ALERT: {passport_id} - {risk_score.risk_level}")
    
    async def _page_security_team(self, risk_score: FraudRiskScore, passport_id: str):
        """Page security team via PagerDuty"""
        # Send PagerDuty alert (mock)
        logger.critical(f"CRITICAL FRAUD: {passport_id} - {risk_score.risk_score}/100")
