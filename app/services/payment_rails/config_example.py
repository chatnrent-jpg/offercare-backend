"""
VettedPay Multi-Rail Configuration Example

Shows how to configure the payment router with multiple rails
and switch providers with a single flag.
"""

from typing import Dict, Any
from .payout_adapter import PayoutRail
from .payout_router import PayoutRouter, RoutingStrategy
from .compliance_packet import CompliancePacketGenerator
from .providers.airwallex_rail import AirwallexRail


# ============================================================================
# SINGLE POINT OF CONFIGURATION - Change primary_rail to switch providers
# ============================================================================

def create_vettedpay_router(
    primary_rail: PayoutRail = PayoutRail.AIRWALLEX,  # ← FLIP THIS TO SWITCH RAILS
    environment: str = "sandbox"
) -> PayoutRouter:
    """
    Create configured payment router.
    
    To switch from Airwallex to Nium:
        Just change: primary_rail=PayoutRail.NIUM
    
    To enable automatic failover:
        Set routing_strategy=RoutingStrategy.FAILOVER
    """
    
    # ========================================================================
    # Provider Credentials (from environment variables in production)
    # ========================================================================
    
    airwallex_config = {
        "environment": environment,
        "api_url": "https://api.airwallex.com",
        "api_token": "YOUR_AIRWALLEX_API_TOKEN",
    }
    
    # nium_config = {
    #     "environment": environment,
    #     "client_id": "YOUR_NIUM_CLIENT_ID",
    #     "client_secret": "YOUR_NIUM_SECRET",
    # }
    
    # wise_config = {
    #     "environment": environment,
    #     "api_token": "YOUR_WISE_TOKEN",
    # }
    
    # ========================================================================
    # Compliance Configuration
    # ========================================================================
    
    # Bank public keys for payload encryption
    # The bank can decrypt, but your server cannot
    bank_public_keys = {
        "chase": """-----BEGIN PUBLIC KEY-----
YOUR_CHASE_PUBLIC_KEY_HERE
-----END PUBLIC KEY-----""",
        "hsbc": """-----BEGIN PUBLIC KEY-----
YOUR_HSBC_PUBLIC_KEY_HERE
-----END PUBLIC KEY-----""",
    }
    
    compliance_generator = CompliancePacketGenerator(
        signing_key="YOUR_HMAC_SIGNING_KEY",
        recipient_public_keys=bank_public_keys,
        environment=environment
    )
    
    # ========================================================================
    # Initialize Provider Adapters
    # ========================================================================
    
    adapters = {
        PayoutRail.AIRWALLEX: AirwallexRail(airwallex_config),
        # PayoutRail.NIUM: NiumRail(nium_config),
        # PayoutRail.WISE: WiseRail(wise_config),
    }
    
    # ========================================================================
    # Router Configuration
    # ========================================================================
    
    router_config = {
        "routing_strategy": RoutingStrategy.FAILOVER.value,
        "failover_rails": [
            # PayoutRail.NIUM,
            # PayoutRail.WISE,
        ],
        "max_retries": 3,
        "circuit_breaker_threshold": 5,
    }
    
    return PayoutRouter(
        primary_rail=primary_rail,
        adapters=adapters,
        compliance_generator=compliance_generator,
        config=router_config
    )


# ============================================================================
# Usage Example
# ============================================================================

async def example_payout():
    """
    Example showing how to execute a compliant cross-border payout.
    """
    from .compliance_packet import CompliancePayload
    from datetime import datetime
    
    # Initialize router (flip primary_rail to switch providers)
    router = create_vettedpay_router(
        primary_rail=PayoutRail.AIRWALLEX  # ← Change to NIUM, WISE, etc.
    )
    
    # Provider compliance data
    provider_data = CompliancePayload(
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
        sanction_check_timestamp=datetime.utcnow().isoformat(),
        sanction_check_result="CLEAR",
        ofac_check=True,
        eu_sanctions_check=True,
        un_sanctions_check=True,
        source_of_funds="Employment income",
        purpose_of_payment="Healthcare services rendered",
        compliance_officer="compliance@vettedcare.ai"
    )
    
    # Execute payout
    result = await router.execute_payout(
        amount=1500.00,
        currency="USD",
        destination="beneficiary_abc123",
        provider_data=provider_data,
        recipient_bank_id="chase",  # Which bank's key to use for encryption
        metadata={
            "shift_id": "shift_789",
            "facility": "Johns Hopkins Hospital",
            "reason": "Per-diem nursing shift - 12 hours"
        }
    )
    
    if result.success:
        print(f"✅ Payout successful!")
        print(f"Transaction ID: {result.transaction_id}")
        print(f"Rail: {result.rail.value}")
        print(f"Status: {result.status.value}")
        print(f"Compliance verified: {result.compliance_verified}")
    else:
        print(f"❌ Payout failed: {result.error_message}")
    
    return result


# ============================================================================
# Provider Migration Example
# ============================================================================

"""
SCENARIO: Airwallex shuts down your API access

OLD CODE (Before):
    primary_rail = PayoutRail.AIRWALLEX

NEW CODE (After - single line change):
    primary_rail = PayoutRail.NIUM

That's it. Your entire application continues working.
Zero business logic changes. Zero database migrations.
Your compliance packets work with any provider.

This is the power of the Adapter Pattern + Provider Abstraction.
"""


# ============================================================================
# Environment-Based Configuration (Production Pattern)
# ============================================================================

def create_production_router() -> PayoutRouter:
    """
    Production configuration using environment variables.
    """
    import os
    
    # Read primary rail from environment
    primary_rail_name = os.getenv("VETTEDPAY_PRIMARY_RAIL", "airwallex").upper()
    primary_rail = PayoutRail[primary_rail_name]
    
    # Airwallex config from env
    airwallex_config = {
        "environment": os.getenv("VETTEDPAY_ENVIRONMENT", "production"),
        "api_url": os.getenv("AIRWALLEX_API_URL", "https://api.airwallex.com"),
        "api_token": os.getenv("AIRWALLEX_API_TOKEN"),
    }
    
    # Bank keys from secure storage
    bank_public_keys = {
        "chase": os.getenv("CHASE_PUBLIC_KEY"),
        "hsbc": os.getenv("HSBC_PUBLIC_KEY"),
    }
    
    compliance_generator = CompliancePacketGenerator(
        signing_key=os.getenv("COMPLIANCE_SIGNING_KEY"),
        recipient_public_keys=bank_public_keys,
        environment=os.getenv("VETTEDPAY_ENVIRONMENT", "production")
    )
    
    adapters = {
        PayoutRail.AIRWALLEX: AirwallexRail(airwallex_config),
    }
    
    router_config = {
        "routing_strategy": os.getenv("VETTEDPAY_ROUTING_STRATEGY", "failover"),
        "max_retries": int(os.getenv("VETTEDPAY_MAX_RETRIES", "3")),
        "circuit_breaker_threshold": int(os.getenv("VETTEDPAY_CIRCUIT_THRESHOLD", "5")),
    }
    
    return PayoutRouter(
        primary_rail=primary_rail,
        adapters=adapters,
        compliance_generator=compliance_generator,
        config=router_config
    )
