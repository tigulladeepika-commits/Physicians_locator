"""
Shared HTTP client for all remote API calls.
Provides a single configured requests.Session instance.
"""

import requests

# Single shared HTTP session
http_client = requests.Session()
http_client.headers.update({"User-Agent": "PhysicianLocator/2.0"})
