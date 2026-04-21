import importlib
from datetime import datetime, timedelta


def _setup(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("RAKUTEN_APP_ID", "dummy")
    import db
    importlib.reload(db)
    import watcher
    importlib.reload(watcher)
    import app as app_module
    importlib.reload(app_module)
    return app_module.app, db


def _seed(db_mod, count=5, hours_ago_each=1):
    """Insert one watch + `count` notification_history rows."""
    with db_mod.get_conn() as conn:
        conn.execute(
            "INSERT INTO watches (id, region, hotel_no, hotel_name, checkin, checkout, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("w_test", "oita", 1, "TestHotel", "2026-05-01", "2026-05-02", "2026-01-01T00:00:00"),
        )
        for i in range(count):
            ts = (datetime.utcnow() - timedelta(hours=i * hours_ago_each)).isoformat()
            conn.execute(
                "INSERT INTO notification_history (watch_id, notified_at, matched_count, channels) "
                "VALUES (?,?,?,?)",
                ("w_test", ts, 2 + i, '["wecom"]'),
            )


def test_history_returns_records(tmp_path, monkeypatch):
    app, db = _setup(monkeypatch, tmp_path)
    _seed(db, count=3)
    client = app.test_client()
    r = client.get("/api/notifications/history?days=7")
    assert r.status_code == 200
    body = r.get_json()
    assert body["count"] == 3
    assert body["items"][0]["hotel_name"] == "TestHotel"
    assert body["items"][0]["channels"] == ["wecom"]


def test_history_filter_by_watch(tmp_path, monkeypatch):
    app, db = _setup(monkeypatch, tmp_path)
    _seed(db, count=2)
    client = app.test_client()
    r = client.get("/api/notifications/history?watch_id=w_nope")
    assert r.get_json()["count"] == 0


def test_daily_buckets_fill_zeros(tmp_path, monkeypatch):
    app, db = _setup(monkeypatch, tmp_path)
    _seed(db, count=3, hours_ago_each=24)  # 1 today, 1 yesterday, 1 day before
    client = app.test_client()
    r = client.get("/api/notifications/daily?days=7")
    body = r.get_json()
    assert body["days"] == 7
    assert len(body["buckets"]) == 7  # always 7 entries even if some are 0
    total = sum(b["count"] for b in body["buckets"])
    assert total == 3


def test_daily_clamps_max_days(tmp_path, monkeypatch):
    app, _db = _setup(monkeypatch, tmp_path)
    client = app.test_client()
    r = client.get("/api/notifications/daily?days=9999")
    assert len(r.get_json()["buckets"]) == 90  # clamped to max
