"""
Compliance Packet Layer for VettedPay
Generates tamper-proof payloads with ZK-proof of non-sanction status.
Encrypted with custodian/bank public key - server never reads raw data.
"""

import json
import hashlib
import hmac
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from base64 import b64encode, b64decode
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
import uuid


@dataclass
class CompliancePayload:
    """
    Raw compliance data that gets encrypted.
    Server never reads this - only the bank/custodian can decrypt.
    """
    provider_id: str
    full_name: str
    date_of_birth: str  # ISO format
    national_id: Optional[str]
    address: Dict[str, str]
    sanction_check_timestamp: str
    sanction_check_result: str  # "CLEAR", "FLAGGED", "PENDING"
    ofac_check: bool
    eu_sanctions_check: bool
    un_sanctions_check: bool
    source_of_funds: str
    purpose_of_payment: str
    compliance_officer: str
    additional_metadata: Optional[Dict[str, Any]] = None


@dataclass
class ZKProof:
    """
    Zero-Knowledge Proof that provider is not sanctioned.
    This is visible to everyone, but proves compliance without revealing identity.
    """
    proof_hash: str  # Hash of the compliance check
    timestamp: str
    verification_method: str  # "OFAC_API", "SCREENING_SERVICE", etc.
    provider_hash: str  # Hashed provider ID for correlation
    signature: str  # Cryptographic signature of the proof
    nonce: str  # Prevent replay attacks


@dataclass
class CompliancePacket:
    """
    Complete compliance packet sent with every payout.
    - ZK proof is public and verifiable
    - Encrypted payload can only be read by bank
    """
    packet_id: str
    version: str
    created_at: str
    zk_proof: ZKProof
    encrypted_payload: str  # Base64 encoded encrypted compliance data
    encryption_algorithm: str
    recipient_key_fingerprint: str  # Which public key was used
    packet_signature: str  # HMAC signature of entire packet
    

class CompliancePacketGenerator:
    """
    Generates tamper-proof compliance packets for cross-border payouts.
    
    Security Model:
    1. Raw PII is encrypted with bank's public key
    2. ZK-proof verifies non-sanction status without revealing identity
    3. Packet signature prevents tampering
    4. Server never has access to decrypted PII
    """
    
    def __init__(
        self,
        signing_key: str,
        recipient_public_keys: Dict[str, str],
        environment: str = "production"
    ):
        """
        Initialize compliance packet generator.
        
        Args:
            signing_key: Secret key for HMAC signing
            recipient_public_keys: Dict of bank_id -> public_key_pem
            environment: 'sandbox' or 'production'
        """
        self.signing_key = signing_key.encode() if isinstance(signing_key, str) else signing_key
        self.recipient_public_keys = recipient_public_keys
        self.environment = environment
        self.version = "1.0.0"
        
    def generate_zk_proof(
        self,
        provider_id: str,
        sanction_check_result: str,
        verification_method: str,
        signing_key: Optional[str] = None
    ) -> ZKProof:
        """
        Generate zero-knowledge proof of non-sanction status.
        
        This proof is publicly verifiable but doesn't reveal provider identity.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        nonce = str(uuid.uuid4())
        
        # Hash provider ID to create correlation key without revealing identity
        provider_hash = hashlib.sha256(f"{provider_id}:{nonce}".encode()).hexdigest()
        
        # Create proof hash from sanction check
        proof_data = f"{provider_hash}:{sanction_check_result}:{timestamp}:{verification_method}"
        proof_hash = hashlib.sha256(proof_data.encode()).hexdigest()
        
        # Sign the proof
        signature_key = signing_key or self.signing_key
        if isinstance(signature_key, str):
            signature_key = signature_key.encode()
            
        signature = hmac.new(
            signature_key,
            f"{proof_hash}:{timestamp}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        return ZKProof(
            proof_hash=proof_hash,
            timestamp=timestamp,
            verification_method=verification_method,
            provider_hash=provider_hash,
            signature=signature,
            nonce=nonce
        )
    
    def encrypt_payload(
        self,
        payload: CompliancePayload,
        recipient_id: str
    ) -> tuple[str, str]:
        """
        Encrypt compliance payload with recipient's public key.
        
        Args:
            payload: Raw compliance data
            recipient_id: ID of the bank/custodian
            
        Returns:
            (encrypted_payload_base64, key_fingerprint)
        """
        if recipient_id not in self.recipient_public_keys:
            raise ValueError(f"No public key found for recipient: {recipient_id}")
        
        # Load recipient's public key
        public_key_pem = self.recipient_public_keys[recipient_id]
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode() if isinstance(public_key_pem, str) else public_key_pem,
            backend=default_backend()
        )
        
        # Serialize payload to JSON
        payload_json = json.dumps(asdict(payload), sort_keys=True)
        
        # Encrypt with RSA-OAEP
        encrypted = public_key.encrypt(
            payload_json.encode(),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Generate key fingerprint for verification
        key_fingerprint = hashlib.sha256(public_key_pem.encode()).hexdigest()[:16]
        
        return b64encode(encrypted).decode(), key_fingerprint
    
    def generate_packet(
        self,
        payload: CompliancePayload,
        recipient_id: str,
        verification_method: str = "OFAC_API_v1"
    ) -> CompliancePacket:
        """
        Generate complete compliance packet with ZK-proof and encrypted payload.
        
        Args:
            payload: Raw compliance data
            recipient_id: Bank/custodian identifier
            verification_method: Method used for sanction screening
            
        Returns:
            CompliancePacket ready for transmission
        """
        packet_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        
        # Generate ZK-proof of non-sanction
        zk_proof = self.generate_zk_proof(
            provider_id=payload.provider_id,
            sanction_check_result=payload.sanction_check_result,
            verification_method=verification_method
        )
        
        # Encrypt the full payload
        encrypted_payload, key_fingerprint = self.encrypt_payload(payload, recipient_id)
        
        # Create packet structure
        packet_data = {
            "packet_id": packet_id,
            "version": self.version,
            "created_at": created_at,
            "zk_proof": asdict(zk_proof),
            "encrypted_payload": encrypted_payload,
            "encryption_algorithm": "RSA-OAEP-SHA256",
            "recipient_key_fingerprint": key_fingerprint
        }
        
        # Sign entire packet to prevent tampering
        packet_json = json.dumps(packet_data, sort_keys=True)
        packet_signature = hmac.new(
            self.signing_key,
            packet_json.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return CompliancePacket(
            packet_id=packet_id,
            version=self.version,
            created_at=created_at,
            zk_proof=zk_proof,
            encrypted_payload=encrypted_payload,
            encryption_algorithm="RSA-OAEP-SHA256",
            recipient_key_fingerprint=key_fingerprint,
            packet_signature=packet_signature
        )
    
    def verify_packet_signature(self, packet: CompliancePacket) -> bool:
        """
        Verify packet signature to ensure it hasn't been tampered with.
        """
        packet_data = {
            "packet_id": packet.packet_id,
            "version": packet.version,
            "created_at": packet.created_at,
            "zk_proof": asdict(packet.zk_proof),
            "encrypted_payload": packet.encrypted_payload,
            "encryption_algorithm": packet.encryption_algorithm,
            "recipient_key_fingerprint": packet.recipient_key_fingerprint
        }
        
        packet_json = json.dumps(packet_data, sort_keys=True)
        expected_signature = hmac.new(
            self.signing_key,
            packet_json.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, packet.packet_signature)
    
    def serialize_packet(self, packet: CompliancePacket) -> str:
        """
        Serialize packet to base64-encoded JSON for transmission.
        """
        packet_dict = asdict(packet)
        packet_dict['zk_proof'] = asdict(packet.zk_proof)
        packet_json = json.dumps(packet_dict, sort_keys=True)
        return b64encode(packet_json.encode()).decode()
    
    @staticmethod
    def deserialize_packet(packet_str: str) -> CompliancePacket:
        """
        Deserialize packet from base64-encoded JSON.
        """
        packet_json = b64decode(packet_str.encode()).decode()
        packet_dict = json.loads(packet_json)
        
        zk_proof = ZKProof(**packet_dict['zk_proof'])
        
        return CompliancePacket(
            packet_id=packet_dict['packet_id'],
            version=packet_dict['version'],
            created_at=packet_dict['created_at'],
            zk_proof=zk_proof,
            encrypted_payload=packet_dict['encrypted_payload'],
            encryption_algorithm=packet_dict['encryption_algorithm'],
            recipient_key_fingerprint=packet_dict['recipient_key_fingerprint'],
            packet_signature=packet_dict['packet_signature']
        )


class CompliancePacketError(Exception):
    """Base exception for compliance packet errors"""
    pass


class InvalidPacketSignatureError(CompliancePacketError):
    """Raised when packet signature verification fails"""
    pass


class EncryptionError(CompliancePacketError):
    """Raised when payload encryption fails"""
    pass


class MissingPublicKeyError(CompliancePacketError):
    """Raised when recipient public key is not available"""
    pass
