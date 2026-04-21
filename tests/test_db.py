import importlib


def _reload_db(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    import db
    importlib.reload(db)
    return db


def test_init_db_creates_three_tables(tmp_path, monkeypatch):
    db = _reload_db(monkeypatch, tmp_path)
    db.init_db()
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    table_names = {r["name"] for r in rows}
    assert "watches" in table_names
    assert "watch_state" in table_names
    assert "notification_history" in table_names


def test_notification_history_insert_and_read(tmp_path, monkeypatch):
    db = _reload_db(monkeypatch, tmp_path)
    db.init_db()

    # Insert a watch first (FK constraint)
    with db.get_conn() as conn:
        conn.execute(
            """INSERT INTO watches (id, region, hotel_no, checkin, checkout, created_at)
               VALUES (?,?,?,?,?,?)""",
            ("w_test01", "oita", 123456, "2026-05-01", "2026-05-02", "2026-01-01T00:00:00"),
        )

    # Insert a notification_history entry
    with db.get_conn() as conn:
        conn.execute(
            """INSERT INTO notification_history (watch_id, notified_at, matched_count, channels)
               VALUES (?,?,?,?)""",
            ("w_test01", "2026-05-01T10:00:00", 3, '["wecom"]'),
        )

    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM notification_history WHERE watch_id = ?",
            ("w_test01",),
        ).fetchone()

    assert row is not None
    assert row["watch_id"] == "w_test01"
    assert row["matched_count"] == 3
    assert row["channels"] == '["wecom"]'
