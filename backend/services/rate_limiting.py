"""
Rate limiting service for API endpoints.
Provides per-IP request limiting with configurable windows.
"""

import threading
import time
import logging
from functools import wraps
from typing import Callable, Any
from flask import request, g, jsonify
from config import cfg
from utils.helpers import RateLimiter

logger = logging.getLogger(__name__)

_rate_limiter = RateLimiter()


def start_rate_limiter_purge():
    """Start background thread that periodically purges old rate limit entries."""
    def _run_rl_purge():
        while True:
            time.sleep(300)
            try:
                _rate_limiter.purge_old()
            except Exception as e:
                logger.warning("Rate limiter purge failed: %s", e)

    threading.Thread(target=_run_rl_purge, daemon=True, name="rl-purge").start()


def rate_limit(limit: int, window: int = None) -> Callable:
    """
    Decorator to apply rate limiting to Flask routes.

    Args:
        limit: Maximum requests allowed
        window: Time window in seconds (defaults to RATE_LIMIT_WINDOW)

    Returns:
        Decorated function with rate limiting
    """
    _window = window or cfg.RATE_LIMIT_WINDOW

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs) -> Any:
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
            key = (ip, fn.__name__)
            if not _rate_limiter.is_allowed(key, limit, _window):
                logger.warning("Rate limit exceeded | ip=%s endpoint=%s", ip, fn.__name__)
                return jsonify({
                    "error": "Too many requests. Please slow down.",
                    "code": "RATE_LIMITED",
                    "request_id": g.get("request_id", "-"),
                }), 429
            return fn(*args, **kwargs)
        return wrapper
    return decorator
