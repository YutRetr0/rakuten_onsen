import importlib
import pytest
import watcher


def _reload_modules(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    import db
    import watcher
    importlib.reload(db)
    importlib.reload(watcher)
    return watcher


def test_add_and_list_watches(tmp_path, monkeypatch):
    watcher = _reload_modules(monkeypatch, tmp_path)

    item = {
        "region": "oita",
        "hotel_no": "123456",
        "checkin": "2026-05-01",
        "checkout": "2026-05-02",
    }
    added = watcher.add_watch(item)
    watches = watcher.list_watches()

    assert len(watches) == 1
    assert watches[0]["hotel_no"] == 123456
    assert watches[0]["id"] == added["id"]


def test_remove_watch(tmp_path, monkeypatch):
    watcher = _reload_modules(monkeypatch, tmp_path)

    item = {
        "region": "oita",
        "hotel_no": "654321",
        "checkin": "2026-06-01",
        "checkout": "2026-06-02",
    }
    added = watcher.add_watch(item)
    assert len(watcher.list_watches()) == 1

    watcher.remove_watch(added["id"])
    assert watcher.list_watches() == []


def test_watch_id_format(tmp_path, monkeypatch):
    watcher = _reload_modules(monkeypatch, tmp_path)

    item = {
        "region": "hokkaido",
        "hotel_no": "999",
        "checkin": "2026-07-01",
        "checkout": "2026-07-02",
    }
    added = watcher.add_watch(item)
    assert added["id"].startswith("w_")


def test_watch_created_at_is_iso(tmp_path, monkeypatch):
    watcher = _reload_modules(monkeypatch, tmp_path)

    item = {
        "region": "kyoto",
        "hotel_no": "777",
        "checkin": "2026-08-01",
        "checkout": "2026-08-02",
    }
    from datetime import datetime
    added = watcher.add_watch(item)
    dt = datetime.fromisoformat(added["created_at"])
    assert dt.year >= 2024


def test_two_watches_ordered_by_created_at(tmp_path, monkeypatch):
    watcher = _reload_modules(monkeypatch, tmp_path)

    item1 = {"region": "oita", "hotel_no": "1", "checkin": "2026-05-01", "checkout": "2026-05-02"}
    item2 = {"region": "kyoto", "hotel_no": "2", "checkin": "2026-06-01", "checkout": "2026-06-02"}
    watcher.add_watch(item1)
    watcher.add_watch(item2)

    watches = watcher.list_watches()
    assert len(watches) == 2
    assert watches[0]["created_at"] <= watches[1]["created_at"]


def test_remove_nonexistent_returns_false(tmp_path, monkeypatch):
    watcher = _reload_modules(monkeypatch, tmp_path)
    assert watcher.remove_watch("nonexistent") is False

