from fastapi.testclient import TestClient

from ai_trader_project.main import app


client = TestClient(app)


def test_health() -> None:
    r = client.get('/health')
    assert r.status_code == 200
    payload = r.json()
    assert payload['status'] == 'ok'
    assert payload['mode'] == 'SIMULATION'


def test_governance_payload() -> None:
    r = client.get('/api/ai/governance')
    assert r.status_code == 200
    payload = r.json()
    assert 'system' in payload
    assert 'memory' in payload
    assert 'commands' in payload


def test_actions_and_command() -> None:
    r1 = client.post('/api/actions/pause')
    assert r1.status_code == 200
    assert r1.json()['status'] == 'paused'

    r2 = client.post('/api/actions/resume')
    assert r2.status_code == 200
    assert r2.json()['status'] == 'running'

    r3 = client.post('/api/ai/command', json={'command': '测试AI记忆', 'operator': 'human'})
    assert r3.status_code == 200
    assert r3.json()['status'] == 'ok'

    r4 = client.post('/api/actions/halt')
    assert r4.status_code == 200
    assert r4.json()['status'] == 'halted'
