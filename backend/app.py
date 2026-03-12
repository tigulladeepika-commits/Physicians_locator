"""
Physician Locator — Aquarient
Fixed version: uses ZIP→centroid lookup so every provider has coordinates,
no per-provider geocoding, US-only, dynamic taxonomy from NUCC CSV.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests, os, json, logging, traceback, csv, io, threading, math, zipfile, random
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ── CORS: allow requests from Vercel frontend ─────────────────────────────────
# Set FRONTEND_URL env var on Render to your Vercel deployment URL
# e.g.  FRONTEND_URL=https://physician-locator.vercel.app
FRONTEND_URL = os.environ.get("FRONTEND_URL", "*")
CORS(app, origins=[FRONTEND_URL] if FRONTEND_URL != "*" else "*",
     methods=["GET","POST","OPTIONS"],
     allow_headers=["Content-Type","Authorization"])

MAPQUEST_API_KEY = os.environ.get("MAPQUEST_API_KEY", "")
GEOAPIFY_API_KEY = os.environ.get("GEOAPIFY_API_KEY", "")
NPPES_BASE_URL   = "https://npiregistry.cms.hhs.gov/api/"
MAX_DISPLAY      = 10

logger.info(f"MapQuest: {'SET' if MAPQUEST_API_KEY else 'NOT SET'}")
logger.info(f"Geoapify: {'SET' if GEOAPIFY_API_KEY else 'NOT SET'}")


# ═══════════════════════════════════════════════════════════════════════════════
#  ZIP CODE → LAT/LNG CENTROID DATABASE
#  We use GeoNames US ZIP database — no API call needed per provider.
#  Every NPPES record includes a ZIP, so every provider gets coordinates.
# ═══════════════════════════════════════════════════════════════════════════════

_zip_db: dict = {}
_zip_db_ready = False
_zip_db_lock  = threading.Lock()

GEONAMES_ZIP_URL = "https://download.geonames.org/export/zip/US.zip"

def _load_zip_database():
    global _zip_db, _zip_db_ready
    local_cache = "us_zip_db.json"

    if os.path.exists(local_cache):
        try:
            with open(local_cache) as f:
                data = json.load(f)
            db = {k: (float(v[0]), float(v[1])) for k, v in data.items()}
            with _zip_db_lock:
                _zip_db.update(db)
                _zip_db_ready = True
            logger.info(f"ZIP db loaded from cache: {len(_zip_db)} entries")
            return
        except Exception as e:
            logger.warning(f"ZIP cache load failed: {e}")

    try:
        logger.info("Downloading GeoNames US ZIP database...")
        resp = requests.get(GEONAMES_ZIP_URL, timeout=60)
        resp.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        with zf.open("US.txt") as f:
            content = f.read().decode("utf-8", errors="replace")
        db = {}
        for line in content.splitlines():
            parts = line.split("\t")
            if len(parts) >= 11:
                zcode = parts[1].strip()
                try:
                    db[zcode] = (float(parts[9]), float(parts[10]))
                except (ValueError, IndexError):
                    pass
        with _zip_db_lock:
            _zip_db.update(db)
            _zip_db_ready = True
        try:
            with open(local_cache, "w") as f:
                json.dump({k: list(v) for k, v in db.items()}, f)
        except Exception:
            pass
        logger.info(f"ZIP db downloaded: {len(_zip_db)} entries")
    except Exception as e:
        logger.error(f"ZIP db download failed: {e} — loading fallback")
        _load_zip_fallback()


def _load_zip_fallback():
    global _zip_db, _zip_db_ready
    fallback = {
        "10001":(40.7506,-73.9971),"10007":(40.7135,-74.0078),"10016":(40.7459,-73.9813),
        "10021":(40.7691,-73.9596),"10036":(40.7590,-73.9893),"10065":(40.7649,-73.9623),
        "90001":(33.9736,-118.2489),"90024":(34.0620,-118.4432),"90210":(34.0901,-118.4065),
        "60601":(41.8859,-87.6181),"60611":(41.8966,-87.6207),"60614":(41.9229,-87.6484),
        "77001":(29.7544,-95.3677),"77030":(29.7079,-95.4010),"85001":(33.4472,-112.0740),
        "94102":(37.7793,-122.4192),"94103":(37.7726,-122.4099),"94109":(37.7956,-122.4213),
        "98101":(47.6089,-122.3352),"30301":(33.7627,-84.4229),"30309":(33.7919,-84.3843),
        "02101":(42.3598,-71.0547),"02111":(42.3551,-71.0614),"02114":(42.3617,-71.0654),
        "02115":(42.3437,-71.0992),"02116":(42.3473,-71.0824),"02215":(42.3468,-71.1009),
        "19101":(39.9528,-75.1635),"19103":(39.9527,-75.1797),"20001":(38.9123,-77.0177),
        "20005":(38.9019,-77.0312),"33101":(25.7959,-80.2870),"33130":(25.7650,-80.2025),
        "75201":(32.7884,-96.7989),"75204":(32.8009,-96.7876),"48201":(42.3533,-83.0524),
        "80201":(39.7392,-104.9903),"80203":(39.7288,-104.9774),"97201":(45.5169,-122.6809),
        "89101":(36.1756,-115.1391),"92101":(32.7264,-117.1552),"28201":(35.2271,-80.8431),
    }
    with _zip_db_lock:
        _zip_db.update(fallback)
        _zip_db_ready = True
    logger.info(f"ZIP fallback loaded: {len(_zip_db)} entries")


def get_zip_coords(zipcode: str):
    z = str(zipcode or "")[:5].strip()
    with _zip_db_lock:
        v = _zip_db.get(z)
    if v:
        return float(v[0]), float(v[1])
    return None, None


threading.Thread(target=_load_zip_database, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════════════════
#  HAVERSINE
# ═══════════════════════════════════════════════════════════════════════════════

def haversine(lat1, lon1, lat2, lon2) -> float:
    R = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1; dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))


# ═══════════════════════════════════════════════════════════════════════════════
#  DYNAMIC NUCC TAXONOMY
# ═══════════════════════════════════════════════════════════════════════════════

NUCC_CSV_URL = "https://www.nucc.org/images/stories/CSV/nucc_taxonomy_250.csv"

_taxonomy_entries: list = []
_taxonomy_loaded        = False
_taxonomy_source        = "none"
_taxonomy_lock          = threading.Lock()

_SEED_TAXONOMY = [
    ("Allopathic & Osteopathic Physicians","Addiction Medicine"),
    ("Allopathic & Osteopathic Physicians","Allergy & Immunology"),
    ("Allopathic & Osteopathic Physicians","Anesthesiology"),
    ("Allopathic & Osteopathic Physicians","Cardiac Surgery"),
    ("Allopathic & Osteopathic Physicians","Cardiovascular Disease"),
    ("Allopathic & Osteopathic Physicians","Colon & Rectal Surgery"),
    ("Allopathic & Osteopathic Physicians","Dermatology"),
    ("Allopathic & Osteopathic Physicians","Diagnostic Radiology"),
    ("Allopathic & Osteopathic Physicians","Emergency Medicine"),
    ("Allopathic & Osteopathic Physicians","Endocrinology, Diabetes & Metabolism"),
    ("Allopathic & Osteopathic Physicians","Family Medicine"),
    ("Allopathic & Osteopathic Physicians","Gastroenterology"),
    ("Allopathic & Osteopathic Physicians","General Practice"),
    ("Allopathic & Osteopathic Physicians","General Surgery"),
    ("Allopathic & Osteopathic Physicians","Geriatric Medicine"),
    ("Allopathic & Osteopathic Physicians","Hematology & Oncology"),
    ("Allopathic & Osteopathic Physicians","Infectious Disease"),
    ("Allopathic & Osteopathic Physicians","Internal Medicine"),
    ("Allopathic & Osteopathic Physicians","Interventional Cardiology"),
    ("Allopathic & Osteopathic Physicians","Medical Oncology"),
    ("Allopathic & Osteopathic Physicians","Nephrology"),
    ("Allopathic & Osteopathic Physicians","Neurology"),
    ("Allopathic & Osteopathic Physicians","Neurosurgery"),
    ("Allopathic & Osteopathic Physicians","Obstetrics & Gynecology"),
    ("Allopathic & Osteopathic Physicians","Ophthalmology"),
    ("Allopathic & Osteopathic Physicians","Orthopaedic Surgery"),
    ("Allopathic & Osteopathic Physicians","Pain Medicine"),
    ("Allopathic & Osteopathic Physicians","Pediatrics"),
    ("Allopathic & Osteopathic Physicians","Physical Medicine & Rehabilitation"),
    ("Allopathic & Osteopathic Physicians","Plastic Surgery"),
    ("Allopathic & Osteopathic Physicians","Psychiatry"),
    ("Allopathic & Osteopathic Physicians","Pulmonary Disease"),
    ("Allopathic & Osteopathic Physicians","Radiation Oncology"),
    ("Allopathic & Osteopathic Physicians","Rheumatology"),
    ("Allopathic & Osteopathic Physicians","Sleep Medicine"),
    ("Allopathic & Osteopathic Physicians","Sports Medicine"),
    ("Allopathic & Osteopathic Physicians","Thoracic Surgery"),
    ("Allopathic & Osteopathic Physicians","Urology"),
    ("Allopathic & Osteopathic Physicians","Vascular Surgery"),
    ("Dental Providers","Dentist"),
    ("Dental Providers","Dental Hygienist"),
    ("Dental Providers","Endodontics"),
    ("Dental Providers","Oral and Maxillofacial Surgery"),
    ("Dental Providers","Orthodontics and Dentofacial Orthopedics"),
    ("Dental Providers","Pediatric Dentistry"),
    ("Dental Providers","Periodontics"),
    ("Dental Providers","Prosthodontics"),
    ("Podiatric Medicine & Surgery Providers","Podiatrist"),
    ("Pharmacy Service Providers","Pharmacist"),
    ("Pharmacy Service Providers","Clinical Pharmacy Specialist"),
    ("Nursing Service Providers","Certified Nurse Midwife"),
    ("Nursing Service Providers","Certified Registered Nurse Anesthetist"),
    ("Nursing Service Providers","Clinical Nurse Specialist"),
    ("Nursing Service Providers","Licensed Practical Nurse"),
    ("Nursing Service Providers","Nurse Practitioner"),
    ("Nursing Service Providers","Registered Nurse"),
    ("Physician Assistants & Advanced Practice Nursing Providers","Physician Assistant"),
    ("Eye and Vision Services Providers","Optometrist"),
    ("Chiropractic Providers","Chiropractor"),
    ("Physical Medicine & Rehabilitation Providers","Physical Therapist"),
    ("Physical Medicine & Rehabilitation Providers","Occupational Therapist"),
    ("Respiratory, Developmental, Rehabilitative & Restorative Service Providers","Respiratory Therapist"),
    ("Speech, Language and Hearing Service Providers","Audiologist"),
    ("Speech, Language and Hearing Service Providers","Speech-Language Pathologist"),
    ("Behavioral Health & Social Service Providers","Counselor"),
    ("Behavioral Health & Social Service Providers","Marriage & Family Therapist"),
    ("Behavioral Health & Social Service Providers","Psychologist"),
    ("Behavioral Health & Social Service Providers","Social Worker"),
    ("Behavioral Health & Social Service Providers","Social Worker, Clinical"),
    ("Dietetic & Nutritional Service Providers","Dietitian, Registered"),
    ("Emergency Medical Service Providers","Emergency Medical Technician"),
    ("Emergency Medical Service Providers","Paramedic"),
    ("Ambulatory Health Care Facilities","Ambulatory Surgical"),
    ("Ambulatory Health Care Facilities","Urgent Care"),
    ("Hospital","General Acute Care Hospital"),
]


def _build_entries(rows):
    out = []
    for classification, specialization in rows:
        c = (classification or "").strip()
        s = (specialization or "").strip()
        if not c:
            continue
        display = s if s else c
        out.append({
            "classification": c,
            "specialization": s,
            "display":        display,
            "search_text":    f"{c} {s}".lower(),
        })
    return out


def _load_taxonomy_background():
    global _taxonomy_entries, _taxonomy_loaded, _taxonomy_source
    seed = _build_entries(_SEED_TAXONOMY)
    with _taxonomy_lock:
        _taxonomy_entries = seed
        _taxonomy_loaded  = True
        _taxonomy_source  = "seed"
    logger.info(f"Taxonomy seed ready: {len(seed)} entries")
    try:
        resp = requests.get(NUCC_CSV_URL, timeout=15)
        resp.raise_for_status()
        reader = csv.DictReader(io.StringIO(resp.text))
        rows = [(r.get("Classification","").strip(), r.get("Specialization","").strip())
                for r in reader if r.get("Classification","").strip()]
        if rows:
            live = _build_entries(rows)
            with _taxonomy_lock:
                _taxonomy_entries = live
                _taxonomy_source  = "NUCC CSV"
            logger.info(f"NUCC CSV loaded: {len(live)} entries")
    except Exception as e:
        logger.warning(f"NUCC CSV failed: {e} — keeping seed")


threading.Thread(target=_load_taxonomy_background, daemon=True).start()


def _taxonomy_search(q: str, limit: int = 12) -> list:
    q = q.lower().strip()
    if not q:
        return []
    q_words = [w for w in q.split() if len(w) >= 2]
    with _taxonomy_lock:
        entries = list(_taxonomy_entries)
    scored, seen = [], set()
    for e in entries:
        st = e["search_text"]
        d  = e["display"]
        score = 0
        if q == e["specialization"].lower():              score = 100
        elif e["specialization"].lower().startswith(q):  score = 85
        elif e["classification"].lower().startswith(q):  score = 75
        elif q in st:                                     score = 60
        elif all(w in st for w in q_words):              score = 50
        elif any(w in st for w in q_words):              score = 30
        if score > 0 and d not in seen:
            seen.add(d)
            scored.append((score, d, e["classification"]))
    results = []
    for _, display, classification in sorted(scored, key=lambda x: (-x[0], x[1]))[:limit]:
        results.append({"display": display, "classification": classification})
    return results


# ═══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/autocomplete")
def autocomplete():
    text  = request.args.get("text", "").strip()
    limit = request.args.get("limit", 6)
    if not text or len(text) < 2:
        return jsonify({"features": []})
    if not GEOAPIFY_API_KEY:
        return jsonify({"error": "Geoapify key not configured", "features": []}), 500
    try:
        resp = requests.get(
            "https://api.geoapify.com/v1/geocode/autocomplete",
            params={"text": text, "limit": limit,
                    "filter": "countrycode:us", "bias": "countrycode:us",
                    "apiKey": GEOAPIFY_API_KEY},
            timeout=6)
        resp.raise_for_status()
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e), "features": []}), 500


@app.route("/api/geocode")
def geocode():
    address = request.args.get("address", "").strip()
    if not address:
        return jsonify({"error": "Address required"}), 400
    if not GEOAPIFY_API_KEY:
        return jsonify({"error": "Geoapify key not configured"}), 500
    try:
        resp = requests.get(
            "https://api.geoapify.com/v1/geocode/search",
            params={"text": address, "limit": 1, "filter": "countrycode:us",
                    "apiKey": GEOAPIFY_API_KEY},
            timeout=8)
        resp.raise_for_status()
        features = resp.json().get("features", [])
        if not features:
            return jsonify({"error": "Address not found in US"}), 404
        coords = features[0]["geometry"]["coordinates"]
        props  = features[0].get("properties", {})
        return jsonify({
            "lat": coords[1], "lng": coords[0],
            "formatted": props.get("formatted", address),
            "city":     str(props.get("city") or props.get("county") or ""),
            "state":    str(props.get("state_code") or ""),
            "postcode": str(props.get("postcode") or "")[:5],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/taxonomy-search")
def taxonomy_search_route():
    q = request.args.get("q", "").strip()
    results = _taxonomy_search(q, limit=12)
    return jsonify({"results": results, "loaded": _taxonomy_loaded, "source": _taxonomy_source})


@app.route("/api/taxonomy-status")
def taxonomy_status():
    return jsonify({
        "loaded":        _taxonomy_loaded,
        "count":         len(_taxonomy_entries),
        "source":        _taxonomy_source,
        "zip_db_count":  len(_zip_db),
        "zip_db_ready":  _zip_db_ready,
    })


@app.route("/api/search")
def search_physicians():
    """
    Architecture:
    1. Geocode the search address → center lat/lng (one Geoapify call, done in frontend)
    2. Find all ZIPs within radius using local ZIP centroid DB (no API, instant)
    3. Query NPPES by ZIP + taxonomy_description (exact NUCC term)
    4. Assign coords to each provider from ZIP centroid DB (no per-provider API call)
    5. Haversine-filter and sort by distance
    """
    lat           = request.args.get("lat",         type=float)
    lng           = request.args.get("lng",         type=float)
    radius        = request.args.get("radius", 10,  type=float)
    taxonomy_code = request.args.get("taxonomy_code", "").strip()
    # Accept either a single 'description' param (legacy) or 'descriptions' JSON array (new)
    descriptions_raw = request.args.get("descriptions", "")
    description_single = request.args.get("description", "").strip()
    search_city   = request.args.get("city",   "").strip()
    search_state  = request.args.get("state",  "").strip()

    if lat is None or lng is None:
        return jsonify({"error": "lat and lng are required"}), 400

    # Parse descriptions list
    descriptions: list = []
    if descriptions_raw:
        try:
            parsed = json.loads(descriptions_raw)
            descriptions = [str(d).strip() for d in parsed if str(d).strip()]
        except Exception:
            descriptions = [descriptions_raw.strip()] if descriptions_raw.strip() else []
    elif description_single:
        descriptions = [description_single]

    try:
        # ── Build taxonomy filter params for each description ─────────────
        # Each description is resolved to the best NUCC match, then queried
        # separately in NPPES so results are merged (OR logic across conditions).
        tax_param_sets = []
        if taxonomy_code:
            tax_param_sets = [{"taxonomy_description": taxonomy_code}]
        elif descriptions:
            for desc in descriptions:
                matches = _taxonomy_search(desc, limit=1)
                best = matches[0]["display"] if matches else desc
                logger.info(f"Taxonomy resolved: '{desc}' → '{best}'")
                tax_param_sets.append({"taxonomy_description": best})
        else:
            tax_param_sets = [{}]  # no taxonomy filter — search all

        logger.info(f"Running {len(tax_param_sets)} taxonomy queries: {[t.get('taxonomy_description','all') for t in tax_param_sets]}")

        # Find ZIPs in radius using local DB (fast, no API)
        zips_in_radius = _find_zips_in_radius(lat, lng, radius)
        logger.info(f"ZIPs in {radius}mi radius: {len(zips_in_radius)}")

        # Fetch from NPPES — run each taxonomy param set, merge all results
        seen_npis, all_raw = set(), []

        def add(rows):
            for r in rows:
                npi = r.get("number")
                if npi and npi not in seen_npis:
                    seen_npis.add(npi)
                    all_raw.append(r)

        for tax_params in tax_param_sets:
            # Primary: query by ZIP
            for z in zips_in_radius[:30]:
                rows, _ = _nppes_fetch({"postal_code": z, **tax_params})
                add(rows)

            # Secondary: city+state
            if search_city and search_state:
                rows, _ = _nppes_fetch({"city": search_city.title(),
                                        "state": search_state.upper(), **tax_params})
                add(rows)

        # Fallback: state-wide if nothing found at all
        if not all_raw and search_state:
            logger.info("No ZIP/city results — trying state fallback")
            for tax_params in tax_param_sets:
                rows, _ = _nppes_fetch({"state": search_state.upper(), **tax_params})
                add(rows)

        logger.info(f"NPPES unique records: {len(all_raw)}")

        # Parse all records
        physicians = []
        for raw in all_raw:
            try:
                p = _parse_physician(raw)
                if p:
                    physicians.append(p)
            except Exception as pe:
                logger.debug(f"Parse error: {pe}")

        # ── Coordinate assignment strategy ────────────────────────────────
        # Priority 1: Geocode the full street address (cached — same address = one API call)
        # Priority 2: ZIP centroid + small random jitter so markers spread out
        #
        # We geocode only the first MAX_DISPLAY providers to stay within rate limits,
        # since only those will be shown on the map anyway.
        # The remaining providers still get ZIP centroids for radius filtering.

        # Step A: assign ZIP centroids to ALL providers first (for radius filter)
        for p in physicians:
            if p.get("zip"):
                p["lat"], p["lng"] = get_zip_coords(p["zip"])

        # Step B: radius filter using ZIP centroids
        in_radius = []
        for p in physicians:
            if p.get("lat") and p.get("lng"):
                d = haversine(lat, lng, p["lat"], p["lng"])
                if d <= radius:
                    p["distance_miles"] = round(d, 1)
                    in_radius.append(p)

        in_radius.sort(key=lambda x: x.get("distance_miles", 9999))

        # Include providers without coords at the end
        no_coords = [p for p in physicians if not p.get("lat")]
        for p in no_coords[:5]:
            p["distance_miles"] = None
            in_radius.append(p)

        total = len(in_radius)
        shown = in_radius[:MAX_DISPLAY]

        # Step C: geocode the displayed providers' FULL STREET ADDRESS
        # This gives precise per-building coords instead of ZIP centroid.
        # Uses a cache so repeated addresses don't burn API quota.
        _geocode_batch_for_display(shown)

        # Step D: apply tiny jitter to any providers that still share
        # the exact same coordinates (e.g. multiple doctors at same building).
        _apply_coord_jitter(shown)

        logger.info(f"Returning {len(shown)} of {total} physicians")
        return jsonify({"total": total, "returned": len(shown), "physicians": shown})

    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route("/api/leads", methods=["POST"])
def capture_lead():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    for field in ["first_name", "last_name", "email"]:
        if not data.get(field):
            return jsonify({"error": f"'{field}' is required"}), 400
    lead = {
        "id":             f"lead_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
        "first_name":     data.get("first_name", ""),
        "last_name":      data.get("last_name",  ""),
        "email":          data.get("email",       ""),
        "phone":          data.get("phone",       ""),
        "company":        data.get("company",     ""),
        "title":          data.get("title",       ""),
        "search_context": data.get("search_context", {}),
        "created_at":     datetime.utcnow().isoformat(),
        "source":         "PhysicianLocator",
        "status":         "New",
        "salesforce_id":  None,
        "synced_to_sf":   False,
    }
    _save_lead(lead)
    return jsonify({"success": True, "lead_id": lead["id"],
                    "message": "Thank you! Our team will contact you shortly."})


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _find_zips_in_radius(center_lat, center_lng, radius_miles):
    """Pure-Python scan of ZIP centroid DB — no API call."""
    deg_lat = radius_miles / 69.0
    deg_lng = radius_miles / (69.0 * math.cos(math.radians(center_lat)) + 1e-6)
    min_lat, max_lat = center_lat - deg_lat, center_lat + deg_lat
    min_lng, max_lng = center_lng - deg_lng, center_lng + deg_lng

    result = []
    with _zip_db_lock:
        for z, (zlat, zlng) in _zip_db.items():
            if min_lat <= zlat <= max_lat and min_lng <= zlng <= max_lng:
                d = haversine(center_lat, center_lng, zlat, zlng)
                if d <= radius_miles:
                    result.append((d, z))
    result.sort()
    return [z for _, z in result]


def _nppes_fetch(params: dict) -> tuple:
    clean = {k: str(v).strip() for k, v in params.items() if v and str(v).strip()}
    query = {"version": "2.1", "enumeration_type": "NPI-1",
             "limit": 200, "skip": 0, "country_code": "US", **clean}
    logger.debug(f"NPPES: {clean}")
    try:
        resp = requests.get(NPPES_BASE_URL, params=query, timeout=20)
        resp.raise_for_status()
        d = resp.json()
        rows  = d.get("results") or []
        total = int(d.get("result_count") or 0)
        logger.debug(f"NPPES returned {len(rows)} rows (total={total})")
        return rows, total
    except Exception as e:
        logger.warning(f"NPPES fetch failed: {e} | params={clean}")
        return [], 0


def _parse_physician(result: dict):
    basic      = result.get("basic", {})
    addresses  = result.get("addresses",  [])
    taxonomies = result.get("taxonomies", [])
    addr = next((a for a in addresses if a.get("address_purpose") == "LOCATION"),
                addresses[0] if addresses else {})
    primary_tax = next((t for t in taxonomies if t.get("primary")),
                       taxonomies[0] if taxonomies else {})

    first  = str(basic.get("first_name") or "")
    last   = str(basic.get("last_name")  or "")
    cred   = str(basic.get("credential") or "")
    name   = f"{first} {last}".strip() or "Unknown Provider"
    if cred: name += f", {cred}"

    addr1    = str(addr.get("address_1")        or "")
    addr2    = str(addr.get("address_2")        or "")
    city     = str(addr.get("city")             or "")
    state    = str(addr.get("state")            or "")
    zipcode  = str(addr.get("postal_code")      or "")[:5]
    phone    = str(addr.get("telephone_number") or "")

    full_address = ", ".join(p for p in [addr1, addr2, city, state, zipcode] if p)

    all_tax = [{"code": str(t.get("code") or ""), "desc": str(t.get("desc") or "")}
               for t in taxonomies]

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


# ── Address-level geocode cache ───────────────────────────────────────────────
# Key: normalised address string  →  Value: (lat, lng)
_addr_geocode_cache: dict = {}
_addr_cache_lock = threading.Lock()


def _geocode_address_cached(addr1: str, city: str, state: str, zipcode: str) -> tuple:
    """
    Geocode a full street address via Geoapify, with in-memory caching.
    Returns (lat, lng) or (None, None) on failure.
    Falls back to ZIP centroid if geocoding fails.
    """
    if not GEOAPIFY_API_KEY:
        return get_zip_coords(zipcode)

    # Build a canonical cache key from the address components
    key = f"{addr1.lower().strip()},{city.lower().strip()},{state.upper().strip()},{zipcode[:5]}"
    with _addr_cache_lock:
        if key in _addr_geocode_cache:
            return _addr_geocode_cache[key]

    # Build query string — use full address for best accuracy
    query = ", ".join(p for p in [addr1, city, state, zipcode[:5], "US"] if p.strip())
    try:
        resp = requests.get(
            "https://api.geoapify.com/v1/geocode/search",
            params={"text": query, "limit": 1, "filter": "countrycode:us",
                    "apiKey": GEOAPIFY_API_KEY},
            timeout=5)
        resp.raise_for_status()
        features = resp.json().get("features", [])
        if features:
            coords = features[0]["geometry"]["coordinates"]
            result = (coords[1], coords[0])  # (lat, lng)
            with _addr_cache_lock:
                _addr_geocode_cache[key] = result
            return result
    except Exception as e:
        logger.debug(f"Addr geocode failed '{query}': {e}")

    # Fallback to ZIP centroid
    fallback = get_zip_coords(zipcode)
    with _addr_cache_lock:
        _addr_geocode_cache[key] = fallback
    return fallback


def _geocode_batch_for_display(physicians: list):
    """
    Geocode the full street address for each displayed physician IN PARALLEL
    using threads. Updates lat/lng in-place on each dict.
    Only geocodes providers whose coords are currently a ZIP centroid
    (i.e. they may share coords with others in the same ZIP).
    """
    import concurrent.futures

    def geocode_one(p):
        addr1   = p.get("address_1", "")
        city    = p.get("city", "")
        state   = p.get("state", "")
        zipcode = p.get("zip", "")
        if not addr1:
            return  # No street — keep ZIP centroid
        lat, lng = _geocode_address_cached(addr1, city, state, zipcode)
        if lat and lng:
            p["lat"] = lat
            p["lng"] = lng

    # Run up to 10 geocode calls in parallel (max_display = 10)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(geocode_one, physicians))


def _apply_coord_jitter(physicians: list):
    """
    If two or more physicians share the exact same (lat, lng) — e.g. they are
    all at the same building — apply a tiny random offset so their markers
    don't overlap perfectly on the map.
    Jitter radius: ~10 metres (0.0001 degrees ≈ 11m).
    """
    import random
    seen: dict = {}  # (lat, lng) → count
    for p in physicians:
        lat = p.get("lat")
        lng = p.get("lng")
        if lat is None or lng is None:
            continue
        key = (round(lat, 6), round(lng, 6))
        if key in seen:
            # Apply jitter proportional to how many share this spot
            count = seen[key]
            angle  = (count * 137.5) % 360  # golden angle spread
            radius = 0.00008 * math.ceil(count / 4)  # ~9m per ring
            p["lat"] = lat + radius * math.cos(math.radians(angle))
            p["lng"] = lng + radius * math.sin(math.radians(angle))
            seen[key] += 1
        else:
            seen[key] = 1


def _save_lead(lead: dict):
    """
    ── SALESFORCE INTEGRATION POINT ──────────────────────────────────────────
    Replace the JSON write below with:

        sf_url = "https://<instance>.salesforce.com/services/data/v57.0/sobjects/Lead/"
        headers = {"Authorization": f"Bearer {SF_ACCESS_TOKEN}", "Content-Type": "application/json"}
        payload = {
            "FirstName": lead["first_name"], "LastName": lead["last_name"],
            "Email": lead["email"], "Company": lead.get("company") or "Not Provided",
            "Phone": lead.get("phone",""), "Title": lead.get("title",""),
            "LeadSource": "PhysicianLocator",
            "Description": str(lead.get("search_context", {})),
        }
        requests.post(sf_url, json=payload, headers=headers, timeout=10)
    ──────────────────────────────────────────────────────────────────────────
    """
    leads_file = "leads.json"
    leads = []
    if os.path.exists(leads_file):
        try:
            with open(leads_file) as f: leads = json.load(f)
        except Exception: leads = []
    leads.append(lead)
    with open(leads_file, "w") as f:
        json.dump(leads, f, indent=2)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)