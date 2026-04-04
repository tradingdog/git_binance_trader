from fastapi.testclient import TestClient

from git_binance_trader.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["mode"] == "SIMULATION"


def test_dashboard_endpoint() -> None:
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    payload = response.json()
    assert "state" in payload
    assert payload["state"]["account"]["status"] in {"running", "paused", "halted"}


def test_pause_action() -> None:
    response = client.post("/api/actions/pause")
    assert response.status_code == 200
    assert response.json()["status"] == "paused"
