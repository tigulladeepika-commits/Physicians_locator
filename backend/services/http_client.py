"""
Shared HTTP client for all remote API calls.
Provides a single configured requests.Session instance with retry logic.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Single shared HTTP session with retry strategy
http_client = requests.Session()
http_client.headers.update({"User-Agent": "PhysicianLocator/2.0"})

# Configure retry strategy for transient failures
retry_strategy = Retry(
    total=2,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http_client.mount("http://", adapter)
http_client.mount("https://", adapter)
