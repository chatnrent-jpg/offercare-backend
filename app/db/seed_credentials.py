"""
Healthcare Credential Database Seeding Script
Seeds realistic Maryland nursing credential variants for integration testing

This script populates the healthcare_credentials table (Revision 039) with
test data for MBON scraper and Twilio SMS engine integration testing.
"""

import logging
from datetime import datetime, timedelta, timezone
from app.database import SessionLocal
from app.models import HealthcareCredential

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DB_Seeder")


def seed_ohcq_test_data():
    """
    Seeds the healthcare_credentials table with realistic Maryland variant 
    records to test proxy-rotation tracking, scrapers, and alerting workflows.
    
    Test Data Coverage:
    - Unverified credentials (is_ohcq_verified=False)
    - Verified but not background checked
    - Multiple license types (RN, LPN, CNA)
    - Future expiration dates
    - Stale verification timestamps
    
    Edge Cases:
    - Pending check (null ohcq_verified_at)
    - Stale check (30 days old verification)
    - Ready for verification
    
    Note: Requires at least one MarylandProvider record to exist as foreign key
    """
    db = SessionLocal()
    
    try:
        # Import here to avoid circular dependencies
        from app.models import MarylandProvider
        import uuid
        
        # Get or create a test provider
        test_provider = db.query(MarylandProvider).filter(
            MarylandProvider.full_name.like("%Test Provider%")
        ).first()
        
        if not test_provider:
            logger.info("Creating test provider for credential seeding...")
            test_provider = MarylandProvider(
                provider_id=uuid.uuid4(),
                full_name="Test Provider - Seeded",
                email="test.provider.seed@example.com",
                phone_number="+15550100000",
                npi_number="9999999999",  # Test NPI
                md_license_number="MD-TEST-999999",
                state="MD",
                credential_type="RN",
            )
            db.add(test_provider)
            db.flush()  # Get provider_id
        
        provider_id = test_provider.provider_id
        logger.info(f"Using provider_id: {provider_id}")
        
        # Calculate timestamps
        stale_time = datetime.now(timezone.utc) - timedelta(days=30)
        future_expiry = datetime.now(timezone.utc).date() + timedelta(days=365)
        
        # 📋 1. Mock Data Variant Payload Definitions
        seed_records = [
            HealthcareCredential(
                provider_id=provider_id,
                license_type="RN",
                license_number="RN-TEST-234951",
                expiration_date=future_expiry,
                is_ohcq_verified=False,
                background_check_passed=False,
                ohcq_verified_at=None,  # Never verified
                verification_notes="Test RN - Pending verification"
            ),
            HealthcareCredential(
                provider_id=provider_id,
                license_type="LPN",
                license_number="LPN-TEST-098114",
                expiration_date=future_expiry,
                is_ohcq_verified=True,
                background_check_passed=False,
                ohcq_verified_at=stale_time,  # Stale verification
                verification_notes="Test LPN - Verified but no background check"
            ),
            HealthcareCredential(
                provider_id=provider_id,
                license_type="CNA",
                license_number="CNA-TEST-774123",
                expiration_date=future_expiry,
                is_ohcq_verified=True,
                background_check_passed=True,
                ohcq_verified_at=stale_time,
                background_check_completed_at=stale_time,
                verification_notes="Test CNA - Fully verified (stale)"
            )
        ]

        # Purge old seed credentials
        logger.info("Purging old seed credentials to guarantee test atomicity...")
        db.query(HealthcareCredential).filter(
            HealthcareCredential.license_number.like("%-TEST-%")
        ).delete(synchronize_session=False)

        logger.info(f"Injecting {len(seed_records)} pristine Maryland regulatory test rows...")
        db.add_all(seed_records)
        db.commit()
        
        logger.info("[OK] Database table seeding completed successfully under Revision 039 rules.")
        
        # Log summary of seeded data
        logger.info("")
        logger.info("Seeded Credentials Summary:")
        for record in seed_records:
            logger.info(
                f"  - {record.license_type} #{record.license_number} | "
                f"OHCQ Verified: {record.is_ohcq_verified} | "
                f"Background Check: {record.background_check_passed}"
            )
        
    except Exception as e:
        db.rollback()
        logger.error(f"[ERROR] Critical error executing seeding procedure: {str(e)}")
        raise e
    finally:
        db.close()


def clear_seed_data():
    """
    Removes all seeded test credentials from the database.
    Useful for cleanup after testing.
    """
    db = SessionLocal()
    
    try:
        logger.info("Removing all seed credentials...")
        deleted_count = db.query(HealthcareCredential).filter(
            HealthcareCredential.license_number.like("%-TEST-%")
        ).delete(synchronize_session=False)
        db.commit()
        
        logger.info(f"[OK] Removed {deleted_count} seed credential(s)")
        
    except Exception as e:
        db.rollback()
        logger.error(f"[ERROR] Error clearing seed data: {str(e)}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_ohcq_test_data()
