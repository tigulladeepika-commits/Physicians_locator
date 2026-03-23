"""
Physician Locator — Aquarient
Production-grade backend: rate limiting, input validation, security headers,
request sessions, bounded caches, structured logging, graceful degradation.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import math
import os
import threading
import time
import traceback
import zipfile
from collections import OrderedDict
from datetime import datetime
from functools import wraps
from typing import Optional

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─────────────────────────────────────────────
#  STRUCTURED LOGGING
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("physician_locator")


# ─────────────────────────────────────────────
#  CONFIG  (all from environment — no hardcoded secrets)
# ─────────────────────────────────────────────

class Config:
    MAPQUEST_API_KEY:   str  = os.environ.get("MAPQUEST_API_KEY", "")
    GEOAPIFY_API_KEY:   str  = os.environ.get("GEOAPIFY_API_KEY", "")
    FRONTEND_URL:       str  = os.environ.get("FRONTEND_URL", "")
    SF_OID:             str  = os.environ.get("SF_OID", "")           # was hardcoded
    SF_RET_URL:         str  = os.environ.get("SF_RET_URL", "")
    SF_DEBUG_EMAIL:     str  = os.environ.get("SF_DEBUG_EMAIL", "")
    PORT:               int  = int(os.environ.get("PORT", 5000))

    # Limits
    MAX_DISPLAY:        int  = 10
    MAX_ZIP_QUERIES:    int  = 20           # was 30 — reduces NPPES hammering
    MAX_TAX_QUERIES:    int  = 3            # cap taxonomy fan-out
    MAX_DESC_COUNT:     int  = 5            # max specialty tags per search
    MAX_DESC_LEN:       int  = 120          # chars per specialty string
    MAX_RADIUS:         float = 100.0
    GEOCODE_CACHE_SIZE: int  = 2000
    REQUEST_TIMEOUT:    int  = 15           # seconds for outbound HTTP

    # Rate limiting (in-process, per-IP)
    RATE_LIMIT_WINDOW:  int  = 60           # seconds
    RATE_LIMIT_SEARCH:  int  = 30           # requests per window
    RATE_LIMIT_LEAD:    int  = 5
    RATE_LIMIT_AC:      int  = 120


cfg = Config()

for key, label in [(cfg.MAPQUEST_API_KEY, "MAPQUEST_API_KEY"),
                   (cfg.GEOAPIFY_API_KEY, "GEOAPIFY_API_KEY"),
                   (cfg.SF_OID, "SF_OID")]:
    if not key:
        logger.warning("Environment variable %s is not set", label)


# ─────────────────────────────────────────────
#  FLASK APP + CORS + SECURITY HEADERS
# ─────────────────────────────────────────────

app = Flask(__name__)

_allowed_origins = [cfg.FRONTEND_URL] if cfg.FRONTEND_URL else []
CORS(
    app,
    origins=_allowed_origins or "*",
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=600,
)


@app.after_request
def apply_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=()"
    # Tight CSP — adjust if you add CDN resources
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
#  IN-PROCESS RATE LIMITER
# ─────────────────────────────────────────────

class RateLimiter:
    """Sliding-window rate limiter keyed by (IP, endpoint)."""

    def __init__(self):
        self._store: dict[tuple, list[float]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, key: tuple, limit: int, window: int) -> bool:
        now = time.time()
        cutoff = now - window
        with self._lock:
            hits = self._store.get(key, [])
            hits = [t for t in hits if t > cutoff]
            if len(hits) >= limit:
                return False
            hits.append(now)
            self._store[key] = hits
            return True


_rate_limiter = RateLimiter()


def rate_limit(limit: int, window: int = cfg.RATE_LIMIT_WINDOW):
    """Decorator factory — applies per-IP rate limiting to a route."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
            key = (ip, fn.__name__)
            if not _rate_limiter.is_allowed(key, limit, window):
                return jsonify({"error": "Too many requests. Please slow down."}), 429
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ─────────────────────────────────────────────
#  SHARED HTTP SESSION  (connection pooling)
# ─────────────────────────────────────────────

_http = requests.Session()
_http.headers.update({"User-Agent": "PhysicianLocator/1.0"})


# ─────────────────────────────────────────────
#  LRU CACHE  (bounded, thread-safe)
# ─────────────────────────────────────────────

class LRUCache:
    def __init__(self, max_size: int):
        self._cache: OrderedDict = OrderedDict()
        self._max = max_size
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key not in self._cache:
                return None
            self._cache.move_to_end(key)
            return self._cache[key]

    def set(self, key, value):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self._max:
                self._cache.popitem(last=False)


_addr_cache = LRUCache(cfg.GEOCODE_CACHE_SIZE)


# ─────────────────────────────────────────────
#  ZIP CODE DATABASE
# ─────────────────────────────────────────────

GEONAMES_ZIP_URL = "https://download.geonames.org/export/zip/US.zip"
_zip_db: dict[str, tuple[float, float]] = {}
_zip_db_ready = threading.Event()   # use Event instead of bool flag
_zip_db_lock  = threading.Lock()

# Spatial index: bucket ZIPs by 1-degree lat/lng cell for fast radius lookups
_zip_index: dict[tuple[int, int], list[tuple[float, float, str]]] = {}
_zip_index_lock = threading.Lock()


def _build_spatial_index(db: dict[str, tuple[float, float]]):
    """Group ZIP centroids into 1°×1° grid cells for O(1) candidate lookup."""
    idx: dict[tuple[int, int], list] = {}
    for z, (lat, lng) in db.items():
        cell = (int(math.floor(lat)), int(math.floor(lng)))
        idx.setdefault(cell, []).append((lat, lng, z))
    with _zip_index_lock:
        _zip_index.clear()
        _zip_index.update(idx)
    logger.info("Spatial index built: %d cells", len(_zip_index))


def _load_zip_database():
    global _zip_db
    local_cache = "us_zip_db.json"

    def _apply(db: dict):
        with _zip_db_lock:
            _zip_db.clear()
            _zip_db.update(db)
        _build_spatial_index(db)
        _zip_db_ready.set()
        logger.info("ZIP db ready: %d entries", len(_zip_db))

    # Try local cache first
    if os.path.exists(local_cache):
        try:
            with open(local_cache) as f:
                raw = json.load(f)
            db = {k: (float(v[0]), float(v[1])) for k, v in raw.items()}
            _apply(db)
            logger.info("ZIP db loaded from disk cache")
            return
        except Exception as e:
            logger.warning("ZIP disk cache corrupt, re-downloading: %s", e)

    # Download from GeoNames
    try:
        logger.info("Downloading GeoNames US ZIP database...")
        resp = _http.get(GEONAMES_ZIP_URL, timeout=90)
        resp.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        with zf.open("US.txt") as f:
            content = f.read().decode("utf-8", errors="replace")
        db: dict = {}
        for line in content.splitlines():
            parts = line.split("\t")
            if len(parts) >= 11:
                zcode = parts[1].strip()
                try:
                    db[zcode] = (float(parts[9]), float(parts[10]))
                except (ValueError, IndexError):
                    pass
        # Atomic write — avoid partial file on interruption
        tmp = local_cache + ".tmp"
        with open(tmp, "w") as f:
            json.dump({k: list(v) for k, v in db.items()}, f)
        os.replace(tmp, local_cache)
        _apply(db)
    except Exception as e:
        logger.error("ZIP db download failed: %s — using fallback", e)
        _apply(_ZIP_FALLBACK)


# Minimal fallback covering major metros — same as original but stored as constant
_ZIP_FALLBACK: dict[str, tuple[float, float]] = {
    "10001": (40.7506, -73.9971), "90210": (34.0901, -118.4065),
    "60601": (41.8859, -87.6181), "77030": (29.7079, -95.4010),
    "94102": (37.7793, -122.4192), "98101": (47.6089, -122.3352),
    "30301": (33.7627, -84.4229), "02115": (42.3437, -71.0992),
    "19103": (39.9527, -75.1797), "20001": (38.9123, -77.0177),
    "33101": (25.7959, -80.2870), "75201": (32.7884, -96.7989),
    "48201": (42.3533, -83.0524), "80201": (39.7392, -104.9903),
    "97201": (45.5169, -122.6809), "89101": (36.1756, -115.1391),
    "92101": (32.7264, -117.1552), "28201": (35.2271, -80.8431),
}

threading.Thread(target=_load_zip_database, daemon=False, name="zip-loader").start()


def get_zip_coords(zipcode: str) -> tuple[Optional[float], Optional[float]]:
    z = str(zipcode or "")[:5].strip()
    with _zip_db_lock:
        v = _zip_db.get(z)
    return (float(v[0]), float(v[1])) if v else (None, None)


# ─────────────────────────────────────────────
#  HAVERSINE
# ─────────────────────────────────────────────

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _find_zips_in_radius(center_lat: float, center_lng: float, radius_miles: float) -> list[str]:
    """
    Use spatial index (1°×1° grid) for O(cells_checked) instead of O(all_zips).
    At 10-mile radius, only ~4–9 cells need checking vs 42k entries.
    """
    deg_lat = radius_miles / 69.0
    deg_lng = radius_miles / (69.0 * math.cos(math.radians(center_lat)) + 1e-9)
    min_lat = center_lat - deg_lat; max_lat = center_lat + deg_lat
    min_lng = center_lng - deg_lng; max_lng = center_lng + deg_lng

    cell_lat_min = int(math.floor(min_lat))
    cell_lat_max = int(math.floor(max_lat))
    cell_lng_min = int(math.floor(min_lng))
    cell_lng_max = int(math.floor(max_lng))

    result: list[tuple[float, str]] = []
    with _zip_index_lock:
        for clat in range(cell_lat_min, cell_lat_max + 1):
            for clng in range(cell_lng_min, cell_lng_max + 1):
                for (zlat, zlng, z) in _zip_index.get((clat, clng), []):
                    d = haversine(center_lat, center_lng, zlat, zlng)
                    if d <= radius_miles:
                        result.append((d, z))

    # Fallback to linear scan if index not ready
    if not result and not _zip_index:
        with _zip_db_lock:
            for z, (zlat, zlng) in _zip_db.items():
                d = haversine(center_lat, center_lng, zlat, zlng)
                if d <= radius_miles:
                    result.append((d, z))

    result.sort()
    return [z for _, z in result]


# ─────────────────────────────────────────────
#  NUCC TAXONOMY
# ─────────────────────────────────────────────

NUCC_CSV_URL = "https://www.nucc.org/images/stories/CSV/nucc_taxonomy_250.csv"

_taxonomy_entries: list[dict] = []
_taxonomy_loaded = False
_taxonomy_source = "none"
_taxonomy_lock   = threading.Lock()

_SEED_TAXONOMY = [
    ("Allopathic & Osteopathic Physicians", "Addiction Medicine"),
    ("Allopathic & Osteopathic Physicians", "Allergy & Immunology"),
    ("Allopathic & Osteopathic Physicians", "Anesthesiology"),
    ("Allopathic & Osteopathic Physicians", "Cardiac Surgery"),
    ("Allopathic & Osteopathic Physicians", "Cardiovascular Disease"),
    ("Allopathic & Osteopathic Physicians", "Colon & Rectal Surgery"),
    ("Allopathic & Osteopathic Physicians", "Dermatology"),
    ("Allopathic & Osteopathic Physicians", "Diagnostic Radiology"),
    ("Allopathic & Osteopathic Physicians", "Emergency Medicine"),
    ("Allopathic & Osteopathic Physicians", "Endocrinology, Diabetes & Metabolism"),
    ("Allopathic & Osteopathic Physicians", "Family Medicine"),
    ("Allopathic & Osteopathic Physicians", "Gastroenterology"),
    ("Allopathic & Osteopathic Physicians", "General Practice"),
    ("Allopathic & Osteopathic Physicians", "General Surgery"),
    ("Allopathic & Osteopathic Physicians", "Geriatric Medicine"),
    ("Allopathic & Osteopathic Physicians", "Hematology & Oncology"),
    ("Allopathic & Osteopathic Physicians", "Infectious Disease"),
    ("Allopathic & Osteopathic Physicians", "Internal Medicine"),
    ("Allopathic & Osteopathic Physicians", "Interventional Cardiology"),
    ("Allopathic & Osteopathic Physicians", "Medical Oncology"),
    ("Allopathic & Osteopathic Physicians", "Nephrology"),
    ("Allopathic & Osteopathic Physicians", "Neurology"),
    ("Allopathic & Osteopathic Physicians", "Neurosurgery"),
    ("Allopathic & Osteopathic Physicians", "Obstetrics & Gynecology"),
    ("Allopathic & Osteopathic Physicians", "Ophthalmology"),
    ("Allopathic & Osteopathic Physicians", "Orthopaedic Surgery"),
    ("Allopathic & Osteopathic Physicians", "Pain Medicine"),
    ("Allopathic & Osteopathic Physicians", "Pediatrics"),
    ("Allopathic & Osteopathic Physicians", "Physical Medicine & Rehabilitation"),
    ("Allopathic & Osteopathic Physicians", "Plastic Surgery"),
    ("Allopathic & Osteopathic Physicians", "Psychiatry"),
    ("Allopathic & Osteopathic Physicians", "Pulmonary Disease"),
    ("Allopathic & Osteopathic Physicians", "Radiation Oncology"),
    ("Allopathic & Osteopathic Physicians", "Rheumatology"),
    ("Allopathic & Osteopathic Physicians", "Sleep Medicine"),
    ("Allopathic & Osteopathic Physicians", "Sports Medicine"),
    ("Allopathic & Osteopathic Physicians", "Thoracic Surgery"),
    ("Allopathic & Osteopathic Physicians", "Urology"),
    ("Allopathic & Osteopathic Physicians", "Vascular Surgery"),
    ("Dental Providers", "Dentist"),
    ("Dental Providers", "Dental Hygienist"),
    ("Dental Providers", "Endodontics"),
    ("Dental Providers", "Oral and Maxillofacial Surgery"),
    ("Dental Providers", "Orthodontics and Dentofacial Orthopedics"),
    ("Dental Providers", "Pediatric Dentistry"),
    ("Dental Providers", "Periodontics"),
    ("Dental Providers", "Prosthodontics"),
    ("Podiatric Medicine & Surgery Providers", "Podiatrist"),
    ("Pharmacy Service Providers", "Pharmacist"),
    ("Pharmacy Service Providers", "Clinical Pharmacy Specialist"),
    ("Nursing Service Providers", "Certified Nurse Midwife"),
    ("Nursing Service Providers", "Certified Registered Nurse Anesthetist"),
    ("Nursing Service Providers", "Clinical Nurse Specialist"),
    ("Nursing Service Providers", "Licensed Practical Nurse"),
    ("Nursing Service Providers", "Nurse Practitioner"),
    ("Nursing Service Providers", "Registered Nurse"),
    ("Physician Assistants & Advanced Practice Nursing Providers", "Physician Assistant"),
    ("Eye and Vision Services Providers", "Optometrist"),
    ("Chiropractic Providers", "Chiropractor"),
    ("Physical Medicine & Rehabilitation Providers", "Physical Therapist"),
    ("Physical Medicine & Rehabilitation Providers", "Occupational Therapist"),
    ("Respiratory, Developmental, Rehabilitative & Restorative Service Providers", "Respiratory Therapist"),
    ("Speech, Language and Hearing Service Providers", "Audiologist"),
    ("Speech, Language and Hearing Service Providers", "Speech-Language Pathologist"),
    ("Behavioral Health & Social Service Providers", "Counselor"),
    ("Behavioral Health & Social Service Providers", "Marriage & Family Therapist"),
    ("Behavioral Health & Social Service Providers", "Psychologist"),
    ("Behavioral Health & Social Service Providers", "Social Worker"),
    ("Behavioral Health & Social Service Providers", "Social Worker, Clinical"),
    ("Dietetic & Nutritional Service Providers", "Dietitian, Registered"),
    ("Emergency Medical Service Providers", "Emergency Medical Technician"),
    ("Emergency Medical Service Providers", "Paramedic"),
    ("Ambulatory Health Care Facilities", "Ambulatory Surgical"),
    ("Ambulatory Health Care Facilities", "Urgent Care"),
    ("Hospital", "General Acute Care Hospital"),
]


def _build_entries(rows: list[tuple[str, str]]) -> list[dict]:
    out, seen = [], set()
    for classification, specialization in rows:
        c = (classification or "").strip()
        s = (specialization or "").strip()
        if not c:
            continue
        display = s if s else c
        if display in seen:
            continue
        seen.add(display)
        out.append({
            "classification": c,
            "specialization": s,
            "display":        display,
            "search_text":    f"{c} {s}".lower(),
        })
    return out


def _load_taxonomy_background():
    global _taxonomy_loaded, _taxonomy_source
    seed = _build_entries(_SEED_TAXONOMY)
    with _taxonomy_lock:
        _taxonomy_entries[:] = seed
        _taxonomy_loaded = True
        _taxonomy_source = "seed"
    logger.info("Taxonomy seed ready: %d entries", len(seed))

    try:
        resp = _http.get(NUCC_CSV_URL, timeout=20)
        resp.raise_for_status()
        reader = csv.DictReader(io.StringIO(resp.text))
        rows = [
            (r.get("Classification", "").strip(), r.get("Specialization", "").strip())
            for r in reader
            if r.get("Classification", "").strip()
        ]
        if rows:
            live = _build_entries(rows)
            with _taxonomy_lock:
                _taxonomy_entries[:] = live
                _taxonomy_source = "NUCC CSV"
            logger.info("NUCC CSV loaded: %d entries", len(live))
    except Exception as e:
        logger.warning("NUCC CSV fetch failed: %s — keeping seed", e)


threading.Thread(target=_load_taxonomy_background, daemon=True, name="tax-loader").start()


def _taxonomy_search(q: str, limit: int = 12) -> list[dict]:
    q = q.lower().strip()
    if not q:
        return []
    q_words = [w for w in q.split() if len(w) >= 2]
    with _taxonomy_lock:
        entries = list(_taxonomy_entries)
    scored: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    for e in entries:
        st = e["search_text"]
        d  = e["display"]
        score = 0
        if q == e["specialization"].lower():             score = 100
        elif e["specialization"].lower().startswith(q): score = 85
        elif e["classification"].lower().startswith(q): score = 75
        elif q in st:                                    score = 60
        elif all(w in st for w in q_words):              score = 50
        elif any(w in st for w in q_words):              score = 30
        if score > 0 and d not in seen:
            seen.add(d)
            scored.append((score, d, e["classification"]))
    return [
        {"display": display, "classification": classification}
        for _, display, classification in sorted(scored, key=lambda x: (-x[0], x[1]))[:limit]
    ]


# ─────────────────────────────────────────────
#  INPUT VALIDATION HELPERS
# ─────────────────────────────────────────────

def _validate_lat_lng(lat, lng) -> tuple[float, float]:
    """Raise ValueError if coordinates are out of US bounds."""
    lat, lng = float(lat), float(lng)
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        raise ValueError("Coordinates out of range")
    # Loose US bounding box
    if not (18.0 <= lat <= 72.0) or not (-180.0 <= lng <= -65.0):
        raise ValueError("Coordinates outside the United States")
    return lat, lng


def _validate_radius(radius_str) -> float:
    r = float(radius_str)
    if r <= 0 or r > cfg.MAX_RADIUS:
        raise ValueError(f"Radius must be between 1 and {cfg.MAX_RADIUS} miles")
    return r


def _validate_descriptions(raw: str, single: str) -> list[str]:
    descriptions: list[str] = []
    if raw:
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValueError("descriptions must be a JSON array")
            descriptions = [str(d).strip()[:cfg.MAX_DESC_LEN] for d in parsed if str(d).strip()]
        except json.JSONDecodeError:
            descriptions = [raw.strip()[:cfg.MAX_DESC_LEN]] if raw.strip() else []
    elif single:
        descriptions = [single.strip()[:cfg.MAX_DESC_LEN]]
    return descriptions[:cfg.MAX_DESC_COUNT]


# ─────────────────────────────────────────────
#  NPPES
# ─────────────────────────────────────────────

NPPES_BASE_URL = "https://npiregistry.cms.hhs.gov/api/"


def _nppes_fetch(params: dict) -> tuple[list, int]:
    clean = {k: str(v).strip() for k, v in params.items() if v and str(v).strip()}
    query = {
        "version":          "2.1",
        "enumeration_type": "NPI-1",
        "limit":            200,
        "skip":             0,
        "country_code":     "US",
        **clean,
    }
    try:
        resp = _http.get(NPPES_BASE_URL, params=query, timeout=cfg.REQUEST_TIMEOUT)
        resp.raise_for_status()
        d = resp.json()
        return d.get("results") or [], int(d.get("result_count") or 0)
    except requests.Timeout:
        logger.warning("NPPES timeout | params=%s", clean)
        return [], 0
    except Exception as e:
        logger.warning("NPPES fetch failed: %s | params=%s", e, clean)
        return [], 0


def _nppes_fetch_with_retry(params: dict, retries: int = 2) -> tuple[list, int]:
    """Retry on transient network errors with exponential back-off."""
    delay = 0.5
    for attempt in range(retries + 1):
        rows, total = _nppes_fetch(params)
        if rows or attempt == retries:
            return rows, total
        time.sleep(delay)
        delay *= 2
    return [], 0


def _parse_physician(result: dict) -> Optional[dict]:
    basic      = result.get("basic",      {})
    addresses  = result.get("addresses",  [])
    taxonomies = result.get("taxonomies", [])

    addr = next(
        (a for a in addresses if a.get("address_purpose") == "LOCATION"),
        addresses[0] if addresses else {},
    )
    primary_tax = next(
        (t for t in taxonomies if t.get("primary")),
        taxonomies[0] if taxonomies else {},
    )

    first = str(basic.get("first_name") or "")
    last  = str(basic.get("last_name")  or "")
    cred  = str(basic.get("credential") or "")
    name  = f"{first} {last}".strip() or "Unknown Provider"
    if cred:
        name += f", {cred}"

    addr1   = str(addr.get("address_1")        or "")
    addr2   = str(addr.get("address_2")        or "")
    city    = str(addr.get("city")             or "")
    state   = str(addr.get("state")            or "")
    zipcode = str(addr.get("postal_code")      or "")[:5]
    phone   = str(addr.get("telephone_number") or "")

    full_address = ", ".join(p for p in [addr1, addr2, city, state, zipcode] if p)
    all_tax = [
        {"code": str(t.get("code") or ""), "desc": str(t.get("desc") or "")}
        for t in taxonomies
    ]

    return {
        "npi":            str(result.get("number") or ""),
        "name":           name,
        "taxonomy_code":  str(primary_tax.get("code") or ""),
        "taxonomy_desc":  str(primary_tax.get("desc") or ""),
        "all_taxonomies": all_tax,
        "address":        full_address,
        "address_1":      addr1,
        "city":           city,
        "state":          state,
        "zip":            zipcode,
        "phone":          phone,
        "lat":            None,
        "lng":            None,
        "distance_miles": None,
    }


# ─────────────────────────────────────────────
#  GEOCODING
# ─────────────────────────────────────────────

def _geocode_address(addr1: str, city: str, state: str, zipcode: str) -> tuple[Optional[float], Optional[float]]:
    key = f"{addr1.lower().strip()},{city.lower().strip()},{state.upper().strip()},{zipcode[:5]}"
    cached = _addr_cache.get(key)
    if cached is not None:
        return cached

    if cfg.GEOAPIFY_API_KEY:
        query = ", ".join(p for p in [addr1, city, state, zipcode[:5], "US"] if p.strip())
        try:
            resp = _http.get(
                "https://api.geoapify.com/v1/geocode/search",
                params={"text": query, "limit": 1, "filter": "countrycode:us",
                        "apiKey": cfg.GEOAPIFY_API_KEY},
                timeout=cfg.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            features = resp.json().get("features", [])
            if features:
                coords = features[0]["geometry"]["coordinates"]
                result = (coords[1], coords[0])
                _addr_cache.set(key, result)
                return result
        except Exception as e:
            logger.debug("Addr geocode failed '%s': %s", query, e)

    fallback = get_zip_coords(zipcode)
    _addr_cache.set(key, fallback)
    return fallback


def _geocode_batch_for_display(physicians: list[dict]):
    import concurrent.futures

    def geocode_one(p: dict):
        if not p.get("address_1"):
            return
        lat, lng = _geocode_address(p["address_1"], p["city"], p["state"], p["zip"])
        if lat and lng:
            p["lat"] = lat
            p["lng"] = lng

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(geocode_one, physicians))


def _apply_coord_jitter(physicians: list[dict]):
    seen: dict[tuple, int] = {}
    for p in physicians:
        lat, lng = p.get("lat"), p.get("lng")
        if lat is None or lng is None:
            continue
        key = (round(lat, 6), round(lng, 6))
        count = seen.get(key, 0)
        if count > 0:
            angle  = (count * 137.5) % 360
            radius = 0.00008 * math.ceil(count / 4)
            p["lat"] = lat + radius * math.cos(math.radians(angle))
            p["lng"] = lng + radius * math.sin(math.radians(angle))
        seen[key] = count + 1


# ─────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({
        "status":       "ok",
        "zip_db_ready": _zip_db_ready.is_set(),
        "zip_db_count": len(_zip_db),
        "tax_loaded":   _taxonomy_loaded,
        "tax_count":    len(_taxonomy_entries),
        "tax_source":   _taxonomy_source,
    })


@app.route("/api/autocomplete")
@rate_limit(limit=cfg.RATE_LIMIT_AC)
def autocomplete():
    text  = (request.args.get("text") or "").strip()
    limit = min(int(request.args.get("limit", 6)), 10)
    if not text or len(text) < 2:
        return jsonify({"features": []})
    if not cfg.GEOAPIFY_API_KEY:
        return jsonify({"error": "Geocoding service not configured", "features": []}), 503
    try:
        resp = _http.get(
            "https://api.geoapify.com/v1/geocode/autocomplete",
            params={"text": text[:200], "limit": limit,
                    "filter": "countrycode:us", "bias": "countrycode:us",
                    "apiKey": cfg.GEOAPIFY_API_KEY},
            timeout=cfg.REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return jsonify(resp.json())
    except requests.Timeout:
        return jsonify({"error": "Geocoding service timed out", "features": []}), 504
    except Exception as e:
        logger.error("Autocomplete error: %s", e)
        return jsonify({"error": "Autocomplete unavailable", "features": []}), 502


@app.route("/api/geocode")
@rate_limit(limit=cfg.RATE_LIMIT_SEARCH)
def geocode():
    address = (request.args.get("address") or "").strip()
    if not address:
        return jsonify({"error": "Address is required"}), 400
    if not cfg.GEOAPIFY_API_KEY:
        return jsonify({"error": "Geocoding service not configured"}), 503
    try:
        resp = _http.get(
            "https://api.geoapify.com/v1/geocode/search",
            params={"text": address[:300], "limit": 1,
                    "filter": "countrycode:us", "apiKey": cfg.GEOAPIFY_API_KEY},
            timeout=cfg.REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        features = resp.json().get("features", [])
        if not features:
            return jsonify({"error": "Address not found in the US"}), 404
        coords = features[0]["geometry"]["coordinates"]
        props  = features[0].get("properties", {})
        return jsonify({
            "lat":       coords[1],
            "lng":       coords[0],
            "formatted": props.get("formatted", address),
            "city":      str(props.get("city") or props.get("county") or ""),
            "state":     str(props.get("state_code") or ""),
            "postcode":  str(props.get("postcode") or "")[:5],
        })
    except requests.Timeout:
        return jsonify({"error": "Geocoding service timed out"}), 504
    except Exception as e:
        logger.error("Geocode error: %s", e)
        return jsonify({"error": "Geocoding failed"}), 502


@app.route("/api/taxonomy-search")
@rate_limit(limit=cfg.RATE_LIMIT_AC)
def taxonomy_search_route():
    q = (request.args.get("q") or "").strip()[:100]
    results = _taxonomy_search(q, limit=12)
    return jsonify({"results": results, "loaded": _taxonomy_loaded, "source": _taxonomy_source})


@app.route("/api/taxonomy-status")
def taxonomy_status():
    return jsonify({
        "loaded":       _taxonomy_loaded,
        "count":        len(_taxonomy_entries),
        "source":       _taxonomy_source,
        "zip_db_count": len(_zip_db),
        "zip_db_ready": _zip_db_ready.is_set(),
    })


@app.route("/api/search")
@rate_limit(limit=cfg.RATE_LIMIT_SEARCH)
def search_physicians():
    # ── Validate inputs ──────────────────────────────────────
    try:
        lat, lng = _validate_lat_lng(
            request.args.get("lat"), request.args.get("lng")
        )
    except (TypeError, ValueError) as e:
        return jsonify({"error": f"Invalid coordinates: {e}"}), 400

    try:
        radius = _validate_radius(request.args.get("radius", 10))
    except (TypeError, ValueError) as e:
        return jsonify({"error": f"Invalid radius: {e}"}), 400

    taxonomy_code = (request.args.get("taxonomy_code") or "").strip()[:50]
    descriptions  = _validate_descriptions(
        request.args.get("descriptions", ""),
        request.args.get("description",  ""),
    )
    search_city   = (request.args.get("city",  "") or "").strip()[:80]
    search_state  = (request.args.get("state", "") or "").strip()[:2].upper()

    # Wait up to 3s for ZIP DB to be ready before proceeding
    if not _zip_db_ready.wait(timeout=3.0):
        logger.warning("ZIP DB not ready after 3s — proceeding with partial data")

    try:
        # ── Build taxonomy query sets ─────────────────────────
        tax_param_sets: list[dict] = []
        if taxonomy_code:
            tax_param_sets = [{"taxonomy_description": taxonomy_code}]
        elif descriptions:
            for desc in descriptions[:cfg.MAX_TAX_QUERIES]:
                matches = _taxonomy_search(desc, limit=1)
                best = matches[0]["display"] if matches else desc
                logger.info("Taxonomy resolved: '%s' → '%s'", desc, best)
                tax_param_sets.append({"taxonomy_description": best})
        else:
            tax_param_sets = [{}]

        logger.info("Running %d taxonomy queries for lat=%.4f lng=%.4f radius=%.0f",
                    len(tax_param_sets), lat, lng, radius)

        zips_in_radius = _find_zips_in_radius(lat, lng, radius)
        logger.info("ZIPs in radius: %d", len(zips_in_radius))

        seen_npis: set[str] = set()
        all_raw:  list[dict] = []

        def add(rows: list[dict]):
            for r in rows:
                npi = r.get("number")
                if npi and npi not in seen_npis:
                    seen_npis.add(npi)
                    all_raw.append(r)

        # ZIP-level queries (capped)
        for tax_params in tax_param_sets:
            for z in zips_in_radius[:cfg.MAX_ZIP_QUERIES]:
                rows, _ = _nppes_fetch_with_retry({"postal_code": z, **tax_params})
                add(rows)
            if search_city and search_state:
                rows, _ = _nppes_fetch_with_retry(
                    {"city": search_city.title(), "state": search_state, **tax_params}
                )
                add(rows)

        # State-level fallback only if nothing found
        if not all_raw and search_state:
            logger.info("No ZIP/city results — state fallback")
            for tax_params in tax_param_sets:
                rows, _ = _nppes_fetch_with_retry({"state": search_state, **tax_params})
                add(rows)

        logger.info("NPPES unique records: %d", len(all_raw))

        # ── Parse ────────────────────────────────────────────
        physicians: list[dict] = []
        for raw in all_raw:
            try:
                p = _parse_physician(raw)
                if p:
                    physicians.append(p)
            except Exception:
                logger.debug("Parse error: %s", traceback.format_exc())

        # ── Assign ZIP centroids ─────────────────────────────
        for p in physicians:
            if p.get("zip"):
                p["lat"], p["lng"] = get_zip_coords(p["zip"])

        # ── Filter to radius ─────────────────────────────────
        in_radius: list[dict] = []
        for p in physicians:
            if p.get("lat") and p.get("lng"):
                d = haversine(lat, lng, p["lat"], p["lng"])
                if d <= radius:
                    p["distance_miles"] = round(d, 1)
                    in_radius.append(p)

        in_radius.sort(key=lambda x: x.get("distance_miles", 9999))

        # Append providers with no coords at the end (no distance shown)
        for p in physicians:
            if not p.get("lat"):
                p["distance_miles"] = None
                in_radius.append(p)

        total = len(in_radius)
        shown = in_radius[:cfg.MAX_DISPLAY]

        # ── Precise geocoding for displayed results ───────────
        _geocode_batch_for_display(shown)
        _apply_coord_jitter(shown)

        logger.info("Returning %d of %d physicians", len(shown), total)
        return jsonify({"total": total, "returned": len(shown), "physicians": shown})

    except Exception:
        logger.error("Search error:\n%s", traceback.format_exc())
        return jsonify({"error": "An unexpected error occurred. Please try again."}), 500


@app.route("/api/leads", methods=["POST"])
@rate_limit(limit=cfg.RATE_LIMIT_LEAD)
def capture_lead():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    # Validate required fields
    for field in ("first_name", "last_name", "email"):
        if not (data.get(field) or "").strip():
            return jsonify({"error": f"'{field}' is required"}), 400

    email = (data.get("email") or "").strip().lower()
    if "@" not in email or len(email) > 254:
        return jsonify({"error": "A valid email address is required"}), 400

    lead = {
        "id":             f"lead_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
        "first_name":     str(data.get("first_name",  ""))[:80].strip(),
        "last_name":      str(data.get("last_name",   ""))[:80].strip(),
        "email":          email,
        "phone":          str(data.get("phone",       ""))[:30].strip(),
        "company":        str(data.get("company",     ""))[:120].strip(),
        "title":          str(data.get("title",       ""))[:80].strip(),
        "search_context": data.get("search_context") if isinstance(data.get("search_context"), dict) else {},
        "created_at":     datetime.utcnow().isoformat(),
        "source":         "PhysicianLocator",
        "status":         "New",
    }

    sf_ok   = _push_to_salesforce(lead)
    file_ok = _save_lead_to_file(lead)

    if not sf_ok and not file_ok:
        logger.error("Lead lost — both SF and file backup failed for %s", email)
        return jsonify({"error": "Could not save your request. Please try again."}), 500

    return jsonify({
        "success":  True,
        "lead_id":  lead["id"],
        "message":  "Thank you! Our team will contact you shortly.",
    })


# ─────────────────────────────────────────────
#  LEAD PERSISTENCE
# ─────────────────────────────────────────────

def _push_to_salesforce(lead: dict) -> bool:
    if not cfg.SF_OID:
        logger.warning("SF_OID not configured — skipping Salesforce push")
        return False
    try:
        payload = {
            "oid":         cfg.SF_OID,
            "retURL":      cfg.SF_RET_URL,
            "first_name":  lead["first_name"],
            "last_name":   lead["last_name"],
            "email":       lead["email"],
            "phone":       lead["phone"],
            "company":     lead["company"] or "Unknown",
            "lead_source": "Physician Locator",
        }
        if cfg.SF_DEBUG_EMAIL:
            payload.update({"debug": "1", "debugEmail": cfg.SF_DEBUG_EMAIL})
        resp = _http.post(
            "https://webto.salesforce.com/servlet/servlet.WebToLead?encoding=UTF-8",
            data=payload,
            timeout=cfg.REQUEST_TIMEOUT,
        )
        logger.info("SF Web-to-Lead status: %d | %s", resp.status_code, lead["email"])
        return resp.ok
    except Exception as e:
        logger.error("Salesforce push failed: %s", e)
        return False


def _save_lead_to_file(lead: dict) -> bool:
    """Append lead to NDJSON file (one JSON object per line — safer than rewriting full array)."""
    leads_file = "leads.ndjson"
    try:
        with open(leads_file, "a") as f:
            f.write(json.dumps(lead) + "\n")
        return True
    except Exception as e:
        logger.error("leads.ndjson write failed: %s", e)
        return False


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=cfg.PORT, debug=False)