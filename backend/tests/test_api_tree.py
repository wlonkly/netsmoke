from fastapi.testclient import TestClient

from netsmoke.app import app



def test_tree_endpoint_uses_yaml_config() -> None:
    client = TestClient(app)

    response = client.get('/api/tree')

    assert response.status_code == 200
    payload = response.json()
    assert payload['tree'][0]['name'] == 'Examples'
    assert payload['targets'][0]['id'] == 'examples-example-target'



def test_target_graph_endpoint_requires_real_target_id() -> None:
    client = TestClient(app)

    response = client.get('/api/targets/missing-target/graph.svg')

    assert response.status_code == 404
