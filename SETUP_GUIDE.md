# Physician Locator - Setup & Troubleshooting Guide

## Problem: Map and Physician Details Not Showing

The map and physician details cards don't appear after searching because the **frontend cannot connect to the backend API**.

### Root Causes
1. **Backend is not running** - The backend Flask API must be running for the frontend to fetch physician data
2. **Incorrect backend URL** - `frontend/env.js` has the wrong backend URL configured
3. **CORS configuration** - Backend CORS settings don't match your frontend origin

---

## ✅ Solution: Running Everything Locally

### Step 1: Start the Python Backend

The backend must run on `http://localhost:5000`

**First, set up the Python environment:**

```bash
cd c:\Users\ADMIN\physician-locator\backend
```

**Create and activate a virtual environment (recommended):**

```bash
python -m venv venv
venv\Scripts\activate
```

**Install dependencies:**

```bash
pip install -r requirements.txt
```

**Configure environment variables (already set in .env):**

The `.env` file is already configured with:
- MAPQUEST_API_KEY ✓
- GEOAPIFY_API_KEY ✓
- Other required settings ✓

**Start the backend:**

```bash
python app.py
```

You should see:
```
* Running on http://localhost:5000
 WARNING in ... FRONTEND_URL not set (this is OK for local development)
```

### Step 2: Configure the Frontend

The `frontend/env.js` file has already been updated to use localhost by default:

```javascript
BACKEND_URL: "http://localhost:5000"
```

**No changes needed!** The frontend is now configured to use the local backend.

### Step 3: Start the Frontend

In another terminal/command prompt:

```bash
cd c:\Users\ADMIN\physician-locator\frontend
```

**For local testing, you can use Python's built-in server:**

```bash
python -m http.server 8000
```

Then open: `http://localhost:8000`

**Or use VS Code's Live Server extension** (if installed)

### Step 4: Test the Application

1. **Open browser console** (F12) to see debug logs:
   - Will show: `[PhysicianLocator] Configuration loaded: BACKEND_URL: http://localhost:5000`
   - Will show: `[PhysicianLocator] Calling: http://localhost:5000/api/search?...`

2. **Try a search:**
   - Address: "New York, NY"
   - Specialty: "Cardiologist" (or any specialty)
   - Click "Search Physicians"

3. **Check for these indicators of success:**
   - Loading spinner appears briefly
   - Results panel shows with map and physician cards
   - Browser console shows: `[PhysicianLocator] Found N physicians`

---

## 🔧 Troubleshooting

### Issue: "Cannot reach backend" Error

**Check if backend is running:**

```bash
# In a terminal, try:
curl http://localhost:5000/health
```

Should return JSON with status information.

**If the backend isn't running:**
- Terminal showing backend should be visible
- Make sure you completed **Step 1** above
- Backend is on `http://localhost:5000` (not https)

### Issue: "Backend URL not configured" Error

**Verify `frontend/env.js` exists and has correct content:**

Should contain:
```javascript
BACKEND_URL: "http://localhost:5000"
```

If not, update it manually.

### Issue: Map doesn't show even after search works

**Verify MapQuest API key:**

Backend console should show map initialization. If it doesn't:
- Check browser console (F12) for errors
- Verify MAPQUEST_KEY in backend `.env` is set

### Issue: No physician results found

**Check backend logs in the terminal** for:
- ZIP code database loading: `ZIP db ready: XXXX entries`
- Taxonomy data loading: `Taxonomy loaded: XXXX entries`
- Actual search logs: `NPPES unique records: N`

If ZIP/taxonomy databases aren't loading, restart the backend—they load on startup.

---

## 📊 Optional: For Production/Deployment

### Deploying to Render (Backend)

The backend is configured to run on Render. Update in `backend/render.yaml`:
- Ensure `FRONTEND_URL` matches your Vercel URL
- Ensure `MAPQUEST_API_KEY` and `GEOAPIFY_API_KEY` are set in Render dashboard

### Deploying to Vercel (Frontend)

The frontend `build.sh` will auto-generate `env.js` during build. Set in Vercel dashboard:

```
BACKEND_URL = https://your-render-backend.onrender.com
MAPQUEST_KEY = your-mapquest-api-key
```

---

## 🚀 Quick Start Commands (Copy & Paste)

**Terminal 1 - Start Backend:**
```bash
cd c:\Users\ADMIN\physician-locator\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

**Terminal 2 - Start Frontend:**
```bash
cd c:\Users\ADMIN\physician-locator\frontend
python -m http.server 8000
```

Then: `http://localhost:8000`

---

## 📝 Summary of Changes Made

1. **Updated `frontend/env.js`:**
   - Changed `BACKEND_URL` from `https://physicians-locator.onrender.com` to `http://localhost:5000`
   - Added comments for clarity

2. **Enhanced error logging in `frontend/index.html`:**
   - Added console logs for API calls
   - Better error messages showing which backend didn't respond
   - Clearer indication of configuration issues

3. **Improved error handling:**
   - Search now checks if BACKEND_URL is configured before attempting API call
   - Geocoding errors now suggest checking backend connectivity
   - All API failures include helpful error messages

---

## ✅ Files Modified

- ✅ `frontend/env.js` - Updated BACKEND_URL to localhost
- ✅ `frontend/index.html` - Enhanced error logging and error messages
- ✅ `backend/.env` - Already properly configured

---

**Now test the application and check the browser console for debug logs!**
