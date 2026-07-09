"""
Integration Tests — Unified Shifts API Routes

Tests complete VMS ingest pipeline with shift booking:
- VMSIngestPipeline (concurrent-safe ingestion)
- Time-overlap conflict detection
- Shift status management
- Stress testing capabilities

Validates end-to-end VMS workflow from API to database persistence.
"""

import uuid as uuid_module
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import VMSShiftIngest


@pytest.mark.asyncio
async def test_create_shift_success(test_client, async_db):
    """Test POST /api/v1/shifts/ — successful shift creation via VMS ingest."""
    shift_data = {
        "vms_source": "TEST_VMS",
        "facility_id": str(uuid_module.uuid4()),
        "shift_start": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "shift_end": (datetime.now(timezone.utc) + timedelta(days=1, hours=8)).isoformat(),
        "required_license": "CNA",
        "hourly_rate": 25.0,
        "crisis_rate": False,
    }
    
    response = test_client.post("/api/v1/shifts/", json=shift_data)
    
    assert response.status_code == 201
    data = response.json()
    
    # Verify response structure
    assert "shift_id" in data
    assert data["status"] == "ACTIVE"
    assert data["error"] is None
    assert data["overlap_detected"] is False
    
    # Verify database persistence
    result = await async_db.execute(
        select(VMSShiftIngest).where(VMSShiftIngest.shift_id == data["shift_id"])
    )
    shift = result.scalar_one_or_none()
    
    assert shift is not None
    assert shift.status == "ACTIVE"
    assert shift.required_license == "CNA"
    assert float(shift.hourly_rate) == 25.0


@pytest.mark.asyncio
async def test_create_shift_overlap_conflict(test_client, async_db):
    """Test shift creation with time-overlap conflict detection."""
    facility_id = str(uuid_module.uuid4())
    shift_start = datetime.now(timezone.utc) + timedelta(days=1)
    shift_end = shift_start + timedelta(hours=8)
    
    # Create first shift
    shift1 = VMSShiftIngest(
        shift_id=str(uuid_module.uuid4()),
        vms_source="TEST_VMS",
        facility_id=facility_id,
        shift_start=shift_start,
        shift_end=shift_end,
        required_license="CNA",
        hourly_rate=25.0,
        crisis_rate=False,
        status="ACTIVE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    async_db.add(shift1)
    await async_db.commit()
    
    # Attempt to create overlapping shift
    overlapping_shift_data = {
        "vms_source": "TEST_VMS",
        "facility_id": facility_id,
        "shift_start": (shift_start + timedelta(hours=2)).isoformat(),  # Overlaps
        "shift_end": (shift_end + timedelta(hours=2)).isoformat(),
        "required_license": "CNA",
        "hourly_rate": 30.0,
        "crisis_rate": False,
    }
    
    response = test_client.post("/api/v1/shifts/", json=overlapping_shift_data)
    
    # Should detect conflict
    assert response.status_code == 409
    data = response.json()
    
    assert data["detail"]["error"] == "SHIFT_OVERLAP"
    assert "overlap" in data["detail"]["detail"].lower()


@pytest.mark.asyncio
async def test_get_shifts_success(test_client, async_db):
    """Test GET /api/v1/shifts/ — retrieve all shifts."""
    # Create test shifts
    shift1 = VMSShiftIngest(
        shift_id=str(uuid_module.uuid4()),
        vms_source="TEST_VMS",
        facility_id=str(uuid_module.uuid4()),
        shift_start=datetime.now(timezone.utc) + timedelta(days=1),
        shift_end=datetime.now(timezone.utc) + timedelta(days=1, hours=8),
        required_license="CNA",
        hourly_rate=25.0,
        crisis_rate=False,
        status="ACTIVE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    shift2 = VMSShiftIngest(
        shift_id=str(uuid_module.uuid4()),
        vms_source="TEST_VMS",
        facility_id=str(uuid_module.uuid4()),
        shift_start=datetime.now(timezone.utc) + timedelta(days=2),
        shift_end=datetime.now(timezone.utc) + timedelta(days=2, hours=12),
        required_license="LPN",
        hourly_rate=35.0,
        crisis_rate=True,
        status="ACTIVE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    async_db.add_all([shift1, shift2])
    await async_db.commit()
    
    response = test_client.get("/api/v1/shifts/")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["total"] >= 2
    assert len(data["shifts"]) >= 2
    
    # Verify shift data structure
    shift_data = data["shifts"][0]
    assert "shift_id" in shift_data
    assert "facility_id" in shift_data
    assert "required_license" in shift_data
    assert "hourly_rate" in shift_data
    assert "status" in shift_data


@pytest.mark.asyncio
async def test_get_shifts_with_filters(test_client, async_db):
    """Test GET /api/v1/shifts/ with status and license filters."""
    # Create shifts with different licenses and statuses
    cna_active = VMSShiftIngest(
        shift_id=str(uuid_module.uuid4()),
        vms_source="TEST_VMS",
        facility_id=str(uuid_module.uuid4()),
        shift_start=datetime.now(timezone.utc) + timedelta(days=1),
        shift_end=datetime.now(timezone.utc) + timedelta(days=1, hours=8),
        required_license="CNA",
        hourly_rate=25.0,
        crisis_rate=False,
        status="ACTIVE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    lpn_locked = VMSShiftIngest(
        shift_id=str(uuid_module.uuid4()),
        vms_source="TEST_VMS",
        facility_id=str(uuid_module.uuid4()),
        shift_start=datetime.now(timezone.utc) + timedelta(days=2),
        shift_end=datetime.now(timezone.utc) + timedelta(days=2, hours=8),
        required_license="LPN",
        hourly_rate=35.0,
        crisis_rate=False,
        status="LOCKED",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    async_db.add_all([cna_active, lpn_locked])
    await async_db.commit()
    
    # Filter by CNA license
    response_cna = test_client.get("/api/v1/shifts/?license_filter=CNA")
    assert response_cna.status_code == 200
    data_cna = response_cna.json()
    
    for shift in data_cna["shifts"]:
        assert shift["required_license"] == "CNA"
    
    # Filter by LOCKED status
    response_locked = test_client.get("/api/v1/shifts/?status_filter=LOCKED")
    assert response_locked.status_code == 200
    data_locked = response_locked.json()
    
    for shift in data_locked["shifts"]:
        assert shift["status"] == "LOCKED"


@pytest.mark.asyncio
async def test_get_shift_by_id_success(test_client, async_db):
    """Test GET /api/v1/shifts/{shift_id} — retrieve single shift."""
    shift = VMSShiftIngest(
        shift_id=str(uuid_module.uuid4()),
        vms_source="TEST_VMS",
        facility_id=str(uuid_module.uuid4()),
        shift_start=datetime.now(timezone.utc) + timedelta(days=1),
        shift_end=datetime.now(timezone.utc) + timedelta(days=1, hours=8),
        required_license="CNA",
        hourly_rate=28.0,
        crisis_rate=True,
        status="ACTIVE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    async_db.add(shift)
    await async_db.commit()
    
    response = test_client.get(f"/api/v1/shifts/{shift.shift_id}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["shift_id"] == str(shift.shift_id)
    assert data["required_license"] == "CNA"
    assert data["hourly_rate"] == 28.0
    assert data["crisis_rate"] is True
    assert data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_get_shift_by_id_not_found(test_client):
    """Test GET /api/v1/shifts/{shift_id} — shift not found."""
    fake_id = str(uuid_module.uuid4())
    
    response = test_client.get(f"/api/v1/shifts/{fake_id}")
    
    assert response.status_code == 404
    data = response.json()
    
    assert data["detail"]["error"] == "SHIFT_NOT_FOUND"


@pytest.mark.asyncio
async def test_cancel_shift_success(test_client, async_db):
    """Test DELETE /api/v1/shifts/{shift_id} — successful cancellation."""
    shift = VMSShiftIngest(
        shift_id=str(uuid_module.uuid4()),
        vms_source="TEST_VMS",
        facility_id=str(uuid_module.uuid4()),
        shift_start=datetime.now(timezone.utc) + timedelta(days=1),
        shift_end=datetime.now(timezone.utc) + timedelta(days=1, hours=8),
        required_license="CNA",
        hourly_rate=25.0,
        crisis_rate=False,
        status="ACTIVE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    async_db.add(shift)
    await async_db.commit()
    
    response = test_client.delete(f"/api/v1/shifts/{shift.shift_id}")
    
    assert response.status_code == 204
    
    # Verify shift status updated to CANCELLED
    await async_db.refresh(shift)
    assert shift.status == "CANCELLED"


@pytest.mark.asyncio
async def test_cancel_shift_already_booked(test_client, async_db):
    """Test DELETE /api/v1/shifts/{shift_id} — cannot cancel booked shift."""
    shift = VMSShiftIngest(
        shift_id=str(uuid_module.uuid4()),
        vms_source="TEST_VMS",
        facility_id=str(uuid_module.uuid4()),
        shift_start=datetime.now(timezone.utc) + timedelta(days=1),
        shift_end=datetime.now(timezone.utc) + timedelta(days=1, hours=8),
        required_license="CNA",
        hourly_rate=25.0,
        crisis_rate=False,
        status="BOOKED",  # Already booked
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    async_db.add(shift)
    await async_db.commit()
    
    response = test_client.delete(f"/api/v1/shifts/{shift.shift_id}")
    
    assert response.status_code == 409
    data = response.json()
    
    assert data["detail"]["error"] == "SHIFT_BOOKED"
    
    # Verify status unchanged
    await async_db.refresh(shift)
    assert shift.status == "BOOKED"


@pytest.mark.asyncio
async def test_stress_test_vms_pipeline(test_client, async_db):
    """Test POST /api/v1/shifts/admin/stress-test — VMS pipeline stress test."""
    response = test_client.post(
        "/api/v1/shifts/admin/stress-test?count=50&concurrency=5"
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify stress test report structure
    assert "total" in data
    assert "success" in data
    assert "conflicts" in data
    assert "errors" in data
    assert "execution_time_seconds" in data
    
    assert data["total"] == 50
    assert data["success"] + data["conflicts"] + data["errors"] == data["total"]
    
    # Verify chaos distribution (~15% conflicts, ~10% crisis rates)
    conflict_ratio = data["conflicts"] / data["total"]
    assert 0.10 <= conflict_ratio <= 0.20  # Allow variance
