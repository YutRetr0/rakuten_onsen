import importlib
import sys

import pytest


@pytest.fixture
def app_module(monkeypatch):
    monkeypatch.setenv("RAKUTEN_APP_ID", "test-app-id")
    monkeypatch.setenv("ENABLE_SCHEDULER", "0")
    sys.modules.pop("app", None)
    import app

    module = importlib.reload(app)
    yield module
    sys.modules.pop("app", None)


@pytest.fixture
def client(app_module, monkeypatch):
    monkeypatch.setattr(app_module.cache, "get_or_set", lambda _key, loader: loader())
    monkeypatch.setattr(app_module.client, "search_vacant_onsen", lambda *args, **kwargs: {"hotels": []})
    return app_module.app.test_client()


@pytest.mark.parametrize(
    ("query", "message"),
    [
        ({"region": "mars"}, "invalid region"),
        ({"date": "2026-02-30"}, "invalid date"),
        ({"pages": "0"}, "invalid pages"),
        ({"adults": "0"}, "invalid adults"),
        ({"rooms": "0"}, "invalid rooms"),
    ],
)
def test_api_search_invalid_inputs_return_400(client, query, message):
    response = client.get("/api/search", query_string=query)

    assert response.status_code == 400
    assert response.get_json() == {"error": message}


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"region": "mars", "hotel_no": 1, "checkin": "2026-05-01", "checkout": "2026-05-02"},
            "invalid region",
        ),
        (
            {"region": "oita", "hotel_no": 1, "checkin": "2026-02-30", "checkout": "2026-05-02"},
            "invalid checkin",
        ),
        (
            {"region": "oita", "hotel_no": 1, "checkin": "2026-05-01", "checkout": "2026-05-02", "adults": 0},
            "invalid adults",
        ),
        (
            {"region": "oita", "hotel_no": 1, "checkin": "2026-05-01", "checkout": "2026-05-02", "rooms": 0},
            "invalid rooms",
        ),
    ],
)
def test_api_watch_invalid_inputs_return_400(client, payload, message):
    response = client.post("/api/watch", json=payload)

    assert response.status_code == 400
    assert response.get_json() == {"error": message}
