# Backend Project Structure

## Overview
The backend is now organized into **modular components** with clear separation of concerns.

## Directory Structure

```
backend/
├── app.py                 # Main Flask application (entry point)
├── config.py              # Configuration & environment variables
├── requirements.txt       # Python dependencies
├── services/              # Business logic modules
│   ├── __init__.py
│   ├── rate_limiting.py   # Rate limiter implementation
│   ├── zip_database.py    # ZIP code database & spatial search
│   ├── taxonomy.py        # Medical specialty taxonomy management
│   ├── nppes.py           # NPPES physician registry API
│   └── salesforce.py      # Salesforce lead integration
├── utils/                 # Helper functions & utilities
│   ├── __init__.py
│   ├── helpers.py         # Common utilities (sanitize, cache, rate limiter)
│   └── validation.py      # Input validation functions
└── routes/                # Route handlers (optional, currently in app.py)
    └── health.py          # Example modular route
```

## Key Modules

### `config.py`
- Centralized configuration management
- Environment variable loading
- Configuration validation

### `services/`
- **rate_limiting.py**: Thread-safe rate limiting per IP
- **zip_database.py**: ZIP code lookup & radius search
- **taxonomy.py**: Medical specialty search using NUCC data
- **nppes.py**: Physician data fetching & geocoding
- **salesforce.py**: Lead persistence (SF + file backup)

### `utils/`
- **helpers.py**: Sanitization, LRU cache, rate limiter class
- **validation.py**: Input validation (coordinates, radius, descriptions)

## Architecture Benefits

✅ **Clean Separation**: Each module has a single responsibility
✅ **Testability**: Easy to unit test individual services
✅ **Reusability**: Services can be used independently
✅ **Maintainability**: Clear import structure
✅ **Scalability**: Easy to add new features without modifying existing code

## Adding New Features

### Adding a new API endpoint:
1. Add the route to `app.py`
2. Create a service in `services/` if needed
3. Use validation from `utils/validation.py`

### Adding a new service:
1. Create file in `services/`
2. Add initialization call in `app.py:initialize_app()`
3. Import and use in endpoints

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (see SETUP_GUIDE.md)
export MAPQUEST_API_KEY="..."
export GEOAPIFY_API_KEY="..."
# ... other variables

# Run the app
python app.py

# Or with Gunicorn (production)
gunicorn --workers 4 --worker-class gthread --bind 0.0.0.0:5000 app:app
```

## Future Improvements

- Move each route type to separate files in `routes/` directory
- Add database ORM (SQLAlchemy) for lead persistence
- Add celery tasks for async operations
- Add comprehensive test suite
