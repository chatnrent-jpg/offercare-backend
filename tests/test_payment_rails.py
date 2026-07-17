"""
Tests for VettedPay Multi-Rail Payment Infrastructure
"""

import pytest
from datetime import datetime, timezone
from app.services.payment_rails.compliance_packet import (
    CompliancePacketGenerator,
    CompliancePayload,
    ZKProof
)
from app.services.payment_rails.payout_adapter import PayoutRail, PayoutStatus
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


@pytest.fixture
def test_keypair():
    """Generate test RSA keypair"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    public_key_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode()
    
    return public_key_pem, private_key_pem


@pytest.fixture
def compliance_generator(test_keypair):
    """Create compliance packet generator with test keys"""
    public_key, _ = test_keypair
    
    return CompliancePacketGenerator(
        signing_key="test_signing_key_12345",
        recipient_public_keys={
            "test_bank": public_key
        },
        environment="sandbox"
    )


@pytest.fixture
def sample_compliance_payload():
    """Create sample compliance payload"""
    return CompliancePayload(
        provider_id="caregiver_test_123",
        full_name="Jane Smith",
        date_of_birth="1990-01-15",
        national_id="SSN-XXX-XX-1234",
        address={
            "street": "123 Main St",
            "city": "Baltimore",
            "state": "MD",
            "country": "US",
            "postal_code": "21201"
        },
        sanction_check_timestamp=datetime.now(timezone.utc).isoformat(),
        sanction_check_result="CLEAR",
        ofac_check=True,
        eu_sanctions_check=True,
        un_sanctions_check=True,
        source_of_funds="Employment income",
        purpose_of_payment="Healthcare services rendered",
        compliance_officer="compliance@vettedcare.ai"
    )


def test_zk_proof_generation(compliance_generator):
    """Test ZK-proof generation without revealing identity"""
    proof = compliance_generator.generate_zk_proof(
        provider_id="caregiver_123",
        sanction_check_result="CLEAR",
        verification_method="OFAC_API_v1"
    )
    
    assert isinstance(proof, ZKProof)
    assert proof.proof_hash is not None
    assert proof.provider_hash is not None
    assert proof.signature is not None
    assert proof.nonce is not None
    
    # Provider hash should not reveal original ID
    assert "caregiver_123" not in proof.provider_hash
    
    # Proof should be verifiable
    assert len(proof.proof_hash) == 64  # SHA-256 hex
    assert len(proof.signature) == 64  # HMAC-SHA256 hex


def test_payload_encryption(compliance_generator, sample_compliance_payload):
    """Test that payload is encrypted and server cannot read it"""
    encrypted_payload, key_fingerprint = compliance_generator.encrypt_payload(
        payload=sample_compliance_payload,
        recipient_id="test_bank"
    )
    
    # Encrypted payload should be base64
    assert isinstance(encrypted_payload, str)
    assert len(encrypted_payload) > 100
    
    # Should not contain plaintext PII
    assert "Jane Smith" not in encrypted_payload
    assert "SSN" not in encrypted_payload
    assert "Baltimore" not in encrypted_payload
    
    # Key fingerprint should be generated
    assert key_fingerprint is not None
    assert len(key_fingerprint) == 16


def test_complete_packet_generation(compliance_generator, sample_compliance_payload):
    """Test full compliance packet generation"""
    packet = compliance_generator.generate_packet(
        payload=sample_compliance_payload,
        recipient_id="test_bank",
        verification_method="OFAC_API_v1"
    )
    
    # Packet structure
    assert packet.packet_id is not None
    assert packet.version == "1.0.0"
    assert packet.created_at is not None
    assert packet.zk_proof is not None
    assert packet.encrypted_payload is not None
    assert packet.encryption_algorithm == "RSA-OAEP-SHA256"
    assert packet.packet_signature is not None
    
    # ZK-proof is present
    assert packet.zk_proof.proof_hash is not None
    assert packet.zk_proof.verification_method == "OFAC_API_v1"


def test_packet_signature_verification(compliance_generator, sample_compliance_payload):
    """Test packet signature prevents tampering"""
    packet = compliance_generator.generate_packet(
        payload=sample_compliance_payload,
        recipient_id="test_bank"
    )
    
    # Valid signature
    assert compliance_generator.verify_packet_signature(packet) is True
    
    # Tampered packet
    packet.encrypted_payload = "tampered_data"
    assert compliance_generator.verify_packet_signature(packet) is False


def test_packet_serialization(compliance_generator, sample_compliance_payload):
    """Test packet can be serialized for transmission"""
    packet = compliance_generator.generate_packet(
        payload=sample_compliance_payload,
        recipient_id="test_bank"
    )
    
    # Serialize
    serialized = compliance_generator.serialize_packet(packet)
    assert isinstance(serialized, str)
    assert len(serialized) > 100
    
    # Deserialize
    deserialized = CompliancePacketGenerator.deserialize_packet(serialized)
    assert deserialized.packet_id == packet.packet_id
    assert deserialized.version == packet.version
    assert deserialized.zk_proof.proof_hash == packet.zk_proof.proof_hash
    assert deserialized.encrypted_payload == packet.encrypted_payload


def test_multiple_recipient_keys(test_keypair):
    """Test supporting multiple bank public keys"""
    public_key, _ = test_keypair
    
    generator = CompliancePacketGenerator(
        signing_key="test_key",
        recipient_public_keys={
            "chase": public_key,
            "hsbc": public_key,
            "bofa": public_key,
        }
    )
    
    payload = CompliancePayload(
        provider_id="test",
        full_name="Test User",
        date_of_birth="1990-01-01",
        address={},
        sanction_check_timestamp=datetime.now(timezone.utc).isoformat(),
        sanction_check_result="CLEAR",
        ofac_check=True,
        eu_sanctions_check=True,
        un_sanctions_check=True,
        source_of_funds="Employment",
        purpose_of_payment="Services",
        compliance_officer="test@example.com"
    )
    
    # Should work with any recipient
    packet_chase = generator.generate_packet(payload, "chase")
    packet_hsbc = generator.generate_packet(payload, "hsbc")
    packet_bofa = generator.generate_packet(payload, "bofa")
    
    assert packet_chase.recipient_key_fingerprint is not None
    assert packet_hsbc.recipient_key_fingerprint is not None
    assert packet_bofa.recipient_key_fingerprint is not None


def test_missing_recipient_key(compliance_generator, sample_compliance_payload):
    """Test error when recipient key not found"""
    with pytest.raises(ValueError, match="No public key found"):
        compliance_generator.encrypt_payload(
            payload=sample_compliance_payload,
            recipient_id="nonexistent_bank"
        )


def test_zk_proof_uniqueness(compliance_generator):
    """Test that each proof is unique (due to nonce)"""
    proof1 = compliance_generator.generate_zk_proof(
        provider_id="same_provider",
        sanction_check_result="CLEAR",
        verification_method="OFAC_API_v1"
    )
    
    proof2 = compliance_generator.generate_zk_proof(
        provider_id="same_provider",
        sanction_check_result="CLEAR",
        verification_method="OFAC_API_v1"
    )
    
    # Different nonces = different hashes
    assert proof1.nonce != proof2.nonce
    assert proof1.proof_hash != proof2.proof_hash
    assert proof1.provider_hash != proof2.provider_hash


def test_sanction_check_results(compliance_generator):
    """Test different sanction check results"""
    results = ["CLEAR", "FLAGGED", "PENDING"]
    
    for result in results:
        proof = compliance_generator.generate_zk_proof(
            provider_id="test_provider",
            sanction_check_result=result,
            verification_method="OFAC_API_v1"
        )
        
        assert proof.proof_hash is not None
        # Proof hash should be different for different results
        # (even with same provider_id, due to nonce)
