# Frontend Project Structure

## Overview
The frontend is now organized into **modular CSS and JavaScript** files instead of one monolithic HTML file.

## Directory Structure

```
frontend/
├── index.html             # Main HTML (minimal, imports CSS/JS)
├── env.js                 # Environment configuration
├── css/                   # Stylesheets
│   ├── main.css           # Global styles, layout tokens
│   ├── components.css     # Component-specific styles
│   └── responsive.css     # Media queries & breakpoints
└── js/                    # JavaScript modules
    ├── config.js          # Configuration & constants
    ├── api.js             # API client functions
    ├── state.js           # Application state management
    ├── map.js             # Map initialization & interactions
    ├── search.js          # Search form & logic
    ├── results.js         # Results display & cards
    ├── detail.js          # Physician detail panel
    ├── suggest.js         # Autocomplete & taxonomy search
    ├── modal.js           # Lead capture modal
    ├── ui.js              # UI utilities & toasts
    └── utils.js           # Helper functions
```

## Module Descriptions

### CSS Files

**`css/main.css`**
- CSS tokens (colors, fonts, spacing)
- Global reset & typography
- Layout grid & containers
- Header styles

**`css/components.css`**
- Search card
- Results layout (two-column)
- Physician cards
- Detail panel
- Forms & inputs
- Map styles
- Modal styles

**`css/responsive.css`**
- Mobile breakpoints
- Tablet adjustments
- Desktop optimizations

### JavaScript Files

**`js/config.js`**
- API endpoints
- Configuration constants
- Feature flags

**`js/api.js`**
- `fetchWithTimeout()` - API calls with timeout
- `getAutocomplete()` - Address suggestions
- `searchPhysicians()` - Main search
- `getTaxonomy()` - Specialty search
- `submitLead()` - Lead capture
- `createSalesforceLead()` - Individual physician lead

**`js/state.js`**
- Global state variables
- State getters/setters
- State observers

**`js/map.js`**
- `initMap()` - Map initialization
- `plotMarkers()` - Marker rendering
- `focusMap()` - Pan/zoom to location
- Hover & click interactions

**`js/search.js`**
- `doSearch()` - Search trigger
- `runSearch()` - Execute search
- Error handling

**`js/results.js`**
- `showResultsPhase()` - Display results
- `renderCountBar()` - Result count
- `renderCards()` - Physician cards
- `appendCard()` - Individual card
- `appendLoadMore()` - Load more button

**`js/detail.js`**
- `openDetail()` - Open detail panel
- `closeDetail()` - Close detail panel
- Detail form rendering
- Secondary map rendering

**`js/suggest.js`**
- `initAC()` - Address autocomplete
- `initTaxAC()` - Taxonomy autocomplete
- `addTagTo()` - Add taxonomy tag
- `renderMainTags()` - Render taxonomy chips

**`js/modal.js`**
- `openLeadModal()` - Open lead form
- `closeModal()` - Close modal
- `submitLead()` - Process form

**`js/ui.js`**
- `showToast()` - Toast notifications
- `setLoading()` - Loading spinner
- `announce()` - Screen reader announcements
- `trapFocus()` - Keyboard navigation

**`js/utils.js`**
- `resetToSearch()` - Clear & reset
- `updateSbar()` - Update search banner
- Utility functions

## Import Structure

The `index.html` imports files in this order:

1. **Config** (`config.js`)
2. **State** (`state.js`)
3. **API** (`api.js`)
4. **UI & Utils** (`ui.js`, `utils.js`)
5. **Features** (`search.js`, `results.js`, `map.js`, `detail.js`, `suggest.js`, `modal.js`)
6. **Initialization** (DOMContentLoaded listener)

## Benefits of Modularization

✅ **Easier to Find Code**: Know exactly where each feature lives
✅ **Faster Debugging**: Smaller files to trace through
✅ **Better Performance**: Unused code doesn't load
✅ **Team Collaboration**: Less merge conflicts
✅ **Testing**: Easier to mock & test functions
✅ **Maintenance**: Clear dependencies & responsibilities

## CSS Organization

All CSS remains in `<style>` block in HTML but organized into logical sections:

- **Reset & Tokens**: Base styles
- **Layout**: Grid, flex layouts
- **Components**: Cards, buttons, forms
- **Modal & Overlay**: Dialog styles
- **Detail Panel**: Physician details
- **Responsive**: Mobile-first media queries

## JavaScript Best Practices

- **No build step required**: Standard ES6+ without bundling
- **Fetch API**: Modern async/await
- **Event Delegation**: Single listener per type
- **Scope Management**: Closure-based private variables
- **Accessibility**: ARIA labels, keyboard support, screen reader announcements

## Adding New Features

### Adding a new UI component:

1. Add CSS to appropriate file in `css/`
2. Create JavaScript module in `js/` (e.g., `js/my-feature.js`)
3. Import in `index.html` before initialization
4. Initialize in DOMContentLoaded listener

### Example:

```javascript
// js/my-feature.js
function initMyFeature() {
  // Setup code
}

// In index.html
<script src="/js/my-feature.js" defer></script>

// In DOMContentLoaded
initMyFeature();
```

## File Size Reference

Before restructuring: Single ~1800 line HTML file
After restructuring: Multiple focused modules

This improves:
- Browser caching (separate files can be cached independently)
- Code readability  
- Debugging experience
- Team collaboration

## Future Improvements

- Convert to vanilla JS framework (Lit, Alpine.js)
- Add CSS preprocessor (Sass)
- Add JavaScript bundler (Vite)
- Add unit testing framework
- Move CSS to separate sheet (currently inline styles for simplicity)
