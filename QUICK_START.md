# Quick Start - New Project Structure

## 📁 Where Everything Lives

### Backend (Python)
```
backend/
├── app.py              ← Entry point (routes & Flask setup)
├── config.py           ← Configuration management
├── services/           ← Business logic (one service per concern)
│   ├── zip_database.py (ZIP lookup & radius search)
│   ├── taxonomy.py     (Medical specialty data)
│   ├── nppes.py        (Physician data fetching)
│   ├── salesforce.py   (Lead push & file save)
│   └── rate_limiting.py (API rate limiting)
└── utils/              ← Helper functions
    ├── helpers.py      (Sanitize, cache, etc.)
    └── validation.py   (Input validation)
```

### Frontend (JavaScript/CSS)
```
frontend/
├── index.html          ← HTML structure & imports
├── css/                ← Stylesheets
│   ├── main.css        (Global styles)
│   ├── components.css  (Components)
│   └── responsive.css  (Mobile/responsive)
└── js/                 ← JavaScript modules
    ├── config.js       (Constants)
    ├── api.js          (API functions)
    ├── state.js        (State management)
    ├── map.js          (Map)
    ├── search.js       (Search)
    ├── results.js      (Results display)
    ├── detail.js       (Detail panel)
    ├── suggest.js      (Autocomplete)
    ├── modal.js        (Lead form)
    ├── ui.js           (UI utilities)
    └── utils.js        (Helpers)
```

## 🚀 Running the App

### Backend
```bash
cd backend
python app.py
# Server runs on http://localhost:5000
```

### Frontend
```bash
cd frontend
python -m http.server 8000
# Open http://localhost:8000
```

## 🔍 Finding Code

### "I need to fix the search"
- Logic: `backend/services/nppes.py` (fetch physicians)
- Logic: `backend/app.py` → `/api/search` route
- Frontend: `frontend/js/search.js` (search form)
- Frontend: `frontend/js/results.js` (display results)

### "I need to change the map"
- Frontend: `frontend/js/map.js` (all map code)

### "I need to add a rate limit"
- Backend: `backend/services/rate_limiting.py`

### "I need to validate form input"
- Backend: `backend/utils/validation.py`

### "I need to change styling"
- Frontend: `frontend/css/` (pick the right CSS file)

## ✏️ Adding a Feature

### Backend Example: New API endpoint

```python
# 1. Create service if needed (services/my_service.py)
def process_data(data):
    """Process data and return result."""
    return processed

# 2. Add to app.py
from services import my_service

@app.route("/api/my-endpoint")
def my_endpoint():
    data = request.get_json()
    result = my_service.process_data(data)
    return jsonify(result)
```

### Frontend Example: New JavaScript feature

```javascript
// 1. Create js/my-feature.js
function initMyFeature() {
    // Setup code
}

// 2. Add to index.html
<script src="/js/my-feature.js" defer></script>

// 3. Call in DOMContentLoaded
window.addEventListener("DOMContentLoaded", function() {
    initMyFeature();
});
```

## 📚 Documentation

- **PROJECT_STRUCTURE.md** - Full architecture overview
- **backend/README.md** - Backend details
- **frontend/README.md** - Frontend details
- **RESTRUCTURING_SUMMARY.md** - What changed & why

## 🧪 Testing

### Quick Health Check
```bash
# Test backend
curl http://localhost:5000/health

# Test frontend
open http://localhost:8000

# Verify configuration
curl http://localhost:5000/api/taxonomy-status
```

## 📝 Common Tasks

### Check what services are loaded
```bash
curl http://localhost:5000/health
# Shows: zip_db status, taxonomy status, missing env vars
```

### Debug a search issue
- Check logs in terminal
- Look at all modules in `services/`
- Check `app.py` for the `/api/search` route
- Check browser console for frontend errors

### Check environment variables
```bash
python -c "from config import cfg; print(cfg.SF_OID)"
```

### Test lead pipeline
```bash
# Create dummy lead to test Salesforce integration
curl -X POST http://localhost:5000/api/lead-debug \
  -H "X-Debug-Secret: your-secret"
```

## 🎯 Key Principles

- **One responsibility per file** - Find code by what it does
- **Clear imports** - Understand dependencies easily  
- **Docstrings everywhere** - Understand what code does
- **No monolithic files** - Easy to navigate
- **Testable modules** - Can test each part independently
- **Separation of concerns** - Frontend & backend are independent

## 📦 Key Files at a Glance

| File | Purpose |
|------|---------|
| `app.py` | Flask routes, initialization |
| `config.py` | Environment variables & settings |
| `services/nppes.py` | Fetch physician data |
| `services/taxonomy.py` | Medical specialty search |
| `services/zip_database.py` | ZIP code lookup |
| `services/salesforce.py` | Lead persistence |
| `services/rate_limiting.py` | Request rate limiting |
| `utils/validation.py` | Input validation |
| `utils/helpers.py` | Common utilities |
| `js/search.js` | Search form logic |
| `js/map.js` | Map initialization & interactions |
| `js/results.py` | Display results |
| `css/main.css` | Global styles & tokens |

## 💡 Pro Tips

1. **Use imports** - Don't repeat code, import utilities
2. **Add docstrings** - Comment what functions do
3. **Follow the pattern** - Look at similar code for examples
4. **Test locally first** - Use `python app.py` and browser console
5. **Check git history** - See how code evolved (in `app_backup.py`)

## ❓ Still Confused?

1. Read `PROJECT_STRUCTURE.md`
2. Check docstrings in the relevant file
3. Look at similar features for patterns
4. Check the original `app_backup.py` if you need context

---

**Remember**: The restructuring didn't change functionality, just organization. Everything works the same way! 🎉
