"""
Generate Fernet encryption key for invoice encryption.

Usage:
    python scripts/generate_encryption_key.py

This will generate a new Fernet encryption key and print it to stdout.
Store this key securely in your secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.)
and set it as the INVOICE_ENCRYPTION_KEY environment variable.

IMPORTANT: 
- Keep this key secret and never commit it to version control
- Back up the key securely - lost keys mean lost data
- Rotate keys periodically (recommended: every 90 days)
"""

from cryptography.fernet import Fernet

def generate_key():
    """Generate a new Fernet encryption key."""
    key = Fernet.generate_key()
    key_str = key.decode()
    
    print("=" * 80)
    print("VETTEDPULSE INVOICE ENCRYPTION KEY")
    print("=" * 80)
    print()
    print(f"Generated Key: {key_str}")
    print()
    print("SETUP INSTRUCTIONS:")
    print("1. Copy the key above")
    print("2. Add to your .env file:")
    print(f"   INVOICE_ENCRYPTION_KEY={key_str}")
    print("3. Or set via environment variable:")
    print(f"   export INVOICE_ENCRYPTION_KEY='{key_str}'")
    print()
    print("SECURITY WARNINGS:")
    print("- NEVER commit this key to version control")
    print("- Store in secrets manager (AWS Secrets Manager, Vault, etc.)")
    print("- Back up securely - lost keys = lost data")
    print("- Rotate every 90 days (configurable)")
    print()
    print("=" * 80)

if __name__ == "__main__":
    generate_key()
