from rest_framework.test import APIClient

def test_map_and_landing_are_reachable(db):
    client=APIClient()
    assert client.get('/map/').status_code==200
    assert b'leaflet' in client.get('/map/').content.lower()
    assert client.get('/').status_code==200

def test_api_is_json_only(db):
    response=APIClient().get('/api/route/')
    assert response.status_code==400
    assert response['Content-Type'].startswith('application/json')
