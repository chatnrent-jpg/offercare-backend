"""
VettedCare.ai Core Resilience Module

High-throughput circuit breaker and state fallback engine for external registry calls.
Enforces strict 150ms latency ceiling for MBON/OIG compliance checks.
"""

from app.core.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerState

__all__ = ["CircuitBreaker", "CircuitBreakerState"]
