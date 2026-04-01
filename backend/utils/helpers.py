"""
Helper utilities for the Physician Locator backend.
Includes sanitization, caching, and common functions.
"""

import re
import html
import threading
from collections import OrderedDict
from typing import Any, Optional


# Input sanitization patterns
_TAG_RE = re.compile(r"<[^>]+>")
_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")


def sanitise(value: str, max_len: int = 500) -> str:
    """
    Sanitize user input by removing HTML tags and control characters.
    
    Args:
        value: Input string to sanitize
        max_len: Maximum length of output string
        
    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        value = str(value)
    value = _TAG_RE.sub("", value)
    value = html.unescape(value)
    value = _CTRL_RE.sub("", value)
    return value.strip()[:max_len]


class LRUCache:
    """Thread-safe LRU cache implementation."""
    
    def __init__(self, max_size: int):
        """Initialize cache with max size."""
        self._cache: OrderedDict = OrderedDict()
        self._max = max_size
        self._lock = threading.Lock()
    
    def get(self, key: Any) -> Optional[Any]:
        """Get value from cache, moving to end (most recent)."""
        with self._lock:
            if key not in self._cache:
                return None
            self._cache.move_to_end(key)
            return self._cache[key]
    
    def set(self, key: Any, value: Any) -> None:
        """Set value in cache, evicting oldest if needed."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self._max:
                self._cache.popitem(last=False)


class RateLimiter:
    """Thread-safe rate limiter using in-memory store."""
    
    def __init__(self):
        """Initialize the rate limiter."""
        self._store: dict[tuple, list[float]] = {}
        self._lock = threading.Lock()
    
    def is_allowed(self, key: tuple, limit: int, window: int) -> bool:
        """
        Check if request is within rate limit.
        
        Args:
            key: Unique identifier (e.g., IP + endpoint)
            limit: Maximum requests allowed
            window: Time window in seconds
            
        Returns:
            True if request is allowed, False if rate limited
        """
        import time
        now = time.time()
        cutoff = now - window
        with self._lock:
            hits = [t for t in self._store.get(key, []) if t > cutoff]
            if len(hits) >= limit:
                return False
            hits.append(now)
            self._store[key] = hits
            return True
    
    def purge_old(self) -> None:
        """Remove expired entries from store."""
        import time
        now = time.time()
        cutoff = now - 300
        with self._lock:
            self._store = {
                k: [t for t in v if t > cutoff]
                for k, v in self._store.items()
                if any(t > cutoff for t in v)
            }
