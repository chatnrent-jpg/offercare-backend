# VettedMe Passport - Technical Architecture

## Executive Summary

VettedMe Passport is a **W3C Verifiable Credentials** infrastructure platform that enables users to create cryptographically-signed, portable digital identities. The system allows professionals to verify their credentials once and share them instantly across unlimited platforms.

**Core Value Proposition**: Be the Plaid/Stripe of identity verification - pure infrastructure, not a destination.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     VettedMe Passport Platform                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │  Issuance    │      │ Verification │      │   Revocation │  │
│  │   Engine     │─────▶│     API      │◀─────│    Engine    │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│         │                      │                      │          │
│         └──────────────────────┼──────────────────────┘          │
│                                │                                 │
│                    ┌───────────▼───────────┐                    │
│                    │  Cryptographic Vault  │                    │
│                    │  (Ed25519 Signatures) │                    │
│                    └───────────────────────┘                    │
│                                │                                 │
│         ┌──────────────────────┼──────────────────────┐         │
│         │                      │                       │         │
│  ┌──────▼──────┐      ┌────────▼────────┐   ┌────────▼──────┐ │
│  │   Badge     │      │   Verification  │   │  Audit Trail  │ │
│  │  Registry   │      │     Records     │   │   Ledger      │ │
│  └─────────────┘      └─────────────────┘   └───────────────┘ │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
           │                     │                     │
           ▼                     ▼                     ▼
    ┌──────────┐          ┌──────────┐         ┌──────────┐
    │  User    │          │ Platform │         │ Webhook  │
    │ Dashboard│          │   API    │         │ Delivery │
    └──────────┘          └──────────┘         └──────────┘
```

---

## Core Components

### 1. **Passport Entity**
Each user has ONE passport containing multiple credential badges.

**Schema**:
```python
class Passport:
    id: UUID                      # Unique passport identifier
    user_id: UUID                 # Link to main user account
    public_key: str               # Ed25519 public key for verification
    status: enum["ACTIVE", "SUSPENDED", "REVOKED"]
    issued_at: datetime
    expires_at: datetime          # Passport renewal cycle (2 years)
    biometric_hash: str           # Secure hash of facial biometric
    trust_score: int              # 0-100 algorithmic trust rating
```

### 2. **Credential Badge System**
Modular, verifiable credentials that attach to a passport.

**Badge Types**:
- 🆔 **Identity Badge**: Government ID + biometric liveness verification
- 💼 **Employment Badge**: Verified work history with dates
- 🎓 **Education Badge**: Verified degrees and certifications
- ⚖️ **Compliance Badge**: Background check + criminal record
- 🏥 **Healthcare Badge**: State nursing licenses (Maryland RN/LPN/CNA)
- 💻 **Developer Badge**: GitHub + technical assessments
- 🏢 **Professional Badge**: CPA, EA, Bar admission, etc.

**Schema**:
```python
class CredentialBadge:
    id: UUID
    passport_id: UUID             # FK to Passport
    badge_type: str               # "IDENTITY", "EMPLOYMENT", "HEALTHCARE", etc.
    credential_data: JSONB        # Flexible schema per badge type
    issuer_signature: str         # Ed25519 cryptographic signature
    verification_method: str      # "MBON_SCRAPER", "MANUAL_REVIEW", "OCR_AI"
    verified_at: datetime
    expires_at: datetime          # Credential-specific expiration
    revoked: bool
    revoked_at: datetime | None
    revocation_reason: str | None
```

### 3. **Verification API (The Revenue Engine)**
Instant, cryptographic verification endpoint for external platforms.

**Endpoint**: `POST /api/v1/verify`

**Request**:
```json
{
  "passport_id": "uuid-12345",
  "required_badges": ["IDENTITY", "HEALTHCARE"],
  "requesting_platform": "upwork.com",
  "api_key": "vettedme_live_abc123"
}
```

**Response**:
```json
{
  "verified": true,
  "passport_id": "uuid-12345",
  "trust_score": 98,
  "badges": [
    {
      "type": "IDENTITY",
      "verified": true,
      "expires_at": "2028-07-14T00:00:00Z"
    },
    {
      "type": "HEALTHCARE",
      "verified": true,
      "credential": "RN-Maryland",
      "license_number": "R234951",
      "expires_at": "2027-10-31T00:00:00Z"
    }
  ],
  "verification_token": "vtok_1234567890abcdef"
}
```

**Pricing Model**:
- **Free Tier**: 100 verifications/month
- **Growth**: $0.50 per verification
- **Enterprise**: Custom pricing + webhooks + white-label

### 4. **Cryptographic Trust Model**
We use **Ed25519** digital signatures to ensure tamper-proof credentials.

**Issuance Flow**:
1. User uploads credential (e.g., Maryland RN license)
2. VettedMe verifies via official source (MBON scraper)
3. System generates credential JSON payload
4. System signs payload with VettedMe's private key
5. Public key is embedded in badge for verification

**Verification Flow**:
1. External platform requests verification via API
2. System retrieves credential badge
3. System validates signature using public key
4. Returns instant pass/fail + metadata

**Security Properties**:
- ✅ **Non-repudiation**: VettedMe cannot deny issuing a credential
- ✅ **Tamper-proof**: Any modification breaks the signature
- ✅ **Instant verification**: No database lookup required (can verify offline)
- ✅ **Privacy-preserving**: User controls which badges to share

---

## Database Schema (PostgreSQL)

```sql
-- Core Passport Table
CREATE TABLE passports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    public_key TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    issued_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    biometric_hash TEXT,
    trust_score INTEGER DEFAULT 0 CHECK (trust_score >= 0 AND trust_score <= 100),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_user_passport UNIQUE(user_id)
);

CREATE INDEX idx_passports_status ON passports(status);
CREATE INDEX idx_passports_user_id ON passports(user_id);

-- Credential Badge Table
CREATE TABLE credential_badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    passport_id UUID NOT NULL REFERENCES passports(id) ON DELETE CASCADE,
    badge_type VARCHAR(50) NOT NULL,
    credential_data JSONB NOT NULL,
    issuer_signature TEXT NOT NULL,
    verification_method VARCHAR(50) NOT NULL,
    verified_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    revoked BOOLEAN DEFAULT FALSE,
    revoked_at TIMESTAMP WITH TIME ZONE,
    revocation_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_badges_passport ON credential_badges(passport_id);
CREATE INDEX idx_badges_type ON credential_badges(badge_type);
CREATE INDEX idx_badges_expiration ON credential_badges(expires_at) WHERE NOT revoked;

-- Verification Audit Log
CREATE TABLE verification_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    passport_id UUID NOT NULL REFERENCES passports(id) ON DELETE CASCADE,
    requesting_platform VARCHAR(255) NOT NULL,
    api_key_id UUID NOT NULL,
    requested_badges TEXT[] NOT NULL,
    verification_result JSONB NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT
);

CREATE INDEX idx_verification_logs_passport ON verification_logs(passport_id);
CREATE INDEX idx_verification_logs_timestamp ON verification_logs(timestamp);
CREATE INDEX idx_verification_logs_platform ON verification_logs(requesting_platform);

-- API Keys for External Platforms
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_name VARCHAR(255) NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    key_prefix VARCHAR(20) NOT NULL,
    tier VARCHAR(20) NOT NULL DEFAULT 'FREE',
    rate_limit_per_hour INTEGER NOT NULL DEFAULT 100,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_status ON api_keys(status);
```

---

## API Design (Developer-First)

### Authentication
```bash
curl -X POST https://api.vettedme.ai/v1/verify \
  -H "Authorization: Bearer vettedme_live_abc123" \
  -H "Content-Type: application/json" \
  -d '{"passport_id": "uuid-12345", "required_badges": ["IDENTITY"]}'
```

### Rate Limits
| Tier | Limit | Cost |
|------|-------|------|
| Free | 100/hour | $0 |
| Growth | 10,000/hour | $0.50/verification |
| Enterprise | Unlimited | Custom |

### Webhooks
External platforms can subscribe to credential updates:
```json
{
  "event": "credential.revoked",
  "passport_id": "uuid-12345",
  "badge_type": "HEALTHCARE",
  "timestamp": "2026-07-14T20:31:00Z"
}
```

---

## Migration Strategy (From Current System)

### What We Already Have:
✅ Maryland MBON scraper (healthcare credential verification)
✅ Document upload pipeline (PDF processing)
✅ OpenAI structured extraction (OCR + AI parsing)
✅ Healthcare credentials database (Revision 039)
✅ Compliance audit trails

### What We Need to Build:
1. **Passport issuance engine** (cryptographic signing)
2. **Badge system** (modular credentials)
3. **Verification API** (instant check endpoint)
4. **API key management** (authentication + rate limiting)
5. **User dashboard** (view/share badges)
6. **Developer portal** (API docs + sandbox)

### Migration Path:
**Phase 1 (Week 1-2)**: Build passport core infrastructure
- Create database schema
- Implement Ed25519 signing
- Build badge issuance engine

**Phase 2 (Week 3-4)**: Build verification API
- Create `/verify` endpoint
- Implement API key system
- Add rate limiting

**Phase 3 (Week 5-6)**: Build user-facing features
- Passport dashboard
- Badge sharing UI
- Embeddable widgets

---

## Security & Compliance

### Data Minimization
- User controls which badges to share
- External platforms never see raw PII
- Verification responses contain only necessary metadata

### Encryption
- All credentials encrypted at rest (AES-256)
- TLS 1.3 for all API traffic
- Private keys stored in HSM (Hardware Security Module) in production

### Compliance
- ✅ GDPR: Right to deletion, data portability
- ✅ CCPA: Privacy policy, opt-out mechanisms
- ✅ SOC 2 Type II: Annual audit required
- ✅ HIPAA: For healthcare credentials only

### Audit Trail
Every verification logged with:
- Timestamp
- Requesting platform
- IP address
- Badges requested
- Result (pass/fail)

---

## Success Metrics

### User-Side (Passport Holders)
- Time to first badge: < 24 hours
- Badge verification accuracy: > 99.5%
- User retention (90-day): > 80%

### Platform-Side (API Customers)
- API response time: < 200ms (p95)
- API uptime: 99.95%
- False positive rate: < 0.1%

### Business Metrics
- CAC (Customer Acquisition Cost): < $50 per user
- LTV (Lifetime Value): > $500 per user
- Gross margins: > 85%

---

## Next Steps

1. ✅ Create architecture document (this document)
2. 🔨 Build database schema and models
3. 🔨 Implement cryptographic signing engine
4. 🔨 Create verification API
5. 🔨 Build user dashboard
6. 🔨 Launch developer portal

---

**Last Updated**: 2026-07-14  
**Version**: 1.0.0  
**Author**: VettedMe Engineering Team
