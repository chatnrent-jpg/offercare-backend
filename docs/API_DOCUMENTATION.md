# VettedMe Passport API Documentation

**Version**: 1.0.0  
**Base URL**: `https://api.vettedme.ai/v1`  
**Authentication**: API Key (Bearer Token)

---

## 🚀 Quick Start

### 1. Get an API Key

Create an account at [vettedme.ai/developers](https://vettedme.ai/developers) and generate your API key.

```bash
curl -X POST https://api.vettedme.ai/v1/passport/api-keys \
  -H "Content-Type: application/json" \
  -d '{
    "organization_name": "Your Company",
    "tier": "FREE"
  }'
```

**Response:**
```json
{
  "id": "uuid-12345",
  "organization_name": "Your Company",
  "api_key": "vettedme_live_abc123def456...",
  "tier": "FREE",
  "rate_limit_per_hour": 100,
  "status": "ACTIVE"
}
```

⚠️ **IMPORTANT**: Save your API key securely. It will only be shown once.

### 2. Verify a Passport

Use your API key to verify a user's credentials instantly:

```bash
curl -X POST https://api.vettedme.ai/v1/passport/verify \
  -H "Authorization: Bearer vettedme_live_abc123def456..." \
  -H "Content-Type: application/json" \
  -d '{
    "passport_id": "uuid-67890",
    "required_badges": ["IDENTITY", "HEALTHCARE"],
    "requesting_platform": "yourapp.com"
  }'
```

**Response:**
```json
{
  "verified": true,
  "passport_id": "uuid-67890",
  "trust_score": 98,
  "badges": [
    {
      "type": "IDENTITY",
      "verified": true,
      "verified_at": "2026-01-15T10:30:00Z",
      "expires_at": "2028-07-14T00:00:00Z"
    },
    {
      "type": "HEALTHCARE",
      "verified": true,
      "credential": {
        "license_type": "RN",
        "license_number": "R234951",
        "state": "MD"
      },
      "verified_at": "2026-07-01T14:22:00Z",
      "expires_at": "2027-10-31T00:00:00Z"
    }
  ],
  "verification_token": "vtok_1721073600_uuid6789_abc"
}
```

---

## 🔐 Authentication

All API requests require an API key in the `Authorization` header:

```
Authorization: Bearer vettedme_live_YOUR_KEY_HERE
```

### API Key Tiers

| Tier | Rate Limit | Cost | Use Case |
|------|-----------|------|----------|
| **FREE** | 100/hour | $0 | Testing, small apps |
| **GROWTH** | 10,000/hour | $0.50/verification | Production apps |
| **ENTERPRISE** | Unlimited | Custom | High-volume platforms |

---

## 📋 Core Endpoints

### Passport Management

#### Create a Passport

Create a new passport for a user.

**Endpoint:** `POST /passport/create`

**Request:**
```json
{
  "user_id": "uuid-12345",
  "biometric_data": "base64_encoded_facial_scan"
}
```

**Response:**
```json
{
  "id": "uuid-passport-123",
  "user_id": "uuid-12345",
  "status": "ACTIVE",
  "issued_at": "2026-07-14T16:30:00Z",
  "expires_at": "2028-07-14T16:30:00Z",
  "trust_score": 20,
  "badge_count": 0
}
```

---

#### Get Passport Details

Retrieve passport information.

**Endpoint:** `GET /passport/{passport_id}`

**Response:**
```json
{
  "id": "uuid-passport-123",
  "user_id": "uuid-12345",
  "status": "ACTIVE",
  "issued_at": "2026-07-14T16:30:00Z",
  "expires_at": "2028-07-14T16:30:00Z",
  "trust_score": 98,
  "badge_count": 5
}
```

---

### Badge Management

#### Issue a Credential Badge

Add a verified credential to a passport.

**Endpoint:** `POST /passport/issue-badge`

**Request:**
```json
{
  "passport_id": "uuid-passport-123",
  "badge_type": "HEALTHCARE",
  "credential_data": {
    "license_type": "RN",
    "license_number": "R234951",
    "state": "MD",
    "issuing_authority": "Maryland Board of Nursing"
  },
  "verification_method": "MBON_SCRAPER",
  "expires_at": "2027-10-31T00:00:00Z"
}
```

**Response:**
```json
{
  "id": "uuid-badge-456",
  "passport_id": "uuid-passport-123",
  "badge_type": "HEALTHCARE",
  "credential_data": {
    "license_type": "RN",
    "license_number": "R234951",
    "state": "MD",
    "issuing_authority": "Maryland Board of Nursing",
    "passport_id": "uuid-passport-123",
    "badge_type": "HEALTHCARE",
    "issued_at": "2026-07-14T16:35:00Z",
    "issuer": "VettedMe.ai"
  },
  "verification_method": "MBON_SCRAPER",
  "verified_at": "2026-07-14T16:35:00Z",
  "expires_at": "2027-10-31T00:00:00Z",
  "revoked": false,
  "issuer_signature": "base64_ed25519_signature..."
}
```

---

#### List Badges

Get all badges for a passport.

**Endpoint:** `GET /passport/{passport_id}/badges?include_revoked=false`

**Response:**
```json
[
  {
    "id": "uuid-badge-456",
    "passport_id": "uuid-passport-123",
    "badge_type": "HEALTHCARE",
    "credential_data": { ... },
    "verification_method": "MBON_SCRAPER",
    "verified_at": "2026-07-14T16:35:00Z",
    "expires_at": "2027-10-31T00:00:00Z",
    "revoked": false,
    "issuer_signature": "base64_ed25519_signature..."
  },
  ...
]
```

---

#### Revoke a Badge

Revoke a credential (e.g., license expired, employment ended).

**Endpoint:** `POST /passport/revoke-badge`

**Request:**
```json
{
  "badge_id": "uuid-badge-456",
  "reason": "License expired and not renewed"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Badge uuid-badge-456 revoked successfully"
}
```

---

### Verification (Primary Revenue Endpoint)

#### Verify a Passport

Instantly verify credentials for an external platform.

**Endpoint:** `POST /passport/verify`  
**Authentication:** Required (API Key)

**Request:**
```json
{
  "passport_id": "uuid-passport-123",
  "required_badges": ["IDENTITY", "HEALTHCARE"],
  "requesting_platform": "yourapp.com"
}
```

**Response (Success):**
```json
{
  "verified": true,
  "passport_id": "uuid-passport-123",
  "trust_score": 98,
  "badges": [
    {
      "type": "IDENTITY",
      "verified": true,
      "verified_at": "2026-01-15T10:30:00Z",
      "expires_at": "2028-07-14T00:00:00Z"
    },
    {
      "type": "HEALTHCARE",
      "verified": true,
      "credential": {
        "license_type": "RN",
        "license_number": "R234951",
        "state": "MD"
      },
      "verified_at": "2026-07-01T14:22:00Z",
      "expires_at": "2027-10-31T00:00:00Z"
    }
  ],
  "verification_token": "vtok_1721073600_uuid1234_abc"
}
```

**Response (Failure - Badge Missing):**
```json
{
  "verified": false,
  "passport_id": "uuid-passport-123",
  "trust_score": 68,
  "badges": [
    {
      "type": "IDENTITY",
      "verified": true,
      "verified_at": "2026-01-15T10:30:00Z",
      "expires_at": "2028-07-14T00:00:00Z"
    },
    {
      "type": "HEALTHCARE",
      "verified": false,
      "error": "BADGE_NOT_FOUND"
    }
  ],
  "verification_token": "vtok_1721073600_uuid1234_def"
}
```

---

### Audit Trail

#### View Verification Logs

View audit trail for compliance and security monitoring.

**Endpoint:** `GET /passport/verification-logs?passport_id=uuid-passport-123&limit=100`

**Response:**
```json
[
  {
    "id": "uuid-log-789",
    "passport_id": "uuid-passport-123",
    "requesting_platform": "upwork.com",
    "requested_badges": ["IDENTITY", "HEALTHCARE"],
    "verification_result": { ... },
    "timestamp": "2026-07-14T16:40:00Z",
    "ip_address": "203.0.113.42"
  },
  ...
]
```

---

## 🎯 Badge Types

VettedMe supports multiple credential types:

| Badge Type | Description | Common Use Cases |
|-----------|-------------|------------------|
| **IDENTITY** | Government ID + biometric verification | KYC, account opening, secure logins |
| **HEALTHCARE** | State nursing licenses (RN/LPN/CNA) | Staffing, telehealth, medical platforms |
| **EMPLOYMENT** | Verified work history with dates | Job boards, freelance platforms |
| **EDUCATION** | Verified degrees/certifications | University admissions, professional networks |
| **COMPLIANCE** | Background check + criminal record | Gig economy, childcare, financial services |
| **DEVELOPER** | GitHub + technical assessments | Engineering hiring, open-source maintainers |
| **PROFESSIONAL** | CPA, EA, Bar admission, etc. | Tax services, legal platforms, consulting |

---

## 🔒 Security & Cryptography

### Ed25519 Digital Signatures

All credentials are signed using **Ed25519** (Curve25519) for:

✅ **Tamper-proof**: Any modification breaks the signature  
✅ **Non-repudiation**: VettedMe cannot deny issuing a credential  
✅ **Offline verification**: No database lookup required  
✅ **Fast**: Sub-millisecond signature verification

### Signature Verification Example

```python
import json
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# VettedMe's public key (PEM format)
VETTEDME_PUBLIC_KEY = """
-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEA...
-----END PUBLIC KEY-----
"""

def verify_badge(credential_data, signature_base64):
    # Load public key
    public_key = Ed25519PublicKey.from_public_bytes(
        base64.b64decode(VETTEDME_PUBLIC_KEY)
    )
    
    # Reconstruct canonical JSON
    canonical_json = json.dumps(credential_data, sort_keys=True, separators=(',', ':'))
    message = canonical_json.encode('utf-8')
    
    # Decode signature
    signature = base64.b64decode(signature_base64)
    
    # Verify
    try:
        public_key.verify(signature, message)
        return True
    except:
        return False
```

---

## 📊 Rate Limits

Rate limits are enforced per API key:

| Tier | Limit | Window | Overage |
|------|-------|--------|---------|
| FREE | 100 | 1 hour | `429 Too Many Requests` |
| GROWTH | 10,000 | 1 hour | `429 Too Many Requests` |
| ENTERPRISE | Unlimited | N/A | N/A |

**Response on Rate Limit:**
```json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "detail": "API key has exceeded 100 requests per hour. Upgrade to GROWTH tier.",
  "tier": "FREE",
  "limit": 100,
  "window": "1 hour"
}
```

---

## 🛠️ SDKs & Libraries

### Python

```bash
pip install vettedme-sdk
```

```python
from vettedme import VettedMeClient

client = VettedMeClient(api_key="vettedme_live_abc123...")

# Verify a passport
result = client.verify_passport(
    passport_id="uuid-12345",
    required_badges=["IDENTITY", "HEALTHCARE"],
    requesting_platform="yourapp.com"
)

if result.verified:
    print(f"Trust Score: {result.trust_score}")
    for badge in result.badges:
        print(f"{badge.type}: {badge.verified}")
```

### JavaScript/Node.js

```bash
npm install @vettedme/sdk
```

```javascript
const VettedMe = require('@vettedme/sdk');

const client = new VettedMe('vettedme_live_abc123...');

// Verify a passport
const result = await client.verifyPassport({
  passportId: 'uuid-12345',
  requiredBadges: ['IDENTITY', 'HEALTHCARE'],
  requestingPlatform: 'yourapp.com'
});

if (result.verified) {
  console.log(`Trust Score: ${result.trustScore}`);
  result.badges.forEach(badge => {
    console.log(`${badge.type}: ${badge.verified}`);
  });
}
```

---

## 🔔 Webhooks (Coming Soon)

Subscribe to real-time credential updates:

**Events:**
- `credential.issued`: New badge added to passport
- `credential.revoked`: Badge revoked
- `credential.expiring`: Badge expiring in 30 days
- `passport.suspended`: Passport status changed

**Example Webhook Payload:**
```json
{
  "event": "credential.revoked",
  "passport_id": "uuid-12345",
  "badge_type": "HEALTHCARE",
  "revoked_at": "2026-07-14T16:45:00Z",
  "reason": "License expired",
  "timestamp": "2026-07-14T16:45:00Z"
}
```

---

## 💡 Integration Examples

### Upwork-Style Freelance Platform

```python
# User applies for a job
def verify_freelancer(freelancer_id):
    passport_id = get_passport_id(freelancer_id)
    
    result = vettedme.verify_passport(
        passport_id=passport_id,
        required_badges=["IDENTITY", "PROFESSIONAL"],
        requesting_platform="yourfreelanceapp.com"
    )
    
    if result.verified and result.trust_score >= 80:
        # Auto-approve application
        approve_freelancer(freelancer_id)
    else:
        # Request manual review
        flag_for_review(freelancer_id)
```

### Healthcare Staffing Platform

```javascript
// Facility requests a nurse
async function matchNurseToShift(shiftId, nurseId) {
  const passportId = await getPassportId(nurseId);
  
  const result = await vettedme.verifyPassport({
    passportId: passportId,
    requiredBadges: ['IDENTITY', 'HEALTHCARE', 'COMPLIANCE'],
    requestingPlatform: 'yourstaffingapp.com'
  });
  
  if (result.verified && result.trustScore >= 95) {
    // Nurse is OHCQ-compliant, assign shift
    await assignShift(shiftId, nurseId);
  } else {
    // Nurse doesn't meet compliance requirements
    await notifyNurse(nurseId, 'Please update your credentials');
  }
}
```

---

## 🆘 Support

- **Documentation**: [docs.vettedme.ai](https://docs.vettedme.ai)
- **API Status**: [status.vettedme.ai](https://status.vettedme.ai)
- **Discord Community**: [discord.gg/vettedme](https://discord.gg/vettedme)
- **Email Support**: [developers@vettedme.ai](mailto:developers@vettedme.ai)

---

## 📄 Legal

- **Terms of Service**: [vettedme.ai/terms](https://vettedme.ai/terms)
- **Privacy Policy**: [vettedme.ai/privacy](https://vettedme.ai/privacy)
- **Security**: [vettedme.ai/security](https://vettedme.ai/security)

---

**Last Updated**: 2026-07-14  
**API Version**: v1.0.0
