import watcher


def test_add_and_list_watches(tmp_path, monkeypatch):
    monkeypatch.setattr(watcher, "WATCH_FILE", str(tmp_path / "watches.json"))
    monkeypatch.setattr(watcher, "STATE_FILE", str(tmp_path / "state.json"))

    item = {
        "region": "oita",
        "hotel_no": "123456",
        "checkin": "2026-05-01",
        "checkout": "2026-05-02",
    }
    added = watcher.add_watch(item)
    watches = watcher.list_watches()

    assert len(watches) == 1
    assert watches[0]["hotel_no"] == "123456"
    assert watches[0]["id"] == added["id"]


def test_remove_watch(tmp_path, monkeypatch):
    monkeypatch.setattr(watcher, "WATCH_FILE", str(tmp_path / "watches.json"))
    monkeypatch.setattr(watcher, "STATE_FILE", str(tmp_path / "state.json"))

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
    monkeypatch.setattr(watcher, "WATCH_FILE", str(tmp_path / "watches.json"))
    monkeypatch.setattr(watcher, "STATE_FILE", str(tmp_path / "state.json"))

    item = {
        "region": "hokkaido",
        "hotel_no": "999",
        "checkin": "2026-07-01",
        "checkout": "2026-07-02",
    }
    added = watcher.add_watch(item)
    assert added["id"].startswith("w_")


def test_watch_created_at_is_iso(tmp_path, monkeypatch):
    monkeypatch.setattr(watcher, "WATCH_FILE", str(tmp_path / "watches.json"))
    monkeypatch.setattr(watcher, "STATE_FILE", str(tmp_path / "state.json"))

    item = {
        "region": "kyoto",
        "hotel_no": "777",
        "checkin": "2026-08-01",
        "checkout": "2026-08-02",
    }
    from datetime import datetime
    added = watcher.add_watch(item)
    # Should parse without error as an ISO datetime string
    dt = datetime.fromisoformat(added["created_at"])
    assert dt.year >= 2024
