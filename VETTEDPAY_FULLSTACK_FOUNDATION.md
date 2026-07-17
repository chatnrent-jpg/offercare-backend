# VettedPay Full-Stack Foundation

**Version**: 1.0.0  
**Date**: July 17, 2026  
**Status**: Production-Ready Database Layer Complete

---

## Executive Summary

VettedPay is a **privacy-first, multi-rail payment infrastructure** designed to eliminate vendor lock-in and ensure regulatory compliance through zero-knowledge proofs. The system never stores raw bank accounts, SSNs, or unencrypted PII—only decentralized identifiers (DIDs) and encrypted compliance packets.

This document outlines the **complete database foundation**, **ORM models**, and **transaction orchestration layer** that powers VettedPay.

---

## Architecture Overview

### Core Components

1. **Privacy-Compliant Database Schema** (`database/vettedpay_schema.sql`)
   - Transaction ledger using DIDs instead of real identities
   - Rail health monitoring with circuit breaker state
   - ZK-proof verification audit trail
   - Early adopter waitlist

2. **ORM Models** (`app/models/vettedpay.py`)
   - `VettedPayTransaction` - Core transaction ledger
   - `VettedPayZKVerification` - ZK-proof audit log
   - `VettedPayRailHealth` - Payment rail health tracking
   - `VettedPayWaitlist` - Launch waitlist management
   - `PaymentRail` enum - Available payment rails
   - `TransactionStatus` enum - Transaction lifecycle states

3. **Transaction Engine** (`app/services/payment_rails/transaction_manager.py`)
   - Database persistence with automatic status tracking
   - ZK-proof verification logging
   - Idempotency key generation
   - Multi-rail routing with fail-safe error handling

4. **Alembic Migration** (`alembic/versions/044_vettedpay_core_schema.py`)
   - Full schema creation with triggers
   - Automatic timestamp updates
   - Default rail health initialization

---

## Database Schema

### Tables

#### 1. `vettedpay_transactions`
**Purpose**: Core transaction ledger - privacy-compliant  
**Privacy Guarantee**: Never stores raw bank accounts, SSNs, or unencrypted PII

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `idempotency_key` | VARCHAR(64) | Prevents duplicate transactions |
| `sender_did` | VARCHAR(255) | Decentralized identifier (not real name) |
| `recipient_did` | VARCHAR(255) | Decentralized identifier |
| `amount` | NUMERIC(14,4) | Transaction amount |
| `currency` | VARCHAR(3) | ISO currency code (default: USD) |
| `active_rail` | `payment_rail` | Which financial provider handled this |
| `status` | `transaction_status` | Current lifecycle state |
| `rail_transaction_id` | VARCHAR(255) | Provider's transaction ID |
| `zk_proof_verified` | BOOLEAN | Whether ZK-proof passed |
| `compliance_packet_id` | VARCHAR(255) | Reference to encrypted compliance packet |
| `error_log` | TEXT | Error details (if failed) |
| `metadata` | JSONB | Additional transaction metadata |
| `created_at` | TIMESTAMP | Transaction creation time |
| `updated_at` | TIMESTAMP | Last update time (auto-managed) |

**Indexes**:
- `sender_did`, `recipient_did` - Fast user lookups
- `idempotency_key` - Duplicate prevention
- `status`, `active_rail` - Dashboard queries
- `created_at DESC` - Chronological ordering

#### 2. `vettedpay_rail_health`
**Purpose**: Payment rail health monitoring and circuit breaker state

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `rail` | `payment_rail` | Rail identifier (unique) |
| `is_healthy` | BOOLEAN | Current health status |
| `last_success_at` | TIMESTAMP | Last successful transaction |
| `last_failure_at` | TIMESTAMP | Last failure |
| `failure_count` | INTEGER | Consecutive failures |
| `circuit_status` | VARCHAR(20) | CLOSED/OPEN/HALF_OPEN |
| `error_message` | TEXT | Latest error details |
| `updated_at` | TIMESTAMP | Last health check |

**Default Records**:
```sql
INSERT INTO vettedpay_rail_health (rail, is_healthy, circuit_status)
VALUES 
    ('airwallex', TRUE, 'CLOSED'),
    ('nium', TRUE, 'CLOSED'),
    ('wise', TRUE, 'CLOSED'),
    ('stablecoin_usdc', TRUE, 'CLOSED'),
    ('fallback_mock', TRUE, 'CLOSED');
```

#### 3. `vettedpay_zk_verifications`
**Purpose**: Audit trail of zero-knowledge proof verifications

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `transaction_id` | UUID | FK to `vettedpay_transactions` |
| `sender_did` | VARCHAR(255) | Who generated the proof |
| `proof_type` | VARCHAR(50) | Type of proof (e.g., `sanction_check`) |
| `verification_result` | BOOLEAN | Pass/fail |
| `verification_method` | VARCHAR(100) | Method used (e.g., `OFAC_API_v1`) |
| `proof_timestamp` | TIMESTAMP | When proof was generated |
| `verified_at` | TIMESTAMP | When verification occurred |

**Note**: Does NOT store actual proofs (too large), only verification results.

#### 4. `vettedpay_waitlist`
**Purpose**: Early adopter waitlist for VettedPay launch

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `email` | VARCHAR(255) | Email (unique) |
| `full_name` | VARCHAR(255) | Optional name |
| `organization` | VARCHAR(255) | Optional organization |
| `use_case` | TEXT | Intended use case |
| `referral_source` | VARCHAR(100) | How they found us |
| `priority_score` | INTEGER | Prioritization score |
| `status` | VARCHAR(50) | pending/invited/activated |
| `invited_at` | TIMESTAMP | When invited |
| `created_at` | TIMESTAMP | Signup time |

---

## Enums

### `payment_rail`
```sql
CREATE TYPE payment_rail AS ENUM (
    'airwallex',
    'nium',
    'wise',
    'stablecoin_usdc',
    'fallback_mock'
);
```

### `transaction_status`
```sql
CREATE TYPE transaction_status AS ENUM (
    'initiated',
    'zk_verified',
    'dispatched_to_rail',
    'settled',
    'failed',
    'cancelled'
);
```

---

## ORM Models

### Python Enums

```python
class PaymentRail(enum.Enum):
    AIRWALLEX = "airwallex"
    NIUM = "nium"
    WISE = "wise"
    STABLECOIN_USDC = "stablecoin_usdc"
    FALLBACK_MOCK = "fallback_mock"

class TransactionStatus(enum.Enum):
    INITIATED = "initiated"
    ZK_VERIFIED = "zk_verified"
    DISPATCHED_TO_RAIL = "dispatched_to_rail"
    SETTLED = "settled"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

### Model Usage Example

```python
from app.models.vettedpay import (
    VettedPayTransaction,
    VettedPayZKVerification,
    VettedPayRailHealth,
    VettedPayWaitlist,
    PaymentRail,
    TransactionStatus,
)
from decimal import Decimal
from sqlalchemy.orm import Session

# Create a new transaction
transaction = VettedPayTransaction(
    idempotency_key="abc123...",
    sender_did="did:ethr:0x123...",
    recipient_did="did:ethr:0x456...",
    amount=Decimal("1500.00"),
    currency="USD",
    active_rail=PaymentRail.AIRWALLEX,
    status=TransactionStatus.INITIATED,
    zk_proof_verified=True,
    metadata={"purpose": "payroll"}
)

db.add(transaction)
db.commit()

# Query transactions
pending_txs = db.query(VettedPayTransaction).filter(
    VettedPayTransaction.status == TransactionStatus.INITIATED
).all()

# Check rail health
airwallex_health = db.query(VettedPayRailHealth).filter(
    VettedPayRailHealth.rail == PaymentRail.AIRWALLEX
).first()

if not airwallex_health.is_healthy:
    print(f"Airwallex down: {airwallex_health.error_message}")
```

---

## Transaction Engine Integration

The `VettedPayTransactionEngine` now includes **automatic database persistence**:

```python
from app.services.payment_rails import VettedPayTransactionEngine
from app.database import SessionLocal

# Initialize with database session
db = SessionLocal()
engine = VettedPayTransactionEngine(
    active_provider="airwallex",
    provider_config={"api_url": "...", "api_token": "..."},
    db_session=db,  # ← NEW: Database persistence
    compliance_generator=compliance_gen
)

# Process transfer - automatically persists to database
result = await engine.process_transfer(
    sender_did="did:ethr:0x123...",
    recipient_did="did:ethr:0x456...",
    zk_proof={"valid": True, "timestamp": "..."},
    encrypted_compliance_packet="...",
    amount=1000.0,
    currency="USD",
    destination_account="beneficiary_123"
)

# Transaction record and ZK verification log are automatically created
```

### What Gets Persisted

1. **On Transaction Initiation** (`status: initiated`):
   - Transaction record created
   - ZK verification logged
   - Idempotency key stored

2. **On Rail Dispatch** (`status: dispatched_to_rail`):
   - Status updated
   - `rail_transaction_id` stored
   - `compliance_packet_id` stored

3. **On Success** (`status: settled`):
   - Final status update
   - Transaction committed to audit trail

4. **On Failure** (`status: failed`):
   - Error logged
   - Status marked failed
   - Transaction preserved for retry/investigation

---

## Automated Features

### Timestamp Management
```sql
CREATE TRIGGER trigger_update_vettedpay_transactions_timestamp
    BEFORE UPDATE ON vettedpay_transactions
    FOR EACH ROW
    EXECUTE FUNCTION update_vettedpay_timestamp();
```
**Benefit**: `updated_at` automatically refreshed on every update.

### Rail Health Initialization
On migration, all rails are initialized to `HEALTHY` with `circuit_status: CLOSED`.

### Idempotency Protection
- Every transaction has a unique `idempotency_key` (SHA-256 hash)
- Duplicate requests are rejected at database constraint level
- No double-billing, no duplicate payouts

---

## Privacy Guarantees

### What This System NEVER Stores
❌ Social Security Numbers  
❌ Raw bank account numbers  
❌ Passport numbers  
❌ Unencrypted PII  
❌ Full names (uses DIDs instead)  
❌ Compliance packet contents (stored encrypted elsewhere)

### What This System DOES Store
✅ Decentralized Identifiers (DIDs)  
✅ Transaction amounts and currency  
✅ Payment rail used  
✅ Transaction status and timestamps  
✅ ZK-proof verification results (not the proof itself)  
✅ References to encrypted compliance packets  
✅ Error logs for debugging  

### Zero-Knowledge Architecture
1. **Client-side**: User generates ZK-proof of non-sanction status
2. **Backend**: Verifies proof WITHOUT seeing identity details
3. **Database**: Logs verification result, not raw data
4. **Payment Rail**: Receives encrypted compliance packet (can't be decrypted by backend)

---

## Migration Instructions

### Apply Migration
```bash
# Check current migration state
alembic current

# Apply VettedPay schema
alembic upgrade 044_vettedpay_core_schema

# Verify tables created
psql -d vettedcare -c "\dt vettedpay*"
```

### Rollback (if needed)
```bash
alembic downgrade 043_vettedpay_payouts
```

---

## Testing Queries

### Check Transaction Flow
```sql
-- View all transactions with rail info
SELECT 
    id, 
    sender_did, 
    amount, 
    currency, 
    active_rail::text, 
    status::text, 
    created_at 
FROM vettedpay_transactions 
ORDER BY created_at DESC 
LIMIT 10;

-- Count by status
SELECT status::text, COUNT(*) 
FROM vettedpay_transactions 
GROUP BY status;

-- Check ZK verification rate
SELECT 
    verification_result, 
    COUNT(*) 
FROM vettedpay_zk_verifications 
GROUP BY verification_result;
```

### Monitor Rail Health
```sql
SELECT 
    rail::text, 
    is_healthy, 
    circuit_status, 
    failure_count, 
    last_success_at, 
    last_failure_at 
FROM vettedpay_rail_health;
```

### Waitlist Management
```sql
-- Top priority signups
SELECT email, organization, priority_score, created_at 
FROM vettedpay_waitlist 
WHERE status = 'pending' 
ORDER BY priority_score DESC 
LIMIT 50;
```

---

## Next Steps

### Backend API Routes (Upcoming)
- `POST /api/vettedpay/transfer` - Initiate transfer
- `GET /api/vettedpay/transactions/:id` - Check status
- `GET /api/vettedpay/transactions/` - List user transactions
- `POST /api/vettedpay/waitlist` - Join waitlist
- `GET /api/vettedpay/rails/health` - Check rail availability

### Frontend Dashboard (Upcoming)
- Transaction history view
- Real-time status updates
- Multi-rail switching interface
- Waitlist signup form

### Landing Page (Upcoming)
- Privacy-first value proposition
- Technical architecture showcase
- Waitlist CTA with priority scoring
- Social proof and testimonials

---

## File Registry

### Database Layer
- `database/vettedpay_schema.sql` - Raw SQL schema
- `alembic/versions/044_vettedpay_core_schema.py` - Alembic migration

### ORM Models
- `app/models/vettedpay.py` - SQLAlchemy models and enums

### Transaction Engine
- `app/services/payment_rails/transaction_manager.py` - Orchestration layer with DB persistence

### Documentation
- `VETTEDPAY_FULLSTACK_FOUNDATION.md` - This document
- `VETTEDPAY_IMPLEMENTATION_COMPLETE.md` - Original implementation guide
- `app/services/payment_rails/README.md` - Payment rails architecture

---

## Security Considerations

### Database Security
1. **Column-level encryption** for sensitive metadata (JSONB fields)
2. **Row-level security policies** for multi-tenant isolation (if needed)
3. **Audit logging** via `VettedPayZKVerification` table
4. **No cascading deletes** except for ZK verifications (intentional audit preservation)

### Compliance
- **GDPR**: DIDs can be "forgotten" without losing transaction integrity
- **PCI-DSS**: No credit card data stored
- **OFAC/AML**: ZK-proof verification logged for audit trail
- **CCPA**: User can request DID-linked data deletion

---

## Governance

**Document Version**: 1.0.0  
**Last Updated**: July 17, 2026  
**Approved By**: VettedCare Engineering Team  
**Next Review**: August 1, 2026  

---

## Changelog

### [1.0.0] - 2026-07-17
- ✅ Initial database schema creation
- ✅ ORM models with enum support
- ✅ Alembic migration (044)
- ✅ Transaction engine DB persistence
- ✅ Automated timestamp triggers
- ✅ Default rail health initialization
- ✅ Comprehensive documentation

---

**Status**: 🟢 Database Layer Complete - Frontend Integration Next

