# @vettedme/sdk

[![npm version](https://badge.fury.io/js/%40vettedme%2Fsdk.svg)](https://www.npmjs.com/package/@vettedme/sdk)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Official JavaScript/TypeScript SDK for the VettedMe Passport API - the universal trust layer for digital identity verification.

## Installation

```bash
npm install @vettedme/sdk

# or
yarn add @vettedme/sdk

# or
pnpm add @vettedme/sdk
```

## Quick Start

```typescript
import { VettedMeClient } from '@vettedme/sdk';

// Initialize client
const client = new VettedMeClient({
  apiKey: 'vm_live_...'
});

// Verify a credential (1-line integration!)
const result = await client.verify('PASS-ABC-123');

if (result.valid) {
  console.log(`✅ Verified: ${result.fullName}`);
  console.log(`Trust Score: ${result.trustScore}%`);
  console.log(`Badges: ${result.badges.map(b => b.type).join(', ')}`);
} else {
  console.log('❌ Verification failed');
}
```

That's it! 🚀

## Features

- ✅ **Full TypeScript support** with complete type definitions
- ⚡ **Async/await** - modern promise-based API
- 🔄 **Automatic retries** for transient errors
- 🌐 **Works everywhere** - Node.js, browsers, React, Vue, Angular, Next.js
- 📦 **Tree-shakeable** - only bundle what you use
- 🛡️ **Type-safe** - catch errors at compile time

## Usage

### Node.js / TypeScript

```typescript
import { VettedMeClient } from '@vettedme/sdk';

const client = new VettedMeClient({ apiKey: process.env.VETTEDME_API_KEY });

async function verifyUser(passportId: string) {
  try {
    const result = await client.verify(passportId);
    return result.valid;
  } catch (error) {
    console.error('Verification failed:', error);
    return false;
  }
}
```

### React

```tsx
import { useState } from 'react';
import { VettedMeClient, VerificationResult } from '@vettedme/sdk';

const client = new VettedMeClient({ apiKey: process.env.VETTEDME_API_KEY });

function VerifyButton({ passportId }: { passportId: string }) {
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [loading, setLoading] = useState(false);

  const handleVerify = async () => {
    setLoading(true);
    try {
      const result = await client.verify(passportId);
      setResult(result);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button onClick={handleVerify} disabled={loading}>
        {loading ? 'Verifying...' : 'Verify Credential'}
      </button>
      
      {result?.valid && (
        <div className="success">
          ✅ {result.fullName} - {result.trustScore}% trust
        </div>
      )}
    </div>
  );
}
```

### Next.js API Route

```typescript
// pages/api/verify.ts
import type { NextApiRequest, NextApiResponse } from 'next';
import { VettedMeClient } from '@vettedme/sdk';

const client = new VettedMeClient({ apiKey: process.env.VETTEDME_API_KEY });

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { passportId } = req.body;

  try {
    const result = await client.verify(passportId);
    res.status(200).json(result);
  } catch (error) {
    res.status(500).json({ error: 'Verification failed' });
  }
}
```

### Express.js

```typescript
import express from 'express';
import { VettedMeClient } from '@vettedme/sdk';

const app = express();
const client = new VettedMeClient({ apiKey: process.env.VETTEDME_API_KEY });

app.post('/api/verify', async (req, res) => {
  try {
    const result = await client.verify(req.body.passportId);
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.listen(3000);
```

## API Reference

### Client

```typescript
new VettedMeClient(config: VettedMeConfig)
```

**Config options:**
- `apiKey: string` - Your VettedMe API key (required)
- `baseUrl?: string` - Custom API URL (default: `https://api.vettedme.ai`)
- `timeout?: number` - Request timeout in ms (default: 30000)

### Methods

#### Verification

```typescript
// Verify a passport
await client.verify(passportId: string): Promise<VerificationResult>

// Verify specific badge
await client.verifyBadge(passportId: string, badgeType: BadgeType): Promise<VerificationResult>
```

#### Passport Management

```typescript
// Create passport
await client.createPassport(userData: PassportCreate): Promise<Passport>

// Get passport
await client.getPassport(passportId: string): Promise<Passport>

// List passports
await client.listPassports(options?: ListOptions): Promise<Passport[]>

// Revoke passport
await client.revokePassport(passportId: string, reason: string): Promise<void>
```

#### Badge Management

```typescript
// Add badge
await client.addBadge(passportId: string, badgeData: BadgeCreate): Promise<Badge>

// Get badge
await client.getBadge(badgeId: string): Promise<Badge>

// Revoke badge
await client.revokeBadge(badgeId: string, reason: string): Promise<void>
```

#### Webhooks

```typescript
// Create webhook
await client.createWebhook(url: string, events: string[]): Promise<WebhookSubscription>

// List webhooks
await client.listWebhooks(): Promise<WebhookSubscription[]>

// Delete webhook
await client.deleteWebhook(webhookId: string): Promise<void>
```

#### API Keys

```typescript
// Create API key
await client.createAPIKey(name: string, permissions: string[]): Promise<APIKey>

// List API keys
await client.listAPIKeys(): Promise<APIKey[]>

// Revoke API key
await client.revokeAPIKey(keyId: string): Promise<void>
```

#### Analytics

```typescript
// Get usage stats
await client.getUsageStats(options?: { startDate?: string; endDate?: string }): Promise<object>
```

## Types

### VerificationResult

```typescript
interface VerificationResult {
  valid: boolean;
  passportId: string;
  fullName: string;
  trustScore: number;
  badges: Badge[];
  verifiedAt: string;
  signatureValid: boolean;
  warnings: string[];
}
```

### Badge

```typescript
interface Badge {
  id: string;
  passportId: string;
  type: BadgeType;
  credentialData: Record<string, any>;
  status: 'active' | 'expired' | 'revoked' | 'pending';
  issuerSignature: string;
  issuedAt: string;
  expiresAt?: string;
  verificationCount: number;
}
```

### BadgeType

```typescript
type BadgeType =
  | 'HEALTHCARE'
  | 'SECURITY_CLEARANCE'
  | 'INSURANCE'
  | 'FINANCIAL_ADVISOR'
  | 'REAL_ESTATE'
  | 'LAWYER'
  | 'EDUCATION'
  | 'EMPLOYMENT'
  | 'BIOMETRIC_ID'
  | 'CRIMINAL_BACKGROUND'
  | 'CREDIT_HISTORY'
  | 'PROFESSIONAL_LICENSE';
```

## Error Handling

```typescript
import {
  AuthenticationError,
  NotFoundError,
  ValidationError,
  RateLimitError,
  ServerError
} from '@vettedme/sdk';

try {
  await client.verify('PASS-ABC-123');
} catch (error) {
  if (error instanceof AuthenticationError) {
    console.error('Invalid API key');
  } else if (error instanceof NotFoundError) {
    console.error('Passport not found');
  } else if (error instanceof RateLimitError) {
    console.error('Rate limit exceeded');
  }
}
```

## Environment Variables

```bash
# .env
VETTEDME_API_KEY=vm_live_...
```

Then:

```typescript
const client = new VettedMeClient({
  apiKey: process.env.VETTEDME_API_KEY
});
```

## Testing

```typescript
// Use sandbox environment
const client = new VettedMeClient({
  apiKey: 'vm_test_...',
  baseUrl: 'https://sandbox.vettedme.ai'
});
```

## Support

- **Documentation**: https://docs.vettedme.ai
- **API Reference**: https://docs.vettedme.ai/api
- **GitHub**: https://github.com/vettedme/vettedme-js
- **Email**: sdk@vettedme.ai

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

**Built with ❤️ by the VettedMe Team**

*"The Claude of Digital Truth"*
