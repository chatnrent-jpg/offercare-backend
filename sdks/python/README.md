# VettedMe Python SDK

[![PyPI version](https://badge.fury.io/py/vettedme.svg)](https://badge.fury.io/py/vettedme)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

Official Python library for the VettedMe Passport API - the universal trust layer for digital identity verification.

## Installation

```bash
pip install vettedme
```

## Quick Start

```python
import vettedme

# Initialize client
client = vettedme.Client(api_key="vm_live_...")

# Verify a credential (1-line integration!)
result = client.verify("PASS-ABC-123")

if result.valid:
    print(f"✅ Verified: {result.full_name}")
    print(f"Trust Score: {result.trust_score}%")
    print(f"Badges: {', '.join([b.type for b in result.badges])}")
else:
    print("❌ Verification failed")
```

That's it! 🚀

## Features

- **Instant Verification**: Verify credentials in milliseconds
- **Type-Safe**: Full type hints for IDE autocomplete
- **Async Support**: `AsyncClient` for high-performance applications
- **Automatic Retries**: Built-in retry logic for transient errors
- **Comprehensive**: Full API coverage (passports, badges, webhooks, analytics)

## Usage

### Verify a Passport

```python
# Basic verification
result = client.verify("PASS-ABC-123")

# Verify specific badge type
result = client.verify_badge("PASS-ABC-123", "HEALTHCARE")

# Check result
if result:  # Supports bool checks
    print(f"Valid! Trust score: {result.trust_score}%")
    
    for badge in result.badges:
        print(f"- {badge.type}: {badge.status}")
        if badge.is_expired:
            print("  ⚠️ Expired!")
```

### Create a Passport

```python
passport = client.create_passport({
    "full_name": "Jane Smith",
    "email": "jane@example.com",
    "phone": "+1234567890"
})

print(f"Created passport: {passport.passport_number}")
```

### Add a Badge

```python
badge = client.add_badge("PASS-ABC-123", {
    "type": "HEALTHCARE",
    "credential_data": {
        "license_type": "RN",
        "license_number": "RN123456",
        "state": "MD",
        "expiration_date": "2026-12-31"
    }
})

print(f"Badge issued: {badge.id}")
```

### Webhooks

```python
# Subscribe to events
webhook = client.create_webhook(
    url="https://yourapp.com/webhooks/vettedme",
    events=["credential.verified", "badge.revoked", "passport.updated"]
)

print(f"Webhook ID: {webhook.id}")
print(f"Secret: {webhook.secret}")  # Use for HMAC validation

# List webhooks
webhooks = client.list_webhooks()
for wh in webhooks:
    print(f"{wh.url} - {', '.join(wh.events)}")
```

### Async Client (High Performance)

```python
import asyncio
from vettedme import AsyncClient

async def verify_batch(passport_ids):
    async with AsyncClient(api_key="vm_live_...") as client:
        tasks = [client.verify(pid) for pid in passport_ids]
        results = await asyncio.gather(*tasks)
        
        for result in results:
            print(f"{result.full_name}: {result.trust_score}%")

# Run
asyncio.run(verify_batch(["PASS-001", "PASS-002", "PASS-003"]))
```

### Error Handling

```python
from vettedme import (
    AuthenticationError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    ServerError
)

try:
    result = client.verify("PASS-ABC-123")
except AuthenticationError:
    print("Invalid API key")
except NotFoundError:
    print("Passport not found")
except ValidationError as e:
    print(f"Invalid request: {e}")
except RateLimitError:
    print("Rate limit exceeded - upgrade your plan")
except ServerError:
    print("Server error - try again later")
```

## Configuration

### Environment Variable

```bash
export VETTEDME_API_KEY=vm_live_...
```

Then:

```python
client = vettedme.Client()  # Auto-loads from env
```

### Custom Base URL (for testing)

```python
client = vettedme.Client(
    api_key="vm_test_...",
    base_url="https://sandbox.vettedme.ai"
)
```

## API Reference

### Client Methods

#### Verification
- `verify(passport_id, **kwargs) -> VerificationResult`
- `verify_badge(passport_id, badge_type) -> VerificationResult`

#### Passport Management
- `create_passport(user_data) -> Passport`
- `get_passport(passport_id) -> Passport`
- `list_passports(limit, offset, status) -> List[Passport]`
- `revoke_passport(passport_id, reason) -> dict`

#### Badge Management
- `add_badge(passport_id, badge_data) -> Badge`
- `get_badge(badge_id) -> Badge`
- `revoke_badge(badge_id, reason) -> dict`

#### Webhooks
- `create_webhook(url, events) -> WebhookSubscription`
- `list_webhooks() -> List[WebhookSubscription]`
- `delete_webhook(webhook_id) -> dict`

#### API Keys
- `create_api_key(name, permissions) -> APIKey`
- `list_api_keys() -> List[APIKey]`
- `revoke_api_key(key_id) -> dict`

#### Analytics
- `get_usage_stats(start_date, end_date) -> dict`

## Models

### VerificationResult
- `valid: bool` - Is the credential valid?
- `passport_id: str` - Passport ID
- `full_name: str` - User's full name
- `trust_score: int` - Trust score (0-100)
- `badges: List[Badge]` - Active badges
- `verified_at: datetime` - Verification timestamp
- `signature_valid: bool` - Cryptographic signature valid?
- `warnings: List[str]` - Any warnings

### Badge
- `id: str` - Badge ID
- `type: str` - Badge type (e.g., "HEALTHCARE")
- `credential_data: dict` - Credential details
- `status: str` - "active", "expired", "revoked"
- `issued_at: datetime` - Issue timestamp
- `expires_at: datetime` - Expiration (if applicable)
- `is_expired: bool` - Property: is badge expired?

## Testing

```bash
# Install dev dependencies
pip install vettedme[dev]

# Run tests
pytest

# With coverage
pytest --cov=vettedme --cov-report=html
```

## Support

- **Documentation**: https://docs.vettedme.ai
- **API Reference**: https://docs.vettedme.ai/api
- **GitHub**: https://github.com/vettedme/vettedme-python
- **Email**: sdk@vettedme.ai

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

**Built with ❤️ by the VettedMe Team**

*"The Claude of Digital Truth"*
