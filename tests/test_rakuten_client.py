import json

import pytest
import requests

from rakuten import RakutenTravel


def _response(status_code, payload=None, headers=None):
    response = requests.Response()
    response.status_code = status_code
    response.headers.update(headers or {})
    response._content = json.dumps(payload or {}).encode()
    response.url = "https://example.com/api"
    response.request = requests.Request("GET", response.url).prepare()
    return response


def test_get_retries_on_retryable_status(monkeypatch):
    client = RakutenTravel(app_id="app-id", access_key="access", min_interval=0, max_retries=2, backoff_base=0.25)
    responses = [
        _response(503, {"error": "temporary"}),
        _response(200, {"hotels": []}),
    ]
    sleeps = []

    monkeypatch.setattr(client.session, "get", lambda *args, **kwargs: responses.pop(0))
    monkeypatch.setattr("rakuten.time.sleep", lambda delay: sleeps.append(delay))

    result = client._get("https://example.com/api", {"page": 1})

    assert result == {"hotels": []}
    assert sleeps == [0.25]
    assert responses == []


@pytest.mark.parametrize("error", [requests.Timeout(), requests.ConnectionError()])
def test_get_retries_on_network_errors(monkeypatch, error):
    client = RakutenTravel(app_id="app-id", access_key="access", min_interval=0, max_retries=2, backoff_base=0.25)
    calls = {"count": 0}
    sleeps = []

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise error
        return _response(200, {"hotels": []})

    monkeypatch.setattr(client.session, "get", fake_get)
    monkeypatch.setattr("rakuten.time.sleep", lambda delay: sleeps.append(delay))

    result = client._get("https://example.com/api", {"page": 1})

    assert result == {"hotels": []}
    assert calls["count"] == 2
    assert sleeps == [0.25]


def test_get_honors_retry_after_header(monkeypatch):
    client = RakutenTravel(app_id="app-id", access_key="access", min_interval=0, max_retries=2, backoff_base=0.25)
    responses = [
        _response(429, {"error": "slow down"}, headers={"Retry-After": "1.5"}),
        _response(200, {"hotels": []}),
    ]
    sleeps = []

    monkeypatch.setattr(client.session, "get", lambda *args, **kwargs: responses.pop(0))
    monkeypatch.setattr("rakuten.time.sleep", lambda delay: sleeps.append(delay))

    result = client._get("https://example.com/api", {"page": 1})

    assert result == {"hotels": []}
    assert sleeps == [1.5]
    assert responses == []
