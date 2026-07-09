"""
Test suite for Invoice Encryption Service.

Sprint: VCAI-ENCRYPTION-LAYER-2026-07-07
Coverage: Field-level encryption, decryption, key management
"""

import pytest
from cryptography.fernet import Fernet

from app.services.invoice_encryption import (
    InvoiceEncryptionService,
    encrypt_invoice,
    decrypt_invoice,
)


@pytest.fixture
def encryption_service():
    """Create encryption service with test key."""
    service = InvoiceEncryptionService()
    # Force enable encryption for testing
    service.encryption_enabled = True
    service.cipher = Fernet(Fernet.generate_key())
    return service


@pytest.fixture
def sample_invoice():
    """Sample invoice data."""
    return {
        "hours_worked": 8.0,
        "gross_caregiver_pay_rate": 25.0,
        "margin_pct": 0.40,
        "employer_fica_rate": 0.0765,
        "gross_pay": 200.0,
        "platform_margin": 80.0,
        "employer_taxes": 15.30,
        "total_facility_bill": 295.30,
        "timesheet_id": "test-timesheet-id",
        "provider_id": "test-provider-id",
        "facility_id": "test-facility-id",
        "invoice_payload_json": {"test": "data"}
    }


class TestInvoiceEncryptionService:
    """Test encryption service core functionality."""
    
    def test_encrypt_invoice_payload(self, encryption_service, sample_invoice):
        """Test encrypting invoice payload."""
        encrypted = encryption_service.encrypt_invoice_payload(sample_invoice)
        
        # Check encryption flag is set
        assert encrypted["_encrypted"] is True
        assert "_encryption_timestamp" in encrypted
        
        # Check sensitive fields are encrypted (should be strings, not numbers)
        assert isinstance(encrypted["gross_pay"], str)
        assert isinstance(encrypted["platform_margin"], str)
        assert isinstance(encrypted["employer_taxes"], str)
        assert isinstance(encrypted["total_facility_bill"], str)
        
        # Check non-sensitive fields are unchanged
        assert encrypted["timesheet_id"] == sample_invoice["timesheet_id"]
        assert encrypted["provider_id"] == sample_invoice["provider_id"]
    
    def test_decrypt_invoice_payload(self, encryption_service, sample_invoice):
        """Test decrypting invoice payload."""
        # Encrypt first
        encrypted = encryption_service.encrypt_invoice_payload(sample_invoice)
        
        # Then decrypt
        decrypted = encryption_service.decrypt_invoice_payload(encrypted)
        
        # Check sensitive fields are decrypted correctly
        assert abs(decrypted["gross_pay"] - sample_invoice["gross_pay"]) < 0.01
        assert abs(decrypted["platform_margin"] - sample_invoice["platform_margin"]) < 0.01
        assert abs(decrypted["employer_taxes"] - sample_invoice["employer_taxes"]) < 0.01
        assert abs(decrypted["total_facility_bill"] - sample_invoice["total_facility_bill"]) < 0.01
        
        # Check encryption metadata is removed
        assert "_encrypted" not in decrypted
        assert "_encryption_timestamp" not in decrypted
    
    def test_encrypt_decrypt_roundtrip(self, encryption_service, sample_invoice):
        """Test full encrypt-decrypt roundtrip."""
        encrypted = encryption_service.encrypt_invoice_payload(sample_invoice)
        decrypted = encryption_service.decrypt_invoice_payload(encrypted)
        
        # All sensitive numerical fields should match
        for field in ["gross_pay", "platform_margin", "employer_taxes", "total_facility_bill"]:
            assert abs(decrypted[field] - sample_invoice[field]) < 0.01
    
    def test_encrypt_field(self, encryption_service):
        """Test encrypting single field."""
        cleartext = "sensitive_data"
        encrypted = encryption_service.encrypt_field(cleartext)
        
        assert isinstance(encrypted, str)
        assert encrypted != cleartext
    
    def test_decrypt_field(self, encryption_service):
        """Test decrypting single field."""
        cleartext = "sensitive_data"
        encrypted = encryption_service.encrypt_field(cleartext)
        decrypted = encryption_service.decrypt_field(encrypted)
        
        assert decrypted == cleartext
    
    def test_encryption_disabled(self, sample_invoice):
        """Test that encryption can be disabled."""
        service = InvoiceEncryptionService()
        service.encryption_enabled = False
        service.cipher = None
        
        result = service.encrypt_invoice_payload(sample_invoice)
        
        # Should return unchanged data
        assert result == sample_invoice
        assert "_encrypted" not in result
    
    def test_decrypt_unencrypted_data(self, encryption_service, sample_invoice):
        """Test decrypting data that wasn't encrypted."""
        # Should return data unchanged
        result = encryption_service.decrypt_invoice_payload(sample_invoice)
        assert result == sample_invoice
    
    def test_invalid_token_handling(self, sample_invoice):
        """Test handling of invalid encryption tokens."""
        # Create two services with different keys
        service1 = InvoiceEncryptionService()
        service1.encryption_enabled = True
        service1.cipher = Fernet(Fernet.generate_key())
        
        service2 = InvoiceEncryptionService()
        service2.encryption_enabled = True
        service2.cipher = Fernet(Fernet.generate_key())  # Different key
        
        # Encrypt with service1
        encrypted = service1.encrypt_invoice_payload(sample_invoice)
        
        # Try to decrypt with service2 (different key)
        decrypted = service2.decrypt_invoice_payload(encrypted)
        
        # Should return None for fields that couldn't be decrypted
        assert decrypted["gross_pay"] is None


class TestConvenienceFunctions:
    """Test convenience wrapper functions."""
    
    def test_encrypt_invoice_function(self, sample_invoice):
        """Test encrypt_invoice convenience function."""
        encrypted = encrypt_invoice(sample_invoice)
        
        # Should have encryption metadata if encryption is enabled
        # (depends on global config, so we just check it doesn't crash)
        assert encrypted is not None
    
    def test_decrypt_invoice_function(self, sample_invoice):
        """Test decrypt_invoice convenience function."""
        decrypted = decrypt_invoice(sample_invoice)
        
        # Should return data (encrypted or not)
        assert decrypted is not None


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_null_values(self, encryption_service):
        """Test handling of null values."""
        data = {
            "gross_pay": None,
            "platform_margin": None,
            "total_facility_bill": 100.0,
        }
        
        encrypted = encryption_service.encrypt_invoice_payload(data)
        decrypted = encryption_service.decrypt_invoice_payload(encrypted)
        
        # Null values should remain null
        assert decrypted["gross_pay"] is None
        assert decrypted["platform_margin"] is None
        assert abs(decrypted["total_facility_bill"] - 100.0) < 0.01
    
    def test_empty_invoice(self, encryption_service):
        """Test handling of empty invoice."""
        data = {}
        
        encrypted = encryption_service.encrypt_invoice_payload(data)
        decrypted = encryption_service.decrypt_invoice_payload(encrypted)
        
        # Should handle gracefully
        assert decrypted is not None
    
    def test_large_values(self, encryption_service):
        """Test encryption of large monetary values."""
        data = {
            "gross_pay": 999999.99,
            "platform_margin": 500000.50,
            "employer_taxes": 75000.00,
            "total_facility_bill": 1574999.99,
        }
        
        encrypted = encryption_service.encrypt_invoice_payload(data)
        decrypted = encryption_service.decrypt_invoice_payload(encrypted)
        
        # Large values should encrypt/decrypt correctly
        for field in data.keys():
            assert abs(decrypted[field] - data[field]) < 0.01
    
    def test_precision_maintained(self, encryption_service):
        """Test that decimal precision is maintained."""
        data = {
            "gross_pay": 200.123456,
            "platform_margin": 80.654321,
        }
        
        encrypted = encryption_service.encrypt_invoice_payload(data)
        decrypted = encryption_service.decrypt_invoice_payload(encrypted)
        
        # Precision should be maintained (within floating point limits)
        assert abs(decrypted["gross_pay"] - data["gross_pay"]) < 0.0001
        assert abs(decrypted["platform_margin"] - data["platform_margin"]) < 0.0001
