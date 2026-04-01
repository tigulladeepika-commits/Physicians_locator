"""
Configuration module for Physician Locator backend.
Loads environment variables and provides centralized config.
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
    REQUEST_TIMEOUT: int = 45
    
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
    
    return missing
