from http_client import DEFAULT_BACKOFF_FACTOR, DEFAULT_RETRY_COUNT, RETRY_STATUS_CODES, build_retry_session


def test_build_retry_session_configures_bounded_retries():
    session = build_retry_session()

    for scheme in ("http://", "https://"):
        retries = session.adapters[scheme].max_retries
        assert retries.total == DEFAULT_RETRY_COUNT
        assert retries.connect == DEFAULT_RETRY_COUNT
        assert retries.read == DEFAULT_RETRY_COUNT
        assert retries.status == DEFAULT_RETRY_COUNT
        assert retries.backoff_factor == DEFAULT_BACKOFF_FACTOR
        assert retries.allowed_methods is None
        assert retries.respect_retry_after_header is True
        for status_code in RETRY_STATUS_CODES:
            assert status_code in retries.status_forcelist
