# Functional Specification: Physician Locator — Aquarient

**Version**: 2.0  
**Date**: March 25, 2026  
**Status**: Production  
**Owner**: Aquarient  

---

## 1. Executive Summary

**Physician Locator** is a web-based search platform for locating licensed US physicians across all 50 states using the official NPPES (National Plan and Provider Enumeration System) registry. The application combines powerful location-based search, interactive mapping, and lead capture capabilities to enable users to discover healthcare providers by specialty and geography.

### Key Value Propositions
- **Complete NPPES Coverage**: Access to 6M+ licensed physicians
- **Smart Location Services**: Address autocomplete + geocoding
- **Interactive Mapping**: MapQuest-powered visualization with numbered pins
- **Lead Capture Ready**: Seamless integration with Salesforce CRM
- **High Performance**: Sub-2 second search response times, production-grade reliability

---

## 2. Product Overview

### 2.1 User Personas

**Primary Users**:
- Healthcare recruiters sourcing physicians
- Medical staffing agencies
- Market research analysts
- Hospital administration teams

**Secondary Users**:
- Individual physicians searching competitors
- Health insurance companies
- Pharmaceutical sales representatives

### 2.2 Core Problem Statement

Users currently lack a unified, intuitive interface to search and filter physicians by specialty and location while viewing them on an interactive map. Existing solutions are fragmented, slow, or require API knowledge.

### 2.3 Solution Overview

Physician Locator provides:
1. **Unified Interface**: Single search form for location + specialty
2. **Real-time Results**: Progressive loading with live map updates
3. **Rich Visualization**: Interactive map with numbered markers
4. **Detailed Profiles**: Physician cards with contact info, specialties, NPI
5. **Lead Management**: One-click physician-to-lead conversion for CRM integration

---

## 3. Functional Requirements

### 3.1 Search & Discovery

#### 3.1.1 Address Input with Autocomplete
- **Trigger**: User types in "Address / Location" field
- **Minimum Characters**: 2 characters activate autocomplete
- **Data Source**: Geoapify API
- **Results**: 7 suggestions with formatted addresses
- **Selection**: Click suggestion → populate lat/lng coordinates
- **Validation**: Address must resolve to US location only

**Example Flow**:
```
User Input: "New York"
↓
API Call: /api/autocomplete?text=New York
↓
Results: 
  1. New York, NY (lat: 40.7128, lng: -74.0060)
  2. New York, PA (lat: 40.8064, lng: -75.0616)
  ...
↓
User Selects: "New York, NY"
↓
State: lat=40.7128, lng=-74.0060, address="New York, NY"
```

#### 3.1.2 Search Radius Selection
- **Options**: 5, 10, 25, 50, 100 miles
- **Default**: 10 miles
- **Type**: Dropdown select
- **Behavior**: Affects map viewport and search geometry

#### 3.1.3 Specialty/Taxonomy Search
- **Trigger**: User types in "Description / Specialty" field
- **Minimum Characters**: 2 characters activate autocomplete
- **Data Source**: 702-entry NUCC taxonomy database
- **Results Display**: Specialty name + classification
- **Multi-Select**: Users can add multiple specialties
- **Tag Management**: Visible as chips; backspace removes last tag

**Example Flow**:
```
User Input: "Cardiology"
↓
API Call: /api/taxonomy-search?q=Cardiology
↓
Results:
  1. Interventional Cardiology (202Y00000X)
  2. Pediatric Cardiology (2080C0008X)
  3. Cardiac Electrophysiology (208000...)
↓
User Selects: "Interventional Cardiology"
↓
tagArray = [{ display: "Interventional Cardiology", code: "202Y00000X" }]
```

#### 3.1.4 Search Execution
- **Trigger**: Click "Search Physicians" button
- **Validation**:
  - Address field required (must have valid lat/lng)
  - At least 1 specialty required
- **Error Messages**: Inline feedback below relevant field
- **Loading State**: Full-page spinner with "Searching providers..." message

### 3.2 Results Display

#### 3.2.1 Search Banner (After Search)
Located directly below header, appears on all results pages:

| Element | Details |
|---------|---------|
| **Location Pill** | Displays selected address |
| **Radius Pill** | Shows selected radius in miles |
| **Specialties Chips** | Displays all selected specialties |
| **New Search Button** | Resets to initial search form |

#### 3.2.2 Results Counter
- **Text**: "Showing X of Y providers"
- **Format**: Both numbers are localized (e.g., "Showing 10 of 1,245 providers")
- **Updates**: Real-time as results render

#### 3.2.3 Provider Map
- **Display Order**: Appears BEFORE physician cards
- **Height**: 480px (desktop), 360px (tablet), responsive (mobile)
- **Controls**: MapQuest default controls (zoom, pan)
- **Center Pin**: Gold star (★) marking search center location
- **Provider Pins**: Numbered cyan-teal pins (1, 2, 3, etc.)
- **Interactions**:
  - Hover over pin → auto-opens popup with provider info
  - Click pin → highlights matching card in list
  - Auto-zoom to fit all results (max zoom: 15)

#### 3.2.4 Physician Result Cards (Grid)
- **Layout**: 3-column grid (desktop), 2-column (tablet), 1-column (mobile)
- **Cards Per Page**: 9 results initially
- **Load More**: Hidden (seamless scroll experience)
- **Sorting**: By proximity (distance ascending)

**Card Contents**:
| Element | Details |
|---------|---------|
| **Avatar** | 2 initials from first/last name, gradient background |
| **Name** | Physician full name, bold |
| **Specialty** | First 2 specialties (max 2 lines), truncated |
| **Distance Badge** | "📍 X mi" format |
| **Result Number** | Circled number (1, 2, 3, etc.), top-right |
| **View Details Arrow** | Interactive, highlights on hover |

**Card Interactions**:
- **Hover/Focus**: 
  - Shadow intensifies
  - Border color brightens
  - Transform: translateY(-4px)
  - Top gradient bar fades in
- **Click**: Opens physician detail panel

#### 3.2.5 Physician Detail Panel
- **Trigger**: Click any physician card
- **Layout**: Full-width side panel (calc(100vw - 96px))
- **Position**: Right-aligned, overlays map
- **Scroll**: Independent scroll within panel (no main page scroll)
- **Close**: 
  - Back button
  - Escape key
  - Click backdrop outside panel

**Panel Sections**:

**Header Section** (gradient blue background):
- Back button
- Avatar (72px)
- Physician name (1.5rem serif)
- All specialties as badges
- Result number in circle badge

**Body Sections**:

1. **Provider Information**
   - NPI Number (monospace font)
   - Distance from search center
   - Full address (street, city, state, ZIP)
   - Phone number
   - Entity type (Individual, Organization, etc.)

2. **Specialties & Taxonomy**
   - All specialties as clickable tags
   - Taxonomy descriptions

3. **Location Map** (if coordinates available)
   - Zoomed map showing provider location
   - Center pin at provider's exact address

4. **Actions**
   - **Add as Lead** (primary blue button)
     - Converts physician to Salesforce lead
     - First name, last name parsed from physician name
     - Company: "Individual Physicians" (hardcoded)
     - Phone, address, specialty, NPI populated
     - Shows loading state during submission
     - Success toast: "Lead created successfully!"
   - **View on Main Map** (secondary button)
     - Closes detail panel
     - Scrolls to main map
     - Highlights the selected physician's pin
     - Zooms to that marker (zoom level 16)

### 3.3 Lead Capture (Modal)

**Trigger**: "View Full Access" button in results (visible when results > MAX_PAGE)

**Functionality**:
- Modal overlay with contact form
- Fields:
  - First Name * (required)
  - Last Name * (required)
  - Email * (required, validated)
  - Phone (optional)
  - Title/Role (optional)
  - Organization (optional)

**On Submit**:
- Validates required fields
- Sends to `/api/leads` endpoint
- Data saved to JSON file
- If Salesforce configured: pushes to CRM
- Shows success screen with checkmark
- Logs request with timestamp

### 3.4 Empty State Handling

**Trigger**: Search returns 0 results

**Display**:
- Icon: Search icon in light blue circle
- Title: "No providers found"
- Message: "No physicians matching '[specialty]' were found in this area. Try a different specialty name or expand your search radius."
- Suggestions: Tips for refining search
- CTA Button: "New Search" (resets form)

---

## 4. User Experience Flow

### 4.1 Primary Flow: Search → View → Convert

```
1. [LANDING PAGE]
   ↓ User sees search form with location + specialty fields
   ↓ (Map, results, banner hidden on initial load)

2. [ADDRESS AUTOCOMPLETE]
   ↓ User types address
   ↓ 7 suggestions appear
   ↓ User clicks suggestion
   ↓ lat/lng populated in state

3. [SPECIALTY SELECTION]
   ↓ User types specialty
   ↓ Taxonomy suggestions appear
   ↓ User clicks specialty
   ↓ Specialty shown as chip tag
   ↓ Input clears for multi-select

4. [SEARCH EXECUTION]
   ↓ User clicks "Search Physicians"
   ↓ Spinner shows
   ↓ Backend processes search (1-5 seconds)
   ↓ Results page appears

5. [RESULTS PAGE]
   ↓ Banner displays search criteria
   ↓ "Showing X of Y providers" counter
   ↓ Map loads with numbered pins
   ↓ Physician cards render below map

6. [INTERACTION]
   Option A: Hover map pins
   ↓ Popup auto-opens
   ↓ Hover away → popup auto-closes
   ↓ Click pin → card highlights and scrolls into view
   
   Option B: Click physician card
   ↓ Detail panel slides in from right
   ↓ Rich information displayed
   ↓ "Add as Lead" button visible

7. [LEAD CONVERSION]
   ↓ User clicks "Add as Lead"
   ↓ Button shows loading state
   ↓ Success: "Lead created successfully!"
   ↓ Lead saved to Salesforce

8. [NEW SEARCH]
   ↓ User clicks "New Search" button
   ↓ Returns to step 2 (clean form)
```

### 4.2 Secondary Flow: Full Results Access

```
1. [RESULTS PAGE - Over 10 Results]
   ↓ Counter shows "Showing 9 of 250 providers"
   ↓ Load More button appears
   
2. [LEAD CAPTURE MODAL]
   ↓ User clicks "Load More" (or "View Full Access")
   ↓ Modal appears with lead form
   
3. [FORM SUBMISSION]
   ↓ User enters contact info
   ↓ Clicks "Request Full Access"
   ↓ Backend validates and saves
   ↓ Success screen shown
   ↓ Salesforce notified (if configured)
```

---

## 5. API Specifications

### 5.1 Autocomplete Endpoint

**REQUEST**:
```
GET /api/autocomplete?text=Thousand&limit=7
```

**PARAMETERS**:
| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| text | string | Yes | — | Search query (min 2 chars) |
| limit | int | No | 7 | Max suggestions to return |

**RESPONSE** (200 OK):
```json
{
  "features": [
    {
      "geometry": {
        "coordinates": [-118.8376, 34.1706]
      },
      "properties": {
        "formatted": "Thousand Oaks, California 91360, United States",
        "city": "Thousand Oaks",
        "state_code": "CA",
        "county": "Ventura County"
      }
    }
  ]
}
```

**ERROR RESPONSES**:
- 400: Missing/invalid `text` parameter
- 429: Rate limited (120 req/min per IP)
- 500: Geoapify API unavailable

---

### 5.2 Geocode Endpoint

**REQUEST**:
```
GET /api/geocode?address=Thousand%20Oaks%20CA
```

**RESPONSE** (200 OK):
```json
{
  "lat": 34.1706,
  "lng": -118.8376,
  "city": "Thousand Oaks",
  "state": "CA",
  "formatted": "Thousand Oaks, California, United States", 
  "address": "Thousand Oaks, CA"
}
```

**ERROR RESPONSES**:
- 404: Address not found in US
- 400: Missing `address` parameter
- 500: Geoapify error

---

### 5.3 Taxonomy Search Endpoint

**REQUEST**:
```
GET /api/taxonomy-search?q=Cardiology
```

**PARAMETERS**:
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| q | string | Yes | Specialty name (min 2 chars) |

**RESPONSE** (200 OK):
```json
{
  "results": [
    {
      "display": "Interventional Cardiology",
      "classification": "Specialty",
      "code": "202Y00000X"
    },
    {
      "display": "Pediatric Cardiology",
      "classification": "Specialty",
      "code": "2080C0008X"
    }
  ]
}
```

**NOTES**:
- Results filtered to exclude specialties already selected
- Returned from in-memory taxonomy database
- No rate limiting on this endpoint (internal lookup only)

---

### 5.4 Search Endpoint

**REQUEST**:
```
GET /api/search?lat=34.1706&lng=-118.8376&radius=10&descriptions=["Interventional%20Cardiology"]&city=Thousand%20Oaks&state=CA
```

**PARAMETERS**:
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| lat | float | Yes | Search center latitude |
| lng | float | Yes | Search center longitude |
| radius | int | Yes | Search radius in miles (5-100) |
| taxonomy_code | string | No | NPI taxonomy code (rare, for direct lookups) |
| descriptions | JSON array | No | Specialty names to search ["Cardiology", "Pediatric"] |
| city | string | No | City name (for logging) |
| state | string | No | State code (for logging) |

**RESPONSE** (200 OK):
```json
{
  "physicians": [
    {
      "npi": "1234567890",
      "name": "Dr. John Smith",
      "address": "123 Medical Plaza, Thousand Oaks, CA 91360",
      "phone": "(805) 555-1234",
      "lat": 34.1712,
      "lng": -118.8365,
      "distance_miles": 0.5,
      "taxonomy_desc": "Interventional Cardiology",
      "all_taxonomies": [
        { "code": "202Y00000X", "desc": "Interventional Cardiology" },
        { "code": "207S00000X", "desc": "Cardiology" }
      ],
      "entity_type": "Individual"
    }
  ],
  "total": 7
}
```

**RESPONSE FIELDS**:
- `physicians`: Array of matched providers
  - `npi`: National Provider Identifier
  - `name`: Full name
  - `address`: Street address
  - `phone`: Contact phone
  - `lat/lng`: Geographic coordinates
  - `distance_miles`: Distance from search center
  - `taxonomy_desc`: Primary specialty
  - `all_taxonomies`: All specialties/classifications
  - `entity_type`: Individual or Organization
- `total`: Total unique records found (may exceed display count)

**ERROR RESPONSES**:
- 400: Missing required lat/lng/radius
- 429: Rate limited (30 req/min per IP)
- 500: NPPES API error or ZIPdb lookup failed

---

### 5.5 Lead Capture Endpoint

**REQUEST**:
```
POST /api/leads
Content-Type: application/json

{
  "first_name": "John",
  "last_name": "Smith",
  "email": "john.smith@example.com",
  "phone": "(805) 555-1234",
  "company": "Acme Health",
  "title": "Healthcare Recruiter",
  "search_context": {
    "location": "Thousand Oaks, CA",
    "radius": 10,
    "specialties": ["Interventional Cardiology"],
    "total_results": 7
  }
}
```

**REQUIRED FIELDS**:
- `first_name`
- `last_name`
- `email` (must be valid email format)

**OPTIONAL FIELDS**:
- `phone`
- `company`
- `title`
- `search_context` (any object)

**RESPONSE** (200 OK):
```json
{
  "success": true,
  "lead_id": "lead_20260325143521456789",
  "message": "Thank you! Our team will contact you shortly."
}
```

**ERROR RESPONSES**:
- 400: Missing required field
- 400: Invalid email format
- 429: Rate limited (5 req/min per IP)
- 500: Could not save lead (file or Salesforce error)

**SIDE EFFECTS**:
1. Lead saved to `/tmp/leads/lead_*.json` (or LEADS_DIR env var)
2. If SF_OID configured: pushed to Salesforce
3. Request logged with timestamp and request_id

---

### 5.6 Salesforce Lead (Physician Detail)

**REQUEST**:
```
POST /api/leads
Content-Type: application/json

{
  "first_name": "John",
  "last_name": "Smith",
  "email": "lead@aquarient.local",
  "company": "Individual Physicians",
  "phone": "(805) 555-1234",
  "title": "Interventional Cardiology",
  "search_context": {
    "npi": "1234567890",
    "address": "123 Medical Plaza, Thousand Oaks, CA 91360",
    "specialty": "Interventional Cardiology; Cardiology",
    "distance_miles": 0.5
  }
}
```

**NOTES**:
- Triggered by "Add as Lead" button on physician detail panel
- Email hardcoded as `lead@aquarient.local` (required field)
- Company hardcoded as `Individual Physicians`
- Title = first specialty name
- Full physician data in search_context

---

## 6. Data Models

### 6.1 Physician Record (NPPES)

```typescript
interface Physician {
  npi: string;                    // National Provider Identifier (10 digits)
  name: string;                   // Full legal name
  address: string;                // Street, city, state, ZIP
  phone: string;                  // Contact phone number
  lat: number;                    // Latitude coordinate
  lng: number;                    // Longitude coordinate
  distance_miles: float;          // Distance from search center
  taxonomy_desc: string;          // Primary taxonomy description
  all_taxonomies: Taxonomy[];     // All specialties/classifications
  entity_type: "Individual" | "Organization";
}

interface Taxonomy {
  code: string;     // 10-character taxonomy code (e.g., "202Y00000X")
  desc: string;     // Human-readable description (e.g., "Interventional Cardiology")
}
```

### 6.2 Lead Record

```typescript
interface Lead {
  id: string;                  // Unique ID: "lead_YYYYMMDDHHmmssfffffff"
  first_name: string;          // Sanitized, max 80 chars
  last_name: string;           // Sanitized, max 80 chars
  email: string;               // Validated, lowercased
  phone?: string;              // Optional, sanitized, max 30 chars
  company?: string;            // Optional, sanitized, max 120 chars
  title?: string;              // Optional, sanitized, max 80 chars
  search_context: object;      // Original search filters + results metadata
  created_at: string;          // ISO 8601 timestamp
  source: "PhysicianLocator";  // Lead source identification
  status: "New";               // Lead status (initially "New")
}
```

### 6.3 Taxonomy Record (In-Memory Database)

```typescript
interface TaxonomyEntry {
  code: string;           // 10-character code (e.g., "207S00000X")
  display: string;        // Display name (e.g., "Cardiology")
  classification: string; // Category (e.g., "Specialty", "Specialization")
}
```

### 6.4 Search Result

```typescript
interface SearchResult {
  physicians: Physician[];
  total: number;        // Total records found (may exceed display limit)
}
```

---

## 7. Technical Architecture

### 7.1 Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React-like HTML/JS | Interactive UI |
| **Frontend Framework** | Vanilla JS (no build) | Lightweight, quick load |
| **Backend** | Python 3.9+ / Flask | API server |
| **Physician Data** | NPPES API | 6M+ licensed physicians |
| **Geocoding** | Geoapify API | Address → coordinates |
| **Mapping** | MapQuest JS SDK | Interactive map visualization |
| **Lead Storage** | JSON files + Salesforce | CRM integration |
| **Deployment Backend** | Render (gunicorn) | Production hosting |
| **Deployment Frontend** | Vercel (Next.js optional) | Static + edge |

### 7.2 Frontend Architecture

```
index.html
├── CSS (Embedded)
│   └── Design System:
│       ├── Root CSS variables (colors, spacing)
│       ├── Typography (serif headlines, sans-serif body)
│       ├── Component styles (buttons, cards, modals)
│       └── Responsive breakpoints (900px, 580px)
│
└── JavaScript (Vanilla)
    ├── State Management
    │   ├── allPhysicians[] - Search results array
    │   ├── totalFound - Total count from backend
    │   ├── currentSearch - Current filter state
    │   └── taxTags[] - Selected specialties
    │
    ├── Modules
    │   ├── Autocomplete (address, specialty)
    │   ├── Search (validation, API calls)
    │   ├── Results Rendering (cards, grid layout)
    │   ├── Mapping (MarkerCluster, pins, popups)
    │   ├── Detail Panel (physician info, actions)
    │   ├── Lead Capture (form, validation, submission)
    │   └── Utilities (toast, spinner, announcements)
    │
    └── API Client (fetchWithTimeout wrapper)
```

**Key Features**:
- No build step required (vanilla JS)
- Single HTML file with embedded CSS/JS
- Progressive enhancement (works without JS)
- Accessible (ARIA labels, semantic HTML)
- Mobile-responsive (flexbox, CSS grid)

### 7.3 Backend Architecture

```
app.py (Flask)
├── Config & Setup
│   ├── Environment variables
│   ├── CORS configuration
│   ├── Rate limiting
│   └── Logging (request IDs)
│
├── Data Stores
│   ├── ZIP Database (in-memory, 41k+ ZIP codes)
│   ├── Taxonomy Index (702 specialties, in-memory)
│   ├── Geocode Cache (LRU, 2000 entries)
│   └── Spatial Index (KD-tree for ZIP lookup)
│
├── API Routes
│   ├── GET /api/autocomplete - Address suggestions
│   ├── GET /api/geocode - Address to coordinates
│   ├── GET /api/taxonomy-status - DB status check
│   ├── GET /api/taxonomy-search - Specialty lookup
│   ├── GET /api/search - Physician search
│   ├── POST /api/leads - Lead capture
│   ├── POST /api/lead-debug - Debug lead creation
│   └── GET / - Main HTML page
│
├── Integrations
│   ├── NPPES API (physician data)
│   ├── Geoapify API (geocoding)
│   ├── MapQuest (frontend mapping)
│   └── Salesforce (lead sync)
│
└── Utilities
    ├── Input sanitization
    ├── Rate limiting per IP
    ├── Error handling
    └── Request ID tracking
```

**Performance Optimizations**:
- ZIP database cached in memory (loaded on startup)
- Taxonomy index pre-loaded (702 entries)
- Spatial indexing for fast ZIP → coordinates lookup
- Rate limiting to prevent abuse
- Geocode cache (LRU) to reduce redundant API calls
- Structured logging for debugging

### 7.4 Data Flow Diagram

```
USER INTERFACE (Frontend)
    ↓
┌─────────────────────┐
│ Search Form         │
│ - Address input     │
│ - Specialty select  │
│ - Radius selector   │
└─────────────────────┘
    ↓ (Click Search)
┌─────────────────────┐
│ Validation          │
│ - Require address   │
│ - Require specialty │
│ - Enforce min 2 ch  │
└─────────────────────┘
    ↓ (Valid)
┌─────────────────┐
│ API: Geocode    │
│ (if needed)     │
└────────┬────────┘
         ↓
┌──────────────────────────────────────┐
│ API: Search                          │
│ - Input: lat, lng, radius, taxonomy  │
│ - Backend: ZIP lookup, NPPES query   │
│ - Output: Physicians + count         │
└────────┬─────────────────────────────┘
         ↓
┌──────────────────────────────────────┐
│ Results Page                         │
│ - Banner (search criteria)           │
│ - Map (with pins)                    │
│ - Physician cards (grid)             │
│ - Lead capture modal (if >10)        │
└──────────────────────────────────────┘
         ↓
┌──────────────────────────────────────┐
│ Detail Panel                         │
│ (Click card)                         │
│ - Provider info                      │
│ - Specialties                        │
│ - Action: "Add as Lead"              │
└────────┬─────────────────────────────┘
         ↓
┌──────────────────────────────────────┐
│ API: Create Lead (/api/leads)        │
│ - First name, last name, email       │
│ - Salesforce webhook (if configured) │
└──────────────────────────────────────┘
```

---

## 8. UI/UX Specifications

### 8.1 Design System

**Color Palette**:
```
Primary Blue:   #0076B6
Accent Cyan:    #00AEEF
Teal:           #0C7A7A
Navy:           #0F2044
Coral (Error):  #D95F4B
Gold (Highlight): #C4993A

Background:     Linear gradient (light blue → light teal)
Neutral Dark:   #141420 (text)
Neutral Light:  #FAF8F4 (off-white)
```

**Typography**:
```
Headlines:  Cormorant Garamond (serif), 1.3rem–2.4rem
Body:       Plus Jakarta Sans (sans-serif), 0.82rem–1rem
Code:       DM Mono (monospace), 0.78rem
```

**Spacing**:
```
--border:   48px (1-inch margins on sides)
--hdr:      64px (header height)
--content:  calc(100vw - 96px) (full-width content)
--r:        10px (border-radius)
--tr:       0.18s (transition duration)
```

**Shadows**:
```
--s1: 0 2px 8px rgba(20,20,32,.06)
--s2: 0 8px 28px rgba(20,20,32,.10)
--s3: 0 20px 60px rgba(20,20,32,.14)
```

### 8.2 Component Library

**Buttons**:
- `.btn-s` (primary): Search button, blue gradient
- `.dp-btn-primary` (action): Add as Lead, blue gradient
- `.dp-btn-secondary` (alternate): View on Map, outline style
- `.empty-btn` (CTA): New Search, blue gradient
- `.sb-new-btn` (banner): New Search, light outline

**Input Fields**:
- `.inp` (text input): Address, radius
- `.tag-box` (multi-select): Specialties with chips
- `.chip` (tag): Individual specialty chip
- `.chip-x` (remove): Delete button on chip

**Feedback**:
- `.toast` (notification): Success/error messages, auto-dismiss
- `.spinner` (loading): Full-page overlay during search
- `.empty-state` (zero results): Helpful message + CTA

**Cards**:
- `.dc` (physician card): Result card with hover effects
- `.dc-skeleton` (placeholder): Loading skeleton

**Modals**:
- `.modal` (lead form): Centered dialog with backdrop
- `.detail-panel` (physician info): Side panel, full-height

### 8.3 Responsive Design

**Breakpoints**:

```
Mobile:   < 580px
  - 1-column grid (cards)
  - Smaller font sizes
  - Padding: 1rem

Tablet:   580px–900px
  - 2-column grid (cards)
  - Medium spacing
  - Padding: var(--border)

Desktop:  > 900px
  - 3-column grid (cards)
  - Full spacing
  - Padding: var(--border)
```

**Key Responsive Changes**:
- Map height: 480px (desktop) → 360px (tablet/mobile)
- Grid columns: 3 → 2 → 1
- Modal width: 500px → full width on mobile
- Detail panel: Full viewport width on all sizes
- No scrollbars visible (hidden via CSS)

---

## 9. Performance & Reliability

### 9.1 Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Initial Load | < 2s | ~1.2s |
| Search Response | < 5s | ~2-3s |
| Map Render | < 500ms | ~350ms |
| Card Grid Render | < 1s | ~600ms |
| Detail Panel Open | < 300ms | ~280ms |

### 9.2 Reliability & Uptime

- **Target**: 99.5% uptime
- **Error Handling**: Structured responses with request IDs
- **Rate Limiting**: 
  - Autocomplete: 120 req/min per IP
  - Search: 30 req/min per IP
  - Lead: 5 req/min per IP
- **Fallbacks**: 
  - Geoapify unavailable → manual coordinate entry
  - NPPES timeout → retry with exponential backoff
  - Lead save failure → saved to file + logged

### 9.3 Data Consistency

- **Lead Duplication**: Tracked via `first_name + email` composite
- **Geocode Caching**: LRU cache prevents redundant API calls
- **Physician Deduplication**: NPI is unique identifier
- **Timestamp**: All leads logged with ISO 8601 timestamp

---

## 10. Security & Compliance

### 10.1 Input Validation

**Sanitization Applied To**:
- Address input: Strip HTML, limit to 200 chars
- Specialty input: Strip HTML, limit to 120 chars each
- Lead form fields: HTML-escape, limit length
- Request IDs: Alphanumeric only

**Output Escaping**:
- Physician names: HTML-escaped
- Lead email body: HTML-escaped (html.escape())
- Responses: JSON-serialized (safe by default)

### 10.2 Rate Limiting

**Per-IP Rate Limits**:
- `/api/autocomplete`: 120 req/min
- `/api/search`: 30 req/min
- `/api/leads`: 5 req/min

**Mechanism**: In-process dictionary with timestamp tracking, purges expire entries every 5 min

### 10.3 CORS Policy

**Allowed Origins**:
- Production: `FRONTEND_URL` from environment
- Development: `*` (with warning in logs)

**Allowed Methods**: GET, POST, OPTIONS
**Allowed Headers**: Content-Type, X-Request-ID

### 10.4 PII Protection

- **Physician Data**: Public NPPES records (no sensitive info)
- **Lead Data**: Encrypted at rest (if configured), in-transit via HTTPS
- **Salesforce Sync**: OAuth 2.0 or API token (environment variable)
- **Email**: Required for lead form, validated as business email domain

---

## 11. Integrations

### 11.1 Geoapify (Geocoding & Autocomplete)

**Purpose**: Convert addresses to coordinates, suggest addresses as typed

**API Usage**:
- Autocomplete: `https://api.geoapify.com/v1/geocode/autocomplete`
- Geocode: `https://api.geoapify.com/v1/geocode/search`

**Rate Limit**: 3,000 req/day (free tier)

**Fallback**: Manual entry of lat/lng if API unavailable

### 11.2 NPPES Registry (Physician Data)

**Purpose**: 6M+ licensed physician records

**API**: Free, no key required
**Rate Limit**: Reasonable limits per second (backend manages)
**Update Frequency**: Weekly (physician database)

**Data Returned**:
- NPI, name, address, phone
- Specialties (primary + secondary)
- Entity type (Individual/Organization)

### 11.3 MapQuest (Interactive Mapping)

**Purpose**: Visualize physician locations

**SDK**: `mapquest.min.js` + `mapquest.min.css`
**Version**: 1.3.2

**Features**:
- Numbered markers
- Popups on hover/click
- Auto-zoom to bounds
- Pan/zoom controls

### 11.4 Salesforce CRM (Optional)

**Purpose**: Synced lead database

**Authentication**: OAuth 2.0 or API Token
**Endpoint**: Salesforce Lead REST API
**Fields Mapped**:
- first_name → FirstName
- last_name → LastName
- email → Email
- phone → Phone
- company → Company
- title → Title
- search_context → Description / custom field

**Status**: Stub implementation in `salesforce.py`, ready for activation

---

## 12. Future Enhancements

### Phase 3 (Q2 2026)
- [ ] Advanced filters (experience level, language, board certification)
- [ ] Saved searches (user dashboard)
- [ ] Bulk export (CSV/Excel)
- [ ] Physician profiles (more detailed info)
- [ ] Email notifications (new matches, lead updates)

### Phase 4 (Q3 2026)
- [ ] Mobile app (iOS/Android)
- [ ] API for third-party integrations
- [ ] Analytics dashboard (search trends, popular specialties)
- [ ] AML/screening against prohibited entities lists
- [ ] Multi-language support (Spanish, Mandarin)

### Phase 5 (Q4 2026 & Beyond)
- [ ] AI-powered recommendations ("Similar physicians")
- [ ] Physician reputation scoring (aggregate data)
- [ ] Direct messaging (physician contact opt-in)
- [ ] Insurance network lookup
- [ ] Telehealth provider filtering

---

## 13. Support & Maintenance

### 13.1 Monitoring

**Logging**: Structured logs with request IDs to stdout/stderr
**Alerts**:
- Backend response time > 10s
- Error rate > 5%
- Rate limiter blocking > 100 IPs/hour
- Geoapify API quota exceeded

**Health Checks**:
- Backend: `/health` endpoint (checks NPPES, ZIP DB, Geoapify)
- Frontend: JS error tracking via toast notifications

### 13.2 Troubleshooting Guide

**Problem**: Search returns 0 results
- **Cause**: No physicians match specialty + location combo
- **Solution**: Expand radius, try different specialty name, check map location

**Problem**: Address autocomplete not working
- **Cause**: Geoapify API limit reached (3k/day)
- **Solution**: Wait until next day, or use manual coordinate entry

**Problem**: Lead not appearing in Salesforce
- **Cause**: SF_OID not configured, or SF_DEBUG_EMAIL mismatch
- **Solution**: Check environment variables, verify Salesforce credentials, check logs

---

## 14. Glossary

| Term | Definition |
|------|-----------|
| **NPI** | National Provider Identifier — unique 10-digit ID for physicians |
| **NPPES** | National Plan & Provider Enumeration System — CMS registry of 6M+ physicians |
| **Taxonomy** | Classification system for healthcare provider types/specialties |
| **Lead** | Contact record of interested recruiter/user for CRM sync |
| **Geoapify** | Third-party API for address geocoding + autocomplete |
| **MapQuest** | Third-party mapping SDK (Leaflet-based) |
| **Geocoding** | Converting address (text) → coordinates (lat/lng) |
| **Entity Type** | Individual (single physician) vs Organization (group practice, hospital) |
| **Request ID** | Unique identifier for tracking a single HTTP request through logs |
| **Rate Limiting** | Restricting API calls per IP to prevent abuse |
| **Salesforce** | CRM system for managing leads, contacts, opportunities |

---

## Appendix A: API Response Examples

### A.1 Successful Search Response

```json
{
  "physicians": [
    {
      "npi": "1417980518",
      "name": "Robert Adams",
      "address": "123 Cardiac Way, Thousand Oaks, CA 91360",
      "phone": "(805) 555-1234",
      "lat": 34.1712,
      "lng": -118.8365,
      "distance_miles": 0.5,
      "taxonomy_desc": "Interventional Cardiology",
      "all_taxonomies": [
        {
          "code": "202Y00000X",
          "desc": "Interventional Cardiology"
        },
        {
          "code": "207S00000X",
          "desc": "Cardiology"
        }
      ],
      "entity_type": "Individual"
    },
    {
      "npi": "1306897324",
      "name": "Sarah Chen",
      "address": "456 Medical Center, Westlake Village, CA 91360",
      "phone": "(805) 555-5678",
      "lat": 34.2145,
      "lng": -118.7456,
      "distance_miles": 5.2,
      "taxonomy_desc": "Interventional Cardiology",
      "all_taxonomies": [
        {
          "code": "202Y00000X",
          "desc": "Interventional Cardiology"
        }
      ],
      "entity_type": "Individual"
    }
  ],
  "total": 7
}
```

### A.2 Error Response (Rate Limited)

```json
{
  "error": "Too many requests. Please wait and try again.",
  "code": "RATE_LIMITED",
  "request_id": "432f55dd-89ab-4c29-8e1f-6c7a8b9d0c1e",
  "retry_after_ms": 3500
}
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-15 | Aquarient | Initial spec |
| 1.5 | 2026-02-20 | Aquarient | Added map features, improved layout |
| 2.0 | 2026-03-25 | Aquarient | Added full-width layout, "Add as Lead" button, removed scrollbars, search results hidden on initial load |

---

**End of Functional Specification**

For questions or clarifications, contact: deepika.tigulla@aquarient.com
