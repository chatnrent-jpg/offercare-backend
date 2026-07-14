import pytest
from app.db.session import SessionLocal
from app.models import HealthcareCredential

@pytest.fixture
def db_transaction_context():
    """
    Creates an isolated database transaction window. 
    Guarantees every database mutation is completely rolled back after test completion.
    """
    connection = SessionLocal().bind.connect()
    transaction = connection.begin()
    
    # Bind a session to the open connection context
    db_session = SessionLocal(bind=connection)
    
    yield db_session
    
    # Teardown: Tear down data states cleanly to keep staging clean
    db_session.close()
    transaction.rollback()
    connection.close()

def test_database_credential_insertion_integrity(db_transaction_context):
    """
    Validates that model constraints operate correctly on Revision 039 tables 
    without causing persistent data leakage.
    """
    db = db_transaction_context
    
    # 1. Inject a transient test row
    test_cred = HealthcareCredential(
        id="tx-test-item-99",
        professional_name="Temporary Validation Target",
        license_type="GNA",
        license_number="G991823",
        state="MD",
        status="PENDING"
    )
    db.add(test_cred)
    db.commit()
    
    # 2. Query to prove data is available within the transaction window
    queried_item = db.query(HealthcareCredential).filter_by(id="tx-test-item-99").first()
    assert queried_item is not None
    assert queried_item.license_type == "GNA"
    
    # (Upon exit, the fixture rolls back this transaction completely)
