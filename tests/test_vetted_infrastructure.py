"""Tests for VettedCare infrastructure readiness."""

from fastapi.testclient import TestClient


def test_health_vettedcare_endpoint(client: TestClient) -> None:
    response = client.get("/health/vettedcare")
    assert response.status_code == 200
    body = response.json()
    assert body["manus_worker_required"] is False
    assert "checks" in body
    assert body["required_total"] >= 1


def test_vettedcare_infrastructure_admin(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.get("/api/vettedcare/infrastructure", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["overall"] in {"infra_ready", "not_ready"}
    assert body["manus_worker_required"] is False
    assert any(row["name"] == "database" for row in body["checks"])
