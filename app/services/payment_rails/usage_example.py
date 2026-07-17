"""
VettedPay Transaction Manager - Usage Examples

Shows how to use the transaction engine for processing compliant transfers
with ZK-proof verification and dynamic provider routing.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any

from .transaction_manager import VettedPayTransactionEngine
from .compliance_packet import CompliancePacketGenerator, CompliancePayload


# ============================================================================
# Example 1: Simple Transfer with Pre-Encrypted Compliance Packet
# ============================================================================

async def example_simple_transfer():
    """
    Process a transfer when you already have an encrypted compliance packet.
    This is the most common use case - frontend generates and encrypts the packet.
    """
    
    # Initialize transaction engine (flip provider to switch rails)
    engine = VettedPayTransactionEngine(
        active_provider="airwallex",  # ← Change to "nium", "wise", etc.
        provider_config={
            "api_url": "https://api.airwallex.com",
            "api_token": "your_airwallex_token"
        }
    )
    
    # ZK-proof from frontend (user proved non-sanction without revealing identity)
    zk_proof = {
        "valid": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "signature": "0xabc123...",
        "proof_type": "reclaim_zktls",
        "verified_claims": ["country:US", "sanctions:clear"]
    }
    
    # Pre-encrypted compliance packet (encrypted by frontend with bank's public key)
    encrypted_packet = "base64_encoded_encrypted_packet_here..."
    
    # Process transfer
    result = await engine.process_transfer(
        sender_did="did:vettedcare:caregiver:12345",
        recipient_did="did:vettedcare:facility:67890",
        zk_proof=zk_proof,
        encrypted_compliance_packet=encrypted_packet,
        amount=1500.00,
        currency="USD",
        destination_account="beneficiary_id_123",
        metadata={
            "shift_id": "shift_789",
            "facility": "Johns Hopkins Hospital",
            "reference": "Per-diem nursing shift - 12 hours"
        }
    )
    
    if result["success"]:
        print(f"✅ Transfer successful!")
        print(f"   Transaction ID: {result['transaction_id']}")
        print(f"   Rail: {result['rail']}")
        print(f"   Status: {result['status']}")
        print(f"   Compliance verified: {result['compliance_verified']}")
    else:
        print(f"❌ Transfer failed: {result['error']}")
        print(f"   Error code: {result.get('error_code')}")
    
    return result


# ============================================================================
# Example 2: Transfer with Automatic Compliance Generation
# ============================================================================

async def example_transfer_with_compliance_generation():
    """
    Process a transfer with automatic compliance packet generation.
    Use this when your backend needs to generate the packet.
    """
    
    # Initialize compliance generator
    bank_public_keys = {
        "chase": """-----BEGIN PUBLIC KEY-----
YOUR_CHASE_PUBLIC_KEY_HERE
-----END PUBLIC KEY-----""",
    }
    
    compliance_generator = CompliancePacketGenerator(
        signing_key="your_hmac_signing_key",
        recipient_public_keys=bank_public_keys,
        environment="production"
    )
    
    # Initialize transaction engine with compliance generator
    engine = VettedPayTransactionEngine(
        active_provider="airwallex",
        provider_config={
            "api_url": "https://api.airwallex.com",
            "api_token": "your_airwallex_token"
        },
        compliance_generator=compliance_generator
    )
    
    # Raw compliance data (will be encrypted automatically)
    compliance_data = CompliancePayload(
        provider_id="caregiver_12345",
        full_name="Jane Smith",
        date_of_birth="1990-01-15",
        national_id="SSN-XXX-XX-1234",
        address={
            "street": "123 Main St",
            "city": "Baltimore",
            "state": "MD",
            "country": "US",
            "postal_code": "21201"
        },
        sanction_check_timestamp=datetime.now(timezone.utc).isoformat(),
        sanction_check_result="CLEAR",
        ofac_check=True,
        eu_sanctions_check=True,
        un_sanctions_check=True,
        source_of_funds="Employment income",
        purpose_of_payment="Healthcare services rendered",
        compliance_officer="compliance@vettedcare.ai"
    )
    
    # ZK-proof
    zk_proof = {
        "valid": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "signature": "0xdef456..."
    }
    
    # Process transfer (compliance packet generated automatically)
    result = await engine.process_transfer_with_compliance_generation(
        sender_did="did:vettedcare:caregiver:12345",
        recipient_did="did:vettedcare:facility:67890",
        zk_proof=zk_proof,
        compliance_data=compliance_data,
        recipient_bank_id="chase",  # Which bank's key to use
        amount=2000.00,
        currency="USD",
        destination_account="beneficiary_id_456"
    )
    
    return result


# ============================================================================
# Example 3: Check Transfer Status
# ============================================================================

async def example_check_status(transaction_id: str):
    """Check the status of a previously initiated transfer"""
    
    engine = VettedPayTransactionEngine(
        active_provider="airwallex",
        provider_config={
            "api_url": "https://api.airwallex.com",
            "api_token": "your_airwallex_token"
        }
    )
    
    status = await engine.check_transfer_status(transaction_id)
    
    print(f"Transaction Status:")
    print(f"  ID: {status['transaction_id']}")
    print(f"  Status: {status['status']}")
    print(f"  Amount: {status['amount']} {status['currency']}")
    print(f"  Rail: {status['rail']}")
    
    return status


# ============================================================================
# Example 4: Cancel Pending Transfer
# ============================================================================

async def example_cancel_transfer(transaction_id: str):
    """Cancel a pending transfer before it completes"""
    
    engine = VettedPayTransactionEngine(
        active_provider="airwallex",
        provider_config={
            "api_url": "https://api.airwallex.com",
            "api_token": "your_airwallex_token"
        }
    )
    
    result = await engine.cancel_transfer(transaction_id)
    
    if result["success"]:
        print(f"✅ Transfer cancelled: {transaction_id}")
    else:
        print(f"❌ Cancellation failed: {result['error']}")
    
    return result


# ============================================================================
# Example 5: Health Check
# ============================================================================

async def example_health_check():
    """Check if the active financial rail is healthy"""
    
    engine = VettedPayTransactionEngine(
        active_provider="airwallex",
        provider_config={
            "api_url": "https://api.airwallex.com",
            "api_token": "your_airwallex_token"
        }
    )
    
    health = await engine.health_check()
    
    print(f"Provider Health:")
    print(f"  Provider: {health['provider']}")
    print(f"  Healthy: {health['healthy']}")
    print(f"  Timestamp: {health['timestamp']}")
    
    return health


# ============================================================================
# Example 6: Dynamic Provider Switching
# ============================================================================

async def example_provider_switching():
    """
    Show how to switch providers dynamically.
    If Airwallex shuts down API, just change active_provider.
    """
    
    # Configuration for multiple providers
    providers_config = {
        "airwallex": {
            "api_url": "https://api.airwallex.com",
            "api_token": "airwallex_token"
        },
        "nium": {
            "api_url": "https://api.nium.com",
            "api_token": "nium_token"
        },
        "wise": {
            "api_url": "https://api.wise.com",
            "api_token": "wise_token"
        }
    }
    
    # Read active provider from environment or config
    import os
    active_provider = os.getenv("VETTEDPAY_ACTIVE_PROVIDER", "airwallex")
    
    # Initialize with active provider
    engine = VettedPayTransactionEngine(
        active_provider=active_provider,  # ← SINGLE POINT OF CONTROL
        provider_config=providers_config[active_provider]
    )
    
    print(f"Using provider: {engine.get_active_provider()}")
    
    # Same code works regardless of provider
    # If Airwallex fails → Set VETTEDPAY_ACTIVE_PROVIDER=nium
    # Your application continues working


# ============================================================================
# Example 7: Frontend Integration Pattern
# ============================================================================

async def example_frontend_integration(request_data: Dict[str, Any]):
    """
    Typical pattern for integrating with frontend.
    Frontend sends: ZK-proof + encrypted packet + transfer details
    """
    
    engine = VettedPayTransactionEngine(
        active_provider="airwallex",
        provider_config={
            "api_url": "https://api.airwallex.com",
            "api_token": "your_token"
        }
    )
    
    # Extract data from frontend request
    sender_did = request_data["sender_did"]
    recipient_did = request_data["recipient_did"]
    zk_proof = request_data["zk_proof"]  # Frontend generated
    encrypted_packet = request_data["compliance_packet"]  # Frontend encrypted
    amount = request_data["amount"]
    currency = request_data["currency"]
    destination = request_data["destination_account"]
    
    # Process transfer
    result = await engine.process_transfer(
        sender_did=sender_did,
        recipient_did=recipient_did,
        zk_proof=zk_proof,
        encrypted_compliance_packet=encrypted_packet,
        amount=amount,
        currency=currency,
        destination_account=destination
    )
    
    # Return to frontend
    return {
        "success": result["success"],
        "transaction_id": result.get("transaction_id"),
        "status": result.get("status"),
        "error": result.get("error")
    }


# ============================================================================
# Run Examples
# ============================================================================

async def main():
    """Run all examples"""
    
    print("=" * 60)
    print("VettedPay Transaction Manager Examples")
    print("=" * 60)
    
    # Example 1: Simple transfer
    print("\n1. Simple Transfer")
    print("-" * 60)
    # await example_simple_transfer()
    
    # Example 2: Transfer with compliance generation
    print("\n2. Transfer with Compliance Generation")
    print("-" * 60)
    # await example_transfer_with_compliance_generation()
    
    # Example 3: Check status
    print("\n3. Check Transfer Status")
    print("-" * 60)
    # await example_check_status("transaction_id_here")
    
    # Example 4: Health check
    print("\n4. Health Check")
    print("-" * 60)
    # await example_health_check()
    
    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
