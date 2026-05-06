import importlib

import pytest


def _load_app(monkeypatch, tmp_path):
    monkeypatch.setenv("RAKUTEN_APP_ID", "test-app")
    monkeypatch.setenv("ENABLE_SCHEDULER", "0")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))

    import app as app_module
    import db
    import watcher

    importlib.reload(db)
    importlib.reload(watcher)
    app_module = importlib.reload(app_module)
    return app_module.app.test_client()


@pytest.mark.parametrize(
    ("query", "expected_error"),
    [
        ({"region": "mars"}, "invalid region"),
        ({"date": "not-a-date"}, "invalid date"),
        ({"pages": "0"}, "invalid pages"),
        ({"pages": "6"}, "invalid pages"),
        ({"adults": "0"}, "invalid adults"),
        ({"rooms": "-1"}, "invalid rooms"),
    ],
)
def test_api_search_invalid_inputs_return_400(monkeypatch, tmp_path, query, expected_error):
    client = _load_app(monkeypatch, tmp_path)

    response = client.get("/api/search", query_string=query)

    assert response.status_code == 400
    assert response.get_json() == {"error": expected_error}


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        (
            {"region": "mars", "hotel_no": "1", "checkin": "2026-05-01", "checkout": "2026-05-02"},
            "invalid region",
        ),
        (
            {"region": "oita", "hotel_no": "1", "checkin": "bad", "checkout": "2026-05-02"},
            "invalid checkin",
        ),
        (
            {"region": "oita", "hotel_no": "1", "checkin": "2026-05-01", "checkout": "2026-05-01"},
            "checkout must be after checkin",
        ),
        (
            {"region": "oita", "hotel_no": "1", "checkin": "2026-05-01", "checkout": "2026-05-02", "adults": "0"},
            "invalid adults",
        ),
        (
            {"region": "oita", "hotel_no": "1", "checkin": "2026-05-01", "checkout": "2026-05-02", "rooms": "0"},
            "invalid rooms",
        ),
    ],
)
def test_api_watch_invalid_inputs_return_400(monkeypatch, tmp_path, payload, expected_error):
    client = _load_app(monkeypatch, tmp_path)

    response = client.post("/api/watch", json=payload)

    assert response.status_code == 400
    assert response.get_json() == {"error": expected_error}
