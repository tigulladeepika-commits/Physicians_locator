# 🩺 Physician Locator — User Guide & Playbook

**Version**: 2.0  
**Last Updated**: March 26, 2026  
**For**: Healthcare Recruiters, Staffing Agencies, Medical Researchers

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Interface Overview](#interface-overview)
3. [Searching for Physicians](#searching-for-physicians)
4. [Understanding Results](#understanding-results)
5. [Physician Details & Lead Capture](#physician-details--lead-capture)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)
8. [FAQ](#faq)

---

## Getting Started

### What is Physician Locator?

Physician Locator is a web-based search platform for finding licensed US physicians by location and specialty. It connects to the official **NPPES (National Plan and Provider Enumeration System)** registry, which contains information on 6+ million healthcare providers across all 50 US states.

**Key Features**:
- Search by address + specialty combination
- View results on an interactive map
- See detailed physician profiles (NPI, credentials, contact info)
- Capture physician details as leads in Salesforce CRM
- Multi-specialty support (search for multiple specialties at once)

### Accessing the Application

1. **Navigate to the URL** — Your administrator will provide the application link
2. **No Login Required** — Physician Locator is publicly accessible
3. **Browser Compatibility** — Works on Chrome, Firefox, Safari, Edge (modern versions)
4. **Mobile-Friendly** — Fully responsive on tablets and phones

---

## Interface Overview

### Main Search Page (Home)

The application homepage contains the **search form** and **blank map**. Here's what you'll see:

```
┌─────────────────────────────────────────────────────────────┐
│ 🩺 PHYSICIAN LOCATOR                                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  SEARCH FOR PHYSICIANS                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 📍 Address / Location *                             │   │
│  │ [Search box with autocomplete suggestions]          │   │
│  │                                                     │   │
│  │ 🔍 Radius:  [5 mi ▼]                               │   │
│  │                                                     │   │
│  │ 🏥 Description / Specialty *                        │   │
│  │ [Type specialty, add multiple as chips]             │   │
│  │                                                     │   │
│  │         [SEARCH PHYSICIANS →]                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │          [Empty Map Ready for Results]              │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Key Form Elements

| Element | Description | Required |
|---------|-------------|----------|
| **Address/Location** | Where to search (e.g., "San Francisco, CA") | Yes* |
| **Radius** | Search distance (5, 10, 25, 50, 100 miles) | No (default: 10) |
| **Specialty** | Type of physician (e.g., "Cardiology") | Yes* |
| **Search Button** | Initiates search | — |

*At least one of Address OR Specialty is required; both are recommended.

---

## Searching for Physicians

### Step 1: Enter Your Location

1. **Click the Address field** — "📍 Address / Location"
2. **Type your location** — Examples:
   - City & State: `"Denver, CO"`
   - Full Address: `"123 Main St, Boston, MA"`
   - City Only: `"Miami"`
3. **Wait for autocomplete suggestions** — After 2 characters, suggestions appear
4. **Select from the list** — Click a suggestion to populate the field

**Autocomplete Tips**:
- Suggestions show formatted addresses and latitude/longitude
- Only US locations are supported
- If your exact address isn't listed, select the nearest match
- The first suggestion is usually the most relevant

**Example Autocomplete Dropdown**:
```
Searching "Denver"...
1. Denver, Colorado (39.7392, -104.9903)
2. Denver, North Carolina (35.4387, -80.5527)
3. Denville, New Jersey (40.8843, -74.4720)
```

### Step 2: Select a Search Radius

1. **Click the Radius dropdown** — Shows "[ 10 mi ▼ ]"
2. **Choose your radius**:
   - **5 miles** — Tightest search, fewest results
   - **10 miles** — Default, balanced results
   - **25 miles** — Regional search
   - **50 miles** — Broader coverage
   - **100 miles** — Widest search area

**When to Use Each Radius**:
- **5 miles** → Downtown/urban areas, specific clinics
- **10 miles** → Suburban/metro areas, general recruitment
- **25 miles** → Multi-county recruiting
- **50 miles** → Regional staffing searches
- **100 miles** → Nationwide campaigns, rural areas

### Step 3: Select Specialties

1. **Click the Specialty field** — "🏥 Description / Specialty"
2. **Type a specialty** — Examples:
   - `"Cardiology"`
   - `"Interventional"`
   - `"Pediatric"`
   - `"Surgery"`
3. **Wait for suggestions** — After 2 characters, matching specialties appear
4. **Click a suggestion** — Adds it as a blue chip tag

**Adding Multiple Specialties**:
- Repeat steps 1-4 for each specialty you want
- Tags appear below the search box
- Each tag shows as a removable chip: `[Cardiology ×] [Pediatrics ×]`

**To Remove a Specialty**:
- Click the `×` on a chip, OR
- Click in the specialty field and press backspace

**Common Specialties**:
```
Cardiology          Interventional Radiology
Orthopedic Surgery  Family Medicine
Pediatrics          Emergency Medicine
Oncology            Psychiatry
Neurology           Gastroenterology
```

### Step 4: Execute the Search

1. **Click [SEARCH PHYSICIANS →]** button
2. **Wait for results** — A spinner appears with "Searching providers..."
3. **Results load** — Map and physician cards populate

**What Happens Behind the Scenes**:
- Your location is converted to latitude/longitude
- The system queries the NPPES registry
- Results are filtered by distance and specialty
- Physicians are sorted by distance
- Map is centered and zoomed to fit all results

---

## Understanding Results

### Search Banner (After Search)

Once results load, you'll see a **results banner** above the map:

```
📍 Denver, CO  ·  ⭕ 10 miles  ·  🏥 Cardiology  ·  [← NEW SEARCH]

Showing 10 of 1,245 providers
```

This banner shows:
- **Your search location** — Confirming the area searched
- **Search radius** — Distance perimeter used
- **Selected specialties** — All specialties included
- **New Search button** — Returns to blank search form
- **Results count** — "Showing X of Y" (e.g., "10 of 1,245")

### Interactive Map

The map displays your results visually:

```
┌─────────────────────────────────────────┐
│  ★ (Gold star = your search location)   │
│         ②  ①                             │
│             ③                           │
│      ④     ⑤ (Numbered pins)            │
│                  ⑥ ⑦                    │
└─────────────────────────────────────────┘

Controls (top-right):
+ (Zoom In)
- (Zoom Out)
⊡ (Full Screen)
```

**Map Interactions**:
- **Hover over a pin** → Info popup opens showing physician name & specialty
- **Click a pin** → Card scrolls into view and highlights
- **Pan/Zoom** → Explore the map with mouse or trackpad

### Physician Result Cards

Cards display key physician information. Each card shows:

```
┌────────────────────────────────────────┐
│ #1 Dr. Sarah Johnson                   │ ← Rank & Name
│ ────────────────────────────────────────│
│ 🏥 Interventional Cardiology           │ ← Primary Specialty
│ 📍 123 Cardiac Way, Denver, CO 80202   │ ← Address
│ 📞 (303) 555-0123                      │ ← Phone
│ 📊 NPI: 1417980518                     │ ← National Provider ID
│                                        │
│ 🗺️ 2.3 miles away               [+]   │ ← Distance & Lead Button
└────────────────────────────────────────┘
```

**Card Fields Explained**:
| Field | Meaning |
|-------|---------|
| **Rank (#)** | Position in results (1 = closest/best match) |
| **Name** | Physician's full name |
| **Primary Specialty** | Main focus (from NUCC taxonomy) |
| **Address** | Street address + ZIP code |
| **Phone** | Direct practice phone number |
| **NPI** | Unique national healthcare provider ID |
| **Distance** | Miles from your search location |

### Viewing a Physician's Full Profile

**Click anywhere on a card** to open the **Physician Detail Panel**:

```
┌─────────────────────────────────────────────────────────────┐
│  X                                                          │
│ ☐ DR. ROBERT ADAMS         [1 of 10]                       │
│ ────────────────────────────────────────────────────────────│
│                                                             │
│ 🏥 Specialties:                                             │
│    • Interventional Cardiology                             │
│    • Cardiology                                            │
│                                                             │
│ 📍 Address:                                                 │
│    123 Cardiac Way, Thousand Oaks, CA 91360               │
│                                                             │
│ 📞 Phone:                                                   │
│    (805) 555-0123                                          │
│                                                             │
│ NPI: 1417980518                                            │
│ Distance: 0.5 miles away                                   │
│                                                             │
│  [+ ADD AS LEAD]  [VIEW ON MAP]                           │
│ ────────────────────────────────────────────────────────────│
└─────────────────────────────────────────────────────────────┘
```

**Detail Panel Shows**:
- Full physician name with avatar
- All specialties/certifications
- Complete address with map view option
- Direct phone contact
- NPI number (for CRM reference)
- Distance from search point
- Actions: View on Map, Add as Lead

---

## Physician Details & Lead Capture

### Viewing on Map

1. **Click [VIEW ON MAP]** in the detail panel
2. The map zooms to the physician's location (map pin highlights in blue)
3. An info popup appears with contact details
4. You can continue panning/zooming to explore the area

### Capturing a Physician as a Lead

**What is a Lead?**

A "lead" is a record you save in your CRM system (Salesforce) that captures physician details + your search context. It's your first step in recruitment workflows.

**To Add a Physician as a Lead**:

1. **Click [+ ADD AS LEAD]** on the detail panel
2. A confirmation toast message appears: 
   - ✓ "Lead created successfully!"
3. The physician is now recorded in your system with:
   - Their name, contact info, NPI
   - Their specialties and credentials
   - Your search location and parameters
   - Timestamp of when it was captured

**What Data Gets Saved?**

When you capture a physician as a lead, the following is recorded:

```json
{
  "physician_name": "Dr. Robert Adams",
  "npi": "1417980518",
  "specialties": ["Interventional Cardiology", "Cardiology"],
  "address": "123 Cardiac Way, Thousand Oaks, CA 91360",
  "phone": "(805) 555-0123",
  "distance_miles": 0.5,
  "search_context": {
    "location": "Thousand Oaks, CA",
    "radius_miles": 10,
    "specialties_searched": ["Cardiology"],
    "timestamp": "2026-03-25T14:35:21Z",
    "total_results": 7
  }
}
```

This lead is then sent to your Salesforce instance for CRM management.

### Searching for Full Results

If your search returns more than 10 results, you'll see:

```
Showing 10 of 1,245 providers
```

**To See More Results**:
- Scroll down through the cards (seamless infinite scroll)
- Continue clicking physician cards to view details
- Scroll down to load additional cards

**Tips for Narrowing Results**:
- Reduce radius (e.g., 10 mi → 5 mi)
- Add another specialty filter
- Search a different city

---

## Best Practices

### 1. Effective Location Searches

**✓ DO**:
- Use well-known cities or neighborhoods
- Include state abbreviation (e.g., "Denver, CO")
- Start broad (25-mile radius), then narrow down

**✗ DON'T**:
- Use only ZIP codes (less accurate)
- Search extremely rural areas (fewer results)
- Use international addresses (US only)

**Example Good Searches**:
```
✓ "San Francisco, CA"
✓ "Manhattan, New York"
✓ "Downtown Miami, FL"
✓ "123 Market St, San Francisco, CA"
```

### 2. Specialty Selection Strategy

**Multi-Specialty Searches**:
- Add 2-3 related specialties for broader results
- Example: `Cardiology` + `Interventional Radiology` + `Cardiac Surgery`

**Narrow vs. Broad**:
- **Narrow**: `Interventional Cardiology` (specific, fewer results)
- **Broad**: `Cardiology` (general, many results)

**Finding Specialty Names**:
- Start typing and check autocomplete suggestions
- Use industry-standard terms (not abbreviations)
- When in doubt, use broader specialty first

### 3. Lead Capture Workflow

**Recommended Workflow for Recruiters**:

1. **Define Target**: Decide location, specialty, radius
2. **Search**: Run initial search with broad radius (25-50 mi)
3. **Review Top Results**: Check top 10 physicians on map
4. **Capture High-Quality Leads**: Add promising candidates
5. **Refine**: Adjust radius/specialty based on results quality
6. **Export**: Leads are automatically synced to Salesforce

**Example Campaign**:
```
Goal: Fill 5 Interventional Cardiology positions in California

Search 1: Los Angeles, CA + 25 mile radius → Capture top 15 leads
Search 2: San Francisco, CA + 25 mile radius → Capture top 15 leads
Search 3: San Diego, CA + 25 mile radius → Capture top 10 leads

Total: 40 leads ready for recruitment outreach
```

### 4. Using Lead Data in Salesforce

Once a lead is captured:
1. **Lead is synced** to your Salesforce account automatically
2. **Appears in Sales Cloud** under "Leads" tab
3. **Includes custom fields**:
   - Specialty tags
   - Search location context
   - Distance from your search point
   - Contact Info
4. **Ready for workflow automation**:
   - Assign to recruiter
   - Add to campaign
   - Schedule follow-up tasks

### 5. Mobile Usage Tips

**On Tablets/Phones**:
- Form is responsive (single column)
- Map is touch-friendly (pinch to zoom)
- Swiping left on cards shows actions
- Fullscreen button for map view

---

## Troubleshooting

### "Address not found" or No autocomplete suggestions

**Problem**: Typing a location gives no suggestions.

**Causes & Fixes**:
- Address might not be in the US (only US locations supported)
- Typo in the address
- Too few characters typed (need 2+ characters)

**Solution**:
1. Double-check spelling
2. Try a nearby city instead
3. Include state abbreviation: "Denver, CO" vs. "Denver"

### "No specialties found" / Specialty not appearing

**Problem**: Your specialty doesn't show in autocomplete.

**Causes & Fixes**:
- Specialty name uses non-standard terminology
- Misspelling or abbreviation instead of full name

**Common Specialties to Try**:
```
Instead of: "Peds"                → Try: "Pediatrics"
Instead of: "Cardiologist"        → Try: "Cardiology"
Instead of: "OR Nurse"            → Try: "Surgery"
Instead of: "GP"                  → Try: "Family Medicine"
```

### Search is blank or "No results"

**Problem**: Search returns 0 results after running.

**Causes & Fixes**:
- Specialty doesn't exist in that area
- Radius is too small
- Location or specialty was mistyped

**Solution**:
1. Check the search banner (verify location/specialty)
2. Click [← NEW SEARCH]
3. Try a larger radius (e.g., 10 mi → 25 mi)
4. Try a nearby city
5. Use a broader specialty term

### Map not showing / Map is blank

**Problem**: Map appears but has no pins or is white/gray.

**Causes & Fixes**:
- Slow internet connection (wait 2-3 more seconds)
- Browser cache issue
- Map API not fully loaded

**Solution**:
1. Refresh the page (Ctrl+R / Cmd+R)
2. Check internet connection speed
3. Try a different browser
4. Clear browser cache and cookies

### Can't click physicians / Cards not responding

**Problem**: Clicking cards doesn't open detail panel.

**Causes & Fixes**:
- Page is still loading
- JavaScript disabled in browser
- Browser extension blocking interactions

**Solution**:
1. Wait for page to fully load (spinner gone)
2. Check if JavaScript is enabled
3. Try disabling browser extensions
4. Try incognito/private browsing mode

### Lead wasn't captured / "Failed to create lead"

**Problem**: Error message appears when clicking [+ ADD AS LEAD].

**Causes & Fixes**:
- Rate limited (too many leads too quickly)
- System connectivity issue
- Salesforce account not connected

**Solution**:
1. Wait 30 seconds and try again
2. Check your internet connection
3. Contact your administrator if issue persists

---

## FAQ

### General

**Q: Is my search data stored?**  
A: No. Your search queries are processed and discarded. We only store physician leads you explicitly capture.

**Q: Can I search outside the United States?**  
A: No. This tool searches the US NPPES registry only (50 states + territories).

**Q: How often is the physician data updated?**  
A: The NPPES database is updated continuously. Our system reflects data within 24 hours of updates.

**Q: Can I export search results as CSV/Excel?**  
A: Results are captured as Salesforce leads. Export from your Salesforce account directly.

### Search & Results

**Q: What's the difference between "Cardiology" and "Interventional Cardiology"?**  
A: **Cardiology** = all heart specialists. **Interventional Cardiology** = specialists performing catheterizations/interventions. Searching "Cardiology" returns both; searching "Interventional" returns only interventionalists.

**Q: Why am I getting physicians far away from my search radius?**  
A: Physicians without confirmed addresses appear in results but may not have exact coordinates. The distance shown is estimated.

**Q: Can I save searches?**  
A: Not built-in, but you can bookmark the page to re-enter searches manually.

**Q: What if a physician's info is outdated?**  
A: Contact the NPPES registry directly at www.npi.gov to report inaccuracies.

### Lead Capture

**Q: What happens after I capture a lead?**  
A: The lead is sent to your Salesforce account within seconds. Your Salesforce workflow will then manage it (assignment, tasks, follow-ups, etc.).

**Q: Can I capture the same physician twice?**  
A: Yes, but Salesforce will create duplicate lead records. It's your responsibility to deduplicate in your CRM.

**Q: Can I uncapture a lead?**  
A: No, but you can delete it after it's created in Salesforce.

**Q: What information is included in the lead?**  
A: Physician name, NPI, specialty, address, phone, distance, and your search context (location, radius, specialties searched).

### Technical

**Q: What browsers are supported?**  
A: Chrome, Firefox, Safari, Edge (modern versions, 2+ years old). Internet Explorer is not supported.

**Q: Is there a mobile app?**  
A: No, but the web app is fully mobile-responsive. Use any web browser on your phone/tablet.

**Q: Can I use this offline?**  
A: No, you need an internet connection both to search and to capture leads.

**Q: What's my data privacy policy?**  
A: Ask your administrator. The NPPES data is public; captured leads follow your organization's CRM policies.

### Troubleshooting

**Q: I'm getting rate-limited errors. What should I do?**  
A: You're searching/capturing leads too quickly. Wait 30-60 seconds and try again.

**Q: The map keeps zooming wrong. How do I fix it?**  
A: Click the "Fit to Screen" button (⊡) in the map controls, or zoom manually with +/-.

**Q: Can I search by NPI number?**  
A: No, only by address and/or specialty. If you know the NPI, use npi.gov directly.

**Q: The app says "No results" but I know physicians exist there. Why?**  
A: The NPPES registry may not have licensed any physicians in that specialty at that location. Try a broader specialty or nearby area.

---

## Quick Reference Card

### Search Tips Cheat Sheet

```
LOCATION EXAMPLES:
✓ City + State: "Denver, CO"
✓ Full Address: "123 Main St, Boston, MA"
✗ Just ZIP: "90210" (less accurate)
✗ International: "London, UK" (not supported)

SPECIALTY EXAMPLES:
✓ "Cardiology"
✓ "Interventional Cardiology"
✓ "Family Medicine"
✓ "Orthopedic Surgery"
✗ "MD" (not specific enough)
✗ "Cardiologist" (use "Cardiology")

RADIUS QUICK PICKS:
5 mi   → downtown/clinic specific
10 mi  → metro area (default)
25 mi  → multi-county
50 mi  → regional
100 mi → statewide

LEAD CAPTURE WORKFLOW:
1. Search location + specialty
2. Review top results on map
3. Click promising cards
4. Click [+ ADD AS LEAD]
5. Leads sync to Salesforce
6. Manage in Salesforce CRM
```

---

## Need More Help?

- **Technical Support**: Contact your system administrator
- **NPPES Data Questions**: Visit www.npi.gov
- **Salesforce Lead Management**: Consult your Salesforce admin
- **Recruitment Strategy**: Contact your department head

---

