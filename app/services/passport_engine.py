"""
VettedMe Passport - Cryptographic Issuance & Verification Engine

This module handles the core cryptographic operations for issuing and verifying
credential badges using Ed25519 digital signatures (W3C Verifiable Credentials standard).

Security Properties:
- Non-repudiation: VettedMe cannot deny issuing a credential
- Tamper-proof: Any modification breaks the signature
- Instant verification: No database lookup required (can verify offline)
- Privacy-preserving: User controls which badges to share
"""

import os
import json
import base64
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from sqlalchemy.orm import Session
from app.models.passport import Passport, CredentialBadge, VerificationLog
import uuid


class PassportCryptoEngine:
    """
    Handles Ed25519 key generation, credential signing, and verification.
    
    In production, private keys should be stored in a Hardware Security Module (HSM)
    or secure key management service like AWS KMS or HashiCorp Vault.
    """
    
    def __init__(self):
        # In production, load from secure key store
        # For MVP, we'll use environment variable
        self.issuer_private_key = self._load_issuer_private_key()
        self.issuer_public_key = self.issuer_private_key.public_key()
    
    def _load_issuer_private_key(self) -> Ed25519PrivateKey:
        """
        Load VettedMe's master private key for signing credentials.
        
        SECURITY: In production, this MUST be stored in HSM/KMS, not environment variables.
        """
        private_key_pem = os.getenv("VETTEDME_ISSUER_PRIVATE_KEY")
        
        if not private_key_pem:
            # For development only - generate ephemeral key
            print("⚠️  WARNING: No VETTEDME_ISSUER_PRIVATE_KEY found. Generating ephemeral key (dev only).")
            return Ed25519PrivateKey.generate()
        
        # Load from PEM format
        return serialization.load_pem_private_key(
            private_key_pem.encode(),
            password=None
        )
    
    def generate_passport_keypair(self) -> Dict[str, str]:
        """
        Generate a unique Ed25519 keypair for a new passport.
        
        Returns:
            dict: {
                "public_key": "<PEM encoded public key>",
                "private_key": "<PEM encoded private key>"  # User stores this securely
            }
        """
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()
        
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        
        return {
            "public_key": public_pem,
            "private_key": private_pem
        }
    
    def sign_credential(self, credential_data: Dict[str, Any]) -> str:
        """
        Sign a credential payload with VettedMe's private key.
        
        Args:
            credential_data: The credential JSON payload to sign
        
        Returns:
            Base64-encoded signature string
        """
        # Serialize credential to canonical JSON (sorted keys for consistency)
        canonical_json = json.dumps(credential_data, sort_keys=True, separators=(',', ':'))
        message_bytes = canonical_json.encode('utf-8')
        
        # Sign with Ed25519
        signature = self.issuer_private_key.sign(message_bytes)
        
        # Return base64-encoded signature
        return base64.b64encode(signature).decode('utf-8')
    
    def verify_signature(self, credential_data: Dict[str, Any], signature: str) -> bool:
        """
        Verify a credential's signature using VettedMe's public key.
        
        Args:
            credential_data: The credential JSON payload
            signature: Base64-encoded signature string
        
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Reconstruct canonical JSON
            canonical_json = json.dumps(credential_data, sort_keys=True, separators=(',', ':'))
            message_bytes = canonical_json.encode('utf-8')
            
            # Decode signature
            signature_bytes = base64.b64decode(signature)
            
            # Verify signature
            self.issuer_public_key.verify(signature_bytes, message_bytes)
            return True
        
        except Exception as e:
            print(f"Signature verification failed: {e}")
            return False
    
    def compute_biometric_hash(self, facial_embedding: bytes) -> str:
        """
        Generate a secure hash of a facial biometric embedding.
        
        Args:
            facial_embedding: Raw biometric data from FaceID/liveness check
        
        Returns:
            SHA256 hash (hex string)
        """
        return hashlib.sha256(facial_embedding).hexdigest()


class PassportIssuanceEngine:
    """
    High-level engine for issuing passports and credential badges.
    
    This is the main service layer that orchestrates:
    1. Passport creation
    2. Badge issuance
    3. Badge revocation
    4. Trust score calculation
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.crypto_engine = PassportCryptoEngine()
    
    def create_passport(self, user_id: uuid.UUID, biometric_data: Optional[bytes] = None) -> Passport:
        """
        Issue a new passport for a user.
        
        Args:
            user_id: UUID of the user
            biometric_data: Optional facial biometric embedding
        
        Returns:
            Newly created Passport instance
        """
        # Check if user already has a passport
        existing = self.db.query(Passport).filter_by(user_id=user_id).first()
        if existing:
            raise ValueError(f"User {user_id} already has a passport (ID: {existing.id})")
        
        # Generate keypair for this passport
        keypair = self.crypto_engine.generate_passport_keypair()
        
        # Compute biometric hash if provided
        biometric_hash = None
        if biometric_data:
            biometric_hash = self.crypto_engine.compute_biometric_hash(biometric_data)
        
        # Create passport (expires in 2 years)
        passport = Passport(
            user_id=user_id,
            public_key=keypair["public_key"],
            status="ACTIVE",
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=730),  # 2 years
            biometric_hash=biometric_hash,
            trust_score=0  # Will increase as badges are verified
        )
        
        self.db.add(passport)
        self.db.commit()
        self.db.refresh(passport)
        
        return passport
    
    def issue_badge(
        self,
        passport_id: uuid.UUID,
        badge_type: str,
        credential_data: Dict[str, Any],
        verification_method: str,
        expires_at: Optional[datetime] = None
    ) -> CredentialBadge:
        """
        Issue a new credential badge and attach it to a passport.
        
        Args:
            passport_id: UUID of the passport
            badge_type: Type of badge (IDENTITY, HEALTHCARE, etc.)
            credential_data: JSON payload with credential details
            verification_method: How the credential was verified (MBON_SCRAPER, MANUAL_REVIEW, etc.)
            expires_at: Optional expiration date
        
        Returns:
            Newly created CredentialBadge instance
        """
        # Verify passport exists and is active
        passport = self.db.query(Passport).filter_by(id=passport_id).first()
        if not passport:
            raise ValueError(f"Passport {passport_id} not found")
        if not passport.is_active():
            raise ValueError(f"Passport {passport_id} is not active (status: {passport.status})")
        
        # Add metadata to credential
        credential_with_metadata = {
            **credential_data,
            "passport_id": str(passport_id),
            "badge_type": badge_type,
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "issuer": "VettedMe.ai"
        }
        
        # Sign the credential
        signature = self.crypto_engine.sign_credential(credential_with_metadata)
        
        # Create badge
        badge = CredentialBadge(
            passport_id=passport_id,
            badge_type=badge_type,
            credential_data=credential_with_metadata,
            issuer_signature=signature,
            verification_method=verification_method,
            verified_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            revoked=False
        )
        
        self.db.add(badge)
        
        # Update passport trust score
        self._recalculate_trust_score(passport)
        
        self.db.commit()
        self.db.refresh(badge)
        
        return badge
    
    def revoke_badge(self, badge_id: uuid.UUID, reason: str):
        """
        Revoke a credential badge.
        
        Args:
            badge_id: UUID of the badge to revoke
            reason: Reason for revocation
        """
        badge = self.db.query(CredentialBadge).filter_by(id=badge_id).first()
        if not badge:
            raise ValueError(f"Badge {badge_id} not found")
        
        badge.revoke(reason)
        
        # Update passport trust score
        passport = self.db.query(Passport).filter_by(id=badge.passport_id).first()
        if passport:
            self._recalculate_trust_score(passport)
        
        self.db.commit()
    
    def _recalculate_trust_score(self, passport: Passport):
        """
        Recalculate the algorithmic trust score for a passport.
        
        Trust score formula:
        - Base: 20 points for having a passport
        - Identity badge: +30 points
        - Each additional valid badge: +10 points
        - Biometric verification: +10 points
        - Each revoked badge: -15 points
        - Expired passport: -50 points (drops to 0)
        
        Max score: 100
        """
        score = 20  # Base score
        
        # Count valid badges
        valid_badges = passport.get_active_badges()
        
        for badge in valid_badges:
            if badge.badge_type == "IDENTITY":
                score += 30
            else:
                score += 10
        
        # Biometric bonus
        if passport.biometric_hash:
            score += 10
        
        # Penalty for revoked badges
        revoked_count = len([b for b in passport.badges if b.revoked])
        score -= (revoked_count * 15)
        
        # Passport expiration penalty
        if passport.expires_at < datetime.now(timezone.utc):
            score = 0
        
        # Clamp to 0-100
        passport.trust_score = max(0, min(100, score))


class PassportVerificationEngine:
    """
    Engine for verifying passports and badges via external API requests.
    
    This is the revenue-generating component - every verification request
    is logged and billed according to the API key's tier.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.crypto_engine = PassportCryptoEngine()
    
    def verify_passport(
        self,
        passport_id: uuid.UUID,
        required_badges: List[str],
        api_key_id: uuid.UUID,
        requesting_platform: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify a passport and return requested badge information.
        
        This is the core API endpoint logic that external platforms call.
        
        Args:
            passport_id: UUID of the passport to verify
            required_badges: List of badge types to verify (e.g., ["IDENTITY", "HEALTHCARE"])
            api_key_id: UUID of the API key making the request
            requesting_platform: Domain/name of the requesting platform
            ip_address: IP address of the request
            user_agent: User agent string
        
        Returns:
            Verification result payload
        """
        # Fetch passport
        passport = self.db.query(Passport).filter_by(id=passport_id).first()
        
        if not passport:
            result = {
                "verified": False,
                "error": "PASSPORT_NOT_FOUND",
                "passport_id": str(passport_id)
            }
            self._log_verification(passport_id, api_key_id, requesting_platform, required_badges, result, ip_address, user_agent)
            return result
        
        if not passport.is_active():
            result = {
                "verified": False,
                "error": "PASSPORT_INACTIVE",
                "passport_id": str(passport_id),
                "status": passport.status
            }
            self._log_verification(passport_id, api_key_id, requesting_platform, required_badges, result, ip_address, user_agent)
            return result
        
        # Fetch and verify requested badges
        badges_response = []
        all_verified = True
        
        for badge_type in required_badges:
            badge = self.db.query(CredentialBadge).filter_by(
                passport_id=passport_id,
                badge_type=badge_type
            ).order_by(CredentialBadge.verified_at.desc()).first()
            
            if not badge or not badge.is_valid():
                badges_response.append({
                    "type": badge_type,
                    "verified": False,
                    "error": "BADGE_NOT_FOUND" if not badge else "BADGE_EXPIRED_OR_REVOKED"
                })
                all_verified = False
            else:
                # Verify cryptographic signature
                signature_valid = self.crypto_engine.verify_signature(
                    badge.credential_data,
                    badge.issuer_signature
                )
                
                if not signature_valid:
                    badges_response.append({
                        "type": badge_type,
                        "verified": False,
                        "error": "SIGNATURE_INVALID"
                    })
                    all_verified = False
                else:
                    badges_response.append({
                        "type": badge_type,
                        "verified": True,
                        "credential": badge.credential_data,
                        "verified_at": badge.verified_at.isoformat(),
                        "expires_at": badge.expires_at.isoformat() if badge.expires_at else None
                    })
        
        # Construct response
        result = {
            "verified": all_verified,
            "passport_id": str(passport_id),
            "trust_score": passport.trust_score,
            "badges": badges_response,
            "verification_token": self._generate_verification_token(passport_id)
        }
        
        # Log the verification
        self._log_verification(passport_id, api_key_id, requesting_platform, required_badges, result, ip_address, user_agent)
        
        return result
    
    def _generate_verification_token(self, passport_id: uuid.UUID) -> str:
        """
        Generate a one-time verification token for audit trails.
        
        Format: vtok_<timestamp>_<passport_id_prefix>_<random>
        """
        timestamp = int(datetime.now(timezone.utc).timestamp())
        passport_prefix = str(passport_id)[:8]
        random_suffix = base64.urlsafe_b64encode(os.urandom(12)).decode('utf-8').rstrip('=')
        return f"vtok_{timestamp}_{passport_prefix}_{random_suffix}"
    
    def _log_verification(
        self,
        passport_id: uuid.UUID,
        api_key_id: uuid.UUID,
        requesting_platform: str,
        requested_badges: List[str],
        result: Dict[str, Any],
        ip_address: Optional[str],
        user_agent: Optional[str]
    ):
        """
        Log verification request to audit trail.
        """
        log = VerificationLog(
            passport_id=passport_id,
            api_key_id=api_key_id,
            requesting_platform=requesting_platform,
            requested_badges=requested_badges,
            verification_result=result,
            timestamp=datetime.now(timezone.utc),
            ip_address=ip_address,
            user_agent=user_agent
        )
        self.db.add(log)
        self.db.commit()
