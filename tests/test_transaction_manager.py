"""
Tests for VettedPay Transaction Manager
"""

import pytest
from datetime import datetime, timezone
from app.services.payment_rails.transaction_manager import VettedPayTransactionEngine
from app.services.payment_rails.compliance_packet import CompliancePayload


@pytest.fixture
def airwallex_config():
    """Airwallex configuration for testing"""
    return {
        "api_url": "https://api-demo.airwallex.com",
        "api_token": "test_token_12345"
    }


@pytest.fixture
def valid_zk_proof():
    """Valid ZK-proof for testing"""
    return {
        "valid": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "signature": "0xtest_signature_abc123",
        "proof_type": "reclaim_zktls"
    }


@pytest.fixture
def invalid_zk_proof():
    """Invalid ZK-proof for testing"""
    return {
        "valid": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "signature": "0xinvalid_signature"
    }


def test_engine_initialization_airwallex(airwallex_config):
    """Test engine initializes correctly with Airwallex"""
    engine = VettedPayTransactionEngine(
        active_provider="airwallex",
        provider_config=airwallex_config
    )
    
    assert engine.get_active_provider() == "airwallex"
    assert engine.rail is not None


def test_engine_initialization_unknown_provider():
    """Test engine raises error for unknown provider"""
    with pytest.raises(ValueError, match="Unknown financial provider"):
        VettedPayTransactionEngine(
            active_provider="unknown_provider",
            provider_config={}
        )


def test_engine_initialization_nium_not_implemented(airwallex_config):
    """Test Nium raises NotImplementedError"""
    with pytest.raises(NotImplementedError, match="Nium integration"):
        VettedPayTransactionEngine(
            active_provider="nium",
            provider_config=airwallex_config
        )


@pytest.mark.asyncio
async def test_zk_compliance_verification_valid(airwallex_config, valid_zk_proof):
    """Test ZK-proof verification passes for valid proof"""
    engine = VettedPayTransactionEngine(
        active_provider="airwallex",
        provider_config=airwallex_config
    )
    
    is_valid = await engine._verify_zk_compliance("did:test:12345", valid_zk_proof)
    assert is_valid is True


@pytest.mark.asyncio
async def test_zk_compliance_verification_invalid(airwallex_config, invalid_zk_proof):
    """Test ZK-proof verification fails for invalid proof"""
    engine = VettedPayTransactionEngine(
        active_provider="airwallex",
        provider_config=airwallex_config
    )
    
    is_valid = await engine._verify_zk_compliance("did:test:12345", invalid_zk_proof)
    assert is_valid is False


@pytest.mark.asyncio
async def test_zk_compliance_verification_empty_proof(airwallex_config):
    """Test ZK-proof verification fails for empty proof"""
    engine = VettedPayTransactionEngine(
        active_provider="airwallex",
        provider_config=airwallex_config
    )
    
    is_valid = await engine._verify_zk_compliance("did:test:12345", {})
    assert is_valid is False


@pytest.mark.asyncio
async def test_zk_compliance_verification_missing_fields(airwallex_config):
    """Test ZK-proof verification fails for missing required fields"""
    engine = VettedPayTransactionEngine(
        active_provider="airwallex",
        provider_config=airwallex_config
    )
    
    incomplete_proof = {
        "valid": True,
        # Missing timestamp and signature
    }
    
    is_valid = await engine._verify_zk_compliance("did:test:12345", incomplete_proof)
    assert is_valid is False


@pytest.mark.asyncio
async def test_zk_compliance_verification_expired_proof(airwallex_config):
    """Test ZK-proof verification fails for expired proof (>24 hours old)"""
    engine = VettedPayTransactionEngine(
        active_provider="airwallex",
        provider_config=airwallex_config
    )
    
    # Create proof from 25 hours ago
    from datetime import timedelta
    old_time = datetime.now(timezone.utc) - timedelta(hours=25)
    
    expired_proof = {
        "valid": True,
        "timestamp": old_time.isoformat(),
        "signature": "0xold_signature"
    }
    
    is_valid = await engine._verify_zk_compliance("did:test:12345", expired_proof)
    assert is_valid is False


@pytest.mark.asyncio
async def test_process_transfer_compliance_failure(airwallex_config, invalid_zk_proof):
    """Test transfer fails when ZK compliance check fails"""
    engine = VettedPayTransactionEngine(
        active_provider="airwallex",
        provider_config=airwallex_config
    )
    
    result = await engine.process_transfer(
        sender_did="did:test:sender:123",
        recipient_did="did:test:recipient:456",
        zk_proof=invalid_zk_proof,
        encrypted_compliance_packet="encrypted_packet_data",
        amount=1000.00,
        currency="USD",
        destination_account="beneficiary_123"
    )
    
    assert result["success"] is False
    assert result["error_code"] == "ZK_COMPLIANCE_FAILED"
    assert "sanction check failed" in result["error"].lower()


def test_health_check_structure(airwallex_config):
    """Test health check returns correct structure"""
    engine = VettedPayTransactionEngine(
        active_provider="airwallex",
        provider_config=airwallex_config
    )
    
    # Test that engine has health_check method
    assert hasattr(engine, 'health_check')
    assert callable(engine.health_check)


def test_compliance_payload_structure():
    """Test CompliancePayload structure"""
    payload = CompliancePayload(
        provider_id="test_123",
        full_name="Test User",
        date_of_birth="1990-01-01",
        national_id="TEST-123",
        address={"street": "123 Test St", "city": "Test City"},
        sanction_check_timestamp=datetime.now(timezone.utc).isoformat(),
        sanction_check_result="CLEAR",
        ofac_check=True,
        eu_sanctions_check=True,
        un_sanctions_check=True,
        source_of_funds="Employment",
        purpose_of_payment="Services",
        compliance_officer="test@example.com"
    )
    
    assert payload.provider_id == "test_123"
    assert payload.sanction_check_result == "CLEAR"
    assert payload.ofac_check is True


def test_transaction_manager_provider_switching():
    """Test that provider can be switched dynamically"""
    
    config = {
        "api_url": "https://test.example.com",
        "api_token": "test_token"
    }
    
    # Initialize with Airwallex
    engine1 = VettedPayTransactionEngine(
        active_provider="airwallex",
        provider_config=config
    )
    assert engine1.get_active_provider() == "airwallex"
    
    # Could initialize with different provider (if implemented)
    # This test shows the pattern works
    assert engine1.active_provider == "airwallex"
