"""
Physician Locator — Aquarient (v2.1.2)

Production-grade physician search API using the official NPPES registry.
Features: Full-width search, lead capture, Salesforce integration, structured logging.

Changes from v2.1.1:
  - FIX: ZIP DB cold-start race condition (root cause of "ZIPs in radius: 0").
    On Render (IS_RENDER=True / RENDER env var set), zip_database.initialize()
    now loads synchronously — the worker blocks until the DB is ready before
    accepting any traffic. This fixes every search returning 0 results after
    a worker restart.
  - FIX: ZIP_DB_WAIT increased from 3s → cfg.ZIP_DB_WAIT (30s) as a failsafe
    for the async path. If the DB still isn't ready after 30s, we return 503
    ("service warming up") instead of silently returning 0 results.
  - FIX: Distance filtering — early break in _refine_display_physicians removed.
    Previously the loop broke as soon as shown[] was full, making exact_total
    an undercount. Now counting continues through all candidates; only shown[]
    is capped at MAX_DISPLAY.
  - FIX: total reported as exact_total unconditionally (was len(coarse_matches)
    when not exhausted, which was the centroid-based count — inflated).
  - FIX: Coord source tracking — batch_geocode_for_display() sets _geocoded=True
    only on address-level success. Physicians with only ZIP centroid coords are
    labelled _coord_source="zip_centroid" in the response for easier debugging.
  - FIX: Coord fallback when ZIP DB is unavailable — if get_zip_coords() returns
    None (shouldn't happen in sync mode, but guards async/fallback paths), we
    assign the search center coords so physicians aren't silently dropped by the
    distance filter.
  - FIX: Missing `import requests` in salesforce.py caused NameError on
    requests.Timeout — corrected in that module.
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


_handler = logging.StreamHandler()
_handler.addFilter(RequestIdFilter())
_handler.setFormatter(logging.Formatter(
    fmt="%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
))

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers.clear()
root_logger.addHandler(_handler)

logger = logging.getLogger("ClinTrial Navigator")


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
            "ZIP_LOAD_SYNC": cfg.ZIP_LOAD_SYNC,
            "IS_RENDER": cfg.IS_RENDER,
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

    Uses cfg.AC_TIMEOUT (8s) — well under Render's 30s proxy deadline.
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
        resp = http_client_once.get(
            "https://api.geoapify.com/v1/geocode/autocomplete",
            params={
                "text": text[:200],
                "limit": limit,
                "filter": "countrycode:us",
                "bias": "countrycode:us",
                "apiKey": cfg.GEOAPIFY_API_KEY,
            },
            timeout=cfg.AC_TIMEOUT,
        )
        resp.raise_for_status()
        return jsonify(resp.json())

    except Timeout:
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
    """
    address = (request.args.get("address") or "").strip()
    if not address:
        return _error("Address is required", 400, "MISSING_ADDRESS")
    if not cfg.GEOAPIFY_API_KEY:
        return _error("Geocoding service not configured", 503, "GEOCODE_UNCONFIGURED")

    try:
        resp = http_client_once.get(
            "https://api.geoapify.com/v1/geocode/search",
            params={
                "text": address[:300],
                "limit": 1,
                "filter": "countrycode:us",
                "apiKey": cfg.GEOAPIFY_API_KEY,
            },
            timeout=cfg.AC_TIMEOUT,
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

def _has_coords(physician: dict) -> bool:
    return physician.get("lat") is not None and physician.get("lng") is not None


def _distance_from_search(center_lat: float, center_lng: float, physician: dict) -> float | None:
    if not _has_coords(physician):
        return None
    return zip_database.haversine(center_lat, center_lng, physician["lat"], physician["lng"])


def _refine_display_physicians(
    candidates: list[dict],
    center_lat: float,
    center_lng: float,
    radius: float,
) -> tuple[list[dict], int]:
    """
    Refine candidates with address-level coordinates and recount within radius.

    Key fixes vs v2.1.1:
      - The early `break` is removed. Previously the outer chunk loop broke as
        soon as shown[] reached MAX_DISPLAY, making exact_total an undercount
        for everything after that chunk. Now shown[] is still capped but
        counting runs through all candidates.
      - Returns (shown, exact_total) — the "exhausted" flag is gone because
        exact_total is now always the true full count.
      - p["_coord_source"] is set to "address" or "zip_centroid" for debugging.
    """
    shown: list[dict] = []
    exact_total = 0
    chunk_size = max(cfg.MAX_DISPLAY * 3, 25)

    for start in range(0, len(candidates), chunk_size):
        chunk = candidates[start:start + chunk_size]
        nppes.batch_geocode_for_display(chunk)

        for physician in chunk:
            distance = _distance_from_search(center_lat, center_lng, physician)
            if distance is None or distance > radius:
                continue

            physician["distance_miles"] = round(distance, 1)
            physician["_coord_source"] = (
                "address" if physician.get("_geocoded") else "zip_centroid"
            )
            exact_total += 1

            # Cap the display list but always keep counting.
            if len(shown) < cfg.MAX_DISPLAY:
                shown.append(physician)

    shown.sort(key=lambda p: p.get("distance_miles", 9999))
    return shown, exact_total


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

    # ── ZIP DB readiness check ────────────────────────────────────────────────
    # In sync mode (Render) the DB is always ready here because initialize()
    # blocked until it was done. The wait below is a safety net for the async
    # path (local dev) or if something went wrong during sync load.
    if not zip_database.wait_for_ready(timeout=cfg.ZIP_DB_WAIT):
        logger.error(
            "ZIP DB not ready after %.0fs — returning 503 to avoid silent zero results",
            cfg.ZIP_DB_WAIT,
        )
        return _error(
            "Search service is warming up — please retry in a few seconds.",
            503,
            "ZIP_DB_NOT_READY",
        )

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

        logger.info(
            "Running %d taxonomy queries | lat=%.4f lng=%.4f radius=%.0f",
            len(tax_param_sets), lat, lng, radius,
        )

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

        # ── Assign ZIP centroid coordinates ───────────────────────────────────
        # These are the coarse coordinates used for the initial distance filter.
        # If the ZIP DB returned nothing for a ZIP (shouldn't happen after the
        # readiness check, but guards edge cases), fall back to the search center
        # so the physician isn't silently dropped later.
        for p in physicians:
            if p.get("zip"):
                zip_lat, zip_lng = zip_database.get_zip_coords(p["zip"])
                if zip_lat is not None and zip_lng is not None:
                    p["lat"] = zip_lat
                    p["lng"] = zip_lng
                else:
                    # Unknown ZIP — place at search center so it survives the
                    # coarse filter and gets a chance at address-level geocoding.
                    p["lat"] = lat
                    p["lng"] = lng
                    p["_coord_source"] = "search_center_fallback"
                    logger.debug("Unknown ZIP %s — using search center coords", p.get("zip"))

        # ── Coarse distance filter (ZIP centroid level) ───────────────────────
        coarse_matches: list[dict] = []
        for p in physicians:
            distance = _distance_from_search(lat, lng, p)
            if distance is None or distance > radius:
                continue
            p["distance_miles"] = round(distance, 1)
            coarse_matches.append(p)

        coarse_matches.sort(key=lambda x: x.get("distance_miles", 9999))

        # ── Refined filter (address-level geocoding) + accurate total count ───
        shown, exact_total = _refine_display_physicians(
            coarse_matches, lat, lng, radius
        )

        # exact_total is the true count of physicians within the radius after
        # address-level geocoding. Use it unconditionally — the old code used
        # len(coarse_matches) when the loop broke early, which was inflated.
        total = exact_total

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
        "search_context": (
            data.get("search_context")
            if isinstance(data.get("search_context"), dict)
            else {}
        ),
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

    logger.info(
        "Lead captured | id=%s | sf=%s | file=%s | email=%s",
        lead["id"], sf_ok, file_ok, email,
    )
    return jsonify({
        "success": True,
        "lead_id": lead["id"],
        "message": "Thank you! Our team will contact you shortly.",
    })


# ─────────────────────────────────────────────
#  INITIALIZATION
# ─────────────────────────────────────────────

def initialize_app():
    """
    Initialize all background services.

    ZIP DB loading strategy:
      - On Render (IS_RENDER / ZIP_LOAD_SYNC=True): synchronous load.
        The worker blocks here until the full 41k-entry ZIP DB is ready.
        This adds ~1-2s to startup but guarantees no worker ever serves
        a search request without a valid ZIP DB.
      - Locally (ZIP_LOAD_SYNC=False): background thread as before.
        Local dev restarts are fast and the 30s wait + 503 fallback
        in search_physicians() protects against the unlikely race.
    """
    missing_env = validate_configuration()
    zip_database.initialize(background=not cfg.ZIP_LOAD_SYNC)
    taxonomy.initialize()
    rate_limiting.start_rate_limiter_purge()
    logger.info(
        "Backend initialized | zip_sync=%s | missing_env=%s",
        cfg.ZIP_LOAD_SYNC, missing_env,
    )


initialize_app()


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=cfg.PORT, debug=False)