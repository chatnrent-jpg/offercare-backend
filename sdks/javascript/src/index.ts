/**
 * VettedMe JavaScript/TypeScript SDK
 * 
 * @example
 * ```typescript
 * import { VettedMeClient } from '@vettedme/sdk';
 * 
 * const client = new VettedMeClient({ apiKey: 'vm_live_...' });
 * 
 * const result = await client.verify('PASS-ABC-123');
 * 
 * if (result.valid) {
 *   console.log(`✅ ${result.fullName} - ${result.trustScore}% trust`);
 * }
 * ```
 */

import axios, { AxiosInstance, AxiosError } from 'axios';

// ==================== TYPES ====================

export interface VettedMeConfig {
  apiKey: string;
  baseUrl?: string;
  timeout?: number;
}

export interface Passport {
  id: string;
  userId: string;
  fullName: string;
  email: string;
  phone?: string;
  passportNumber: string;
  trustScore: number;
  status: 'active' | 'revoked' | 'suspended';
  issuerSignature: string;
  issuedAt: string;
  expiresAt?: string;
  badges: Badge[];
  verificationCount: number;
  lastVerifiedAt?: string;
}

export interface Badge {
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

export type BadgeType =
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

export interface VerificationResult {
  valid: boolean;
  passportId: string;
  fullName: string;
  trustScore: number;
  badges: Badge[];
  verifiedAt: string;
  signatureValid: boolean;
  warnings: string[];
}

export interface PassportCreate {
  fullName: string;
  email: string;
  phone?: string;
  [key: string]: any;
}

export interface BadgeCreate {
  type: BadgeType;
  credentialData: Record<string, any>;
  expiresAt?: string;
  [key: string]: any;
}

export interface WebhookSubscription {
  id: string;
  url: string;
  events: string[];
  secret?: string;
  active: boolean;
  createdAt: string;
}

export interface APIKey {
  id: string;
  name: string;
  key?: string;
  permissions: string[];
  active: boolean;
  createdAt: string;
  lastUsedAt?: string;
}

// ==================== EXCEPTIONS ====================

export class VettedMeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'VettedMeError';
  }
}

export class AuthenticationError extends VettedMeError {
  constructor(message = 'Invalid API key') {
    super(message);
    this.name = 'AuthenticationError';
  }
}

export class NotFoundError extends VettedMeError {
  constructor(message = 'Resource not found') {
    super(message);
    this.name = 'NotFoundError';
  }
}

export class ValidationError extends VettedMeError {
  constructor(message = 'Validation error') {
    super(message);
    this.name = 'ValidationError';
  }
}

export class RateLimitError extends VettedMeError {
  constructor(message = 'Rate limit exceeded') {
    super(message);
    this.name = 'RateLimitError';
  }
}

export class ServerError extends VettedMeError {
  constructor(message = 'Server error') {
    super(message);
    this.name = 'ServerError';
  }
}

// ==================== CLIENT ====================

export class VettedMeClient {
  private client: AxiosInstance;
  private apiKey: string;

  constructor(config: VettedMeConfig) {
    this.apiKey = config.apiKey || process.env.VETTEDME_API_KEY || '';
    
    if (!this.apiKey) {
      throw new AuthenticationError(
        'API key required. Pass apiKey in constructor or set VETTEDME_API_KEY environment variable.'
      );
    }

    this.client = axios.create({
      baseURL: config.baseUrl || 'https://api.vettedme.ai',
      timeout: config.timeout || 30000,
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'User-Agent': 'vettedme-js/1.0.0',
        'Content-Type': 'application/json',
      },
    });

    // Error handling interceptor
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response) {
          const status = error.response.status;
          const data: any = error.response.data;

          if (status === 401) {
            throw new AuthenticationError('Invalid API key');
          } else if (status === 404) {
            throw new NotFoundError('Resource not found');
          } else if (status === 422) {
            throw new ValidationError(data?.detail || 'Validation error');
          } else if (status === 429) {
            throw new RateLimitError('Rate limit exceeded. Upgrade your plan or try again later.');
          } else if (status >= 500) {
            throw new ServerError(`Server error: ${status}`);
          }
        }
        throw new VettedMeError(`Request failed: ${error.message}`);
      }
    );
  }

  // ==================== VERIFICATION API ====================

  /**
   * Verify a passport credential (instant verification)
   * 
   * @param passportId - The passport ID (e.g., "PASS-ABC-123")
   * @param options - Additional verification options
   * @returns Verification result
   * 
   * @example
   * ```typescript
   * const result = await client.verify('PASS-ABC-123');
   * 
   * if (result.valid) {
   *   console.log(`✅ ${result.fullName} - ${result.trustScore}% trust`);
   * }
   * ```
   */
  async verify(passportId: string, options?: Record<string, any>): Promise<VerificationResult> {
    const { data } = await this.client.post('/api/v1/passport/verify', {
      passport_id: passportId,
      ...options,
    });
    return data;
  }

  /**
   * Verify a specific badge on a passport
   */
  async verifyBadge(passportId: string, badgeType: BadgeType): Promise<VerificationResult> {
    const { data } = await this.client.post('/api/v1/passport/verify', {
      passport_id: passportId,
      badge_type: badgeType,
    });
    return data;
  }

  // ==================== PASSPORT MANAGEMENT ====================

  /**
   * Create a new passport for a user
   */
  async createPassport(userData: PassportCreate): Promise<Passport> {
    const { data } = await this.client.post('/api/v1/passport', userData);
    return data;
  }

  /**
   * Get passport details
   */
  async getPassport(passportId: string): Promise<Passport> {
    const { data } = await this.client.get(`/api/v1/passport/${passportId}`);
    return data;
  }

  /**
   * List all passports (for your organization)
   */
  async listPassports(options?: {
    limit?: number;
    offset?: number;
    status?: string;
  }): Promise<Passport[]> {
    const { data } = await this.client.get('/api/v1/passport', { params: options });
    return data.passports || [];
  }

  /**
   * Revoke a passport
   */
  async revokePassport(passportId: string, reason: string): Promise<void> {
    await this.client.post(`/api/v1/passport/${passportId}/revoke`, { reason });
  }

  // ==================== BADGE MANAGEMENT ====================

  /**
   * Add a credential badge to a passport
   */
  async addBadge(passportId: string, badgeData: BadgeCreate): Promise<Badge> {
    const { data } = await this.client.post(`/api/v1/passport/${passportId}/badges`, badgeData);
    return data;
  }

  /**
   * Get badge details
   */
  async getBadge(badgeId: string): Promise<Badge> {
    const { data } = await this.client.get(`/api/v1/badges/${badgeId}`);
    return data;
  }

  /**
   * Revoke a badge
   */
  async revokeBadge(badgeId: string, reason: string): Promise<void> {
    await this.client.post(`/api/v1/badges/${badgeId}/revoke`, { reason });
  }

  // ==================== WEBHOOK MANAGEMENT ====================

  /**
   * Create a webhook subscription
   */
  async createWebhook(url: string, events: string[]): Promise<WebhookSubscription> {
    const { data } = await this.client.post('/api/v1/webhooks', { url, events });
    return data;
  }

  /**
   * List all webhook subscriptions
   */
  async listWebhooks(): Promise<WebhookSubscription[]> {
    const { data } = await this.client.get('/api/v1/webhooks');
    return data.webhooks || [];
  }

  /**
   * Delete a webhook subscription
   */
  async deleteWebhook(webhookId: string): Promise<void> {
    await this.client.delete(`/api/v1/webhooks/${webhookId}`);
  }

  // ==================== API KEY MANAGEMENT ====================

  /**
   * Create a new API key
   */
  async createAPIKey(name: string, permissions: string[]): Promise<APIKey> {
    const { data } = await this.client.post('/api/v1/api-keys', { name, permissions });
    return data;
  }

  /**
   * List all API keys
   */
  async listAPIKeys(): Promise<APIKey[]> {
    const { data } = await this.client.get('/api/v1/api-keys');
    return data.keys || [];
  }

  /**
   * Revoke an API key
   */
  async revokeAPIKey(keyId: string): Promise<void> {
    await this.client.delete(`/api/v1/api-keys/${keyId}`);
  }

  // ==================== ANALYTICS ====================

  /**
   * Get usage statistics
   */
  async getUsageStats(options?: {
    startDate?: string;
    endDate?: string;
  }): Promise<Record<string, any>> {
    const { data } = await this.client.get('/api/v1/analytics/usage', { params: options });
    return data;
  }
}

// ==================== DEFAULT EXPORT ====================

export default VettedMeClient;
