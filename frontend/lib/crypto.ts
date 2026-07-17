/**
 * VettedPay Client-Side Encryption Utilities
 * 
 * This module provides RSA-OAEP encryption for sensitive financial data.
 * The backend NEVER sees the plaintext - only the encrypted compliance packet.
 * 
 * Security Model:
 * 1. Client encrypts PII with recipient's (bank's) public key
 * 2. Backend passes encrypted payload to payment rail
 * 3. Only the payment rail can decrypt (has the private key)
 * 4. Backend logs only the encrypted blob reference
 */

interface BankData {
  account_number: string;
  routing_number: string;
  legal_name: string;
  source_of_funds?: string;
  purpose_of_payment?: string;
}

/**
 * Convert PEM public key to CryptoKey object
 */
async function importPublicKey(pemKey: string): Promise<CryptoKey> {
  // Remove PEM headers and whitespace
  const pemContents = pemKey
    .replace(/-----BEGIN PUBLIC KEY-----/g, '')
    .replace(/-----END PUBLIC KEY-----/g, '')
    .replace(/\s/g, '');
  
  // Base64 decode
  const binaryDer = atob(pemContents);
  const binaryArray = new Uint8Array(binaryDer.length);
  
  for (let i = 0; i < binaryDer.length; i++) {
    binaryArray[i] = binaryDer.charCodeAt(i);
  }
  
  // Import as CryptoKey
  return await window.crypto.subtle.importKey(
    'spki',
    binaryArray.buffer,
    {
      name: 'RSA-OAEP',
      hash: 'SHA-256',
    },
    true,
    ['encrypt']
  );
}

/**
 * Encrypt bank data with recipient's public key
 * 
 * @param bankData - Sensitive financial information to encrypt
 * @param publicKeyPem - Recipient's RSA public key in PEM format
 * @returns Base64-encoded encrypted payload
 */
export async function encryptBankDataForRail(
  bankData: BankData,
  publicKeyPem: string
): Promise<string> {
  try {
    // 1. Convert bank data to JSON
    const jsonPayload = JSON.stringify({
      ...bankData,
      encrypted_at: new Date().toISOString(),
      version: '1.0.0',
    });
    
    // 2. Convert JSON to Uint8Array
    const encoder = new TextEncoder();
    const data = encoder.encode(jsonPayload);
    
    // 3. Import the public key
    const publicKey = await importPublicKey(publicKeyPem);
    
    // 4. Encrypt with RSA-OAEP
    const encryptedData = await window.crypto.subtle.encrypt(
      {
        name: 'RSA-OAEP',
      },
      publicKey,
      data
    );
    
    // 5. Convert to Base64 for transport
    const encryptedArray = new Uint8Array(encryptedData);
    const base64Encrypted = btoa(
      String.fromCharCode.apply(null, Array.from(encryptedArray))
    );
    
    return base64Encrypted;
    
  } catch (error) {
    console.error('Encryption failed:', error);
    throw new Error('Failed to encrypt bank data. Please try again.');
  }
}

/**
 * Generate a ZK-proof of non-sanction (mock implementation)
 * 
 * In production, this would integrate with:
 * - Reclaim Protocol for zkTLS attestations
 * - Your existing compliance verification system
 * - Government sanction list APIs (OFAC, EU, UN)
 * 
 * @param userDid - User's decentralized identifier
 * @returns ZK proof object
 */
export async function generateZKSanctionProof(userDid: string): Promise<object> {
  // TODO: Integrate with Reclaim Protocol or zkTLS library
  
  // Mock implementation for development
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        valid: true,
        timestamp: new Date().toISOString(),
        verification_method: 'OFAC_API_v1',
        provider_hash: generateHash(userDid),
        signature: generateMockSignature(userDid),
        nonce: generateNonce(),
      });
    }, 500); // Simulate async proof generation
  });
}

/**
 * Generate SHA-256 hash of input
 */
function generateHash(input: string): string {
  // In production, use crypto.subtle.digest
  return `sha256_${btoa(input).substring(0, 16)}`;
}

/**
 * Generate mock signature (placeholder)
 */
function generateMockSignature(input: string): string {
  return `sig_${btoa(input + Date.now()).substring(0, 24)}`;
}

/**
 * Generate random nonce
 */
function generateNonce(): string {
  return Math.random().toString(36).substring(2, 15);
}

/**
 * Validate DID format
 */
export function isValidDID(did: string): boolean {
  // Basic DID format validation
  // Example: did:vettedme:123456 or did:ethr:0x123...
  const didRegex = /^did:[a-z]+:[a-zA-Z0-9._-]+$/;
  return didRegex.test(did);
}

/**
 * Validate amount
 */
export function isValidAmount(amount: number): boolean {
  return amount > 0 && amount < 1000000 && Number.isFinite(amount);
}

/**
 * Validate currency code
 */
export function isValidCurrency(currency: string): boolean {
  const validCurrencies = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CHF'];
  return validCurrencies.includes(currency.toUpperCase());
}

/**
 * Format amount for display
 */
export function formatAmount(amount: number, currency: string): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
  }).format(amount);
}

/**
 * Sanitize bank account number (show only last 4 digits)
 */
export function maskAccountNumber(accountNumber: string): string {
  if (accountNumber.length <= 4) return accountNumber;
  return '****' + accountNumber.slice(-4);
}
