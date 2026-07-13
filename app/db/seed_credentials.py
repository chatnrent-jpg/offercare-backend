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
    - PENDING status (never verified)
    - ACTIVE status with stale verification
    - Multiple license types (RN, LPN, CNA)
    - Different facilities
    - Test phone numbers for Twilio
    
    Edge Cases:
    - Pending check (null last_verified_at)
    - Stale check (30 days old)
    - Active credentials ready for verification
    """
    db = SessionLocal()
    
    # Calculate a stale timestamp (e.g., last checked 30 days ago)
    stale_time = datetime.now(timezone.utc) - timedelta(days=30)
    
    # 📋 1. Mock Data Variant Payload Definitions
    seed_records = [
        HealthcareCredential(
            id="cred-seed-md-01",
            professional_name="Sarah Jenkins, RN",
            license_type="RN",
            license_number="R234951",
            state="MD",
            status="PENDING",
            facility_name="Johns Hopkins Hospital",
            phone_number="+15550199111",  # Targets Twilio testing
            last_verified_at=None
        ),
        HealthcareCredential(
            id="cred-seed-md-02",
            professional_name="Michael Chang, LPN",
            license_type="LPN",
            license_number="L098114",
            state="MD",
            status="ACTIVE",
            facility_name="University of Maryland Medical Center",
            phone_number="+15550199222",
            last_verified_at=stale_time
        ),
        HealthcareCredential(
            id="cred-seed-md-03",
            professional_name="Elena Rostova, CNA",
            license_type="CNA",
            license_number="A774123",
            state="MD",
            status="ACTIVE",
            facility_name="Levindale Behavioral Health",
            phone_number="+15550199333",
            last_verified_at=stale_time
        )
    ]

    try:
        logger.info("Purging old seed credentials to guarantee test atomicity...")
        db.query(HealthcareCredential).filter(
            HealthcareCredential.id.like("cred-seed-md-%")
        ).delete(synchronize_session=False)

        logger.info(f"Injecting {len(seed_records)} pristine Maryland regulatory test rows...")
        db.add_all(seed_records)
        db.commit()
        
        logger.info("✅ Database table seeding completed successfully under Revision 039 rules.")
        
        # Log summary of seeded data
        logger.info("")
        logger.info("Seeded Credentials Summary:")
        for record in seed_records:
            logger.info(
                f"  - {record.professional_name} | {record.license_type} #{record.license_number} | "
                f"Status: {record.status} | Phone: {record.phone_number}"
            )
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Critical error executing seeding procedure: {str(e)}")
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
            HealthcareCredential.id.like("cred-seed-md-%")
        ).delete(synchronize_session=False)
        db.commit()
        
        logger.info(f"✅ Removed {deleted_count} seed credential(s)")
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error clearing seed data: {str(e)}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_ohcq_test_data()
