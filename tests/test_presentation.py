from rest_framework.test import APIClient


def test_map_and_landing_are_reachable(db):
    client = APIClient()
    map_response = client.get("/map/")
    assert map_response.status_code == 200
    assert b"leaflet" in map_response.content.lower()
    assert (
        b'<meta name="referrer" content="strict-origin-when-cross-origin">'
        in map_response.content.lower()
    )
    assert b"<style" not in map_response.content.lower()
    assert client.get("/").status_code == 200


def test_map_static_and_favicon_are_reachable(db):
    client = APIClient()
    assert client.get("/static/routing/map.js").status_code == 200
    assert client.get("/favicon.ico").status_code == 204


def test_referrer_policy_headers(db):
    client = APIClient()
    assert client.get("/")["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert client.get("/map/")["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_api_is_json_only(db):
    response = APIClient().get("/api/route/")
    assert response.status_code == 400
    assert response["Content-Type"].startswith("application/json")
