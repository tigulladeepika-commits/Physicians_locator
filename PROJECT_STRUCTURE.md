# Physician Locator - Professional Project Structure

## Overview

This project has been **restructured into a professional, scalable architecture** with clear separation between frontend and backend concerns.

## Project Layout

```
physician-locator/
├── README.md                           # This file
├── FUNCTIONAL_SPEC.md
├── TECHNICAL_SPEC.md
├── USER_GUIDE.md
├── SETUP_GUIDE md
│
├── backend/                            # Flask API Server
│   ├── README.md                       # Backend documentation
│   ├── app.py                          # Main Flask application (clean, modular)
│   ├── config.py                       # Configuration management
│   ├── requirements.txt
│   ├── Procfile                        # Deployment configuration
│   ├── render.yaml
│   │
│   ├── services/                       # Core business logic
│   │   ├── rate_limiting.py            # Request rate limiting
│   │   ├── zip_database.py             # ZIP code database & search
│   │   ├── taxonomy.py                 # Medical specialty taxonomy
│   │   ├── nppes.py                    # Physician data fetching
│   │   └── salesforce.py               # Lead integration
│   │
│   ├── utils/                          # Utility functions
│   │   ├── helpers.py                  # Common utilities
│   │   └── validation.py               # Input validation
│   │
│   └── routes/                         # Optional: decouple routes (future)
│       └── health.py
│
├── frontend/                           # Vue/HTML Frontend
│   ├── README.md                       # Frontend documentation
│   ├── index.html                      # Main HTML (clean imports)
│   ├── env.js                          # Client-side config
│   ├── vercel.json
│   │
│   ├── css/                            # Stylesheets (organized)
│   │   ├── main.css                    # Global styles & tokens
│   │   ├── components.css              # Component styles
│   │   └── responsive.css              # Media queries
│   │
│   ├── js/                             # JavaScript modules
│   │   ├── config.js                   # Configuration
│   │   ├── api.js                      # API client
│   │   ├── state.js                    # State management
│   │   ├── map.js                      # Map functionality
│   │   ├── search.js                   # Search logic
│   │   ├── results.js                  # Results display
│   │   ├── detail.js                   # Detail panel
│   │   ├── suggest.js                  # Autocomplete
│   │   ├── modal.js                    # Lead modal
│   │   ├── ui.js                       # UI utilities
│   │   └── utils.js                    # Helper functions
│   │
│   ├── static/                         # Static assets
│   │   ├── css/
│   │   └── js/
│   │
│   └── templates/                      # HTML templates (if needed)
│
├── data/                               # Data files
│   ├── leads.json
│   └── us_zip_db.json
│
└── docs/                               # Documentation (optional)
    ├── ARCHITECTURE.md
    ├── API_ENDPOINTS.md
    ├── DEPLOYMENT.md
    └── TROUBLESHOOTING.md
```

## Architecture Highlights

### Backend (`/backend`)

**Modular Design**
- `app.py`: Clean entry point with Flask routes
- `services/`: Encapsulated business logic
  - Each service handles one concern
  - Independently testable
  - Reusable across endpoints

- `utils/`: Shared utilities
  - Input validation
  - Sanitization
  - Caching & rate limiting

**Benefits**
- ✅ Easy to understand and navigate
- ✅ Simple to add new features
- ✅ Straightforward to test
- ✅ Clean dependency management
- ✅ Production-ready error handling

### Frontend (`/frontend`)

**Organized JavaScript & CSS**
- `index.html`: Clean, minimal HTML
- `css/`: Organized into focused files
- `js/`: Feature-based modules

**Benefits**
- ✅ No build step needed
- ✅ Easy browser caching
- ✅ Clear where each feature lives
- ✅ Standard ES6+ JavaScript
- ✅ Vanilla JS (no framework overhead)

## Key Features

### Search Capabilities
- 6M+ licensed US physicians
- Address/ZIP autocomplete
- Medical specialty search
- Radius-based filtering
- Interactive map display

### Lead Management
- Capture lead information
- Push to Salesforce
- File-based backup
- Rate limiting protection

### User Experience
- Responsive design (desktop/tablet/mobile)
- Accessibility (ARIA labels, keyboard navigation)
- Smooth animations
- Real-time search feedback

## Development Workflow

### Backend Development

```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Run locally
python app.py

# Or with hot-reload
python -m flask --app app run --debug

# Deploy to Render
git push origin main  # Auto-deploys via Render
```

### Frontend Development

```bash
# Serve locally
cd frontend
python -m http.server 8000

# Or with live reload
npx live-server

# Open http://localhost:8000
```

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | System status check |
| GET | `/api/autocomplete` | Address suggestions |
| GET | `/api/geocode` | Address to coordinates |
| GET | `/api/taxonomy-search` | Specialty suggestions |
| GET | `/api/taxonomy-status` | Taxonomy data status |
| GET | `/api/search` | Physician search |
| POST | `/api/leads` | Capture lead |
| POST | `/api/lead-debug` | Test lead pipeline |

See `TECHNICAL_SPEC.md` for detailed API documentation.

## Configuration

### Environment Variables (Backend)

```bash
# API Keys
MAPQUEST_API_KEY=your_mapquest_key
GEOAPIFY_API_KEY=your_geoapify_key

# Salesforce
SF_OID=your_salesforce_oid
SF_RET_URL=https://your-domain.com
SF_DEBUG_EMAIL=your-email@example.com

# URLs
FRONTEND_URL=https://your-frontend.com

# Security
DEBUG_SECRET=your-secret-key

# Storage
LEADS_DIR=/var/data

# Server
PORT=5000
```

### Configuration (Frontend)

Edit `env.js`:
```javascript
window.ENV = {
  BACKEND_URL: "https://api.example.com",
  MAPQUEST_KEY: "your_mapquest_key"
};
```

## Deployment

### Backend (Render)

1. Connect GitHub repo
2. Set environment variables in dashboard
3. Deploy with `gunicorn`

### Frontend (Vercel)

1. Connect GitHub repo
2. Build command: `echo "Static files only"`
3. Output directory: `frontend`

## Testing

### Manual Testing
- Test on different devices/browsers
- Verify rate limiting
- Check Salesforce lead creation
- Validate form inputs

### Future: Automated Testing
- Add pytest for backend
- Add pytest fixtures for services
- Add Jest for frontend
- Add E2E tests with Playwright

## Troubleshooting

### Backend Issues
- Check `/health` endpoint for status
- Review logs: `logs` directory
- Check environment variables are set
- Verify NPPES API is reachable

### Frontend Issues
- Check browser console for errors
- Verify `env.js` configuration
- Check CORS headers from backend
- Clear browser cache

See `SETUP_GUIDE.md` and `USER_GUIDE.md` for more details.

## Future Improvements

### Backend
- [ ] Add database (PostgreSQL)
- [ ] Async task processing (Celery)
- [ ] Comprehensive test suite
- [ ] API versioning
- [ ] GraphQL endpoint

### Frontend
- [ ] Migrate to component framework (Lit, Vue)
- [ ] Add PWA support
- [ ] Improve offline functionality
- [ ] Add analytics
- [ ] Add dark mode

### DevOps
- [ ] Docker containerization
- [ ] CI/CD pipeline
- [ ] Monitoring & alerting
- [ ] Performance optimization
- [ ] Security scanning

## Code Quality Standards

- Clean, readable code
- Meaningful variable/function names
- Comprehensive comments & docstrings
- Proper error handling
- Input validation everywhere
- Thread-safe operations
- Logging for debugging

## License

© 2026 Aquarient. All rights reserved.

---

**Last Updated**: March 31, 2026
**Version**: 2.1 (Modularized)
**Status**: Production Ready
