# VettedPay Frontend Integration Guide

**Version**: 1.0.0  
**Date**: July 17, 2026  
**Status**: Task 2 Complete - Transfer Dashboard Live

---

## Overview

The VettedPay frontend provides a **privacy-first, zero-knowledge payment interface** that encrypts sensitive data client-side before transmission. The backend NEVER sees plaintext bank account numbers, routing numbers, or personally identifiable information.

---

## Architecture

```
┌─────────────────┐
│   User Browser  │
│   (Client-Side) │
└────────┬────────┘
         │
         │ 1. Encrypt Bank Data (RSA-OAEP)
         │ 2. Generate ZK-Proof
         │
         ▼
┌─────────────────┐
│  TransferForm   │
│  Component      │
└────────┬────────┘
         │
         │ POST /api/v1/vettedpay/transfer
         │ {
         │   sender_did: "did:vettedme:...",
         │   recipient_did: "did:vettedme:...",
         │   zk_proof: {...},
         │   encrypted_compliance_packet: "base64..."
         │ }
         ▼
┌─────────────────┐
│  FastAPI Backend│
│  (Blind Router) │
└────────┬────────┘
         │
         │ 3. Verify ZK-Proof (without seeing identity)
         │ 4. Route to Active Rail
         │
         ▼
┌─────────────────┐
│  Payment Rail   │
│  (Airwallex/    │
│   Nium/Wise)    │
└─────────────────┘
```

---

## Components

### 1. TransferDashboard.tsx

**Location**: `frontend/components/TransferDashboard.tsx`

**Purpose**: Main transfer initiation form with client-side encryption.

**Key Features**:
- Recipient DID input
- Amount and currency selection
- Bank account fields (encrypted client-side)
- ZK-proof generation (mocked for now)
- Status messages and error handling
- Loading states

**Usage**:
```tsx
import TransferDashboard from '@/components/TransferDashboard';

export default function TransferPage() {
  return <TransferDashboard />;
}
```

**Props**: None (self-contained with internal state)

---

### 2. crypto.ts

**Location**: `frontend/lib/crypto.ts`

**Purpose**: Client-side encryption utilities using Web Crypto API.

**Key Functions**:

#### `encryptBankDataForRail(bankData, publicKeyPem)`
Encrypts sensitive bank data with recipient's RSA public key.

```typescript
const encryptedData = await encryptBankDataForRail(
  {
    account_number: "123456789",
    routing_number: "021000021",
    legal_name: "John Doe",
    source_of_funds: "Employment Income",
    purpose_of_payment: "Payroll"
  },
  BANK_PUBLIC_KEY_PEM
);
// Returns: Base64-encoded encrypted payload
```

**Encryption Details**:
- Algorithm: RSA-OAEP
- Hash: SHA-256
- Key Size: 2048 bits (minimum)
- Output: Base64-encoded

#### `generateZKSanctionProof(userDid)`
Generates a zero-knowledge proof of non-sanction status.

**Current Status**: Mock implementation (returns `{valid: true}`)  
**Production TODO**: Integrate with Reclaim Protocol or zkTLS library

#### Validation Helpers
- `isValidDID(did)` - DID format validation
- `isValidAmount(amount)` - Amount range check
- `isValidCurrency(currency)` - Currency code validation
- `formatAmount(amount, currency)` - Display formatting
- `maskAccountNumber(accountNumber)` - Security masking

---

## Backend API Endpoints

### POST `/api/v1/vettedpay/transfer`

**Purpose**: Initiate a new payment transfer

**Request Body**:
```json
{
  "sender_did": "did:vettedme:sender123",
  "recipient_did": "did:vettedme:recipient456",
  "amount": 1000.00,
  "currency": "USD",
  "zk_proof": {
    "valid": true,
    "timestamp": "2026-07-17T12:00:00Z",
    "verification_method": "OFAC_API_v1",
    "provider_hash": "sha256_abc...",
    "signature": "sig_xyz...",
    "nonce": "abc123"
  },
  "encrypted_compliance_packet": "base64_encrypted_data...",
  "destination_account": "encrypted_account_ref",
  "metadata": {
    "initiated_from": "web_dashboard",
    "client_version": "1.0.0"
  }
}
```

**Response** (201 Created):
```json
{
  "success": true,
  "transaction_id": "uuid-1234-5678",
  "idempotency_key": "sha256_hash...",
  "status": "initiated",
  "rail": "airwallex",
  "amount": 1000.00,
  "currency": "USD",
  "compliance_verified": true,
  "created_at": "2026-07-17T12:00:00Z",
  "message": "Transfer initiated successfully"
}
```

**Error Response** (400 Bad Request):
```json
{
  "success": false,
  "error": "Zero-knowledge sanction check failed validation.",
  "error_code": "ZK_COMPLIANCE_FAILED"
}
```

---

### GET `/api/v1/vettedpay/transactions/{transaction_id}`

**Purpose**: Get transaction details

**Response**:
```json
{
  "id": "uuid-1234-5678",
  "sender_did": "did:vettedme:sender123",
  "recipient_did": "did:vettedme:recipient456",
  "amount": "1000.00",
  "currency": "USD",
  "status": "settled",
  "rail": "airwallex",
  "zk_proof_verified": true,
  "rail_transaction_id": "airwallex_txn_789",
  "error_log": null,
  "created_at": "2026-07-17T12:00:00Z",
  "updated_at": "2026-07-17T12:05:00Z"
}
```

---

### GET `/api/v1/vettedpay/transactions/`

**Purpose**: List transactions with filtering

**Query Parameters**:
- `sender_did` (optional) - Filter by sender
- `recipient_did` (optional) - Filter by recipient
- `status` (optional) - Filter by status (initiated, settled, failed, etc.)
- `limit` (optional, default 50) - Max results
- `offset` (optional, default 0) - Pagination offset

**Response**: Array of `TransactionDetailSchema`

---

### GET `/api/v1/vettedpay/rails/health`

**Purpose**: Get health status of all payment rails

**Response**:
```json
[
  {
    "rail": "airwallex",
    "is_healthy": true,
    "circuit_status": "CLOSED",
    "failure_count": 0,
    "last_success_at": "2026-07-17T11:50:00Z",
    "last_failure_at": null,
    "error_message": null
  },
  {
    "rail": "nium",
    "is_healthy": false,
    "circuit_status": "OPEN",
    "failure_count": 5,
    "last_success_at": "2026-07-16T10:00:00Z",
    "last_failure_at": "2026-07-17T08:00:00Z",
    "error_message": "Connection timeout"
  }
]
```

---

### POST `/api/v1/vettedpay/waitlist`

**Purpose**: Join the VettedPay waitlist

**Request Body**:
```json
{
  "email": "user@example.com",
  "full_name": "John Doe",
  "organization": "Acme Healthcare",
  "use_case": "International payroll disbursement",
  "referral_source": "twitter"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Welcome to VettedPay! You're #47 on the waitlist.",
  "priority_score": 15,
  "position": 47,
  "email": "user@example.com"
}
```

---

## Environment Configuration

### Frontend (.env.local)

```bash
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000

# VettedPay Configuration
NEXT_PUBLIC_VETTEDPAY_ENABLED=true
NEXT_PUBLIC_DEFAULT_PAYMENT_RAIL=airwallex

# ZK-Proof Configuration
NEXT_PUBLIC_ZK_PROOF_ENABLED=true
NEXT_PUBLIC_ZK_PROOF_PROVIDER=reclaim-protocol

# Feature Flags
NEXT_PUBLIC_ENABLE_WAITLIST=true
NEXT_PUBLIC_ENABLE_TRANSACTION_HISTORY=true
NEXT_PUBLIC_ENABLE_RAIL_HEALTH_MONITORING=true

# Security
NEXT_PUBLIC_ENABLE_CLIENT_SIDE_ENCRYPTION=true
NEXT_PUBLIC_RSA_KEY_SIZE=2048

# Development
NEXT_PUBLIC_DEBUG_MODE=false
NEXT_PUBLIC_MOCK_ZK_PROOFS=true
```

### Backend (.env)

```bash
# VettedPay Configuration
VETTEDPAY_ACTIVE_PROVIDER=airwallex
VETTEDPAY_AIRWALLEX_API_URL=https://api.airwallex.com
VETTEDPAY_AIRWALLEX_API_TOKEN=your_airwallex_token

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/vettedcare

# Security
VETTEDPAY_HMAC_SECRET=your_hmac_secret_key
VETTEDPAY_ENCRYPTION_KEY=your_encryption_key
```

---

## Security Model

### What Gets Encrypted Client-Side
✅ Bank account numbers  
✅ Routing numbers / BIC codes  
✅ Legal beneficiary names  
✅ Source of funds  
✅ Purpose of payment  

### What Stays in Plaintext
- Sender DID (decentralized identifier)
- Recipient DID
- Transfer amount
- Currency code
- ZK-proof verification result

### Encryption Flow

1. **Client-Side Encryption**:
   ```typescript
   const encrypted = await encryptBankDataForRail(
     { account_number, routing_number, legal_name },
     BANK_PUBLIC_KEY_PEM
   );
   ```

2. **Backend Receives**:
   - Backend sees only the **encrypted blob**
   - Cannot decrypt (doesn't have private key)
   - Verifies ZK-proof WITHOUT seeing identity

3. **Payment Rail Decryption**:
   - Only the payment rail (Airwallex/Nium/Wise) can decrypt
   - Has the corresponding private key
   - Processes payment with full bank details

### Privacy Guarantees

❌ Backend NEVER sees:
- Social Security Numbers
- Raw bank account numbers
- Full legal names (uses DIDs instead)
- Unencrypted PII

✅ Backend DOES see:
- Encrypted compliance packets (base64 blobs)
- ZK-proof verification results (not the proof itself)
- Transaction amounts and currencies
- Decentralized identifiers (DIDs)

---

## Page Structure

### `/vettedpay/transfer` (Implemented ✅)

**Components**:
- TransferDashboard form
- Header with navigation
- Info cards (Zero-Knowledge, Multi-Rail, Encrypted)
- Technical details accordion
- Footer

**Features**:
- Client-side encryption
- ZK-proof generation (mocked)
- Real-time status updates
- Error handling with user-friendly messages
- Form validation
- Loading states

---

## Next Steps (Upcoming Pages)

### `/vettedpay/transactions` (Planned)
- Transaction history list
- Filtering by status, date, rail
- Pagination
- Transaction detail modal

### `/vettedpay/rails` (Planned)
- Real-time rail health dashboard
- Circuit breaker status
- Failure count and last success/failure timestamps
- Auto-refresh every 30 seconds

### `/vettedpay/waitlist` (Planned)
- Waitlist signup form
- Priority scoring visualization
- Queue position tracking

---

## Testing

### Frontend Testing
```bash
cd frontend
npm run dev
# Navigate to http://localhost:3000/vettedpay/transfer
```

### Backend Testing
```bash
# Start FastAPI server
uvicorn app.main:app --reload --port 8000

# Test transfer endpoint
curl -X POST http://localhost:8000/api/v1/vettedpay/transfer \
  -H "Content-Type: application/json" \
  -d '{
    "sender_did": "did:vettedme:test",
    "recipient_did": "did:vettedme:recipient",
    "amount": 100.00,
    "currency": "USD",
    "zk_proof": {"valid": true, "timestamp": "2026-07-17T12:00:00Z", "verification_method": "OFAC_API_v1"},
    "encrypted_compliance_packet": "base64_test_data",
    "destination_account": "test_account"
  }'
```

### End-to-End Testing
1. Start backend: `uvicorn app.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Open browser: `http://localhost:3000/vettedpay/transfer`
4. Fill out form and submit
5. Check network tab for API request
6. Verify transaction in database

---

## CORS Configuration

**Backend** (`app/main.py`):
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://vettedpay.ai",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
```

---

## Deployment Checklist

### Frontend
- [ ] Set production `NEXT_PUBLIC_API_URL`
- [ ] Fetch real bank public keys from backend
- [ ] Integrate real ZK-proof generation (Reclaim Protocol)
- [ ] Enable Sentry error tracking
- [ ] Configure CSP headers
- [ ] Test on mobile devices

### Backend
- [ ] Run Alembic migration: `alembic upgrade head`
- [ ] Set production `VETTEDPAY_ACTIVE_PROVIDER`
- [ ] Configure real Airwallex/Nium/Wise credentials
- [ ] Enable rate limiting
- [ ] Set up monitoring (Datadog/Sentry)
- [ ] Test idempotency key enforcement

---

## Troubleshooting

### "CORS error when submitting transfer"
**Solution**: Ensure backend CORS middleware includes your frontend origin.

### "Encryption failed"
**Solution**: Verify public key format (must be valid PEM with proper headers).

### "ZK-proof verification failed"
**Solution**: In dev mode, ensure `NEXT_PUBLIC_MOCK_ZK_PROOFS=true`. In production, integrate real zkTLS library.

### "Transaction not found in database"
**Solution**: Check that Alembic migration 044 has been applied: `alembic current`

---

## File Registry

### Frontend
- `frontend/components/TransferDashboard.tsx` - Main transfer form ✅
- `frontend/lib/crypto.ts` - Encryption utilities ✅
- `frontend/pages/vettedpay/transfer.tsx` - Transfer page ✅
- `frontend/.env.local.example` - Environment template ✅

### Backend
- `app/routers/vettedpay.py` - API endpoints ✅
- `app/services/payment_rails/transaction_manager.py` - Transaction engine ✅
- `app/models/vettedpay.py` - Database models ✅
- `alembic/versions/044_vettedpay_core_schema.py` - Database migration ✅

### Documentation
- `VETTEDPAY_FULLSTACK_FOUNDATION.md` - Database architecture ✅
- `VETTEDPAY_FRONTEND_INTEGRATION.md` - This document ✅
- `VETTEDPAY_TASK_CHECKLIST.md` - Implementation roadmap ✅

---

## Changelog

### [1.0.0] - 2026-07-17
- ✅ TransferDashboard component created
- ✅ Client-side encryption utilities (crypto.ts)
- ✅ Transfer page with header/footer
- ✅ Backend API endpoints (transfer, transactions, rails, waitlist)
- ✅ CORS configuration
- ✅ Environment configuration templates
- ✅ Comprehensive documentation

---

**Status**: 🟢 Task 2 Complete - Transfer Dashboard Live and Functional

**Next**: Task 3 - High-Conversion Landing Page

