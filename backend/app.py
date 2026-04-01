"""
Physician Locator — Aquarient (v2.1 — modularized)

Production-grade physician search API using the official NPPES registry.
Features: Full-width search, lead capture, Salesforce integration, structured logging.

Changes from v2:
  - Modularized codebase: services, routes, utils
  - Separated concerns: config, validation, geocoding, taxonomy, NPPES, Salesforce
  - Cleaner imports and dependency structure
  - Thread-safe rate limiting and caching
  - Comprehensive error handling

Fix v2.1.1:
  - REQUEST_TIMEOUT reduced from 45s → 25s (Render proxy kills at 30s)
  - AC_TIMEOUT = 8s hard cap on autocomplete/geocode (user-facing, must be fast)
  - autocomplete returns HTTP 200 with empty features on timeout/error
    (frontend degrades gracefully instead of showing an error banner)
  - geocode keeps 504/502 status codes (it's a blocking user action)
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys
import time
import traceback
import uuid
from datetime import datetime

# Ensure current directory is in Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from requests import Timeout
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from flask import Flask, g, jsonify, request
from flask_cors import CORS

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import our modular components
from config import cfg, validate_configuration
from services import zip_database, taxonomy, nppes, salesforce, rate_limiting
from services.http_client import http_client, http_client_once
from services.rate_limiting import rate_limit
from utils.helpers import sanitise
from utils.validation import validate_lat_lng, validate_radius, validate_descriptions


# ─────────────────────────────────────────────
#  STRUCTURED LOGGING WITH REQUEST-ID FILTER
# ─────────────────────────────────────────────

class RequestIdFilter(logging.Filter):
    def filter(self, record):
        try:
            record.request_id = g.get("request_id", "-")
        except RuntimeError:
            record.request_id = "-"
        return True


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("physician_locator")
logger.addFilter(RequestIdFilter())


# ─────────────────────────────────────────────
#  FLASK APP SETUP
# ─────────────────────────────────────────────

app = Flask(__name__)

_allowed_origins = [cfg.FRONTEND_URL] if cfg.FRONTEND_URL else []
CORS(
    app,
    origins=_allowed_origins or "*",
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
    max_age=600,
)


@app.before_request
def assign_request_id():
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
    g.request_id = rid


@app.after_request
def apply_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=()"
    response.headers["X-Request-ID"] = g.get("request_id", "-")
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://api.mqcdn.com; "
        "style-src 'self' https://api.mqcdn.com https://fonts.googleapis.com 'unsafe-inline'; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https://*.mqcdn.com https://*.mapquest.com; "
        "connect-src 'self' https://npiregistry.cms.hhs.gov https://api.geoapify.com;"
    )
    return response


# ─────────────────────────────────────────────
#  ERROR HELPER
# ─────────────────────────────────────────────

def _error(message: str, status: int, code: str = "") -> tuple:
    return jsonify({
        "error": message,
        "code": code or f"E{status}",
        "request_id": g.get("request_id", "-"),
    }), status


# ─────────────────────────────────────────────
#  ROUTES: HEALTH & SYSTEM
# ─────────────────────────────────────────────

@app.route("/health")
def health():
    missing_env = validate_configuration()
    zip_ready = zip_database.is_ready()
    
    return jsonify({
        "status": "ok" if zip_ready else "degraded",
        "zip_db_ready": zip_ready,
        "zip_db_count": zip_database.count(),
        "tax_loaded": taxonomy.is_loaded(),
        "tax_count": taxonomy.count(),
        "tax_source": taxonomy.source(),
        "missing_env_vars": missing_env,
    }), 200 if zip_ready else 503


@app.route("/api/lead-debug", methods=["POST"])
def lead_debug():
    """Debug endpoint to test full lead pipeline."""
    if cfg.DEBUG_SECRET:
        provided = request.headers.get("X-Debug-Secret", "")
        expected_hash = hashlib.sha256(cfg.DEBUG_SECRET.encode()).digest()
        provided_hash = hashlib.sha256(provided.encode()).digest()
        if expected_hash != provided_hash:
            logger.warning("lead-debug: bad secret | ip=%s",
                         request.headers.get("X-Forwarded-For", request.remote_addr))
            return _error("Forbidden", 403, "FORBIDDEN")
    else:
        logger.warning("lead-debug called — DEBUG_SECRET not set, allowing (insecure)")

    dummy = {
        "id": "debug_" + datetime.utcnow().strftime("%Y%m%d%H%M%S"),
        "first_name": "Debug",
        "last_name": "Test",
        "email": cfg.SF_DEBUG_EMAIL or "test@test.com",
        "phone": "5550000000",
        "company": "Aquarient Test",
        "title": "Debug",
        "search_context": {
            "address": "Test City, CA",
            "descriptions": ["Cardiology"],
            "radius": "10",
            "total_results": 0,
        },
        "created_at": datetime.utcnow().isoformat(),
        "source": "PhysicianLocator-DEBUG",
        "status": "Test",
    }

    sf_ok, sf_status, sf_snippet, sf_error = salesforce.push_to_salesforce(dummy)
    file_ok, file_path, file_error = salesforce.save_to_file(dummy)

    return jsonify({
        "lead_id": dummy["id"],
        "salesforce": {
            "success": sf_ok,
            "http_status": sf_status,
            "oid_configured": bool(cfg.SF_OID),
            "oid_preview": cfg.SF_OID[:8] + "..." if cfg.SF_OID else "NOT SET",
            "debug_email": cfg.SF_DEBUG_EMAIL or "NOT SET",
            "response_snippet": (sf_snippet or "")[:300],
            "error": sf_error,
        },
        "file_backup": {
            "success": file_ok,
            "path": file_path,
            "error": file_error,
        },
        "env_status": {
            "MAPQUEST_API_KEY": "SET" if cfg.MAPQUEST_API_KEY else "MISSING",
            "GEOAPIFY_API_KEY": "SET" if cfg.GEOAPIFY_API_KEY else "MISSING",
            "SF_OID": "SET" if cfg.SF_OID else "MISSING",
            "SF_RET_URL": "SET" if cfg.SF_RET_URL else "MISSING",
            "SF_DEBUG_EMAIL": "SET" if cfg.SF_DEBUG_EMAIL else "MISSING",
            "FRONTEND_URL": "SET" if cfg.FRONTEND_URL else "MISSING",
            "DEBUG_SECRET": "SET" if cfg.DEBUG_SECRET else "MISSING — endpoint unprotected",
            "LEADS_DIR": cfg.LEADS_DIR,
        },
    })


# ─────────────────────────────────────────────
#  ROUTES: GEOCODING & AUTOCOMPLETE
# ─────────────────────────────────────────────

@app.route("/api/autocomplete")
@rate_limit(limit=cfg.RATE_LIMIT_AC)
def autocomplete():
    """
    Address autocomplete via Geoapify.

    Uses cfg.AC_TIMEOUT (8 s) — well under Render's 30 s proxy deadline.
    Returns HTTP 200 with empty features on timeout or upstream error so the
    frontend degrades silently instead of showing an error banner.
    """
    text = (request.args.get("text") or "").strip()
    limit = min(int(request.args.get("limit", 6)), 10)

    if not text or len(text) < 2:
        return jsonify({"features": []})

    if not cfg.GEOAPIFY_API_KEY:
        return _error("Geocoding service not configured", 503, "GEOCODE_UNCONFIGURED")

    try:
        resp = http_client_once.get(    # no-retry: fails in 8s, not 27s
            "https://api.geoapify.com/v1/geocode/autocomplete",
            params={
                "text": text[:200],
                "limit": limit,
                "filter": "countrycode:us",
                "bias": "countrycode:us",
                "apiKey": cfg.GEOAPIFY_API_KEY,
            },
            timeout=cfg.AC_TIMEOUT,  # ← 8 s hard cap (was cfg.REQUEST_TIMEOUT = 45 s)
        )
        resp.raise_for_status()
        return jsonify(resp.json())

    except Timeout:
        # Log a warning but return 200 — the user is just typing; an empty
        # dropdown is far better than a visible error.
        logger.warning(
            "Geoapify autocomplete timed out | text=%r | timeout=%ss",
            text[:30], cfg.AC_TIMEOUT,
        )
        return jsonify({"features": [], "_timeout": True}), 200

    except Exception as e:
        logger.error("Autocomplete error: %s", e)
        return jsonify({"features": [], "_error": True}), 200


@app.route("/api/geocode")
@rate_limit(limit=cfg.RATE_LIMIT_SEARCH)
def geocode():
    """
    Forward geocode a US address via Geoapify.

    Also uses cfg.AC_TIMEOUT — the user clicked Search and is waiting,
    but we still must not exceed Render's proxy deadline.
    """
    address = (request.args.get("address") or "").strip()
    if not address:
        return _error("Address is required", 400, "MISSING_ADDRESS")
    if not cfg.GEOAPIFY_API_KEY:
        return _error("Geocoding service not configured", 503, "GEOCODE_UNCONFIGURED")

    try:
        resp = http_client_once.get(   # no-retry: fails in 8s, not 27s
            "https://api.geoapify.com/v1/geocode/search",
            params={
                "text": address[:300],
                "limit": 1,
                "filter": "countrycode:us",
                "apiKey": cfg.GEOAPIFY_API_KEY,
            },
            timeout=cfg.AC_TIMEOUT,  # ← 8 s hard cap (was cfg.REQUEST_TIMEOUT = 45 s)
        )
        resp.raise_for_status()
        features = resp.json().get("features", [])
        if not features:
            return _error("Address not found in the US", 404, "ADDRESS_NOT_FOUND")
        coords = features[0]["geometry"]["coordinates"]
        props = features[0].get("properties", {})
        return jsonify({
            "lat": coords[1],
            "lng": coords[0],
            "formatted": props.get("formatted", address),
            "city": str(props.get("city") or props.get("county") or ""),
            "state": str(props.get("state_code") or ""),
            "postcode": str(props.get("postcode") or "")[:5],
        })

    except Timeout:
        return _error("Geocoding service timed out — please try again", 504, "GEOCODE_TIMEOUT")

    except Exception as e:
        logger.error("Geocode error: %s", e)
        return _error("Geocoding failed", 502, "GEOCODE_ERROR")


# ─────────────────────────────────────────────
#  ROUTES: TAXONOMY
# ─────────────────────────────────────────────

@app.route("/api/taxonomy-search")
@rate_limit(limit=cfg.RATE_LIMIT_AC)
def taxonomy_search_route():
    q = (request.args.get("q") or "").strip()[:100]
    return jsonify({
        "results": taxonomy.search(q, limit=12),
        "loaded": taxonomy.is_loaded(),
        "source": taxonomy.source(),
    })


@app.route("/api/taxonomy-status")
def taxonomy_status():
    return jsonify({
        "loaded": taxonomy.is_loaded(),
        "count": taxonomy.count(),
        "source": taxonomy.source(),
        "zip_db_count": zip_database.count(),
        "zip_db_ready": zip_database.is_ready(),
    })


# ─────────────────────────────────────────────
#  ROUTES: PHYSICIAN SEARCH
# ─────────────────────────────────────────────

@app.route("/api/search")
@rate_limit(limit=cfg.RATE_LIMIT_SEARCH)
def search_physicians():
    try:
        lat, lng = validate_lat_lng(
            request.args.get("lat"), request.args.get("lng")
        )
    except (TypeError, ValueError) as e:
        return _error(f"Invalid coordinates: {e}", 400, "INVALID_COORDS")

    try:
        radius = validate_radius(request.args.get("radius", 10))
    except (TypeError, ValueError) as e:
        return _error(f"Invalid radius: {e}", 400, "INVALID_RADIUS")

    taxonomy_code = sanitise(request.args.get("taxonomy_code") or "", 50)
    descriptions = validate_descriptions(
        request.args.get("descriptions", ""),
        request.args.get("description", ""),
    )
    search_city = sanitise(request.args.get("city", "") or "", 80)
    search_state = sanitise(request.args.get("state", "") or "", 2).upper()

    if not zip_database.wait_for_ready(timeout=3.0):
        logger.warning("ZIP DB not ready after 3s — proceeding with partial data")

    try:
        tax_param_sets: list[dict] = []
        if taxonomy_code:
            tax_param_sets = [{"taxonomy_description": taxonomy_code}]
        elif descriptions:
            for desc in descriptions[:cfg.MAX_TAX_QUERIES]:
                matches = taxonomy.search(desc, limit=1)
                best = matches[0]["display"] if matches else desc
                logger.info("Taxonomy resolved: '%s' → '%s'", desc, best)
                tax_param_sets.append({"taxonomy_description": best})
        else:
            tax_param_sets = [{}]

        logger.info("Running %d taxonomy queries | lat=%.4f lng=%.4f radius=%.0f",
                    len(tax_param_sets), lat, lng, radius)

        zips_in_radius = zip_database.find_zips_in_radius(lat, lng, radius)
        logger.info("ZIPs in radius: %d", len(zips_in_radius))

        seen_npis: set[str] = set()
        all_raw: list[dict] = []

        def add(rows: list[dict]):
            for r in rows:
                npi = r.get("number")
                if npi and npi not in seen_npis:
                    seen_npis.add(npi)
                    all_raw.append(r)

        for tax_params in tax_param_sets:
            for z in zips_in_radius[:cfg.MAX_ZIP_QUERIES]:
                rows, _ = nppes.fetch_with_retry({"postal_code": z, **tax_params})
                add(rows)
            if search_city and search_state:
                rows, _ = nppes.fetch_with_retry(
                    {"city": search_city.title(), "state": search_state, **tax_params}
                )
                add(rows)

        if not all_raw and search_state:
            logger.info("No ZIP/city results — state fallback")
            for tax_params in tax_param_sets:
                rows, _ = nppes.fetch_with_retry({"state": search_state, **tax_params})
                add(rows)

        logger.info("NPPES unique records: %d", len(all_raw))

        physicians: list[dict] = []
        for raw in all_raw:
            try:
                p = nppes.parse_physician(raw)
                if p:
                    physicians.append(p)
            except Exception:
                logger.debug("Parse error: %s", traceback.format_exc())

        for p in physicians:
            if p.get("zip"):
                p["lat"], p["lng"] = zip_database.get_zip_coords(p["zip"])

        in_radius: list[dict] = []
        for p in physicians:
            if p.get("lat") and p.get("lng"):
                d = zip_database.haversine(lat, lng, p["lat"], p["lng"])
                if d <= radius:
                    p["distance_miles"] = round(d, 1)
                    in_radius.append(p)

        in_radius.sort(key=lambda x: x.get("distance_miles", 9999))

        for p in physicians:
            if not p.get("lat"):
                p["distance_miles"] = None
                in_radius.append(p)

        total = len(in_radius)
        shown = in_radius[:cfg.MAX_DISPLAY]

        nppes.batch_geocode_for_display(shown)
        nppes.apply_coord_jitter(shown)

        logger.info("Returning %d of %d physicians", len(shown), total)
        return jsonify({"total": total, "returned": len(shown), "physicians": shown})

    except Exception:
        logger.error("Search error:\n%s", traceback.format_exc())
        return _error("An unexpected error occurred. Please try again.", 500, "SEARCH_ERROR")


# ─────────────────────────────────────────────
#  ROUTES: LEAD CAPTURE
# ─────────────────────────────────────────────

@app.route("/api/leads", methods=["POST"])
@rate_limit(limit=cfg.RATE_LIMIT_LEAD)
def capture_lead():
    data = request.get_json(silent=True)
    if not data:
        return _error("JSON body required", 400, "BAD_REQUEST")

    for field in ("first_name", "last_name", "email"):
        if not (data.get(field) or "").strip():
            return _error(f"'{field}' is required", 400, "MISSING_FIELD")

    email = sanitise(data.get("email") or "").lower()
    if "@" not in email or len(email) > 254:
        return _error("A valid email address is required", 400, "INVALID_EMAIL")

    lead = {
        "id": f"lead_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
        "first_name": sanitise(data.get("first_name", ""), 80),
        "last_name": sanitise(data.get("last_name", ""), 80),
        "email": email,
        "phone": sanitise(data.get("phone", ""), 30),
        "company": sanitise(data.get("company", ""), 120),
        "title": sanitise(data.get("title", ""), 80),
        "search_context": data.get("search_context") if isinstance(data.get("search_context"), dict) else {},
        "created_at": datetime.utcnow().isoformat(),
        "source": "PhysicianLocator",
        "status": "New",
    }

    sf_ok, sf_status, sf_snippet, sf_error = salesforce.push_to_salesforce(lead)
    file_ok, file_path, file_error = salesforce.save_to_file(lead)

    if not sf_ok and not file_ok:
        logger.error(
            "Lead LOST — both SF and file failed | email=%s | sf_err=%s | file_err=%s",
            email, sf_error, file_error,
        )
        return _error("Could not save your request. Please try again.", 500, "LEAD_SAVE_FAILED")

    logger.info("Lead captured | id=%s | sf=%s | file=%s | email=%s",
                lead["id"], sf_ok, file_ok, email)
    return jsonify({
        "success": True,
        "lead_id": lead["id"],
        "message": "Thank you! Our team will contact you shortly.",
    })


# ─────────────────────────────────────────────
#  INITIALIZATION
# ─────────────────────────────────────────────

def initialize_app():
    """Initialize all background services."""
    missing_env = validate_configuration()
    zip_database.initialize()
    taxonomy.initialize()
    rate_limiting.start_rate_limiter_purge()
    logger.info("Backend initialized | missing_env=%s", missing_env)


initialize_app()


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=cfg.PORT, debug=False)