# 🩺 Physician Locator — Aquarient

A professional, scalable Flask web application for locating physicians using the NPPES NPI Registry, with map integration, address autocomplete, and lead capture.

> **📋 NOTE**: This project has been **restructured into a professional architecture**. See [RESTRUCTURING_SUMMARY.md](RESTRUCTURING_SUMMARY.md) for what changed.
> 
> **Quick Links**:
> - [Project Structure Overview](PROJECT_STRUCTURE.md)  
> - [Backend Details](backend/README.md)
> - [Frontend Details](frontend/README.md)
> - [Setup Guide](SETUP_GUIDE.md)

---

## Features

- **Address Autocomplete** — Geoapify-powered suggestions as you type
- **Physician Search** — Queries the NPPES NPI Registry (free, no key required)
- **MapQuest Map** — Numbered markers for each physician result
- **Result Limiting** — Shows first 10 results; prompts lead capture for more
- **Lead Capture Modal** — Collects contact info for users wanting full access
- **Salesforce-Ready** — `salesforce.py` stub ready for activation

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python / Flask |
| Physician Data | NPPES NPI Registry API |
| Map | MapQuest JS SDK |
| Geocoding / Autocomplete | Geoapify |
| Lead Storage | JSON file (→ Salesforce) |
| Future CRM | Salesforce Lead API |

---

## Quick Start

### 1. Clone & Install

```bash
cd physician-locator
pip install -r requirements.txt
```

### 2. Configure API Keys

```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

**API Keys needed:**
- **MapQuest**: https://developer.mapquest.com/ (free tier available)
- **Geoapify**: https://www.geoapify.com/ (free: 3,000 req/day)
- **NPPES**: No key required (public API)

### 3. Run

```bash
python app.py
# Visit http://localhost:5000
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Main application |
| GET | `/api/autocomplete?text=...` | Address suggestions |
| GET | `/api/geocode?address=...` | Convert address to lat/lng |
| GET | `/api/search?lat=&lng=&radius=&...` | Search NPPES physicians |
| POST | `/api/leads` | Capture lead (→ Salesforce) |

### Search Parameters

| Param | Type | Description |
|---|---|---|
| `lat` | float | Search center latitude |
| `lng` | float | Search center longitude |
| `radius` | int | Radius in miles (5/10/25/50/100) |
| `taxonomy_code` | string | NPI taxonomy code (optional) |
| `description` | string | Taxonomy description (optional) |

---

## Salesforce Integration

When ready to activate:

1. Install the Salesforce library:
   ```bash
   pip install simple-salesforce
   ```

2. Fill in Salesforce credentials in `.env`

3. Open `salesforce.py` and uncomment the implementation

4. In `app.py`, update `_save_lead()` to call `salesforce_create_lead(lead)` from `salesforce.py`

---

## Project Structure

```
physician-locator/
├── app.py              # Flask application + API routes
├── salesforce.py       # Salesforce integration stub
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
├── leads.json          # Lead storage (auto-created, replace with DB/SF)
└── templates/
    └── index.html      # Full frontend (HTML + CSS + JS)
```

---

## Notes on NPPES API

The NPPES NPI Registry is a free public API with no authentication required:
- Endpoint: `https://npiregistry.cms.hhs.gov/api/`
- Max 200 results per request
- Does **not** return lat/lng coordinates — addresses must be geocoded
- Rate limits apply; for production, add caching

For production use, consider:
- Caching NPPES results (Redis)
- Batch geocoding physician addresses
- A ZIP code → coordinates database for faster filtering

---

## License

Proprietary — Aquarient © 2024