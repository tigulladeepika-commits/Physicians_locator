# Technical Specification: Physician Locator — Aquarient

**Version**: 2.0  
**Date**: March 25, 2026  
**Status**: Production  
**Owner**: Aquarient Engineering  

---

## 1. Executive Summary

This document outlines the technical architecture, design decisions, implementation details, and infrastructure for the Physician Locator platform. It serves as a reference for developers, DevOps engineers, and architects involved in building, deploying, and maintaining the system.

**Key Technical Decisions**:
- Single-page application (SPA) with vanilla JavaScript (no framework overhead)
- Python Flask backend with synchronous request handling
- Stateless microservice architecture (Render + Vercel deployment)
- In-memory caching for geographic and taxonomy data
- RESTful API with rate limiting and structured logging

---

## 2. System Architecture Overview

### 2.1 High-Level Architecture Diagram

```
                    ┌─────────────────────────────────────┐
                    │        End User Browser              │
                    │  (Desktop, Tablet, Mobile)          │
                    └────────────┬────────────────────────┘
                                 │ HTTPS
                    ┌────────────▼────────────────────────┐
                    │  Frontend (Vercel CDN)              │
                    │  ├─ index.html (gzip: 45KB)         │
                    │  ├─ Embedded CSS (120KB)            │
                    │  ├─ Embedded JS (380KB)             │
                    │  └─ Static Assets (CSS, JS)         │
                    └────────────┬────────────────────────┘
                                 │ REST/CORS
                    ┌────────────▼────────────────────────┐
                    │  Backend (Render platform)          │
                    │  ├─ Flask Application               │
                    │  ├─ Gunicorn Workers (4)            │
                    │  ├─ Rate Limiter                    │
                    │  └─ Structured Logging              │
                    └────────────┬─────┬──────┬───────────┘
                                 │     │      │
                  ┌──────────────┘     │      └──────────────┐
                  │                    │                     │
                  ▼                    ▼                      ▼
        ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
        │  NPPES Registry  │  │  Geoapify API    │  │  Salesforce      │
        │  (Physician DB)  │  │  (Geocoding)     │  │  (Lead CRM)      │
        │  6M+ Records     │  │  Rate: 3k/day    │  │  OAuth 2.0       │
        └──────────────────┘  └──────────────────┘  └──────────────────┘
                  │
        ┌─────────▼──────────┐
        │ ZIP Code Database  │
        │ (41,257 ZIPs)      │
        │ In-Memory Index    │
        └────────────────────┘
```

### 2.2 Component Architecture

```
FRONTEND (Single HTML File)
├── DOM Structure
│   ├── Header (sticky, 64px)
│   ├── Main Content (flex, scrollable)
│   │   ├── Search Phase
│   │   │   ├── Address input + autocomplete
│   │   │   ├── Specialty multi-select
│   │   │   └── Radius selector + Search button
│   │   │
│   │   └── Results Phase (display:none by default)
│   │       ├── Search banner (sticky)
│   │       ├── Map container (MapQuest)
│   │       ├── Results grid (3-col, responsive)
│   │       │   └── Physician cards (9+ rows)
│   │       │
│   │       └── Detail panel (position:fixed, right)
│   │           ├── Provider info section
│   │           ├── Map section
│   │           └── Actions (Add as Lead, View on Map)
│   │
│   └── Modals
│       ├── Lead capture modal (display:none default)
│       └── Toast notifications (stacked)
│
├── Styling System
│   ├── CSS Root Variables
│   │   ├── Colors (11 primary + gradients)
│   │   ├── Spacing (border, padding, gaps)
│   │   ├── Typography (font families, sizes, weights)
│   │   └── Shadows (3 levels: s1, s2, s3)
│   │
│   ├── Component Styles
│   │   ├── Search form (.search-card, .inp, .tag-box)
│   │   ├── Results (.phase-results, .results-banner)
│   │   ├── Map (.map-container)
│   │   ├── Cards (.dc, .dc-inner, .dc-avatar)
│   │   ├── Detail Panel (.detail-panel, .dp-content)
│   │   ├── Buttons (.btn-s, .dp-btn-primary, .empty-btn)
│   │   └── Feedback (.toast, .spinner, .empty-state)
│   │
│   └── Responsive Rules
│       ├── Desktop (>900px): 3-col grid, full spacing
│       ├── Tablet (580-900px): 2-col grid, medium spacing
│       └── Mobile (<580px): 1-col grid, compact spacing
│
└── JavaScript Module
    ├── State Management
    │   ├── allPhysicians (Array<Physician>)
    │   ├── totalFound (number)
    │   ├── currentSearch (Object)
    │   ├── taxTags (Array<string>)
    │   ├── selectedIdx (number | null)
    │   ├── detailOpen (boolean)
    │   └── mapInstance (MapQuest object)
    │
    ├── Core Modules
    │   ├── Form Inputs
    │   │   ├── addressInput.addEventListener('input', debounce(fetchAutocomplete))
    │   │   ├── specialtyInput.addEventListener('input', debounce(fetchTaxonomy))
    │   │   └── radiusSelect.addEventListener('change', updateRadiusValue)
    │   │
    │   ├── Search Handler
    │   │   ├── validateForm()
    │   │   ├── geocodeAddress() [if needed]
    │   │   ├── submitSearch()
    │   │   └── showLoadingSpinner()
    │   │
    │   ├── Results Rendering
    │   │   ├── renderBanner()
    │   │   ├── renderCards()
    │   │   │   └── Loop: createPhysicianCard(physician, idx)
    │   │   ├── attachCardListeners()
    │   │   └── scrollToCard(idx)
    │   │
    │   ├── Mapping (MapQuest SDK)
    │   │   ├── initMap()
    │   │   ├── plotMarkers()
    │   │   │   └── L.marker(lat, lng, { icon: customIcon(num) })
    │   │   ├── attachMarkerHover()
    │   │   │   ├── openPopup() on mouseover
    │   │   │   └── closePopup() on mouseout
    │   │   └── fitBounds()
    │   │
    │   ├── Detail Panel
    │   │   ├── openDetail(idx)
    │   │   │   └── Slide in panel, populate HTML
    │   │   ├── closeDetail()
    │   │   │   └── Slide out, restore main view
    │   │   ├── attachDetailListeners()
    │   │   └── populatePanelHTML(physician)
    │   │
    │   ├── Lead Capture
    │   │   ├── openLeadModal()
    │   │   ├── validateLeadForm()
    │   │   ├── submitLead()
    │   │   │   └── POST /api/leads
    │   │   └── closeLeadModal()
    │   │
    │   └── Utilities
    │       ├── fetchWithTimeout(url, options, timeout=8s)
    │       ├── showToast(message, type='success')
    │       ├── debounce(fn, delay=300ms)
    │       ├── formatDistance(miles)
    │       └── parseCoordinates(feature)
    │
    └── API Client Layer
        ├── GET /api/autocomplete?text=value
        ├── GET /api/geocode?address=value
        ├── GET /api/taxonomy-search?q=value
        ├── GET /api/search?lat=&lng=&radius=&descriptions=[]
        ├── POST /api/leads (physician or user lead)
        └── GET / (main page fallback)

BACKEND (Python Flask)
├── Application Factory (app.py)
│   ├── Config(Object)
│   │   ├── Environment variables (15+)
│   │   ├── Rate limits (per endpoint)
│   │   ├── Debug mode toggle
│   │   └── CORS origins
│   │
│   ├── Request Logging
│   │   ├── Request ID generator (UUID v4)
│   │   ├── Structured logging filter
│   │   │   └── Adds request_id to all log records
│   │   ├── Log format (JSON-compatible)
│   │   └── stdout to log aggregator
│   │
│   ├── Rate Limiter
│   │   ├── Per-IP tracking (dict, in-memory)
│   │   ├── Time window: 60 seconds
│   │   ├── Auto-purge expired entries
│   │   └── Routes configured:
│   │       ├── /api/autocomplete: 120 req/min
│   │       ├── /api/search: 30 req/min
│   │       └── /api/leads: 5 req/min
│   │
│   └── Data Initialization (on startup)
│       ├── Load and index ZIP database (41,257 entries)
│       ├── Build spatial KD-tree for ZIP lookup
│       ├── Load taxonomy index (702 specialties)
│       └── Initialize geocode cache (LRU, max 2,000)
│
├── Route Handlers (Flask blueprints)
│   ├── Autocomplete Route
│   │   ├── GET /api/autocomplete
│   │   ├── Calls: Geoapify API
│   │   ├── Input: ?text=...&limit=7
│   │   ├── Output: Array of formatted addresses
│   │   └── Errors: 400 (invalid input), 429 (rate limit), 500 (API error)
│   │
│   ├── Geocode Route
│   │   ├── GET /api/geocode
│   │   ├── Calls: Geoapify API (cached)
│   │   ├── Input: ?address=...
│   │   ├── Output: { lat, lng, city, state, formatted }
│   │   └── Cache: LRU 2,000 entries
│   │
│   ├── Taxonomy Search Route
│   │   ├── GET /api/taxonomy-search
│   │   ├── Calls: In-memory taxonomy index (702 entries)
│   │   ├── Input: ?q=specialty_name
│   │   ├── Output: Array of matching specialties
│   │   └── No rate limiting (internal lookup only)
│   │
│   ├── Physician Search Route
│   │   ├── GET /api/search
│   │   ├── Process:
│   │   │   ├── Validate input (lat, lng, radius, taxonomy)
│   │   │   ├── Find nearby ZIPs via spatial index
│   │   │   ├── Query NPPES API (batch by ZIP)
│   │   │   ├── Filter by taxonomy
│   │   │   ├── Calculate distance (haversine)
│   │   │   ├── Sort by proximity
│   │   │   └── Return up to 1,000 results
│   │   ├── Input: lat, lng, radius (5-100), descriptions[]
│   │   ├── Output: { physicians: [], total: int }
│   │   └── Caching: None (fresh data each search)
│   │
│   ├── Lead Creation Route
│   │   ├── POST /api/leads
│   │   ├── Input: first_name, last_name, email, [optional fields]
│   │   ├── Process:
│   │   │   ├── Sanitize all input (HTML escape)
│   │   │   ├── Validate email format
│   │   │   ├── Check for duplicates (first_name + email)
│   │   │   ├── Generate unique ID
│   │   │   ├── Save to JSON file
│   │   │   └── [Optional] Push to Salesforce
│   │   ├── Output: { success: true, lead_id, message }
│   │   └── Errors: 400 (validation), 429 (rate limit), 500 (save/SF error)
│   │
│   ├── Lead Debug Route
│   │   ├── POST /api/lead-debug
│   │   ├── Purpose: Testing lead creation without Salesforce
│   │   ├── Auth: X-Debug-Secret header required
│   │   └── Response: Same as /api/leads
│   │
│   └── Root Route
│       ├── GET /
│       └── Returns: index.html (frontend SPA)
│
├── Data Access Layer
│   ├── ZIP Database Handler
│   │   ├── Load: us_zip_db.json
│   │   ├── Structure: { "zip": { lat, lng, city, state, ... } }
│   │   ├── Index: Build KD-tree for spatial lookups
│   │   ├── Query: Find ZIPs within radius (haversine)
│   │   └── Cache: In-memory (loaded once on startup)
│   │
│   ├── Taxonomy Index
│   │   ├── Load: Hard-coded NUCC taxonomy
│   │   ├── Search: Case-insensitive substring match
│   │   ├── Index: Build lookup dictionary by code + description
│   │   └── Cache: In-memory (702 entries)
│   │
│   ├── Geocode Cache
│   │   ├── Type: LRU cache (functools.lru_cache or custom)
│   │   ├── Size: Max 2,000 addresses
│   │   ├── Key: Address string
│   │   ├── Value: { lat, lng, city, state, formatted }
│   │   └── TTL: None (fixed size cache)
│   │
│   └── Lead Storage
│       ├── File: /tmp/leads/ or LEADS_DIR env var
│       ├── Format: One JSON per lead (lead_YYYYMMDDHHMMSSFFFFF.json)
│       ├── Fields: Mirrors Lead interface
│       └── Permissions: Read/write by app user
│
├── External API Integration
│   ├── NPPES API Client
│   │   ├── Endpoint: https://npiregistry.cms.hhs.gov/
│   │   ├── Authentication: None (public API)
│   │   ├── Rate Limit: ~300 req/min (enforced server-side)
│   │   ├── Timeout: 10 seconds per request
│   │   ├── Batch Strategy: 1 ZIP at a time, then merge results
│   │   └── Retry: Exponential backoff (3 retries)
│   │
│   ├── Geoapify API Client
│   │   ├── Endpoints:
│   │   │   ├── Autocomplete: /v1/geocode/autocomplete
│   │   │   └── Geocode: /v1/geocode/search
│   │   ├── Authentication: API key (env var GEOAPIFY_API_KEY)
│   │   ├── Rate Limit: 3,000 req/day (backend enforces)
│   │   ├── Timeout: 8 seconds per request
│   │   └── Results Limit: 7 for autocomplete
│   │
│   └── Salesforce API Client
│       ├── Endpoint: Org-specific (SF_OID env var)
│       ├── Authentication: OAuth 2.0 or API token
│       ├── Method: REST API /sobjects/Lead
│       ├── Timeout: 10 seconds
│       ├── Field Mapping:
│       │   ├── first_name → FirstName
│       │   ├── last_name → LastName
│       │   ├── email → Email
│       │   ├── phone → Phone
│       │   ├── company → Company
│       │   └── Title → Title (specialty)
│       └── Status: Optional (stub ready, requires SF creds)
│
├── Error Handling
│   ├── HTTP Status Codes
│   │   ├── 200 (OK) - Successful response
│   │   ├── 400 (Bad Request) - Validation error
│   │   ├── 404 (Not Found) - Resource not found
│   │   ├── 429 (Too Many Requests) - Rate limited
│   │   └── 500 (Server Error) - Unexpected error
│   │
│   ├── Error Response Format
│   │   └── { error: str, code: str, request_id: str, [details: obj] }
│   │
│   └── Error Logging
│       ├── All errors logged with request_id
│       ├── Stack trace included for 500s
│       ├── Geoapify 429 logged as warning
│       └── NPPES timeout logged with retry info
│
└── Deployment Configuration
    ├── Gunicorn (WSGI server)
    │   ├── Workers: 4 (configurable)
    │   ├── Threads: 2 per worker
    │   ├── Timeout: 30 seconds
    │   ├── Max Requests: 1,000 (reload to prevent memory leak)
    │   └── Binding: 0.0.0.0:8080
    │
    ├── Dockerfile (containerization)
    │   ├── Base: python:3.9-slim
    │   ├── Workdir: /app
    │   ├── Copy: requirements.txt, *.py, *.json
    │   ├── Install: pip install -r requirements.txt
    │   ├── Expose: 8080
    │   └── Cmd: gunicorn backend.app:app
    │
    └── Procfile (Render deployment)
        └── web: gunicorn backend.app:app
```

---

## 3. Frontend Architecture

### 3.1 HTML Structure (Single File)

**File**: `frontend/index.html` (≈1,500 lines)

**Structure**:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <!-- Meta tags -->
  <!-- External CSS: MapQuest, Google Fonts -->
  <!-- Inline CSS (120KB) -->
</head>
<body>
  <!-- Header (sticky) -->
  <!-- Main content wrapper -->
    <!-- Phase 1: Search Form (display:flex) -->
    <!-- Phase 2: Results (display:none initially) -->
      <!-- Results Banner -->
      <!-- Map Container -->
      <!-- Physician Cards Grid -->
      <!-- Detail Panel (position:fixed) -->
  <!-- Modals -->
    <!-- Lead Capture Modal -->
  <!-- Toast Container -->
  <!-- Spinner Overlay -->
  
  <!-- External Scripts -->
  <!-- MapQuest SDK -->
  <!-- Inline JavaScript (380KB) -->
</body>
</html>
```

### 3.2 CSS Architecture

**Scope**: Entire stylesheet embedded in `<style>` tag

**Organization**:
1. **Root Variables** (25 CSS custom properties)
   ```css
   :root {
     /* Colors */
     --primary: #0076B6;
     --accent: #00AEEF;
     --teal: #0C7A7A;
     --navy: #0F2044;
     --error: #D95F4B;
     --gold: #C4993A;
     --bg: linear-gradient(135deg, #E0F4FF 0%, #D0E8F2 100%);
     --dark: #141420;
     --light: #FAF8F4;
     
     /* Spacing */
     --border: 48px;
     --hdr: 64px;
     --content: calc(100vw - 96px);
     --r: 10px;
     --tr: 0.18s;
     
     /* Shadows */
     --s1: 0 2px 8px rgba(20,20,32,.06);
     --s2: 0 8px 28px rgba(20,20,32,.10);
     --s3: 0 20px 60px rgba(20,20,32,.14);
   }
   ```

2. **Component Styles** (200+ rules)
   - `.search-card`: Main search form container
   - `.inp`: Text input fields (address, specialty)
   - `.tag-box`: Multi-select container for specialties
   - `.btn-s`: Primary button (Search Physicians)
   - `.phase-results`: Results container (hidden by default)
   - `.results-banner`: Search criteria display
   - `.map-container`: MapQuest map (480px desktop, 360px mobile)
   - `.dc`: Physician result card
   - `.detail-panel`: Right-aligned detail overlay
   - `.modal`: Lead capture form
   - `.toast`: Notification message
   - `.spinner`: Loading indicator

3. **Responsive Breakpoints**
   ```css
   /* Desktop (>900px) */
   @media(min-width:901px){
     .grid { grid-template-columns: repeat(3, 1fr); }
     .map-container { height: 480px; }
   }
   
   /* Tablet (580-900px) */
   @media(max-width:900px) and (min-width:580px){
     .grid { grid-template-columns: repeat(2, 1fr); }
     .map-container { height: 360px; }
   }
   
   /* Mobile (<580px) */
   @media(max-width:579px){
     .grid { grid-template-columns: 1fr; }
     .map-container { height: 360px; }
     .detail-panel { width: 100%; }
   }
   ```

4. **Scrollbar Hiding** (cross-browser)
   ```css
   /* Firefox */
   .scrollable { scrollbar-width: none; }
   
   /* IE/Edge */
   .scrollable { -ms-overflow-style: none; }
   
   /* WebKit */
   .scrollable::-webkit-scrollbar { display: none; }
   ```

### 3.3 JavaScript Architecture

**Scope**: Entire application logic in single `<script>` tag

**Module Organization**:

#### A. State Management
```javascript
// Global state object
window.appState = {
  allPhysicians: [],           // All search results
  totalFound: 0,               // Total count from backend
  currentSearch: {             // Search context
    address: "",
    lat: null,
    lng: null,
    radius: 10,
    specialties: [],
    city: "",
    state: ""
  },
  taxTags: [],                // Selected specialties (display + code)
  selectedIdx: null,           // Currently selected physician (detail panel)
  detailOpen: false,           // Detail panel state
  mapInstance: null,           // MapQuest map object
  mapMarkers: [],              // Marker references
};
```

#### B. Event Listeners (Initialization)
```javascript
document.addEventListener('DOMContentLoaded', () => {
  setupAddressAutocomplete();
  setupSpecialtyAutocomplete();
  setupSearchForm();
  setupDetailPanel();
  setupLeadModal();
  setupKeyboardShortcuts();
  initMapInstance();
});
```

#### C. Core Functions

**Address Autocomplete**:
```javascript
function setupAddressAutocomplete() {
  const inp = document.getElementById('address-input');
  inp.addEventListener('input', debounce(async (e) => {
    const text = e.target.value.trim();
    if (text.length < 2) {
      showSuggestions([]);
      return;
    }
    try {
      const suggestions = await fetchWithTimeout(
        `/api/autocomplete?text=${encodeURIComponent(text)}&limit=7`,
        {},
        8000
      );
      renderAutocompleteSuggestions(suggestions, 'address');
    } catch (err) {
      console.error('Autocomplete error:', err);
      showToast('Could not fetch suggestions', 'error');
    }
  }, 300));
}
```

**Specialty Multi-Select**:
```javascript
function setupSpecialtyAutocomplete() {
  const inp = document.getElementById('specialty-input');
  inp.addEventListener('input', debounce(async (e) => {
    const text = e.target.value.trim();
    if (text.length < 2) {
      showSuggestions([]);
      return;
    }
    try {
      const results = await fetchWithTimeout(
        `/api/taxonomy-search?q=${encodeURIComponent(text)}`,
        {},
        8000
      );
      renderAutocompleteSuggestions(results, 'specialty');
    } catch (err) {
      showToast('Could not fetch specialties', 'error');
    }
  }, 300));
  
  // Allow adding specialty on suggestion click
  document.addEventListener('click', (e) => {
    if (e.target.dataset.action === 'select-specialty') {
      const specialty = {
        display: e.target.textContent,
        code: e.target.dataset.code
      };
      window.appState.taxTags.push(specialty);
      renderTaxTags();
      inp.value = '';
      showSuggestions([]);
    }
  });
}
```

**Search Submission**:
```javascript
async function submitSearch(e) {
  e.preventDefault();
  
  // Validation
  const address = document.getElementById('address-input').value.trim();
  if (!address) {
    showToast('Please enter an address', 'error');
    return;
  }
  
  if (window.appState.taxTags.length === 0) {
    showToast('Please select at least one specialty', 'error');
    return;
  }
  
  // Show loading state
  showSpinner('Searching providers...');
  
  try {
    // Geocode address if not already cached
    if (!window.appState.currentSearch.lat) {
      const geo = await fetchWithTimeout(
        `/api/geocode?address=${encodeURIComponent(address)}`,
        {},
        8000
      );
      window.appState.currentSearch.lat = geo.lat;
      window.appState.currentSearch.lng = geo.lng;
      window.appState.currentSearch.address = address;
      window.appState.currentSearch.city = geo.city;
      window.appState.currentSearch.state = geo.state;
    }
    
    // Execute search
    const radius = document.getElementById('radius-select').value;
    const descriptions = window.appState.taxTags.map(t => t.display);
    
    const results = await fetchWithTimeout(
      `/api/search?lat=${window.appState.currentSearch.lat}&lng=${window.appState.currentSearch.lng}&radius=${radius}&descriptions=${encodeURIComponent(JSON.stringify(descriptions))}&city=${window.appState.currentSearch.city}&state=${window.appState.currentSearch.state}`,
      {},
      10000
    );
    
    window.appState.allPhysicians = results.physicians || [];
    window.appState.totalFound = results.total || 0;
    
    hideSpinner();
    showResultsPhase();
    renderResults();
    
  } catch (err) {
    hideSpinner();
    showToast('Search failed. Please try again.', 'error');
    console.error('Search error:', err);
  }
}
```

**Results Rendering**:
```javascript
function renderResults() {
  renderBanner();
  renderResultsCounter();
  renderMap();
  renderCards();
  attachCardListeners();
}

function renderCards() {
  const grid = document.getElementById('results-grid');
  grid.innerHTML = '';
  
  window.appState.allPhysicians.slice(0, 9).forEach((phys, idx) => {
    const card = createPhysicianCard(phys, idx);
    grid.appendChild(card);
  });
}

function createPhysicianCard(physician, idx) {
  const card = document.createElement('div');
  card.className = 'dc';
  card.innerHTML = `
    <div class="dc-inner">
      <span class="dc-num">${idx + 1}</span>
      <div class="dc-avatar">${physician.name.split(' ').map(n => n[0]).join('')}</div>
      <h3>${physician.name}</h3>
      <p class="dc-specialty">${physician.taxonomy_desc}</p>
      <span class="dc-distance">📍 ${physician.distance_miles.toFixed(1)} mi</span>
    </div>
  `;
  card.addEventListener('click', () => openDetail(idx));
  return card;
}
```

**Map Initialization**:
```javascript
function initMapInstance() {
  window.appState.mapInstance = L.map(
    document.getElementById('map-container'),
    { zoomControl: false, attributionControl: false }
  );
  
  // Add MapQuest tile layer
  L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
    { maxZoom: 18 }
  ).addTo(window.appState.mapInstance);
}

function renderMap() {
  const map = window.appState.mapInstance;
  
  // Clear existing markers
  window.appState.mapMarkers.forEach(m => map.removeLayer(m));
  window.appState.mapMarkers = [];
  
  // Add center pin
  const centerIcon = L.icon({
    iconUrl: 'data:image/svg+xml;base64,...', // Gold star SVG
    iconSize: [32, 32],
    iconAnchor: [16, 16]
  });
  
  const centerMarker = L.marker(
    [window.appState.currentSearch.lat, window.appState.currentSearch.lng],
    { icon: centerIcon, title: 'Search center' }
  ).addTo(map);
  window.appState.mapMarkers.push(centerMarker);
  
  // Add physician pins (numbered)
  window.appState.allPhysicians.forEach((phys, idx) => {
    const icon = L.icon({
      iconUrl: `data:image/svg+xml;base64,...`, // Numbered cyan pin
      iconSize: [40, 40],
      iconAnchor: [20, 40]
    });
    
    const marker = L.marker([phys.lat, phys.lng], { icon, title: phys.name }).
      bindPopup(`<strong>${phys.name}</strong><br/>${phys.taxonomy_desc}`).
      addTo(map);
    
    // Auto-open popup on hover
    marker.on('mouseover', () => marker.openPopup());
    marker.on('mouseout', () => marker.closePopup());
    
    // Click to highlight and scroll card
    marker.on('click', () => {
      window.appState.selectedIdx = idx;
      scrollToCard(idx);
    });
    
    window.appState.mapMarkers.push(marker);
  });
  
  // Auto-fit bounds to all markers
  if (window.appState.mapMarkers.length > 1) {
    const group = new L.featureGroup(window.appState.mapMarkers);
    map.fitBounds(group.getBounds(), { padding: [50, 50], maxZoom: 15 });
  }
}
```

**Detail Panel**:
```javascript
function openDetail(idx) {
  const physician = window.appState.allPhysicians[idx];
  window.appState.selectedIdx = idx;
  window.appState.detailOpen = true;
  
  const panel = document.getElementById('detail-panel');
  panel.innerHTML = `
    <div class="dp-header">
      <button onClick="closeDetail()" class="dp-back-btn">← Back</button>
      <div class="dp-avatar">${physician.name.split(' ').map(n => n[0]).join('')}</div>
      <h2>${physician.name}</h2>
      <div class="dp-taxonomies">
        ${physician.all_taxonomies.map(t => `<span class="dp-badge">${t.desc}</span>`).join('')}
      </div>
    </div>
    <div class="dp-content">
      <!-- NPI, Address, Phone -->
      <!-- Specialties -->
      <!-- Map -->
      <!-- Actions: Add as Lead, View on Map -->
    </div>
  `;
  
  panel.classList.add('open');
  document.addEventListener('keydown', closeDetailOnEscape);
}

function closeDetail() {
  document.getElementById('detail-panel').classList.remove('open');
  window.appState.selectedIdx = null;
  window.appState.detailOpen = false;
  document.removeEventListener('keydown', closeDetailOnEscape);
}
```

**Lead Capture**:
```javascript
async function submitLeadForm(e) {
  e.preventDefault();
  
  const form = document.getElementById('lead-form');
  const formData = new FormData(form);
  
  // Client-side validation
  if (!formData.get('first_name').trim()) {
    showToast('First name is required', 'error');
    return;
  }
  if (!formData.get('email').match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)) {
    showToast('Valid email required', 'error');
    return;
  }
  
  try {
    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting...';
    
    const response = await fetchWithTimeout('/api/leads', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        first_name: formData.get('first_name'),
        last_name: formData.get('last_name'),
        email: formData.get('email'),
        phone: formData.get('phone') || '',
        company: formData.get('company') || '',
        title: formData.get('title') || ''
      })
    }, 8000);
    
    if (response.success) {
      showToast('Lead created successfully!', 'success');
      closeLeadModal();
      form.reset();
    }
  } catch (err) {
    showToast('Failed to create lead. Please try again.', 'error');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Submit';
  }
}
```

### 3.4 API Communication

**Wrapper Function** (with timeout and error handling):
```javascript
async function fetchWithTimeout(url, options = {}, timeout = 8000) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      }
    });
    
    clearTimeout(id);
    
    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.error || 'API error');
    }
    
    return await response.json();
  } catch (err) {
    clearTimeout(id);
    throw err;
  }
}
```

### 3.5 Performance Optimizations

1. **Debouncing**: Autocomplete requests debounced 300ms
2. **Lazy Rendering**: Cards render on-demand, not all at once
3. **Event Delegation**: Use single listener for card clicks, not per card
4. **CSS Animations**: Hardware-accelerated (transform, opacity)
5. **Image Optimization**: SVG pins (no external images)
6. **Caching**: Geocode results cached client-side (in appState)
7. **Minification**: CSS and JS embedded as single file

---

## 4. Backend Architecture

### 4.1 Flask Application Structure

**File**: `backend/app.py` (≈1,200 lines)

**Initialization**:
```python
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import os
from datetime import datetime
import json
import uuid
from functools import wraps
import requests
from scipy.spatial import KDTree
import html

# Configuration
class Config:
    MAPQUEST_API_KEY = os.getenv('MAPQUEST_API_KEY')
    GEOAPIFY_API_KEY = os.getenv('GEOAPIFY_API_KEY')
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
    SF_OID = os.getenv('SF_OID')
    SF_DEBUG_EMAIL = os.getenv('SF_DEBUG_EMAIL')
    DEBUG_SECRET = os.getenv('DEBUG_SECRET')
    LEADS_DIR = os.getenv('LEADS_DIR', '/tmp/leads')
    DEBUG = os.getenv('FLASK_ENV') == 'development'

# Flask app factory
app = Flask(__name__)
app.config.from_object(Config)

# CORS setup
CORS(app, origins=[Config.FRONTEND_URL], methods=['GET', 'POST', 'OPTIONS'])

# Logging with request ID
class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = getattr(g, 'request_id', 'N/A')
        return True

logging_handler = logging.StreamHandler()
logging_handler.setFormatter(logging.Formatter(
    '%(asctime)s [%(request_id)s] %(levelname)s: %(message)s'
))
logging_handler.addFilter(RequestIDFilter())
app.logger.addHandler(logging_handler)

# Request middleware
@app.before_request
def before_request():
    g.request_id = str(uuid.uuid4())[:8]
    app.logger.info(f'{request.method} {request.path}')

# Data initialization (on startup)
def load_data():
    global ZIP_DB, TAXONOMY_INDEX, SPATIAL_INDEX
    
    # Load ZIP database
    with open('us_zip_db.json', 'r') as f:
        ZIP_DATA = json.load(f)
    
    ZIP_DB = {}
    coords = []
    for zip_code, data in ZIP_DATA.items():
        ZIP_DB[zip_code] = {
            'lat': data['latitude'],
            'lng': data['longitude'],
            'city': data['city'],
            'state': data['state']
        }
        coords.append([data['latitude'], data['longitude']])
    
    # Build spatial index (KD-tree)
    SPATIAL_INDEX = KDTree(coords)
    
    # Load taxonomy
    TAXONOMY_INDEX = {
        '207S00000X': 'Cardiology',
        '202Y00000X': 'Interventional Cardiology',
        # ... 700+ more entries
    }
    
    app.logger.info(f'Loaded {len(ZIP_DB)} ZIP codes and {len(TAXONOMY_INDEX)} specialties')

load_data()

# Rate limiter
RATE_LIMITS = {}

def rate_limit(limit, window=60):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            ip = request.remote_addr
            key = f'{ip}:{request.endpoint}'
            now = time.time()
            
            if key not in RATE_LIMITS:
                RATE_LIMITS[key] = []
            
            # Purge old entries
            RATE_LIMITS[key] = [t for t in RATE_LIMITS[key] if now - t < window]
            
            if len(RATE_LIMITS[key]) >= limit:
                return jsonify({
                    'error': 'Too many requests',
                    'code': 'RATE_LIMITED',
                    'request_id': g.request_id,
                    'retry_after_ms': 1000
                }), 429
            
            RATE_LIMITS[key].append(now)
            return f(*args, **kwargs)
        return decorated_function
    return decorator
```

### 4.2 API Routes

**Route 1: Autocomplete**
```python
@app.route('/api/autocomplete', methods=['GET'])
@rate_limit(120)  # 120 req/min
def autocomplete():
    text = request.args.get('text', '').strip()
    limit = request.args.get('limit', 7, type=int)
    
    if not text or len(text) < 2:
        return jsonify({'error': 'Invalid input'}), 400
    
    try:
        response = requests.get(
            'https://api.geoapify.com/v1/geocode/autocomplete',
            params={
                'text': text,
                'limit': limit,
                'apiKey': Config.GEOAPIFY_API_KEY,
                'bias': {
                    'countrycodes': ['US']
                }
            },
            timeout=8
        )
        
        if response.status_code != 200:
            return jsonify({'error': 'Geoapify API error'}), 500
        
        data = response.json()
        return jsonify(data)
    
    except requests.Timeout:
        return jsonify({'error': 'Geocoding service timeout'}), 500
    except Exception as e:
        app.logger.error(f'Autocomplete error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500
```

**Route 2: Geocode**
```python
@app.route('/api/geocode', methods=['GET'])
def geocode():
    address = request.args.get('address', '').strip()
    
    if not address:
        return jsonify({'error': 'Address required'}), 400
    
    try:
        response = requests.get(
            'https://api.geoapify.com/v1/geocode/search',
            params={
                'text': address,
                'apiKey': Config.GEOAPIFY_API_KEY,
                'countrycodes': 'US'
            },
            timeout=8
        )
        
        if response.status_code != 200:
            return jsonify({'error': 'Geocoding failed'}), 500
        
        data = response.json()
        if not data.get('features'):
            return jsonify({'error': 'Address not found'}), 404
        
        feature = data['features'][0]
        coords = feature['geometry']['coordinates']
        props = feature['properties']
        
        return jsonify({
            'lat': coords[1],
            'lng': coords[0],
            'city': props.get('city', ''),
            'state': props.get('state_code', ''),
            'formatted': props.get('formatted', address),
            'address': f"{props.get('city', '')}, {props.get('state_code', '')}"
        })
    
    except requests.Timeout:
        return jsonify({'error': 'Geocoding timeout'}), 500
    except Exception as e:
        app.logger.error(f'Geocode error: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500
```

**Route 3: Physician Search**
```python
@app.route('/api/search', methods=['GET'])
@rate_limit(30)  # 30 req/min
def search():
    try:
        lat = float(request.args.get('lat'))
        lng = float(request.args.get('lng'))
        radius = int(request.args.get('radius'))
        descriptions = json.loads(request.args.get('descriptions', '[]'))
        
        if radius < 5 or radius > 100:
            return jsonify({'error': 'Radius must be 5-100'}), 400
        
        #Step 1: Find nearby ZIP codes using spatial index
        nearby_zips = find_nearby_zips(lat, lng, radius)
        
        # Step 2: Query NPPES API for each ZIP
        physicians = []
        for zip_code in nearby_zips:
            npi_results = query_nppes(zip_code, descriptions)
            physicians.extend(npi_results)
        
        # Step 3: Calculate distances and sort
        for phys in physicians:
            phys['distance_miles'] = haversine(lat, lng, phys['lat'], phys['lng'])
        
        physicians.sort(key=lambda p: p['distance_miles'])
        
        # Step 4: Remove duplicates (by NPI)
        seen_npis = set()
        unique_physicians = []
        for phys in physicians:
            if phys['npi'] not in seen_npis:
                unique_physicians.append(phys)
                seen_npis.add(phys['npi'])
        
        return jsonify({
            'physicians': unique_physicians[:100],  # Display limit
            'total': len(unique_physicians)
        })
    
    except ValueError:
        return jsonify({'error': 'Invalid parameters'}), 400
    except Exception as e:
        app.logger.error(f'Search error: {str(e)}')
        return jsonify({'error': 'Search failed'}), 500

def query_nppes(zip_code, descriptions):
    """Query NPPES API with retry logic"""
    for attempt in range(3):
        try:
            response = requests.get(
                'https://npiregistry.cms.hhs.gov/api/',
                params={
                    'number': zip_code,
                    'address_purpose': 'LOCATION',
                    'state': 'US',
                    'limit': 200
                },
                timeout=10
            )
            
            if response.status_code != 200:
                app.logger.warning(f'NPPES API error: {response.status_code}')
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                return []
            
            data = response.json()
            physicians = []
            
            for result in data.get('results', []):
                # Parse and validate record...
                phys = parse_nppes_record(result, descriptions)
                if phys:
                    physicians.append(phys)
            
            return physicians
        
        except requests.Timeout:
            app.logger.warning(f'NPPES timeout (attempt {attempt+1}/3)')
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            return []
    
    return []
```

**Route 4: Lead Creation**
```python
@app.route('/api/leads', methods=['POST'])
@rate_limit(5)  # 5 req/min
def create_lead():
    try:
        data = request.get_json()
        
        # Validation
        first_name = html.escape((data.get('first_name') or '').strip()[:80])
        last_name = html.escape((data.get('last_name') or '').strip()[:80])
        email = html.escape((data.get('email') or '').strip().lower()[:120])
        phone = html.escape((data.get('phone') or '').strip()[:30])
        company = html.escape((data.get('company') or '').strip()[:120])
        title = html.escape((data.get('title') or '').strip()[:80])
        
        if not first_name or not last_name or not email:
            return jsonify({'error': 'Missing required fields'}), 400
        
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            return jsonify({'error': 'Invalid email'}), 400
        
        # Generate lead ID
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
        lead_id = f'lead_{timestamp}'
        
        # Build lead record
        lead = {
            'id': lead_id,
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'phone': phone or None,
            'company': company or None,
            'title': title or None,
            'search_context': data.get('search_context', {}),
            'created_at': datetime.utcnow().isoformat(),
            'source': 'PhysicianLocator',
            'status': 'New'
        }
        
        # Save to file
        leads_dir = Config.LEADS_DIR
        os.makedirs(leads_dir, exist_ok=True)
        
        lead_file = os.path.join(leads_dir, f'{lead_id}.json')
        with open(lead_file, 'w') as f:
            json.dump(lead, f, indent=2)
        
        app.logger.info(f'Lead created: {lead_id}')
        
        # [Optional] Push to Salesforce
        if Config.SF_OID:
            try:
                push_to_salesforce(lead)
            except Exception as e:
                app.logger.error(f'Salesforce push failed: {str(e)}')
                # Don't fail lead creation if SF fails
        
        return jsonify({
            'success': True,
            'lead_id': lead_id,
            'message': 'Lead created successfully'
        })
    
    except Exception as e:
        app.logger.error(f'Lead creation error: {str(e)}')
        return jsonify({'error': 'Failed to create lead'}), 500
```

### 4.3 Data Access Patterns

**ZIP Lookup with Spatial Index**:
```python
def find_nearby_zips(lat, lng, radius_miles):
    """Find ZIPs within radius using KD-tree"""
    # Convert miles to approximate lat/lng degrees
    # (1 degree latitude ≈ 69 miles, 1 degree longitude varies)
    lat_delta = radius_miles / 69
    lng_delta = radius_miles / (69 * math.cos(math.radians(lat)))
    
    # Query KD-tree for nearby points
    indices = SPATIAL_INDEX.query_ball_point(
        [lat, lng],
        math.sqrt(lat_delta**2 + lng_delta**2)
    )
    
    # Convert indices back to ZIP codes
    nearby_zips = [
        list(ZIP_DB.keys())[idx] for idx in indices
    ]
    
    return nearby_zips[:50]  # Limit to 50 ZIPs per search
```

**Taxonomy Lookup**:
```python
def find_matching_taxonomies(descriptions):
    """Find taxonomy codes matching specialty descriptions"""
    matching_codes = []
    
    for desc in descriptions:
        # Case-insensitive substring match
        for code, taxonomy_desc in TAXONOMY_INDEX.items():
            if desc.lower() in taxonomy_desc.lower():
                matching_codes.append(code)
    
    return matching_codes
```

---

## 4.4 Lead Generation Architecture

### 4.4.1 Lead Lifecycle

**State Diagram**:
```
┌─────────────────────────────────────────────────────────────────┐
│                    LEAD LIFECYCLE                               │
└─────────────────────────────────────────────────────────────────┘

[User Search]
    ↓
[Click "Add as Lead" on Physician Card]
    ↓
[Frontend POST /api/leads]
    ↓
[Backend: create_lead()] ─────┐
    ├─ Validate input         │
    ├─ Sanitize fields        │
    ├─ Check duplicates       ├─→ [Lead: NEW]
    ├─ Generate lead_id       │
    └─ Save to JSON file      │
                              ↓
         ┌────────────────────────────────────┐
         │ Salesforce Push (async, optional)  │
         ├────────────────────────────────────┤
         │ If SF_OID configured:              │
         │  → POST /services/data/v59.0/...   │
         │  → Map fields (SF Lead object)     │
         │  → Retry on 5xx errors (exp. backoff)
         │  → Log SF_ID for tracking          │
         └────────────────────────────────────┘
                      ↓
         ┌─────────────────────────────────────┐
         │ Lead Status Transitions             │
         ├─────────────────────────────────────┤
         │ NEW → SUBMITTED                     │
         │ SUBMITTED → CONTACTED               │
         │ CONTACTED → QUALIFIED / REJECTED    │
         │ QUALIFIED → NURTURING / CLOSED      │
         └─────────────────────────────────────┘
```

### 4.4.3 Salesforce Experience Cloud Deployment

- The Physician Locator app is deployed in Salesforce Experience Cloud (Experience Builder / Community Cloud) as a site.
- `frontend/index.html` is embedded in the Experience Cloud page and communicates with backend API endpoints on the same domain (or via CORS from a configured `FRONTEND_URL`).
- User form submissions and physician detail lead creation both post to `/api/leads`:
  - Standard user lead (contact request): first_name, last_name, email, company, title, phone, search_context (search selections, total_results, etc.)
  - Physician lead (from “Add as Lead” button): first_name, last_name, email=lead@aquarient.local, company=Individual Physicians, title=specialty, phone, search_context includes npi/address/specialty/distance_miles.
- Backend lead pipeline:
  - Input validation + sanitisation
  - Generate internal lead id (`lead_{timestamp}`)
  - Persist to local file (`LEADS_DIR/leads.ndjson` for redundancy)
  - Push to Salesforce (if `SF_OID` is configured)

### 4.4.4 Salesforce Lead Sync

- Web-to-Lead endpoint: `https://webto.salesforce.com/servlet/servlet.WebToLead?encoding=UTF-8`.
- Required Salesforce fields mapped:
  - `first_name` -> `FirstName`
  - `last_name` -> `LastName`
  - `email` -> `Email`
  - `phone` -> `Phone`
  - `company` -> `Company` (default `N/A` / `Individual Physicians`)
  - `title` -> `Title`
  - `lead_source` -> `LeadSource` (`Physician Locator`)
  - `description` -> `Description` (includes search_context + physician metadata)
- `SF_OID`, `SF_RET_URL`, `SF_DEBUG_EMAIL` are pulled from env vars.
- HTTP success = 200/301/302 without error text; otherwise lead is marked failed in logs and retries are expected in additional architecture.

### 4.4.5 Lead Storage Strategy

**Primary Storage: JSON Files**

**Location**: `/tmp/leads/` or custom LEADS_DIR

**Filename Format**: `lead_YYYYMMDDHHMMSSFFFFF.json`

**File Structure**:
```json
{
  "id": "lead_20260325143521456789",
  "type": "recruiter_lead",
  "source": "PhysicianLocator",
  "created_at": "2026-03-25T14:35:21.456789Z",
  "updated_at": "2026-03-25T14:35:21.456789Z",
  
  "contact_info": {
    "first_name": "John",
    "last_name": "Smith",
    "email": "john.smith@example.com",
    "phone": "(805) 555-1234",
    "title": "Senior Recruiter",
    "organization": "HealthCare Staffing Inc"
  },
  
  "search_context": {
    "location": "Thousand Oaks, CA",
    "latitude": 34.1706,
    "longitude": -118.8376,
    "radius_miles": 10,
    "specialties": ["Interventional Cardiology", "Cardiology"],
    "results_found": 7,
    "selected_physician": {
      "npi": "1417980518",
      "name": "Robert Adams",
      "specialty": "Interventional Cardiology",
      "address": "123 Cardiac Way, Thousand Oaks, CA 91360"
    }
  },
  
  "salesforce_sync": {
    "status": "synced",
    "sf_lead_id": "00Qxx0000012345",
    "sf_object_id": "A01xx000003456",
    "synced_at": "2026-03-25T14:35:25.789123Z",
    "sync_attempts": 1,
    "last_error": null
  },
  
  "activity_log": [
    {
      "timestamp": "2026-03-25T14:35:21.456789Z",
      "action": "created",
      "details": "Lead created via PhysicianLocator"
    },
    {
      "timestamp": "2026-03-25T14:35:25.789123Z",
      "action": "salesforce_synced",
      "details": "Successfully synced to Salesforce"
    }
  ],
  
  "metadata": {
    "request_id": "a1b2c3d4",
    "user_agent": "Mozilla/5.0...",
    "ip_address": "192.168.1.1",
    "lead_score": 85
  }
}
```

**File System Operations**:
```python
import os
import json
from pathlib import Path
from datetime import datetime

class LeadStorage:
    def __init__(self, storage_dir="/tmp/leads"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def create_lead(self, lead_data):
        """Create and persist lead record"""
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
        lead_id = f'lead_{timestamp}'
        
        lead_record = {
            'id': lead_id,
            'type': 'recruiter_lead',
            'source': 'PhysicianLocator',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'contact_info': lead_data.get('contact_info', {}),
            'search_context': lead_data.get('search_context', {}),
            'salesforce_sync': {
                'status': 'pending',
                'sf_lead_id': None,
                'sync_attempts': 0,
                'last_error': None
            },
            'activity_log': [
                {
                    'timestamp': datetime.utcnow().isoformat(),
                    'action': 'created',
                    'details': 'Lead created via PhysicianLocator'
                }
            ],
            'metadata': lead_data.get('metadata', {})
        }
        
        lead_file = self.storage_dir / f'{lead_id}.json'
        
        try:
            with open(lead_file, 'w', encoding='utf-8') as f:
                json.dump(lead_record, f, indent=2, ensure_ascii=False)
            
            # Set file permissions (owner read/write only)
            os.chmod(lead_file, 0o600)
            
            return lead_id, lead_record
        
        except IOError as e:
            raise LeadStorageError(f'Failed to save lead: {str(e)}')
    
    def update_lead(self, lead_id, updates):
        """Update existing lead record"""
        lead_file = self.storage_dir / f'{lead_id}.json'
        
        if not lead_file.exists():
            raise LeadNotFoundError(f'Lead {lead_id} not found')
        
        try:
            with open(lead_file, 'r', encoding='utf-8') as f:
                lead_record = json.load(f)
            
            # Apply updates
            if 'salesforce_sync' in updates:
                lead_record['salesforce_sync'].update(updates['salesforce_sync'])
            
            if 'activity' in updates:
                lead_record['activity_log'].append({
                    'timestamp': datetime.utcnow().isoformat(),
                    'action': updates['activity'].get('action'),
                    'details': updates['activity'].get('details')
                })
            
            lead_record['updated_at'] = datetime.utcnow().isoformat()
            
            with open(lead_file, 'w', encoding='utf-8') as f:
                json.dump(lead_record, f, indent=2, ensure_ascii=False)
            
            return lead_record
        
        except IOError as e:
            raise LeadStorageError(f'Failed to update lead: {str(e)}')
    
    def get_lead(self, lead_id):
        """Retrieve lead record"""
        lead_file = self.storage_dir / f'{lead_id}.json'
        
        if not lead_file.exists():
            raise LeadNotFoundError(f'Lead {lead_id} not found')
        
        with open(lead_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def list_leads(self, limit=100, offset=0, filter_status=None):
        """List all leads with pagination"""
        lead_files = sorted(self.storage_dir.glob('lead_*.json'), reverse=True)
        
        results = []
        for lead_file in lead_files[offset:offset+limit]:
            with open(lead_file, 'r') as f:
                lead = json.load(f)
            
            if filter_status and lead.get('salesforce_sync', {}).get('status') != filter_status:
                continue
            
            results.append(lead)
        
        return results, len(lead_files)
```

### 4.4.3 Lead Deduplication

**Strategy**: Prevent duplicate leads for same person

```python
class LeadDeduplication:
    """Prevent creating duplicate leads"""
    
    @staticmethod
    def generate_fingerprint(first_name, last_name, email):
        """Generate unique fingerprint for lead"""
        import hashlib
        
        fingerprint_str = f'{first_name.lower().strip()}|{last_name.lower().strip()}|{email.lower().strip()}'
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()
    
    @staticmethod
    def check_duplicate(lead_storage, first_name, last_name, email):
        """Check if lead already exists"""
        current_fingerprint = LeadDeduplication.generate_fingerprint(
            first_name, last_name, email
        )
        
        leads, _ = lead_storage.list_leads(limit=10000)
        
        for lead in leads:
            existing_fp = LeadDeduplication.generate_fingerprint(
                lead['contact_info']['first_name'],
                lead['contact_info']['last_name'],
                lead['contact_info']['email']
            )
            
            if existing_fp == current_fingerprint:
                return True, lead['id']
        
        return False, None
```

### 4.4.4 Lead Scoring Algorithm

**Score Calculation**:
```python
class LeadScorer:
    """Calculate lead quality score (0-100)"""
    
    @staticmethod
    def calculate_score(lead_data):
        """
        Score based on:
        - Contact completeness (40 points)
        - Search context quality (30 points)
        - Physician match quality (20 points)
        - Time decay (10 points)
        """
        score = 0
        
        # 1. Contact completeness (40 points)
        contact_info = lead_data.get('contact_info', {})
        completeness_fields = [
            'first_name', 'last_name', 'email', 'phone', 'title', 'organization'
        ]
        filled = sum(1 for f in completeness_fields if contact_info.get(f))
        score += (filled / len(completeness_fields)) * 40
        
        # 2. Search context quality (30 points)
        search_context = lead_data.get('search_context', {})
        if search_context.get('selected_physician'):
            score += 10  # Physician was selected
        if len(search_context.get('specialties', [])) > 0:
            score += 10  # Multiple specialties searched
        if search_context.get('results_found', 0) > 5:
            score += 10  # Good result set (not too narrow)
        
        # 3. Physician match quality (20 points)
        physician = search_context.get('selected_physician', {})
        if physician.get('specialty'):
            score += 10
        if physician.get('address'):
            score += 10
        
        # 4. Time decay (10 points, max after 1 hour)
        created_at = lead_data.get('created_at')
        if created_at:
            from datetime import datetime
            created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            age_hours = (datetime.utcnow() - created).total_seconds() / 3600
            decay = max(0, 10 - (age_hours * 0.1))
            score += decay
        
        return min(100, int(score))
```

---

## 4.5 Salesforce Integration Architecture

### 4.5 Salesforce Integration Architecture

This project uses Salesforce Web-to-Lead (form-based lead injection) instead of OAuth 2.0 API client flow.

### 4.5.1 Salesforce Web-to-Lead Flow (current implementation)

1. Frontend triggers `POST /api/leads` from either:
   - user contact lead modal `submitLead()`
   - physician detail panel `createSalesforceLead(physician)`

2. Backend `capture_lead()`:
   - validate required fields (`first_name`, `last_name`, `email`)
   - sanitize fields and normalize
   - generate internal `lead_id`
   - save local backup in `LEADS_DIR/leads.ndjson`

3. `_push_to_salesforce(lead)` if `SF_OID` present:
   - payload: `oid`, `retURL`, `first_name`, `last_name`, `email`, `phone`, `company`, `title`, `lead_source`, `description`
   - endpoint: `https://webto.salesforce.com/servlet/servlet.WebToLead?encoding=UTF-8`
   - route success when status code in [200,301,302] and no textual error in response body

4. Response to frontend:
   - `{success: true, lead_id: ..., message: ...}` on partial or full success
   - Detailed failure when both file save and Salesforce push fail

5. Physicians can be saved as leads with a normalized physician-focused payload (email set to `lead@aquarient.local`, company `Individual Physicians`, title from taxonomy, and `search_context` includes physician details).

### 4.5.2 Lead API Integration

**Salesforce Lead Object Field Mapping**:

| Salesforce Field | Source | Type | Required | Example |
|------------------|--------|------|----------|---------|
| `FirstName` | lead.first_name | string | Yes | "John" |
| `LastName` | lead.last_name | string | Yes | "Smith" |
| `Email` | lead.email | string | Yes | "john@example.com" |
| `Phone` | lead.phone | string | No | "(805) 555-1234" |
| `Company` | lead.company | string | No | "HealthCare Staffing Inc" |
| `Title` | lead.title | string | No | "Senior Recruiter" |
| `LeadSource` | hardcoded | string | Yes | "Physician Locator" |
| `Description` | search_context | text | No | "Search location:..." |
| `Custom: NPI__c` | search_context.npi | string | No | "1417980518" |
| `Custom: PhysicianName__c` | search_context.selected_physician.name | string | No | "Dr. Robert Adams" |
| `Custom: Specialty__c` | search_context.specialty | string | No | "Interventional Cardiology" |
| `Custom: SourceSystem__c` | hardcoded | string | Yes | "PhysicianLocator" |

### 4.5.3 Salesforce Experience Cloud Deploy + QA Checklist

- Confirm community site is configured and published in Salesforce Experience Cloud.
- Ensure CORS and `FRONTEND_URL` are set to the Experience domain.
- Set env vars: `SF_OID`, `SF_RET_URL`, `SF_DEBUG_EMAIL` (optional), `LEADS_DIR`, `FRONTEND_URL`.
- Validate `/api/leads` for user form and physician add lead flows.
- Confirm log lines for `Lead saved`, `Pushing to SF`, and success/failure statuses.
- Verify Salesforce lead records include the required field mappings and custom patient detail fields.


### 4.5.3 Salesforce Experience Cloud Deploy + QA Checklist

- Confirm community site is configured and published in Salesforce Experience Cloud.
- Ensure CORS and `FRONTEND_URL` are set to the Experience domain.
- Set env vars: `SF_OID`, `SF_RET_URL`, `SF_DEBUG_EMAIL` (optional), `LEADS_DIR`, `FRONTEND_URL`.
- Validate `/api/leads` for user form and physician add lead flows.
- Confirm log lines for `Lead saved`, `Pushing to SF`, and success/failure statuses.
- Verify Salesforce lead records include the required field mappings and custom fields.

                'organization': str (opt),
                'title': str (opt),
                'search_context': dict (opt),
                'physician': dict (opt)
            }
        
        Returns:
            {
                'success': bool,
                'sf_lead_id': str (if success),
                'error': str (if failure)
            }
        """
        
        access_token, instance_url = self.oauth.get_valid_access_token()
        
        # Build Salesforce Lead payload
        sf_lead = {
            'FirstName': lead_data['first_name'],
            'LastName': lead_data['last_name'],
            'Email': lead_data['email'],
            'LeadSource': 'PhysicianLocator',
            'Status': 'Open - Not Contacted'
        }
        
        # Optional fields
        if lead_data.get('phone'):
            sf_lead['Phone'] = lead_data['phone']
        
        if lead_data.get('organization'):
            sf_lead['Company'] = lead_data['organization']
        
        if lead_data.get('title'):
            sf_lead['Title'] = lead_data['title']
        
        # Custom fields (if configured in Salesforce org)
        physician = lead_data.get('physician', {})
        if physician.get('npi'):
            sf_lead['NPI__c'] = physician['npi']
        if physician.get('name'):
            sf_lead['PhysicianName__c'] = physician['name']
        if physician.get('specialty'):
            sf_lead['Specialty__c'] = physician['specialty']
        
        search_ctx = lead_data.get('search_context', {})
        if search_ctx.get('radius_miles'):
            sf_lead['SearchRadius__c'] = search_ctx['radius_miles']
        
        # Build description from search context
        description_parts = []
        if search_ctx.get('specialties'):
            description_parts.append(
                f"Specialties: {', '.join(search_ctx['specialties'])}"
            )
        if search_ctx.get('location'):
            description_parts.append(f"Location: {search_ctx['location']}")
        if search_ctx.get('results_found'):
            description_parts.append(f"Results Found: {search_ctx['results_found']}")
        
        if description_parts:
            sf_lead['Description'] = '\n'.join(description_parts)
        
        sf_lead['SourceSystem__c'] = 'PhysicianLocator'
        
        # Make API call
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        url = f"{instance_url}/services/data/{self.api_version}/sobjects/Lead"
        
        try:
            response = requests.post(
                url,
                json=sf_lead,
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 201:
                result = response.json()
                return {
                    'success': True,
                    'sf_lead_id': result['id'],
                    'sf_url': f"{instance_url}/{result['id']}"
                }
            
            elif response.status_code == 401:
                # Token expired, refresh and retry
                self.oauth.refresh_access_token()
                return self.create_lead(lead_data)  # Retry
            
            else:
                return {
                    'success': False,
                    'error': f'Salesforce API error: {response.status_code}',
                    'details': response.json()
                }
        
        except requests.Timeout:
            return {
                'success': False,
                'error': 'Salesforce API timeout',
                'retryable': True
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'retryable': False
            }
    
    def update_lead(self, sf_lead_id, updates):
        """Update existing Salesforce lead"""
        
        access_token, instance_url = self.oauth.get_valid_access_token()
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        url = f"{instance_url}/services/data/{self.api_version}/sobjects/Lead/{sf_lead_id}"
        
        try:
            response = requests.patch(
                url,
                json=updates,
                headers=headers,
                timeout=15
            )
            
            if response.status_code in [200, 204]:
                return {'success': True}
            else:
                return {
                    'success': False,
                    'error': f'Update failed: {response.status_code}',
                    'details': response.json()
                }
        
        except Exception as e:
            return {'success': False, 'error': str(e)}
```

### 4.5.3 Sync Strategy & Retry Logic

**Sync Process**:
```python
class LeadSyncManager:
    """Manage lead synchronization to Salesforce"""
    
    def __init__(self, lead_storage, sf_api, max_retries=3):
        self.lead_storage = lead_storage
        self.sf_api = sf_api
        self.max_retries = max_retries
    
    def sync_lead_to_salesforce(self, lead_id):
        """
        Sync lead to Salesforce with exponential backoff retry
        
        Retry Logic:
        - Attempt 1: Immediate
        - Attempt 2: 30 seconds (if retryable error)
        - Attempt 3: 5 minutes (if retryable error)
        - Attempt 4: 1 hour (background job)
        """
        
        lead_record = self.lead_storage.get_lead(lead_id)
        
        # Skip if already synced
        if lead_record['salesforce_sync']['status'] == 'synced':
            return {'success': True, 'reason': 'already_synced'}
        
        # Prepare lead data for Salesforce
        physican_info = lead_record['search_context'].get('selected_physician', {})
        sf_lead_data = {
            'first_name': lead_record['contact_info']['first_name'],
            'last_name': lead_record['contact_info']['last_name'],
            'email': lead_record['contact_info']['email'],
            'phone': lead_record['contact_info'].get('phone'),
            'organization': lead_record['contact_info'].get('organization'),
            'title': lead_record['contact_info'].get('title'),
            'search_context': lead_record['search_context'],
            'physician': physican_info
        }
        
        # Attempt sync with retries
        for attempt in range(1, self.max_retries + 1):
            app.logger.info(
                f'Syncing lead {lead_id} (attempt {attempt}/{self.max_retries})'
            )
            
            result = self.sf_api.create_lead(sf_lead_data)
            
            if result['success']:
                # Update lead with Salesforce ID
                self.lead_storage.update_lead(lead_id, {
                    'salesforce_sync': {
                        'status': 'synced',
                        'sf_lead_id': result['sf_lead_id'],
                        'synced_at': datetime.utcnow().isoformat(),
                        'sync_attempts': attempt,
                        'last_error': None
                    },
                    'activity': {
                        'action': 'salesforce_synced',
                        'details': f'Synced to Salesforce (ID: {result["sf_lead_id"]})'
                    }
                })
                
                app.logger.info(f'Lead {lead_id} synced successfully')
                return {'success': True, 'sf_lead_id': result['sf_lead_id']}
            
            elif not result.get('retryable'):
                # Non-retryable error
                self.lead_storage.update_lead(lead_id, {
                    'salesforce_sync': {
                        'status': 'failed',
                        'sync_attempts': attempt,
                        'last_error': result.get('error', 'Unknown error'),
                        'synced_at': None
                    },
                    'activity': {
                        'action': 'salesforce_sync_failed',
                        'details': f'Non-retryable error: {result.get("error")}'
                    }
                })
                
                app.logger.error(
                    f'Lead {lead_id} sync failed (non-retryable): {result.get("error")}'
                )
                return {'success': False, 'error': result.get('error')}
            
            elif attempt < self.max_retries:
                # Retryable error, wait and retry
                wait_time = 2 ** (attempt - 1) * 30  # 30s, 60s, 120s
                
                app.logger.warning(
                    f'Lead {lead_id} sync failed, retrying in {wait_time}s: '
                    f'{result.get("error")}'
                )
                
                self.lead_storage.update_lead(lead_id, {
                    'salesforce_sync': {
                        'status': 'pending_retry',
                        'sync_attempts': attempt,
                        'last_error': result.get('error'),
                        'next_retry': (
                            datetime.utcnow() + timedelta(seconds=wait_time)
                        ).isoformat()
                    }
                })
                
                time.sleep(wait_time)
            
            else:
                # Max retries exceeded
                self.lead_storage.update_lead(lead_id, {
                    'salesforce_sync': {
                        'status': 'retry_exhausted',
                        'sync_attempts': attempt,
                        'last_error': result.get('error')
                    },
                    'activity': {
                        'action': 'salesforce_sync_exhausted',
                        'details': f'Max retries ({self.max_retries}) exhausted'
                    }
                })
                
                app.logger.error(
                    f'Lead {lead_id} sync failed, max retries exhausted'
                )
                return {
                    'success': False,
                    'error': 'Max retries exhausted',
                    'requires_manual_intervention': True
                }
```

### 4.5.4 Webhook Handling (Salesforce → Physician Locator)

**Use Case**: Receive status updates from Salesforce (e.g., lead converted)

```python
from flask import request
from hmac import HMAC, compare_digest
from hashlib import sha256

class SalesforceWebhookHandler:
    """Handle incoming Salesforce webhooks"""
    
    def __init__(self, webhook_secret):
        self.webhook_secret = webhook_secret.encode()
    
    def verify_request(self, body, signature):
        """Verify webhook signature"""
        
        expected_sig = HMAC(
            self.webhook_secret,
            body,
            sha256
        ).hexdigest()
        
        return compare_digest(signature, expected_sig)
    
    @app.route('/webhooks/salesforce', methods=['POST'])
    def handle_webhook(self):
        """
        Receive webhook from Salesforce
        
        Event Types:
        - Lead Status Changed
        - Lead Converted
        - Lead Deleted
        - Custom field updated
        """
        
        # Verify request signature
        signature = request.headers.get('X-Salesforce-Signature')
        if not signature or not self.verify_request(request.data, signature):
            app.logger.warning('Invalid webhook signature')
            return jsonify({'error': 'Invalid signature'}), 401
        
        data = request.get_json()
        event_type = data.get('event_type')
        sf_lead_id = data.get('data', {}).get('sf_lead_id')
        
        app.logger.info(f'Salesforce webhook: {event_type} for lead {sf_lead_id}')
        
        try:
            if event_type == 'lead_status_changed':
                self._handle_status_change(sf_lead_id, data)
            
            elif event_type == 'lead_converted':
                self._handle_conversion(sf_lead_id, data)
            
            elif event_type == 'lead_deleted':
                self._handle_deletion(sf_lead_id, data)
            
            return jsonify({'success': True})
        
        except Exception as e:
            app.logger.error(f'Webhook processing failed: {str(e)}')
            return jsonify({'error': 'Processing failed'}), 500
    
    def _handle_status_change(self, sf_lead_id, data):
        """Update lead status when Salesforce status changes"""
        
        # Find local lead by SF ID
        leads, _ = LeadStorage().list_leads(limit=10000)
        local_lead = next(
            (l for l in leads if l.get('salesforce_sync', {}).get('sf_lead_id') == sf_lead_id),
            None
        )
        
        if not local_lead:
            app.logger.warning(f'Local lead not found for SF ID {sf_lead_id}')
            return
        
        new_status = data.get('data', {}).get('new_status')
        
        LeadStorage().update_lead(local_lead['id'], {
            'salesforce_sync': {
                'status': new_status
            },
            'activity': {
                'action': 'salesforce_status_updated',
                'details': f'Salesforce status: {new_status}'
            }
        })
    
    def _handle_conversion(self, sf_lead_id, data):
        """Mark lead as converted"""
        
        leads, _ = LeadStorage().list_leads(limit=10000)
        local_lead = next(
            (l for l in leads if l.get('salesforce_sync', {}).get('sf_lead_id') == sf_lead_id),
            None
        )
        
        if local_lead:
            LeadStorage().update_lead(local_lead['id'], {
                'salesforce_sync': {'status': 'converted'},
                'activity': {
                    'action': 'lead_converted',
                    'details': f'Lead converted in Salesforce'
                }
            })
    
    def _handle_deletion(self, sf_lead_id, data):
        """Mark as deleted if removed from Salesforce"""
        
        leads, _ = LeadStorage().list_leads(limit=10000)
        local_lead = next(
            (l for l in leads if l.get('salesforce_sync', {}).get('sf_lead_id') == sf_lead_id),
            None
        )
        
        if local_lead:
            LeadStorage().update_lead(local_lead['id'], {
                'salesforce_sync': {'status': 'deleted'},
                'activity': {
                    'action': 'salesforce_lead_deleted',
                    'details': 'Lead deleted in Salesforce'
                }
            })
```

---

## 5. Deployment Architecture

### 5.1 Backend Deployment (Render)

**Platform**: render.com (PaaS)

**Configuration Files**:

**Procfile** (`backend/Procfile`):
```
web: gunicorn backend.app:app --workers 4 --worker-class sync --log-level info --bind 0.0.0.0:8080
```

**render.yaml** (`backend/render.yaml`):
```yaml
services:
  - type: web
    name: physician-locator-api
    env: python
    region: us-east
    plan: standard
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn backend.app:app --workers 4 --timeout 30
    envVars:
      - key: FLASK_ENV
        value: production
      - key: MAPQUEST_API_KEY
        sync: false
      - key: GEOAPIFY_API_KEY
        sync: false
      - key: FRONTEND_URL
        value: https://physician-locator.vercel.app
      - key: SF_OID
        sync: false
      - key: LEADS_DIR
        value: /tmp/leads
```

**Dockerfile** (optional, for local testing):
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY us_zip_db.json .

EXPOSE 8080

CMD ["gunicorn", "app:app", "--workers=4", "--bind=0.0.0.0:8080"]
```

### 5.2 Frontend Deployment (Vercel)

**Platform**: vercel.com (Static hosting + edge)

**Configuration Files**:

**vercel.json** (`frontend/vercel.json`):
```json
{
  "buildCommand": "bash build.sh",
  "outputDirectory": ".",
  "routes": [
    {
      "src": "/.*",
      "dest": "/index.html"
    }
  ],
  "env": {
    "REACT_APP_API_URL": "https://physician-locator-api.onrender.com"
  },
  "headers": [
    {
      "source": "/index.html",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "no-cache, no-store, must-revalidate"
        }
      ]
    },
    {
      "source": "/static/(.*)",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=31536000, immutable"
        }
      ]
    }
  ]
}
```

**build.sh** (`frontend/build.sh`):
```bash
#!/bin/bash
# Minimal build script (index.html is already complete)
echo "Frontend building..."
```

### 5.3 Environment Variables

**Backend (.env)**:
```bash
# Required
MAPQUEST_API_KEY=<obtained from MapQuest dashboard>
GEOAPIFY_API_KEY=<obtained from Geoapify dashboard>
FRONTEND_URL=https://physician-locator.vercel.app

# Optional (Salesforce integration)
SF_OID=<Salesforce org domain>
SF_DEBUG_EMAIL=test@example.com
DEBUG_SECRET=<random string for debug endpoints>

# Deployment
FLASK_ENV=production
LEADS_DIR=/tmp/leads
```

### 5.4 Monitoring & Logging

**Render Logs**:
- All output to stdout/stderr automatically captured
- Request logging with request_id
- Error tracking and alerting

**Health Checks**:
```
GET /
GET /api/autocomplete?text=test
```

---

## 5.5 Exception Handling & Custom Error Classes

### 5.5.1 Exception Hierarchy

**Error Class Structure**:
```python
# Base Exception
class PhysicianLocatorError(Exception):
    """Base exception for all application errors"""
    def __init__(self, message, code=None, details=None):
        self.message = message
        self.code = code or "UNKNOWN_ERROR"
        self.details = details or {}
        super().__init__(self.message)

# Lead-related Exceptions
class LeadError(PhysicianLocatorError):
    """Base exception for lead-related errors"""
    pass

class LeadNotFoundError(LeadError):
    """Lead record not found"""
    pass

class LeadStorageError(LeadError):
    """Error saving/retrieving lead from storage"""
    pass

class LeadValidationError(LeadError):
    """Lead data validation failed"""
    pass

class LeadDuplicateError(LeadError):
    """Lead already exists"""
    pass

# Salesforce-related Exceptions
class SalesforceError(PhysicianLocatorError):
    """Base exception for Salesforce integration errors"""
    pass

class SalesforceAuthError(SalesforceError):
    """Salesforce authentication failed"""
    pass

class SalesforceAPIError(SalesforceError):
    """Salesforce API call failed"""
    pass

class SalesforceFieldMappingError(SalesforceError):
    """Error mapping fields to Salesforce Lead object"""
    pass

class SalesforceTokenExpiredError(SalesforceError):
    """Salesforce access token expired"""
    pass

# External API Exceptions
class GeoapifyError(PhysicianLocatorError):
    """Geoapify API error"""
    pass

class NPPESError(PhysicianLocatorError):
    """NPPES Registry API error"""
    pass

class GeocodingError(PhysicianLocatorError):
    """Address geocoding failed"""
    pass

# Validation Exceptions
class ValidationError(PhysicianLocatorError):
    """Input validation failed"""
    pass

class EmailValidationError(ValidationError):
    """Invalid email address"""
    pass

class AddressValidationError(ValidationError):
    """Invalid address"""
    pass

class CoordinateValidationError(ValidationError):
    """Invalid geographic coordinates"""
    pass
```

### 5.5.2 Global Error Handler

```python
from flask import jsonify

@app.errorhandler(PhysicianLocatorError)
def handle_app_error(error):
    """Handle custom application errors"""
    
    response = {
        'error': error.message,
        'code': error.code,
        'request_id': g.request_id,
        'status': 'error'
    }
    
    if error.details:
        response['details'] = error.details
    
    # Log error
    app.logger.error(
        f'{error.code}: {error.message}',
        extra={'request_id': g.request_id, 'details': error.details}
    )
    
    # Determine HTTP status code
    status_code_map = {
        'VALIDATION_ERROR': 400,
        'LEAD_NOT_FOUND': 404,
        'LEAD_DUPLICATE': 409,
        'SALESFORCE_AUTH_ERROR': 401,
        'SALESFORCE_API_ERROR': 502,
        'GEOAPIFY_ERROR': 502,
        'NPPES_ERROR': 502,
        'INTERNAL_ERROR': 500,
    }
    
    status_code = status_code_map.get(error.code, 500)
    return jsonify(response), status_code

@app.errorhandler(Exception)
def handle_unexpected_error(error):
    """Handle unexpected errors"""
    
    app.logger.error(
        f'Unexpected error: {str(error)}',
        extra={'request_id': g.request_id},
        exc_info=True
    )
    
    return jsonify({
        'error': 'Internal server error',
        'code': 'INTERNAL_ERROR',
        'request_id': g.request_id,
        'status': 'error'
    }), 500
```

### 5.5.3 Error Response Examples

**Lead Validation Error (400)**:
```json
{
  "error": "Lead validation failed",
  "code": "LEAD_VALIDATION_ERROR",
  "request_id": "a1b2c3d4",
  "details": {
    "first_name": "required",
    "email": "invalid format"
  },
  "status": "error"
}
```

**Lead Duplicate Error (409)**:
```json
{
  "error": "Lead already exists",
  "code": "LEAD_DUPLICATE",
  "request_id": "a1b2c3d4",
  "details": {
    "existing_lead_id": "lead_20260325143521456789",
    "existing_email": "john@example.com"
  },
  "status": "error"
}
```

**Salesforce Authentication Error (401)**:
```json
{
  "error": "Salesforce authentication required",
  "code": "SALESFORCE_AUTH_ERROR",
  "request_id": "a1b2c3d4",
  "details": {
    "reason": "No valid access token",
    "retry": true
  },
  "status": "error"
}
```

**Salesforce API Error (502)**:
```json
{
  "error": "Salesforce API error",
  "code": "SALESFORCE_API_ERROR",
  "request_id": "a1b2c3d4",
  "details": {
    "sf_status": 400,
    "sf_error": "REQUIRED_FIELD_MISSING",
    "sf_message": "Required field missing: [Email]",
    "retryable": false
  },
  "status": "error"
}
```

---

## 6. Security Architecture

### 6.1 Input Validation & Sanitization

**Tier 1: Client-Side**:
- Form validation (required fields, email format)
- Character limits
- No sensitive data in URLs (POST for forms)

**Tier 2: Server-Side**:
```python
# HTML escaping (prevent XSS)
import html
sanitized = html.escape(user_input)

# Length validation
if len(value) > 80:
    raise ValueError('Input too long')

# Email validation
import re
if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
    raise ValueError('Invalid email')

# Number validation
lat = float(request.args.get('lat'))
radius = int(request.args.get('radius'))
if radius < 5 or radius > 100:
    raise ValueError('Invalid radius')
```

### 6.2 API Security

**CORS Configuration**:
```python
CORS(app, 
    origins=[Config.FRONTEND_URL],
    methods=['GET', 'POST', 'OPTIONS'],
    allow_headers=['Content-Type', 'X-Request-ID'],
    supports_credentials=False
)
```

**Rate Limiting**:
- Per-IP tracking in-memory
- Automatic time-window cleanup
- Configured per endpoint

**HTTPS**:
- All traffic encrypted in transit
- Redirect HTTP → HTTPS
- Enforced at Render/Vercel level

### 6.3 Data Protection

**Lead Data**:
- Stored in JSON files (encrypted at rest if configured)
- File permissions: 0600 (read/write by app only)
- Backup strategy: Versioned in Salesforce

**API Keys**:
- Never in code, always in environment variables
- Render secrets automatically injected
- Vercel environment variables encrypted at rest

**User PII**:
- Physician data: Public NPPES records (no sensitive info)
- Lead data: Required for CRM sync, optional email

---

## 7. Performance Optimization

### 7.1 Frontend Performance

**Optimization Strategies**:

| Technique | Implementation | Benefit |
|-----------|----------------|---------|
| **Lazy Rendering** | Render cards on-demand (not all at once) | Faster initial render (9 cards vs 1,000) |
| **Event Delegation** | Single listener for card clicks | Reduced memory footprint |
| **Debouncing** | Autocomplete requests throttled 300ms | Reduced API calls (100 → 20 per session) |
| **CSS Animations** | Hardware-accelerated (transform/opacity) | 60fps smooth animations |
| **Image Optimization** | SVG pins (vector, scalable) | Small file size, sharp at any resolution |
| **Caching** | Client-side geocode cache | Instant re-searches (no API call) |
| **Gzip Compression** | HTML, CSS, JS all gzipped | 45KB → 15KB (index.html) |
| **No Build Step** | Vanilla JS, no React/Babel | Fast initial load (no transpiling) |

**Metrics**:
- Initial load: ~1.2s (gzipped HTML)
- Search response: ~2-3s (backend-dependent)
- Map render: ~350ms
- Card grid render: ~600ms

### 7.2 Backend Performance

**Optimization Strategies**:

| Technique | Implementation | Benefit |
|-----------|----------------|---------|
| **In-Memory Caching** | ZIP DB + taxonomy loaded at startup | Sub-10ms lookups |
| **Spatial Indexing** | KD-tree for ZIP proximity | Fast radius searches |
| **Geocode Cache** | LRU cache (2,000 entries) | Prevents redundant API calls |
| **Request Batching** | NPI queries grouped by ZIP | Reduced API overhead |
| **Connection Pooling** | requests library with Session | Reused HTTP connections |
| **Async-Ready** | Synchronous now, async-upgradeable later | Blocking allowed on simple operations |

**Gunicorn Tuning**:
- Workers: 4 (configurable per instance size)
- Threads: 2 per worker
- Timeout: 30 seconds
- Max requests: 1,000 (reload to prevent memory leak)

### 7.3 Database Query Optimization

**ZIP Lookup**:
- Time: O(log n) KD-tree query on 41k ZIPs
- Result: ~50 ZIPs per search
- Caching: None (data immutable)

**Taxonomy Lookup**:
- Time: O(1) dictionary lookup
- Result: 1-5 taxonomy codes per specialty
- Caching: In-memory (702 entries loaded once)

**NPPES Query**:
- Time: ~2-3s per ZIP (external API)
- Batching: 1 ZIP at a time (50 parallel requests worst-case)
- Caching: None (live data)

---

## 9. Detailed Error Handling & Observability (Part 2)

**Format** (stdout):
```
2026-03-25 14:32:15,123 [a1b2c3d4] INFO: GET /api/search
2026-03-25 14:32:15,234 [a1b2c3d4] INFO: Querying 47 nearby ZIPs
2026-03-25 14:32:15,945 [a1b2c3d4] INFO: Found 127 physicians
2026-03-25 14:32:16,023 [a1b2c3d4] INFO: Returning 100 results (127 total)
2026-03-25 14:32:16,023 [a1b2c3d4] INFO: Response time: 900ms
```

**Key Fields**:
- Timestamp (ISO 8601)
- Request ID (UUID v4, first 8 chars)
- Log level (INFO, WARNING, ERROR)
- Message

### 8.3 Alerting

**Conditions**:
- Response time > 10s
- Error rate > 5%
- Rate limiter blocking > 100 IPs/hour
- Geoapify quota exceeded (429)
- NPPES API timeout

**Channels**:
- Email (critical)
- Slack (warnings)
- Dashboard (all)

---

## 8. Configuration Management

### 8.1 Environment-Based Configuration

**Development Environment** (.env.development):
```bash
FLASK_ENV=development
DEBUG=true
MAPQUEST_API_KEY=pk.test_xyz...
GEOAPIFY_API_KEY=geoapify-test...
FRONTEND_URL=http://localhost:3000
SF_OID=sandbox.salesforce.com
SF_DEBUG_EMAIL=test@example.com
DEBUG_SECRET=dev-secret-key
LEADS_DIR=./leads_dev
LOG_LEVEL=DEBUG
```

**Production Environment** (.env.production):
```bash
FLASK_ENV=production
DEBUG=false
MAPQUEST_API_KEY=pk.prod_xyz...
GEOAPIFY_API_KEY=geoapify-prod...
FRONTEND_URL=https://physician-locator.vercel.app
SF_OID=login.salesforce.com
SF_CLIENT_ID=3MVG...
SF_CLIENT_SECRET=***hidden***
SF_TOKENS_FILE=/secure/sf_tokens.json
LEADS_DIR=/var/data/leads
LOG_LEVEL=INFO
SENTRY_DSN=https://key@sentry.io/project
```

**Configuration Class**:
```python
import os
from pathlib import Path

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
    
    # API Keys
    MAPQUEST_API_KEY = os.environ.get('MAPQUEST_API_KEY')
    GEOAPIFY_API_KEY = os.environ.get('GEOAPIFY_API_KEY')
    
    # URLs
    FRONTEND_URL = os.environ.get('FRONTEND_URL')
    
    # Salesforce
    SF_OID = os.environ.get('SF_OID')
    SF_CLIENT_ID = os.environ.get('SF_CLIENT_ID')
    SF_CLIENT_SECRET = os.environ.get('SF_CLIENT_SECRET')
    SF_TOKENS_FILE = os.environ.get('SF_TOKENS_FILE', '/tmp/sf_tokens.json')
    SF_DEBUG_EMAIL = os.environ.get('SF_DEBUG_EMAIL')
    
    # Storage
    LEADS_DIR = os.environ.get('LEADS_DIR', '/tmp/leads')
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    SENTRY_DSN = os.environ.get('SENTRY_DSN')
    
    # Rate Limiting
    RATE_LIMITS = {
        '/api/autocomplete': {'limit': 120, 'window': 60},
        '/api/geocode': {'limit': 120, 'window': 60},
        '/api/search': {'limit': 30, 'window': 60},
        '/api/leads': {'limit': 5, 'window': 60}
    }
    
    # Timeouts (seconds)
    EXTERNAL_API_TIMEOUT = 10
    SALESFORCE_API_TIMEOUT = 15
    REQUEST_TIMEOUT = 30
    
    # Data Limits
    MAX_RESULTS_PER_SEARCH = 1000
    MAX_RESULTS_DISPLAY = 10
    GEOCODE_CACHE_SIZE = 2000
    MAX_DESCRIPTION_LENGTH = 120
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        required = ['MAPQUEST_API_KEY', 'GEOAPIFY_API_KEY', 'FRONTEND_URL']
        missing = [k for k in required if not getattr(cls, k)]
        
        if missing:
            raise ValueError(f'Missing required config: {", ".join(missing)}')
        
        return True

# Environment-specific configs
class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

class TestingConfig(Config):
    DEBUG = True
    TESTING = True
    PRESERVE_CONTEXT_ON_EXCEPTION = False
```

---

##  8.2 Advanced Caching Strategies

### Geocode Cache (LRU)

```python
from functools import lru_cache
from datetime import datetime, timedelta
import threading

class GeocodingCache:
    """LRU cache for geocoding results"""
    
    def __init__(self, max_size=2000, ttl_hours=24):
        self.max_size = max_size
        self.ttl = timedelta(hours=ttl_hours)
        self.cache = {}
        self.timestamps = {}
        self.lock = threading.RLock()
    
    def get(self, address):
        """Get cached geocoding result"""
        with self.lock:
            if address in self.cache:
                # Check TTL
                created = self.timestamps[address]
                if datetime.utcnow() - created < self.ttl:
                    return self.cache[address]
                else:
                    # Expired, remove
                    del self.cache[address]
                    del self.timestamps[address]
            return None
    
    def set(self, address, coordinates):
        """Cache geocoding result"""
        with self.lock:
            if len(self.cache) >= self.max_size:
                # Remove oldest entry
                oldest_key = min(
                    self.timestamps,
                    key=self.timestamps.get
                )
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]
            
            self.cache[address] = coordinates
            self.timestamps[address] = datetime.utcnow()
    
    def clear_expired(self):
        """Remove expired entries"""
        with self.lock:
            now = datetime.utcnow()
            expired = [
                k for k, t in self.timestamps.items()
                if now - t > self.ttl
            ]
            for k in expired:
                del self.cache[k]
                del self.timestamps[k]
    
    def stats(self):
        """Get cache statistics"""
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hit_rate': self._calculate_hit_rate()
        }
    
    def _calculate_hit_rate(self):
        """Calculate hit/miss ratio"""
        if not hasattr(self, 'hits'):
            self.hits = 0
        if not hasattr(self, 'misses'):
            self.misses = 0
        
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0

# Global geocoding cache instance
geocoding_cache = GeocodingCache(max_size=2000, ttl_hours=24)

@app.route('/api/geocode', methods=['GET'])
def geocode():
    address = request.args.get('address', '').strip()
    
    # Check cache first
    cached = geocoding_cache.get(address)
    if cached:
        app.logger.info(f'Geocode cache hit: {address}')
        return jsonify(cached)
    
    # Call Geoapify
    response = requests.get(...)
    result = response.json()
    
    # Cache result
    geocoding_cache.set(address, result)
    
    return jsonify(result)
```

### Taxonomy Index Cache

```python
class TaxonomyCache:
    """In-memory taxonomy lookup cache"""
    
    def __init__(self):
        self.code_to_desc = {}  # code → description
        self.desc_to_codes = {}  # description → [codes]
        self.loaded = False
    
    def load(self):
        """Load taxonomy from data source"""
        # Hard-coded NUCC taxonomy (702 entries)
        taxonomy_data = {
            '207S00000X': 'Cardiology',
            '202Y00000X': 'Interventional Cardiology',
            # ... 700+ more
        }
        
        self.code_to_desc = taxonomy_data
        
        # Build reverse index for faster searching
        for code, desc in taxonomy_data.items():
            desc_lower = desc.lower()
            if desc_lower not in self.desc_to_codes:
                self.desc_to_codes[desc_lower] = []
            self.desc_to_codes[desc_lower].append(code)
        
        self.loaded = True
        app.logger.info(f'Loaded {len(self.code_to_desc)} taxonomy entries')
    
    def search(self, query):
        """Search for specialty by name (case-insensitive substring match)"""
        if not self.loaded:
            self.load()
        
        query_lower = query.lower()
        results = []
        
        for desc, codes in self.desc_to_codes.items():
            if query_lower in desc:
                for code in codes:
                    results.append({
                        'code': code,
                        'description': self.code_to_desc[code]
                    })
        
        # Sort by relevance (exact match first)
        results.sort(
            key=lambda x: (
                x['description'].lower() != query_lower,  # Exact match = 0
                x['description']  # Then alphabetical
            )
        )
        
        return results
    
    def get_by_code(self, code):
        """Get description by code"""
        if not self.loaded:
            self.load()
        return self.code_to_desc.get(code)

# Global taxonomy cache instance
taxonomy_cache = TaxonomyCache()
taxonomy_cache.load()
```

---

## 8.3 Monitoring & Metrics

### Application Metrics

```python
from dataclasses import dataclass
from datetime import datetime
import json

@dataclass
class MetricEvent:
    """Single metric data point"""
    timestamp: str
    metric_name: str
    value: float
    unit: str
    tags: dict
    request_id: str

class MetricsCollector:
    """Collect and export application metrics"""
    
    def __init__(self):
        self.metrics = []
        self.lock = threading.Lock()
    
    def record(self, metric_name, value, unit='count', tags=None, request_id=None):
        """Record a metric"""
        event = MetricEvent(
            timestamp=datetime.utcnow().isoformat(),
            metric_name=metric_name,
            value=value,
            unit=unit,
            tags=tags or {},
            request_id=request_id or 'N/A'
        )
        
        with self.lock:
            self.metrics.append(event)
            
            # Keep only last 10,000 metrics (rolling window)
            if len(self.metrics) > 10000:
                self.metrics = self.metrics[-10000:]
    
    def export(self, format='json'):
        """Export metrics"""
        with self.lock:
            if format == 'json':
                return json.dumps(
                    [m.__dict__ for m in self.metrics],
                    default=str
                )

# Global metrics collector
metrics = MetricsCollector()

# Track metrics in request lifecycle
@app.before_request
def before_request():
    g.start_time = time.time()
    g.request_id = str(uuid.uuid4())[:8]

@app.after_request
def after_request(response):
    if hasattr(g, 'start_time'):
        elapsed = time.time() - g.start_time
        
        metrics.record(
            'request_duration_ms',
            elapsed * 1000,
            unit='milliseconds',
            tags={
                'endpoint': request.endpoint,
                'method': request.method,
                'status': response.status_code
            },
            request_id=g.request_id
        )
    
    return response

# Key Metrics to Track
TRACKED_METRICS = {
    'search_requests': 'Count of /api/search calls',
    'search_duration_ms': 'Time to complete search',
    'physician_count': 'Number of results found',
    'lead_creation_requests': 'Count of /api/leads POST',
    'lead_creation_duration_ms': 'Time to create lead',
    'salesforce_sync_requests': 'Count of SF sync attempts',
    'salesforce_sync_duration_ms': 'Time to sync to Salesforce',
    'geocoding_cache_hit_rate': 'Percentage of geocode cache hits',
    'error_rate': 'Percentage of requests with 4xx/5xx',
    'external_api_latency_ms': 'Response time from NPPES/Geoapify/SF',
}
```

### Health Check Endpoint

```python
@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '2.0',
        'components': {}
    }
    
    # Check data initialization
    try:
        health_status['components']['zip_db'] = {
            'status': 'ready',
            'entries': len(ZIP_DB),
            'last_reload': 'startup'
        }
    except:
        health_status['components']['zip_db'] = {'status': 'error'}
        health_status['status'] = 'degraded'
    
    # Check Geoapify connectivity
    try:
        resp = requests.get(
            'https://api.geoapify.com/v1/staticmap',
            params={'apiKey': Config.GEOAPIFY_API_KEY},
            timeout=5
        )
        health_status['components']['geoapify'] = {
            'status': 'available',
            'response_code': resp.status_code
        }
    except:
        health_status['components']['geoapify'] = {'status': 'unavailable'}
        health_status['status'] = 'degraded'
    
    # Check Salesforce (if configured)
    if Config.SF_OID:
        try:
            oauth = SalesforceOAuth(...)
            oauth.get_valid_access_token()
            health_status['components']['salesforce'] = {'status': 'authenticated'}
        except:
            health_status['components']['salesforce'] = {'status': 'authentication_failed'}
            health_status['status'] = 'degraded'
    else:
        health_status['components']['salesforce'] = {'status': 'not_configured'}
    
    # Check file system (leads storage)
    try:
        Path(Config.LEADS_DIR).mkdir(exist_ok=True)
        health_status['components']['storage'] = {'status': 'writable'}
    except:
        health_status['components']['storage'] = {'status': 'error'}
        health_status['status'] = 'unhealthy'
    
    status_code = 200 if health_status['status'] == 'healthy' else 503
    return jsonify(health_status), status_code
```

---

## 8.4 Data Consistency & ACID Properties

### Lead Creation Atomicity

```python
def create_lead_atomic(lead_data, lead_storage, sf_api=None):
    """
    Create lead with ACID properties
    
    Atomicity: Lead saved to file OR not at all
    Consistency: Lead record valid before save
    Isolation: No partial writes visible
    Durability: Persisted to disk immediately
    """
    
    import fcntl
    
    # Validate lead data
    validator = LeadValidator()
    if not validator.validate(lead_data):
        raise LeadValidationError(
            'Invalid lead data',
            details=validator.errors
        )
    
    lead_id = f'lead_{datetime.utcnow().strftime("%Y%m%d%H%M%S%f")}'
    lead_file = Path(Config.LEADS_DIR) / f'{lead_id}.json'
    lock_file = Path(Config.LEADS_DIR) / f'{lead_id}.lock'
    
    try:
        # Acquire exclusive lock
        with open(lock_file, 'w') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            
            # Build complete lead record
            lead_record = {
                'id': lead_id,
                'type': 'recruiter_lead',
                'source': 'PhysicianLocator',
                'created_at': datetime.utcnow().isoformat(),
                'contact_info': lead_data.get('contact_info', {}),
                'search_context': lead_data.get('search_context', {}),
                'salesforce_sync': {
                    'status': 'pending' if sf_api else 'skipped',
                    'sf_lead_id': None,
                    'sync_attempts': 0,
                    'last_error': None
                },
                'activity_log': [{
                    'timestamp': datetime.utcnow().isoformat(),
                    'action': 'created',
                    'details': 'Lead created'
                }]
            }
            
            # Write to file atomically (write to temp, then rename)
            temp_file = lead_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(lead_record, f, indent=2)
            
            # Atomic rename
            temp_file.replace(lead_file)
            os.chmod(lead_file, 0o600)
            
            # Sync to Salesforce asynchronously (fire and forget)
            if sf_api:
                try:
                    sf_result = sf_api.create_lead(lead_data)
                    if sf_result['success']:
                        # Update sync status
                        with open(lead_file, 'r+') as f:
                            record = json.load(f)
                            record['salesforce_sync']['status'] = 'synced'
                            record['salesforce_sync']['sf_lead_id'] = sf_result['sf_lead_id']
                            f.seek(0)
                            json.dump(record, f, indent=2)
                            f.truncate()
                except Exception as e:
                    app.logger.error(f'SF sync failed for {lead_id}: {str(e)}')
                    # Lead still created locally, SF sync can retry later
        
        return {'success': True, 'lead_id': lead_id}
    
    finally:
        # Release lock
        try:
            lock_file.unlink()
        except:
            pass
```

---

## 9. Testing Strategy

### 9.1 Frontend Testing

**Unit Tests** (future):
- Autocomplete debouncing
- Validation logic
- Distance formatting
- Card rendering

**Integration Tests** (future):
- Search flow end-to-end
- Map interactions
- Detail panel lifecycle
- Lead form submission

**Manual Testing** (current):
- Browser DevTools (network, performance)
- Cross-browser testing (Chrome, Firefox, Safari, Edge)
- Mobile device testing (iOS, Android)
- Accessibility testing (ARIA labels, keyboard nav)

### 9.2 Backend Testing

**Unit Tests** (future):
```python
def test_zipddb_lookup():
    zips = find_nearby_zips(40.7128, -74.0060, 10)
    assert len(zips) > 0
    assert all(z in ZIP_DB for z in zips)

def test_taxonomy_search():
    codes = find_matching_taxonomies(['Cardiology'])
    assert '207S00000X' in codes

def test_rate_limiting():
    for i in range(35):
        response = app.test_client().get('/api/search?...')
    assert response.status_code == 429
```

**Integration Tests** (future):
```python
def test_search_flow():
    # Geocode address
    resp = app.test_client().get('/api/geocode?address=NYC')
    assert resp.status_code == 200
    lat, lng = resp.json['lat'], resp.json['lng']
    
    # Search physicians
    resp = app.test_client().get(f'/api/search?lat={lat}&lng={lng}&radius=10&descriptions=["Cardiology"]')
    assert resp.status_code == 200
    assert 'physicians' in resp.json
    assert len(resp.json['physicians']) > 0

def test_lead_creation():
    resp = app.test_client().post('/api/leads', json={
        'first_name': 'John',
        'last_name': 'Doe',
        'email': 'john@example.com'
    })
    assert resp.status_code == 200
    assert 'lead_id' in resp.json
```

**Load Testing** (future):
- Simulate 100 concurrent users
- 1,000 searches/minute
- Monitor response times and error rates

---

## 10. Development Workflow

### 10.1 Local Development Setup

**Prerequisites**:
```bash
# Install Python 3.9+
python --version

# Install Node.js (for running local dev server)
node --version
```

**Backend Setup**:
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with API keys

# Run Flask development server
flask run --debug
# http://localhost:5000
```

**Frontend Setup**:
```bash
cd frontend

# Serve with Python simple HTTP server (or use live-server npm package)
python -m http.server 3000

# Or use live-server for auto-reload
npx live-server --port=3000
```

**Testing in Browser**:
- Frontend: http://localhost:3000
- Backend: http://localhost:5000
- DevTools: F12 (network, console, performance)

### 10.2 Code Quality

**Linting** (future):
```bash
# Backend
pylint backend/app.py
flake8 backend/app.py

# Frontend
eslint frontend/index.html
# (Using HTML embedded script linting)
```

**Formatting**:
```bash
# Python formatting
black backend/app.py

# No official formatter for vanilla JS (consider prettier)
```

### 10.3 Git Workflow

**Branches**:
- `main`: Production-ready code
- `develop`: Integration branch
- `feature/xyz`: Feature branches
- `bugfix/xyz`: Bug fix branches
- `hotfix/xyz`: Critical fixes

**Commit Convention**:
```
feat(frontend): Add physician detail panel
fix(backend): Fix ZIP lookup radius calculation
docs(spec): Update functional specification
perf(frontend): Debounce autocomplete requests
refactor(backend): Extract rate limiting to decorator
```

---

## 11. Troubleshooting & Known Issues

### 11.1 Common Issues

| Issue | Root Cause | Solution |
|-------|-----------|----------|
| **Autocomplete not working** | Geoapify API 429 error | Wait 24 hours (3k/day limit) or upgrade plan |
| **Search returns 0 results** | No physicians in ZIP range | Expand radius, try different specialty |
| **Map not displaying markers** | MapQuest JS CDN error | Check MAPQUEST_API_KEY, verify CDN accessible |
| **Lead not in Salesforce** | SF_OID not configured | Set SF_OID in env, verify Salesforce creds |
| **Slow search response** | NPPES API timeout | Reduce radius, wait for retry |
| **CORS errors** | Frontend URL not in CORS_ORIGINS | Update FRONTEND_URL env var, restart backend |

### 11.2 Debug Mode

**Enable Debug Logging**:
```bash
FLASK_ENV=development flask run --debug
```

**Test Lead Endpoint**:
```bash
curl -X POST http://localhost:5000/api/lead-debug \
  -H "Content-Type: application/json" \
  -H "X-Debug-Secret: YOUR_SECRET" \
  -d '{"first_name":"John","last_name":"Doe","email":"test@example.com"}'
```

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-15 | Initial technical specification |
| 1.5 | 2026-02-20 | Added deployment architecture, added monitoring |
| 2.0 | 2026-03-25 | Added full API implementation details, performance optimizations, error handling |

---

**End of Technical Specification**

For technical questions: engineering@aquarient.com
