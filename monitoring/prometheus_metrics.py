"""
Prometheus metrics instrumentation for VettedPulse.

Exposes custom business and performance metrics for Prometheus/Grafana.
"""

from prometheus_client import Counter, Histogram, Gauge, Summary
import time
from functools import wraps
from typing import Callable

# ============================================================================
# BUSINESS METRICS
# ============================================================================

# Shift metrics
shifts_posted_total = Counter(
    'vettedpulse_shifts_posted_total',
    'Total number of shifts posted',
    ['facility_id', 'license_type']
)

shifts_filled_total = Counter(
    'vettedpulse_shifts_filled_total',
    'Total number of shifts filled',
    ['facility_id', 'license_type']
)

shifts_cancelled_total = Counter(
    'vettedpulse_shifts_cancelled_total',
    'Total number of shifts cancelled',
    ['reason']
)

# Provider metrics
providers_active = Gauge(
    'vettedpulse_providers_active',
    'Number of active providers',
    ['license_type']
)

providers_registered_total = Counter(
    'vettedpulse_providers_registered_total',
    'Total providers registered',
    ['license_type']
)

# Facility metrics
facilities_active = Gauge(
    'vettedpulse_facilities_active',
    'Number of active facilities'
)

# Revenue metrics (estimated)
revenue_total = Counter(
    'vettedpulse_revenue_total_dollars',
    'Total revenue in dollars',
    ['facility_id']
)

# ============================================================================
# PERFORMANCE METRICS
# ============================================================================

# Wave dispatch
wave_dispatch_duration = Histogram(
    'vettedpulse_wave_dispatch_duration_seconds',
    'Time taken for wave dispatch',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

wave_dispatch_providers_contacted = Histogram(
    'vettedpulse_wave_dispatch_providers_contacted',
    'Number of providers contacted per wave',
    buckets=[5, 10, 20, 50, 100, 200]
)

wave_dispatch_success = Counter(
    'vettedpulse_wave_dispatch_success_total',
    'Successful wave dispatches'
)

wave_dispatch_failure = Counter(
    'vettedpulse_wave_dispatch_failure_total',
    'Failed wave dispatches',
    ['error_type']
)

# Billing
billing_calculation_duration = Histogram(
    'vettedpulse_billing_calculation_duration_seconds',
    'Time taken to calculate invoice',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
)

billing_invoices_generated = Counter(
    'vettedpulse_billing_invoices_generated_total',
    'Total invoices generated',
    ['facility_id']
)

# Geofence monitoring
geofence_checks_total = Counter(
    'vettedpulse_geofence_checks_total',
    'Total geofence location checks',
    ['status']
)

geofence_check_duration = Histogram(
    'vettedpulse_geofence_check_duration_seconds',
    'Time taken for geofence check',
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0]
)

# Traffic routing
traffic_routing_duration = Histogram(
    'vettedpulse_traffic_routing_duration_seconds',
    'Time taken for traffic routing calculation',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
)

# MBON verification
mbon_verifications_total = Counter(
    'vettedpulse_mbon_verifications_total',
    'Total MBON license verifications',
    ['status']
)

mbon_verification_duration = Histogram(
    'vettedpulse_mbon_verification_duration_seconds',
    'Time taken for MBON verification',
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0]
)

# ============================================================================
# RELIABILITY METRICS
# ============================================================================

# SMS delivery
sms_sent_total = Counter(
    'vettedpulse_sms_sent_total',
    'Total SMS messages sent',
    ['purpose']
)

sms_delivered_total = Counter(
    'vettedpulse_sms_delivered_total',
    'Total SMS messages delivered',
    ['purpose']
)

sms_failed_total = Counter(
    'vettedpulse_sms_failed_total',
    'Total SMS messages failed',
    ['error_type']
)

# Email delivery
email_sent_total = Counter(
    'vettedpulse_email_sent_total',
    'Total emails sent',
    ['purpose']
)

# External API calls
external_api_calls_total = Counter(
    'vettedpulse_external_api_calls_total',
    'Total external API calls',
    ['service', 'status']
)

external_api_duration = Histogram(
    'vettedpulse_external_api_duration_seconds',
    'Time taken for external API calls',
    ['service'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# ============================================================================
# DECORATOR UTILITIES
# ============================================================================

def track_duration(metric: Histogram):
    """Decorator to track function execution duration."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.time() - start
                metric.observe(duration)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.time() - start
                metric.observe(duration)
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def track_success_failure(success_counter: Counter, failure_counter: Counter):
    """Decorator to track success/failure rates."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                success_counter.inc()
                return result
            except Exception as e:
                failure_counter.labels(error_type=type(e).__name__).inc()
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                success_counter.inc()
                return result
            except Exception as e:
                failure_counter.labels(error_type=type(e).__name__).inc()
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

"""
# In wave_match_dispatcher.py:
from monitoring.prometheus_metrics import (
    wave_dispatch_duration,
    wave_dispatch_success,
    wave_dispatch_failure,
    track_duration,
    track_success_failure
)

class WaveMatchDispatcher:
    @track_duration(wave_dispatch_duration)
    @track_success_failure(wave_dispatch_success, wave_dispatch_failure)
    async def trigger_wave_dispatch(self, job_offer_id: UUID):
        # ... dispatch logic ...
        pass

# In billing engine:
from monitoring.prometheus_metrics import billing_calculation_duration, track_duration

class B2BInvoicingEngine:
    @track_duration(billing_calculation_duration)
    async def calculate_invoice(self, timesheet_id: UUID):
        # ... billing logic ...
        pass
"""
