"""
Shared HTTP client for all remote API calls.
Provides two configured requests.Session instances:

  http_client        — for NPPES, Salesforce, taxonomy, ZIP download.
                       Has retry logic (total=2) for transient failures.
                       Safe for idempotent, non-latency-sensitive calls.

  http_client_once   — for Geoapify autocomplete & geocode endpoints.
                       NO retries. A single 8 s attempt, then fail fast.
                       Retries on autocomplete are harmful:
                         total=2 + backoff_factor=1 turns one 8 s timeout
                         into ~27 s of waiting, which hits Render's 30 s
                         proxy deadline and produces a 504 before the app
                         can even return a graceful empty response.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── Retry-enabled session (NPPES, Salesforce, taxonomy CSV, GeoNames) ────────
http_client = requests.Session()
http_client.headers.update({"User-Agent": "PhysicianLocator/2.0"})

_retry_strategy = Retry(
    total=2,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"],
)
_retry_adapter = HTTPAdapter(max_retries=_retry_strategy)
http_client.mount("http://",  _retry_adapter)
http_client.mount("https://", _retry_adapter)


# ── No-retry session (Geoapify autocomplete & geocode) ───────────────────────
http_client_once = requests.Session()
http_client_once.headers.update({"User-Agent": "PhysicianLocator/2.0"})

_no_retry_adapter = HTTPAdapter(max_retries=Retry(total=0, raise_on_status=False))
http_client_once.mount("http://",  _no_retry_adapter)
http_client_once.mount("https://", _no_retry_adapter)