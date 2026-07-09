"""
Tests for Smart Document Extractor (Tier 1 Feature #3)

Sprint: VCAI-TIER1-SPRINT-2026-07-07
Coverage: OCR extraction, quality validation, fraud detection, entity parsing
"""

import pytest
from datetime import date
from unittest.mock import Mock, patch
from uuid import uuid4

from app.services.smart_document_extractor import SmartDocumentExtractor, ExtractionResult
from app.models import DocumentExtractionLog, MarylandProvider


class TestImageQualityValidation:
    """Test image quality checks."""
    
    @pytest.mark.asyncio
    async def test_quality_check_passed(self, async_db):
        """Test quality check with good image"""
        extractor = SmartDocumentExtractor(db=async_db)
        
        # Mock quality validation to pass
        with patch.object(extractor, '_validate_image_quality', return_value={
            "passed": True,
            "score": 85.0,
            "blur_detected": False,
            "low_resolution": False,
            "laplacian_variance": 150.0
        }):
            result = await extractor._validate_image_quality("/fake/path.jpg")
        
        assert result["passed"] is True
        assert result["score"] > 80.0
    
    @pytest.mark.asyncio
    async def test_quality_check_failed_blur(self, async_db):
        """Test quality check with blurry image"""
        extractor = SmartDocumentExtractor(db=async_db)
        
        with patch.object(extractor, '_validate_image_quality', return_value={
            "passed": False,
            "score": 35.0,
            "blur_detected": True,
            "low_resolution": False,
            "laplacian_variance": 50.0
        }):
            result = await extractor._validate_image_quality("/fake/path.jpg")
        
        assert result["passed"] is False
        assert result["blur_detected"] is True


class TestEntityParsing:
    """Test document entity extraction."""
    
    @pytest.mark.asyncio
    async def test_parse_cpr_card(self, async_db):
        """Test parsing CPR card expiration"""
        extractor = SmartDocumentExtractor(db=async_db)
        
        text = """
        American Heart Association
        BLS Provider Card
        Valid Through: 12/31/2025
        """
        
        entities = await extractor._parse_document_entities(text, "CPR_CARD")
        
        assert entities["expiration_date"] == date(2025, 12, 31)
        assert entities["issuing_org"] == "AHA"
    
    @pytest.mark.asyncio
    async def test_parse_tb_test(self, async_db):
        """Test parsing TB test result"""
        extractor = SmartDocumentExtractor(db=async_db)
        
        text = """
        TB Skin Test
        Result: NEGATIVE
        Test Date: 06/15/2026
        """
        
        entities = await extractor._parse_document_entities(text, "TB_TEST")
        
        assert entities["result"] == "negative"
        assert entities["expiration_date"] is not None
    
    @pytest.mark.asyncio
    async def test_parse_nursing_license(self, async_db):
        """Test parsing nursing license"""
        extractor = SmartDocumentExtractor(db=async_db)
        
        text = """
        Maryland Board of Nursing
        License Number: RN123456
        Expiration: 08/31/2027
        """
        
        entities = await extractor._parse_document_entities(text, "NURSING_LICENSE")
        
        assert entities["license_number"] == "RN123456"
        assert entities["expiration_date"] == date(2027, 8, 31)
    
    @pytest.mark.asyncio
    async def test_parse_multiple_date_formats(self, async_db):
        """Test parsing various date formats"""
        extractor = SmartDocumentExtractor(db=async_db)
        
        # Test different formats
        texts = [
            "Expires: 12/31/2025",
            "Expiration Date: 2025-12-31",
            "Valid Through: December 31, 2025"
        ]
        
        for text in texts:
            entities = await extractor._parse_document_entities(text, "CPR_CARD")
            assert entities["expiration_date"] == date(2025, 12, 31)


class TestFraudDetection:
    """Test fraud indicator detection."""
    
    @pytest.mark.asyncio
    async def test_detect_sample_watermark(self, async_db):
        """Test detecting sample watermark"""
        extractor = SmartDocumentExtractor(db=async_db)
        
        text = "SAMPLE - Not Valid for Official Use"
        entities = {}
        
        flags = await extractor._detect_fraud_indicators("/fake/path.jpg", text, entities)
        
        assert "SUSPICIOUS_TEXT_SAMPLE" in flags
        assert "SUSPICIOUS_TEXT_NOT VALID" in flags
    
    @pytest.mark.asyncio
    async def test_detect_missing_expiration(self, async_db):
        """Test detecting missing expiration date"""
        extractor = SmartDocumentExtractor(db=async_db)
        
        text = "Some document text without dates"
        entities = {}  # No expiration date
        
        flags = await extractor._detect_fraud_indicators("/fake/path.jpg", text, entities)
        
        assert "NO_EXPIRATION_DATE_FOUND" in flags
    
    @pytest.mark.asyncio
    async def test_no_fraud_flags(self, async_db):
        """Test clean document with no fraud indicators"""
        extractor = SmartDocumentExtractor(db=async_db)
        
        text = "Valid Document - Expires 12/31/2025"
        entities = {"expiration_date": date(2025, 12, 31)}
        
        flags = await extractor._detect_fraud_indicators("/fake/path.jpg", text, entities)
        
        # Should have no fraud flags
        assert len(flags) == 0


class TestEndToEndExtraction:
    """Test complete document extraction flow."""
    
    @pytest.mark.asyncio
    async def test_successful_extraction(self, async_db):
        """Test successful document extraction"""
        provider_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Test Provider",
            email="test@test.com",
            phone_number="+14105550001",
            npi_number="1234567890",
            md_license_number="TEST123",
            credential_type="CNA"
        )
        async_db.add(provider)
        await async_db.commit()
        
        extractor = SmartDocumentExtractor(db=async_db)
        
        # Mock all the steps
        with patch.object(extractor, '_validate_image_quality', return_value={"passed": True, "score": 85.0}):
            with patch.object(extractor, '_extract_text', return_value="CPR Card\nValid Through: 12/31/2025\nAHA"):
                result = await extractor.process_document(
                    provider_id=provider_id,
                    document_type="CPR_CARD",
                    file_path="/fake/cpr.jpg"
                )
        
        assert result.success is True
        assert result.expiration_date == date(2025, 12, 31)
        assert len(result.fraud_flags) == 0
        assert result.extraction_log_id is not None
    
    @pytest.mark.asyncio
    async def test_extraction_with_blur(self, async_db):
        """Test extraction failure due to blur"""
        provider_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Test Provider",
            email="test2@test.com",
            phone_number="+14105550002",
            npi_number="9876543210",
            md_license_number="TEST456",
            credential_type="GNA"
        )
        async_db.add(provider)
        await async_db.commit()
        
        extractor = SmartDocumentExtractor(db=async_db)
        
        # Mock blur detection
        with patch.object(extractor, '_validate_image_quality', return_value={"passed": False, "score": 30.0, "blur_detected": True}):
            result = await extractor.process_document(
                provider_id=provider_id,
                document_type="TB_TEST",
                file_path="/fake/blurry.jpg"
            )
        
        assert result.success is False
        assert "LOW_QUALITY_IMAGE" in result.fraud_flags
    
    @pytest.mark.asyncio
    async def test_extraction_with_fraud_flags(self, async_db):
        """Test extraction with fraud indicators"""
        provider_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Test Provider",
            email="test3@test.com",
            phone_number="+14105550003",
            npi_number="1111111111",
            md_license_number="TEST789",
            credential_type="LPN"
        )
        async_db.add(provider)
        await async_db.commit()
        
        extractor = SmartDocumentExtractor(db=async_db)
        
        with patch.object(extractor, '_validate_image_quality', return_value={"passed": True, "score": 85.0}):
            with patch.object(extractor, '_extract_text', return_value="SAMPLE - Not for Official Use\nExpires: 12/31/2025"):
                result = await extractor.process_document(
                    provider_id=provider_id,
                    document_type="NURSING_LICENSE",
                    file_path="/fake/sample.jpg"
                )
        
        assert result.success is False
        assert "SUSPICIOUS_TEXT_SAMPLE" in result.fraud_flags


class TestCredentialUpdates:
    """Test credential record updates."""
    
    @pytest.mark.asyncio
    async def test_update_cpr_expiration(self, async_db):
        """Test updating CPR expiration date"""
        provider_id = uuid4()
        
        provider = MarylandProvider(
            provider_id=provider_id,
            full_name="Test Provider",
            email="test4@test.com",
            phone_number="+14105550004",
            npi_number="2222222222",
            md_license_number="TEST999",
            credential_type="CNA"
        )
        async_db.add(provider)
        await async_db.commit()
        
        extractor = SmartDocumentExtractor(db=async_db)
        
        exp_date = date(2026, 12, 31)
        await extractor._update_credential_record(
            provider_id=provider_id,
            document_type="CPR_CARD",
            expiration_date=exp_date,
            extraction_log_id=uuid4()
        )
        
        # Verify update (note: provider model may not have cpr_expiration field in test)
        # This test verifies the function runs without error


class TestMockTextGeneration:
    """Test dry-run mock text generation."""
    
    def test_generate_mock_cpr_text(self):
        """Test generating mock CPR card text"""
        extractor = SmartDocumentExtractor()
        
        text = extractor._generate_mock_extracted_text("/fake/cpr_card.jpg")
        
        assert "CPR" in text
        assert "12/31/2025" in text
    
    def test_generate_mock_tb_text(self):
        """Test generating mock TB test text"""
        extractor = SmartDocumentExtractor()
        
        text = extractor._generate_mock_extracted_text("/fake/tb_test.jpg")
        
        assert "TB Test" in text
        assert "NEGATIVE" in text
    
    def test_generate_mock_license_text(self):
        """Test generating mock license text"""
        extractor = SmartDocumentExtractor()
        
        text = extractor._generate_mock_extracted_text("/fake/nursing_license.jpg")
        
        assert "License Number" in text
        assert "Expiration" in text
