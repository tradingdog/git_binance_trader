from fastapi.testclient import TestClient

from ai_trader_project.main import app


client = TestClient(app)


def test_health() -> None:
    r = client.get('/health')
    assert r.status_code == 200
    payload = r.json()
    assert payload['status'] == 'ok'
    assert payload['mode'] == 'SIMULATION'
    assert 'equity' in payload
    assert 'positions' in payload


def test_governance_payload() -> None:
    r = client.get('/api/ai/governance')
    assert r.status_code == 200
    payload = r.json()
    assert 'system' in payload
    assert 'ai_usage' in payload
    assert 'positions' in payload
    assert 'trades' in payload
    assert 'runtime_logs' in payload
    assert 'ai_tasks' in payload
    assert 'memory' in payload
    assert 'commands' in payload
    assert 'governance_config' in payload
    assert 'release_state' in payload
    assert 'approvals' in payload
    assert 'candidates' in payload
    assert 'audit_events' in payload
    assert 'reports' in payload
    assert 'total_cost_usd' in payload['ai_usage']


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


def test_governance_actions_and_approvals() -> None:
    # 冻结自治
    r1 = client.post('/api/actions/freeze-autonomy', json={'operator': 'human', 'role': 'human_root'})
    assert r1.status_code == 200
    assert r1.json()['status'] == 'halted'

    # 高风险命令应进入审批队列
    r2 = client.post('/api/ai/command', json={'command': 'deploy challenger', 'operator': 'human'})
    assert r2.status_code == 200
    assert r2.json()['status'] == 'pending_approval'
    approval_id = r2.json()['approval']['id']

    # 审批通过
    r3 = client.post(
        f'/api/governance/approvals/{approval_id}',
        json={'operator': 'human', 'role': 'human_root', 'decision': 'approve'},
    )
    assert r3.status_code == 200
    assert r3.json()['status'] == 'approved'

    # 治理配置更新
    r4 = client.post(
        '/api/governance/config',
        json={
            'operator': 'human',
            'role': 'human_root',
            'autonomy_level': 'L3',
            'allow_night_autonomy': True,
            'objective_daily_return_pct': 1.2,
            'max_fee_ratio_pct': 30.0,
        },
    )
    assert r4.status_code == 200
    assert r4.json()['status'] == 'ok'
    cfg = r4.json()['config']
    assert cfg['autonomy_level'] == 'L3'
    assert cfg['allow_night_autonomy'] is True

    # 无快照时回滚失败是可预期行为
    r5 = client.post('/api/actions/rollback', json={'operator': 'human', 'role': 'human_root'})
    assert r5.status_code == 200
    assert r5.json()['status'] in {'ok', 'failed'}


def test_dashboard_endpoint_shape() -> None:
    r = client.get('/api/dashboard')
    assert r.status_code == 200
    payload = r.json()
    assert 'system' in payload
    assert 'ai_usage' in payload
    assert isinstance(payload['positions'], list)
    assert isinstance(payload['trades'], list)
