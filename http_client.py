import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
DEFAULT_RETRY_COUNT = 3
DEFAULT_BACKOFF_FACTOR = 0.5


def build_retry_session(
    session: requests.Session | None = None,
    total: int = DEFAULT_RETRY_COUNT,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
):
    """Build a requests session with bounded retries for transient HTTP failures."""
    session = session or requests.Session()
    retry = Retry(
        total=total,
        connect=total,
        read=total,
        status=total,
        backoff_factor=backoff_factor,
        allowed_methods=None,
        status_forcelist=RETRY_STATUS_CODES,
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
