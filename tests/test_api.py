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
    assert "margin_used" in payload["state"]["account"]
    assert "equity_history" in payload["state"]
    assert "storage" in payload["state"]
    if payload["state"]["watchlist"]:
        assert "market_type" in payload["state"]["watchlist"][0]
        assert "leverage" in payload["state"]["watchlist"][0]


def test_pause_action() -> None:
    response = client.post("/api/actions/pause")
    assert response.status_code == 200
    assert response.json()["status"] == "paused"


def test_trades_endpoint_with_limit() -> None:
    response = client.get("/api/trades?limit=500")
    assert response.status_code == 200
    payload = response.json()
    assert "count" in payload
    assert "items" in payload


def test_logs_tail_endpoint_with_limit() -> None:
    response = client.get("/api/logs/tail?lines=500")
    assert response.status_code == 200
    assert isinstance(response.text, str)
