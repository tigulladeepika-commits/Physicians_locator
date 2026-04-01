"""
ZIP code database service.
Manages loading and querying US ZIP code coordinates.
"""

import io
import json
import logging
import math
import os
import threading
import zipfile
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from services.http_client import http_client

GEONAMES_ZIP_URL = "https://download.geonames.org/export/zip/US.zip"

# Global state
_zip_db: Dict[str, Tuple[float, float]] = {}
_zip_db_ready = threading.Event()
_zip_db_lock = threading.Lock()
_zip_index: Dict[Tuple[int, int], List] = {}
_zip_index_lock = threading.Lock()

_ZIP_FALLBACK: Dict[str, Tuple[float, float]] = {
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


def _build_spatial_index(db: Dict) -> None:
    """Build spatial index for efficient ZIP code lookup."""
    idx: Dict = {}
    for z, (lat, lng) in db.items():
        cell = (int(math.floor(lat)), int(math.floor(lng)))
        idx.setdefault(cell, []).append((lat, lng, z))
    with _zip_index_lock:
        _zip_index.clear()
        _zip_index.update(idx)
    logger.info("Spatial index built: %d cells", len(_zip_index))


def _load_zip_database() -> None:
    """Load ZIP database from cache or download from GeoNames."""
    local_cache = "us_zip_db.json"

    def _apply(db: Dict) -> None:
        with _zip_db_lock:
            _zip_db.clear()
            _zip_db.update(db)
        _build_spatial_index(db)
        _zip_db_ready.set()
        logger.info("ZIP db ready: %d entries", len(_zip_db))

    # Try loading from disk cache first
    if os.path.exists(local_cache):
        try:
            with open(local_cache) as f:
                raw = json.load(f)
            _apply({k: (float(v[0]), float(v[1])) for k, v in raw.items()})
            logger.info("ZIP db loaded from disk cache")
            return
        except Exception as e:
            logger.warning("ZIP disk cache corrupt, re-downloading: %s", e)

    # Download from GeoNames
    try:
        logger.info("Downloading GeoNames US ZIP database...")
        resp = http_client.get(GEONAMES_ZIP_URL, timeout=90)
        resp.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        with zf.open("US.txt") as f:
            content = f.read().decode("utf-8", errors="replace")
        
        db: Dict = {}
        for line in content.splitlines():
            parts = line.split("\t")
            if len(parts) >= 11:
                try:
                    db[parts[1].strip()] = (float(parts[9]), float(parts[10]))
                except (ValueError, IndexError):
                    pass
        
        # Save to disk
        tmp = local_cache + ".tmp"
        with open(tmp, "w") as f:
            json.dump({k: list(v) for k, v in db.items()}, f)
        os.replace(tmp, local_cache)
        _apply(db)
    except Exception as e:
        logger.error("ZIP db download failed: %s — using fallback", e)
        _apply(_ZIP_FALLBACK)


def initialize() -> None:
    """Start background thread to load ZIP database."""
    threading.Thread(target=_load_zip_database, daemon=False, name="zip-loader").start()


def get_zip_coords(zipcode: str) -> Tuple[Optional[float], Optional[float]]:
    """Get latitude and longitude for a ZIP code."""
    z = str(zipcode or "")[:5].strip()
    with _zip_db_lock:
        v = _zip_db.get(z)
    return (float(v[0]), float(v[1])) if v else (None, None)


def is_ready() -> bool:
    """Check if ZIP database is loaded and ready."""
    return _zip_db_ready.is_set()


def wait_for_ready(timeout: Optional[float] = None) -> bool:
    """Wait for ZIP database to be ready."""
    return _zip_db_ready.wait(timeout=timeout)


def count() -> int:
    """Get number of ZIP codes in database."""
    with _zip_db_lock:
        return len(_zip_db)


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in miles using Haversine formula."""
    R = 3958.8  # Earth radius in miles
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2 + 
        math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(a))


def find_zips_in_radius(
    center_lat: float, 
    center_lng: float, 
    radius_miles: float
) -> List[str]:
    """Find all ZIP codes within radius of center point."""
    deg_lat = radius_miles / 69.0
    deg_lng = radius_miles / (69.0 * math.cos(math.radians(center_lat)) + 1e-9)

    cell_lat_min = int(math.floor(center_lat - deg_lat))
    cell_lat_max = int(math.floor(center_lat + deg_lat))
    cell_lng_min = int(math.floor(center_lng - deg_lng))
    cell_lng_max = int(math.floor(center_lng + deg_lng))

    result: List[Tuple[float, str]] = []
    with _zip_index_lock:
        for clat in range(cell_lat_min, cell_lat_max + 1):
            for clng in range(cell_lng_min, cell_lng_max + 1):
                for (zlat, zlng, z) in _zip_index.get((clat, clng), []):
                    d = haversine(center_lat, center_lng, zlat, zlng)
                    if d <= radius_miles:
                        result.append((d, z))

    if not result and not _zip_index:
        with _zip_db_lock:
            for z, (zlat, zlng) in _zip_db.items():
                d = haversine(center_lat, center_lng, zlat, zlng)
                if d <= radius_miles:
                    result.append((d, z))

    result.sort()
    return [z for _, z in result]
