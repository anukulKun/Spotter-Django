from rest_framework.test import APIClient

def test_map_and_landing_are_reachable(db):
    client=APIClient()
    map_response=client.get('/map/')
    assert map_response.status_code==200
    assert b'leaflet' in map_response.content.lower()
    assert b'<meta name="referrer" content="strict-origin-when-cross-origin">' in map_response.content.lower()
    assert client.get('/')['Referrer-Policy']=='strict-origin-when-cross-origin'
    assert map_response['Referrer-Policy']=='strict-origin-when-cross-origin'
    assert client.get('/').status_code==200

def test_api_is_json_only(db):
    response=APIClient().get('/api/route/')
    assert response.status_code==400
    assert response['Content-Type'].startswith('application/json')