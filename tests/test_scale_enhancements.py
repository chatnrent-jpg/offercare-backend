import pytest
from datetime import datetime, timedelta, timezone
from data_engine.external_adapters import TransitAwareRoutingService
from data_engine.matching_engine import AutonomousDispatcher

def test_transit_aware_routing_corridor_latency():
    """Confirms that major Maryland bottlenecks inject the proper travel latency padding."""
    # Test a known bottleneck ZIP code (Baltimore Beltway / I-695 area)
    bottleneck_latency = TransitAwareRoutingService.calculate_corridor_latency("21201", "21117")
    assert bottleneck_latency == 25

    # Test clean, non-bottleneck regional ZIP routing
    clean_latency = TransitAwareRoutingService.calculate_corridor_latency("20001", "20002")
    assert clean_latency == 0

def test_autonomous_dispatcher_wave_segmentation():
    """Confirms that provider arrays slice cleanly into 5-minute cascading notification tiers."""
    mock_provider_ids = [f"provider_{i}" for i in range(20)]
    waves = AutonomousDispatcher.segment_match_waves(mock_provider_ids)

    assert len(waves[1]) == 5   # Tier 1: Top 5 closest matches
    assert len(waves[2]) == 10  # Tier 2: Mid-tier options
    assert len(waves[3]) == 5   # Tier 3: Remainder of index group

def test_autonomous_dispatcher_price_escalation_trigger():
    """Confirms pay auto-escalates when approaching a high-priority, unfilled shift window."""
    # Create a mock shift context expiring in 1 hour (3600 seconds), under budget cap
    urgent_shift = {
        "start_time": datetime.now(timezone.utc) + timedelta(hours=1),
        "current_escalated_rate": 45.00,
        "max_budget_hourly_rate": 60.00
    }
    
    new_rate = AutonomousDispatcher.evaluate_price_escalation(urgent_shift)
    assert new_rate == 50.00  # Confirms a clean $5.00 automated incremental rate increase

def test_autonomous_dispatcher_price_escalation_capped():
    """Confirms pay escalation strictly respects pre-approved facility budget ceilings."""
    # Shift expiring soon, but current rate is already hitting the maximum budget cap
    capped_shift = {
        "start_time": datetime.now(timezone.utc) + timedelta(hours=1),
        "current_escalated_rate": 58.00,
        "max_budget_hourly_rate": 60.00
    }
    
    new_rate = AutonomousDispatcher.evaluate_price_escalation(capped_shift)
    assert new_rate == 60.00  # Caps out right at the maximum line without breaking limits
