import pytest
import json
from data_engine.production_telemetry import VettedMeTelemetry

def test_telemetry_logs_circuit_state_accurately():
    """Confirms that circuit state tracking serializes telemetry payloads correctly."""
    telemetry = VettedMeTelemetry()
    raw_report = telemetry.log_circuit_state(
        component="SemanticMatcher",
        state="CLOSED",
        latency=0.045  # 45 milliseconds
    )
    
    report_data = json.loads(raw_report)
    assert report_data["state"] == "CLOSED"
    assert report_data["last_latency_ms"] == 45.0
    assert "timestamp" in report_data
    assert report_data["failure_count"] == 0

def test_verify_database_pool_health_thresholds():
    """Confirms that database connection tracking flags saturation risks properly."""
    # Under healthy load bounds
    assert VettedMeTelemetry.verify_database_pool_health(150) is True
    
    # Exceeding healthy load limits (>450 connections)
    assert VettedMeTelemetry.verify_database_pool_health(500) is False
