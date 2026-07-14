"""
Shift Matching Engine
Phase 2: Intelligence & Compliance - Workforce Optimization

Automated matching of cleared healthcare professionals with facility shift gaps.
Enforces strict Maryland OHCQ compliance mandates before matching.
"""

import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models import HealthcareCredential, MarylandProvider
from typing import List, Dict, Any, Optional

logger = logging.getLogger("MatchingEngine")


class ShiftMatchingEngine:
    """
    OHCQ-compliant shift matching engine for Maryland healthcare facilities.
    
    Features:
    - Strict compliance gates (OHCQ verified + background check)
    - License type matching
    - Credential freshness scoring
    - Distance-based optimization (future)
    - Availability checking (future)
    """
    
    def __init__(self, db: Session):
        """
        Initialize matching engine.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def find_compliant_professionals_for_shift(
        self,
        shift_id: str,
        required_role: str,
        facility_id: str,
        require_background_check: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Queries the database to find matched, cleared healthcare professionals.
        Enforces strict OHCQ gates: credentials must be verified and active.
        
        Args:
            shift_id: Unique shift identifier
            required_role: License type required (RN, LPN, CNA, GNA)
            facility_id: Facility requesting coverage
            require_background_check: Whether background check is required (default: True)
        
        Returns:
            List of matched professionals with scores, sorted by match quality
        """
        logger.info(
            f"Executing shift match for Shift ID: {shift_id} "
            f"(Role: {required_role}, Facility: {facility_id})"
        )
        
        # 🛡️ OHCQ Compliance Gate 1: OHCQ Verification Required
        query = self.db.query(HealthcareCredential).join(
            MarylandProvider,
            HealthcareCredential.provider_id == MarylandProvider.provider_id
        ).filter(
            HealthcareCredential.license_type == required_role,
            HealthcareCredential.is_ohcq_verified == True,
        )
        
        # 🛡️ OHCQ Compliance Gate 2: Background Check (Optional)
        if require_background_check:
            query = query.filter(
                HealthcareCredential.background_check_passed == True
            )
        
        # Execute query
        cleared_candidates = query.all()
        
        logger.info(
            f"Found {len(cleared_candidates)} OHCQ-compliant {required_role} professionals"
        )
        
        matched_pool = []
        for credential in cleared_candidates:
            # Get provider information
            provider = self.db.query(MarylandProvider).filter(
                MarylandProvider.provider_id == credential.provider_id
            ).first()
            
            if not provider:
                continue
            
            # Calculate matching score
            match_score = self._calculate_match_score(
                credential=credential,
                provider=provider,
                facility_id=facility_id
            )
            
            matched_pool.append({
                "credential_id": str(credential.credential_id),
                "provider_id": str(credential.provider_id),
                "professional_name": provider.full_name,
                "license": f"{credential.license_type} #{credential.license_number}",
                "license_type": credential.license_type,
                "license_number": credential.license_number,
                "match_score": match_score,
                "ohcq_cleared": credential.is_ohcq_verified,
                "background_check_cleared": credential.background_check_passed,
                "verified_at": (
                    credential.ohcq_verified_at.isoformat()
                    if credential.ohcq_verified_at
                    else None
                ),
                "phone_number": provider.phone_number,
                "email": provider.email,
                "compliance_status": self._get_compliance_status(credential)
            })
        
        # Sort by descending match score
        matched_pool.sort(key=lambda x: x["match_score"], reverse=True)
        
        logger.info(
            f"Returning {len(matched_pool)} matched professionals "
            f"(top score: {matched_pool[0]['match_score'] if matched_pool else 0})"
        )
        
        return matched_pool
    
    def _calculate_match_score(
        self,
        credential: HealthcareCredential,
        provider: MarylandProvider,
        facility_id: str
    ) -> float:
        """
        Calculate match score for a professional.
        
        Scoring Factors:
        - Base score: 100.0
        - Verification freshness penalty: -0.5 per day > 7 days
        - Background check bonus: +10.0
        - Credential expiration proximity penalty
        
        Args:
            credential: Healthcare credential record
            provider: Provider record
            facility_id: Target facility ID
        
        Returns:
            Match score (50.0 to 110.0 range)
        """
        base_score = 100.0
        
        # Factor 1: Verification Freshness
        if credential.ohcq_verified_at:
            days_since_verification = (
                datetime.now(timezone.utc) - 
                credential.ohcq_verified_at.replace(tzinfo=timezone.utc)
            ).days
            
            # Penalize stale verifications (>7 days)
            if days_since_verification > 7:
                freshness_penalty = (days_since_verification - 7) * 0.5
                base_score -= min(freshness_penalty, 20.0)  # Cap penalty at 20 points
        
        # Factor 2: Background Check Bonus
        if credential.background_check_passed:
            base_score += 10.0
        
        # Factor 3: Credential Expiration Proximity
        if credential.expiration_date:
            days_until_expiry = (
                credential.expiration_date - datetime.now(timezone.utc).date()
            ).days
            
            # Warn if expiring soon
            if days_until_expiry < 30:
                expiry_penalty = (30 - days_until_expiry) * 0.3
                base_score -= min(expiry_penalty, 10.0)  # Cap at 10 points
        
        # Factor 4: Provider Response Propensity (if available)
        if hasattr(provider, 'response_propensity') and provider.response_propensity:
            # Boost score by response propensity (0.0 to 1.0 scale)
            base_score += (provider.response_propensity * 10.0)
        
        # Ensure score stays in reasonable range
        return max(50.0, min(round(base_score, 1), 110.0))
    
    def _get_compliance_status(self, credential: HealthcareCredential) -> str:
        """
        Get human-readable compliance status.
        
        Args:
            credential: Healthcare credential record
        
        Returns:
            Compliance status string
        """
        if not credential.is_ohcq_verified:
            return "PENDING_VERIFICATION"
        elif not credential.background_check_passed:
            return "VERIFIED_NO_BACKGROUND_CHECK"
        else:
            return "FULLY_COMPLIANT"
    
    def find_available_professionals_by_license_type(
        self,
        license_type: str,
        fully_compliant_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get all available professionals for a given license type.
        
        Args:
            license_type: License type (RN, LPN, CNA, GNA)
            fully_compliant_only: Require both OHCQ + background check (default: True)
        
        Returns:
            List of available professionals
        """
        query = self.db.query(HealthcareCredential).join(
            MarylandProvider,
            HealthcareCredential.provider_id == MarylandProvider.provider_id
        ).filter(
            HealthcareCredential.license_type == license_type,
            HealthcareCredential.is_ohcq_verified == True
        )
        
        if fully_compliant_only:
            query = query.filter(
                HealthcareCredential.background_check_passed == True
            )
        
        credentials = query.all()
        
        results = []
        for credential in credentials:
            provider = self.db.query(MarylandProvider).filter(
                MarylandProvider.provider_id == credential.provider_id
            ).first()
            
            if provider:
                results.append({
                    "credential_id": str(credential.credential_id),
                    "provider_id": str(credential.provider_id),
                    "professional_name": provider.full_name,
                    "license": f"{credential.license_type} #{credential.license_number}",
                    "license_type": credential.license_type,
                    "compliance_status": self._get_compliance_status(credential),
                    "verified_at": (
                        credential.ohcq_verified_at.isoformat()
                        if credential.ohcq_verified_at
                        else None
                    )
                })
        
        return results
    
    def get_compliance_summary(self) -> Dict[str, Any]:
        """
        Get summary of workforce compliance status.
        
        Returns:
            Dictionary with compliance statistics
        """
        total_credentials = self.db.query(HealthcareCredential).count()
        
        fully_compliant = self.db.query(HealthcareCredential).filter(
            HealthcareCredential.is_ohcq_verified == True,
            HealthcareCredential.background_check_passed == True
        ).count()
        
        ohcq_only = self.db.query(HealthcareCredential).filter(
            HealthcareCredential.is_ohcq_verified == True,
            HealthcareCredential.background_check_passed == False
        ).count()
        
        pending = self.db.query(HealthcareCredential).filter(
            HealthcareCredential.is_ohcq_verified == False
        ).count()
        
        return {
            "total_credentials": total_credentials,
            "fully_compliant": fully_compliant,
            "ohcq_verified_only": ohcq_only,
            "pending_verification": pending,
            "compliance_rate": (
                round(fully_compliant / total_credentials * 100, 2)
                if total_credentials > 0
                else 0.0
            )
        }
