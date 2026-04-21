from cache import TTLCache


def test_get_or_set_loader_called_once():
    counter = {"n": 0}

    def loader():
        counter["n"] += 1
        return "value"

    cache = TTLCache(ttl=300)
    result1 = cache.get_or_set("key", loader)
    result2 = cache.get_or_set("key", loader)

    assert result1 == "value"
    assert result2 == "value"
    assert counter["n"] == 1


def test_get_or_set_ttl_expired():
    counter = {"n": 0}

    def loader():
        counter["n"] += 1
        return counter["n"]

    cache = TTLCache(ttl=0)
    cache.get_or_set("key", loader)
    cache.get_or_set("key", loader)

    assert counter["n"] == 2


def test_get_or_set_ttl_expired_with_monkeypatch(monkeypatch):
    counter = {"n": 0}

    def loader():
        counter["n"] += 1
        return counter["n"]

    cache = TTLCache(ttl=60)

    import cache as cache_module
    monkeypatch.setattr(cache_module.time, "time", lambda: 0.0)
    cache.get_or_set("key", loader)

    monkeypatch.setattr(cache_module.time, "time", lambda: 9999.0)
    cache.get_or_set("key", loader)

    assert counter["n"] == 2


def test_invalidate_all_forces_reload():
    counter = {"n": 0}

    def loader():
        counter["n"] += 1
        return "data"

    cache = TTLCache(ttl=300)
    cache.get_or_set("k", loader)
    cache.invalidate_all()
    cache.get_or_set("k", loader)

    assert counter["n"] == 2
