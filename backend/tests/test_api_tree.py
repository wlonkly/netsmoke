import asyncio
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from netsmoke.app import app
from netsmoke.services.targets import create_measurement_round



def test_tree_endpoint_uses_yaml_config() -> None:
    with TestClient(app) as client:
        response = client.get('/api/tree')

    assert response.status_code == 200
    payload = response.json()
    assert payload['tree'][0]['name'] == 'Examples'
    assert payload['targets'][0]['id'] == 'examples-example-target'



def test_collector_status_endpoint_returns_runtime_state() -> None:
    with TestClient(app) as client:
        response = client.get('/api/collector/status')

    assert response.status_code == 200
    payload = response.json()
    assert 'status' in payload
    assert 'lastSuccessAt' in payload
    assert 'lastRoundSummary' in payload



def test_target_detail_is_backed_by_database_sync() -> None:
    with TestClient(app) as client:
        response = client.get('/api/targets/examples-example-target')

    assert response.status_code == 200
    payload = response.json()
    assert payload['id'] == 'examples-example-target'
    assert payload['enabled'] is True
    assert 'recentMeasurements' in payload



def test_target_graph_endpoint_renders_stored_data() -> None:
    with TestClient(app) as client:
        asyncio.run(
            create_measurement_round(
                target_slug='examples-example-target',
                observed_at=datetime(2026, 3, 8, 5, 0, tzinfo=UTC),
                sent=4,
                received=3,
                loss_pct=25.0,
                median_rtt_ms=12.0,
                samples=(10.0, 12.0, None, 15.0),
            )
        )
        response = client.get('/api/targets/examples-example-target/graph.svg?range=6h')

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('image/svg+xml')
    assert 'Examples/Example Target' in response.text



def test_target_graph_endpoint_requires_real_target_id() -> None:
    with TestClient(app) as client:
        response = client.get('/api/targets/missing-target/graph.svg')

    assert response.status_code == 404
