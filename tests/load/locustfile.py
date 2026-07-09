"""
Load Testing with Locust.

Simulates realistic production load:
- 1000 concurrent providers
- 200 concurrent facilities
- Peak dispatch load (500 shifts/hour)
- Background services (geofence, monitoring)

Usage:
    locust -f locustfile.py --host=http://localhost:8000 --users=1000 --spawn-rate=50
"""

from locust import HttpUser, task, between
import random
from datetime import datetime, timedelta


class ProviderUser(HttpUser):
    """Simulates provider mobile app behavior."""
    
    wait_time = between(5, 15)  # 5-15 seconds between actions
    
    def on_start(self):
        """Login provider."""
        self.provider_id = f"test-provider-{random.randint(1000, 9999)}"
        self.phone = f"+1410555{random.randint(1000, 9999)}"
    
    @task(3)
    def view_available_shifts(self):
        """Most common action: Browse available shifts."""
        self.client.get("/api/v1/shifts/available", name="/shifts/available")
    
    @task(2)
    def update_location(self):
        """Background: Update GPS location."""
        self.client.post(
            "/api/v1/location/update",
            json={
                "provider_id": self.provider_id,
                "latitude": 39.2904 + random.uniform(-0.1, 0.1),
                "longitude": -76.6122 + random.uniform(-0.1, 0.1)
            },
            name="/location/update"
        )
    
    @task(1)
    def accept_shift(self):
        """Accept a shift offer."""
        shift_id = f"shift-{random.randint(1000, 9999)}"
        self.client.post(
            f"/api/v1/shifts/{shift_id}/accept",
            json={"provider_id": self.provider_id},
            name="/shifts/accept"
        )
    
    @task(1)
    def check_schedule(self):
        """Check upcoming shifts."""
        self.client.get(
            f"/api/v1/providers/{self.provider_id}/schedule",
            name="/providers/schedule"
        )


class FacilityUser(HttpUser):
    """Simulates facility admin behavior."""
    
    wait_time = between(10, 30)
    
    def on_start(self):
        """Login facility."""
        self.facility_id = f"test-facility-{random.randint(100, 999)}"
    
    @task(3)
    def post_shift(self):
        """Post new shift opening."""
        shift_start = datetime.now() + timedelta(hours=random.randint(4, 48))
        self.client.post(
            "/api/v1/shifts",
            json={
                "facility_id": self.facility_id,
                "shift_start": shift_start.isoformat(),
                "shift_end": (shift_start + timedelta(hours=8)).isoformat(),
                "license_required": random.choice(["CNA", "GNA", "LPN"]),
                "hourly_rate": random.uniform(25.0, 35.0)
            },
            name="/shifts (POST)"
        )
    
    @task(2)
    def view_matched_providers(self):
        """Check wave dispatch results."""
        shift_id = f"shift-{random.randint(1000, 9999)}"
        self.client.get(
            f"/api/v1/shifts/{shift_id}/matches",
            name="/shifts/matches"
        )
    
    @task(1)
    def get_billing_summary(self):
        """View billing summary."""
        self.client.get(
            f"/api/v1/billing/summary/{self.facility_id}",
            name="/billing/summary"
        )


class BackgroundServiceUser(HttpUser):
    """Simulates background Celery tasks."""
    
    wait_time = between(30, 60)
    
    @task
    def geofence_monitoring(self):
        """Simulate geofence checks."""
        self.client.post(
            "/api/internal/geofence/monitor",
            json={"monitoring_window": 60},
            name="/geofence/monitor"
        )
    
    @task
    def predictive_callout_scan(self):
        """Simulate call-out prediction scan."""
        self.client.post(
            "/api/internal/callout/scan",
            json={"days_ahead": 7},
            name="/callout/scan"
        )
    
    @task
    def cms_ratio_check(self):
        """Simulate CMS ratio monitoring."""
        self.client.post(
            "/api/internal/cms/check-ratios",
            name="/cms/check-ratios"
        )


# Performance Thresholds
class PerformanceTest:
    """
    Performance acceptance criteria:
    
    - Average response time < 200ms (API endpoints)
    - 95th percentile < 500ms
    - 99th percentile < 1000ms
    - Error rate < 0.1%
    - Throughput > 500 req/sec
    - Database connection pool < 80% utilization
    """
    
    THRESHOLDS = {
        "avg_response_time": 200,      # ms
        "p95_response_time": 500,       # ms
        "p99_response_time": 1000,      # ms
        "error_rate": 0.001,            # 0.1%
        "min_throughput": 500,          # req/sec
        "max_db_pool_usage": 0.80       # 80%
    }
