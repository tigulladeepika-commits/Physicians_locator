"""
Configuration module for Physician Locator backend.
Loads environment variables and provides centralized config.

Fix v2.1.2:
  - Added IS_RENDER flag to detect Render deployment environment.
  - ZIP_DB_WAIT increased to 30s (was implicit 3s in app.py).
  - Added ZIP_LOAD_SYNC flag: True on Render, False locally.
    When True, zip_database.initialize() blocks until the DB is ready
    instead of spawning a background thread — eliminates the cold-start
    race condition where workers serve requests before ZIPs are loaded.
"""

import os
import logging

logger = logging.getLogger(__name__)


class Config:
    """Central configuration class for all backend settings."""

    # API Keys
    MAPQUEST_API_KEY: str = os.environ.get("MAPQUEST_API_KEY", "")
    GEOAPIFY_API_KEY: str = os.environ.get("GEOAPIFY_API_KEY", "")

    # URLs
    FRONTEND_URL: str = os.environ.get("FRONTEND_URL", "")

    # Salesforce
    SF_OID: str = os.environ.get("SF_OID", "")
    SF_RET_URL: str = os.environ.get("SF_RET_URL", "")
    SF_DEBUG_EMAIL: str = os.environ.get("SF_DEBUG_EMAIL", "")

    # Server Settings
    PORT: int = int(os.environ.get("PORT", 5000))
    DEBUG_SECRET: str = os.environ.get("DEBUG_SECRET", "")
    LEADS_DIR: str = os.environ.get("LEADS_DIR", "/tmp")

    # Limits
    MAX_DISPLAY: int = 10
    MAX_ZIP_QUERIES: int = 20
    MAX_TAX_QUERIES: int = 3
    MAX_DESC_COUNT: int = 5
    MAX_DESC_LEN: int = 120
    MAX_RADIUS: float = 100.0
    GEOCODE_CACHE_SIZE: int = 2000

    # ── Timeouts ──────────────────────────────────────────────────────────────
    # IMPORTANT: Render's reverse proxy hard-kills connections at 30s.
    # All outbound HTTP calls MUST complete (or fail) before that deadline.
    #
    #   REQUEST_TIMEOUT  — general outbound calls (NPPES, Salesforce, etc.)
    #   AC_TIMEOUT       — autocomplete / geocode calls (user is typing; must feel fast)
    #   ZIP_DL_TIMEOUT   — one-time GeoNames ZIP file download at startup
    REQUEST_TIMEOUT: int = 25    # kept under Render's 30s proxy limit
    AC_TIMEOUT: int = 8          # hard cap for autocomplete/geocode endpoints
    ZIP_DL_TIMEOUT: int = 90     # large file download, runs in background thread only

    # ── Deployment environment ────────────────────────────────────────────────
    # Render sets the RENDER env var on all its runtimes.
    # ZIP_LOAD_SYNC=True means initialize() blocks until ZIP DB is ready
    # before the first worker accepts traffic — eliminates the cold-start
    # race that caused "ZIPs in radius: 0" on every search after a restart.
    IS_RENDER: bool = bool(os.environ.get("RENDER", ""))
    ZIP_LOAD_SYNC: bool = bool(os.environ.get("ZIP_LOAD_SYNC", "")) or bool(
        os.environ.get("RENDER", "")
    )
    # How long search() waits for ZIP DB if somehow still loading (failsafe).
    ZIP_DB_WAIT: float = 30.0    # was 3.0 — gives workers time on slow cold starts

    # Rate limiting (per-IP, in-process)
    RATE_LIMIT_WINDOW: int = 60
    RATE_LIMIT_SEARCH: int = 30
    RATE_LIMIT_LEAD: int = 5
    RATE_LIMIT_AC: int = 120


cfg = Config()


def validate_configuration() -> list[str]:
    """Validate required configuration and return list of missing env vars."""
    missing = []
    for key, label in [
        (cfg.MAPQUEST_API_KEY, "MAPQUEST_API_KEY"),
        (cfg.GEOAPIFY_API_KEY, "GEOAPIFY_API_KEY"),
        (cfg.SF_OID, "SF_OID"),
    ]:
        if not key:
            missing.append(label)
            logger.warning("Environment variable %s is not set", label)

    if not cfg.FRONTEND_URL:
        logger.error(
            "FRONTEND_URL is not set — CORS is open to ALL origins. "
            "Set this to your Vercel URL in the Render dashboard."
        )

    if not cfg.DEBUG_SECRET:
        logger.warning(
            "DEBUG_SECRET is not set — /api/lead-debug is UNPROTECTED. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )

    logger.info("SF_OID configured: %s", bool(cfg.SF_OID))
    logger.info("SF_DEBUG_EMAIL: %s", cfg.SF_DEBUG_EMAIL or "NOT SET")
    logger.info("LEADS_DIR: %s", cfg.LEADS_DIR)
    logger.info(
        "ZIP_LOAD_SYNC=%s IS_RENDER=%s ZIP_DB_WAIT=%ss",
        cfg.ZIP_LOAD_SYNC, cfg.IS_RENDER, cfg.ZIP_DB_WAIT,
    )

    return missing