# Analytics Endpoint Verification Guide

## Quick Verification Methods

### Option 1: Browser (Easiest)
Simply open this URL in your browser:
```
http://localhost:8000/api/v1/analytics/scraper-summary
```

You should see clean JSON data with all metrics.

---

### Option 2: cURL Command
```bash
curl -X 'GET' \
  'http://localhost:8000/api/v1/analytics/scraper-summary' \
  -H 'accept: application/json'
```

---

### Option 3: PowerShell
```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/analytics/scraper-summary" | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

---

### Option 4: Python Script
```python
import httpx
import json

response = httpx.get("http://localhost:8000/api/v1/analytics/scraper-summary")
data = response.json()

print(f"Status: {response.status_code}")
print(f"Compliance Score: {data['global_compliance_score']}%")
print(f"Total Licenses: {data['counters']['total_monitored_licenses']}")
print(json.dumps(data, indent=2))
```

---

## Expected Response Structure

```json
{
  "metrics_calculated_at": "2026-07-13T23:52:00.123456Z",
  "global_compliance_score": 85.67,
  "full_compliance_score": 72.34,
  
  "counters": {
    "total_monitored_licenses": 167,
    "ohcq_verified_active": 143,
    "background_check_cleared": 121,
    "fully_compliant_workers": 108,
    "pending_immediate_sync": 24,
    "stale_verifications_needing_refresh": 15,
    "recently_verified_7days": 32,
    "flagged_issues_count": 59
  },
  
  "verification_pipeline": {
    "stage_1_pending": 24,
    "stage_2_ohcq_verified": 35,
    "stage_3_background_cleared": 13,
    "stage_4_fully_compliant": 108
  },
  
  "license_distribution": {
    "RN": 45,
    "LPN": 32,
    "CNA": 78,
    "GNA": 12
  },
  
  "scraper_infrastructure_telemetry": {
    "proxy_pool_health": "OPTIMAL",
    "active_proxies_counted": 12,
    "average_response_latency_ms": 342,
    "last_successful_cron_beat": "2026-07-13T23:04:00Z",
    "total_scraper_runs_today": 24,
    "success_rate_percentage": 98.5
  }
}
```

---

## All Available Endpoints

### 1. Scraper Summary (Main Dashboard)
```
GET /api/v1/analytics/scraper-summary
```

### 2. Historical Trends
```
GET /api/v1/analytics/credential-trends?days=30
```

### 3. Health Check
```
GET /api/v1/analytics/health
```

---

## Interactive API Documentation

FastAPI automatically generates interactive documentation:

**Swagger UI:**
```
http://localhost:8000/docs
```

**ReDoc:**
```
http://localhost:8000/redoc
```

Navigate to the "Operational Telemetry & Dashboards" section to test all endpoints interactively.

---

## Verification Checklist

- [ ] Server is running on http://localhost:8000
- [ ] Browser test returns JSON data
- [ ] `global_compliance_score` is present
- [ ] `counters` object contains all metrics
- [ ] `license_distribution` shows breakdown by type
- [ ] `scraper_infrastructure_telemetry` is populated
- [ ] No HTTP errors (status code 200)
- [ ] Response time is fast (< 1 second)

---

## Troubleshooting

### If you get a connection error:
1. Check if the server is running
2. Look for "Application startup complete" in terminal
3. Verify port 8000 is not blocked

### If you get a 404:
1. Confirm analytics router is registered in main.py
2. Check for typos in the URL
3. Look for import errors in server logs

### If data looks wrong:
1. Verify database has seeded credentials
2. Run: `python -m app.db.seed_credentials`
3. Check database connection is working

---

## Current Server Status

Check your FastAPI server terminal for:
```
INFO:     Application startup complete.
```

If you see this, the analytics endpoint is ready!
