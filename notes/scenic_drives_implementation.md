# Scenic Drives Feature Implementation Report

**Date:** January 9, 2026  
**Author:** Claude (AI Assistant)

---

## Overview

Added a new "Scenic Drives" tab to the Park Explorer, mirroring the existing Photo Spots feature. This feature scrapes travel blogs for scenic drive information and displays them in an organized, visually appealing format.

---

## Files Created

### 1. `scripts/fetch_scenic_drives.py`
**Purpose:** Fetches scenic drive data from travel blogs using a multi-step pipeline.

**Technology Stack:**
- **Serper API** - Google search to find relevant travel blogs
- **Firecrawl** - Web scraping to extract markdown content
- **Gemini LLM** - Structured data extraction from scraped content

**Key Features:**
- Searches for "best scenic drives [park name] guide routes"
- Scrapes up to 5 blog URLs per park
- Uses Pydantic models for structured output (`ScenicDrive`, `ScenicDriveGuide`)
- Saves processed data to `data_samples/ui_fixtures/{PARK}/scenic_drives.json`
- Saves raw scraped markdown to `data_samples/nps/raw/{PARK}/raw_scenic_drives.json`

**Data Model (`ScenicDrive`):**
```python
- rank: Optional[int]
- name: str
- parkCode: Optional[str]
- description: str
- distance_miles: Optional[float]
- drive_time: Optional[str]  # e.g. "2-3 hours"
- highlights: List[str]      # Key viewpoints/stops
- best_time: Optional[str]   # e.g. "Sunrise", "Any time"
- tips: List[str]
- image_url: Optional[str]
- source_url: Optional[str]
```

---

### 2. `app/ui/views/park_explorer_drives.py`
**Purpose:** Renders scenic drives in a 3-column card layout.

**Features:**
- Displays drive image (with placeholder fallback)
- Shows rank, name, distance, drive time, best time badges
- Lists key stops with styled badges
- Expandable driving tips section
- Prominent "Read Guide" button linking to source

---

## Files Modified

### 1. `app/models.py`
- Added `ScenicDrive` Pydantic model

### 2. `app/config.py`
- Added `"Scenic Drives"` to `EXPLORER_VIEW_OPTIONS`
- Added `"drives": "Scenic Drives"` to `VIEW_PARAM_MAP` for deep linking

### 3. `app/ui/data_access.py`
- Added `ScenicDrive` to imports
- Added `scenic_drives` to result dictionary
- Added `load_list()` call for `scenic_drives.json`

### 4. `app/services/park_data_fetcher.py`
- Added `scenic_drives.json` to `OPTIONAL_FIXTURES`
- Added `fetch_scenic_drives()` method
- Integrated scenic drives into `ensure_park_data()` flow (Step 5 of 6)
- Added `include_scenic_drives` parameter

### 5. `main.py`
- Added import for `render_scenic_drives`
- Added view routing for "Scenic Drives" tab
- Added `include_scenic_drives=True` to data fetch call

### 6. `app/ui/views/park_explorer_photos.py`
- Updated "Read Guide" button styling (vibrant blue gradient, improved visibility)

---

## Issues Faced & Solutions

### Issue 1: Missing Image URLs
**Problem:** Initial scraped data had many drives with `null` image URLs despite source blogs having images.

**Solution:** Enhanced the Gemini prompt with more aggressive image extraction instructions:
```
CRITICAL - IMAGE EXTRACTION:
- Look for ALL image URLs in the markdown content
- Images appear as: ![alt text](https://...) or ![](https://...)
- Also look for image URLs in HTML img tags: <img src="https://...">
- DO NOT return null for image_url unless you truly cannot find ANY image
```

**Result:** All drives now have images (ZION: 8/8, YOSE: 15/15 → 12/12, BRCA: 7/7 → 6/6)

---

### Issue 2: Duplicate Drive Entries
**Problem:** Same drives appeared multiple times with slight name variations (e.g., "Tioga Road" and "Tioga Road (Highway 120)").

**Solution:** Implemented smarter deduplication logic:
```python
# Remove parenthetical suffixes: "Tioga Road (Highway 120)" → "tioga road"
base_name = norm_name.split("(")[0].strip()

# Remove common suffixes: "tioga road" → "tioga"
core_name = base_name.replace(" road", "").replace(" drive", "")...

# Check multiple similarity strategies:
- Exact name match
- Base name match  
- Core name match
- Substring containment
- Prefix matching
```

**Result:** Reduced duplicates (YOSE: 15 → 12, BRCA: 7 → 6)

---

### Issue 3: Raw Data Not Saved
**Problem:** Initial implementation only saved processed data, not the raw scraped markdown.

**Solution:** Added raw data saving:
```python
raw_scraped_data.append({
    "url": url,
    "markdown_length": len(md),
    "markdown": md  # Full markdown content
})

# Save to nps/raw directory
raw_output_path = os.path.join(raw_dir, "raw_scenic_drives.json")
```

---

### Issue 4: "Read Guide" Link Visibility
**Problem:** The "Read Guide" link was too small (0.8em, gray color) and hard to see.

**Solution:** Styled as a prominent button:
```css
background: linear-gradient(135deg, #3b82f6, #2563eb);
color: white;
padding: 8px 8px;
border-radius: 8px;
font-weight: 600;
box-shadow: 0 2px 4px rgba(37,99,235,0.3);
```

**Follow-up Issue:** Initial negative margin caused button to overlap card border.  
**Fix:** Adjusted to `margin-top: 4px; margin-bottom: 4px;`

---

## Data Generated

| Park | Drives | With Images | Raw Data Size |
|------|--------|-------------|---------------|
| ZION | 8 | 8/8 (100%) | 5 sources |
| YOSE | 12 | 12/12 (100%) | 5 sources |
| BRCA | 6 | 6/6 (100%) | 5 sources |

---

## Usage

### Fetch scenic drives for a park:
```bash
PARK_CODE=YOSE python scripts/fetch_scenic_drives.py
```

### Automatic fetching:
Scenic drives are automatically fetched when clicking "🚀 Fetch Park Data" in the UI for a new park.

### Deep linking:
```
http://localhost:8501/?view=drives
```

---

## Future Improvements

1. **Merge similar entries** - "Wawona Road" and "Highway 41 (Wawona Road)" could be merged
2. **Add map visualization** - Show drive routes on an interactive map
3. **Seasonal availability** - Display road closure information
4. **User ratings** - Allow users to rate and review drives
5. **Driving directions** - Integration with Google Maps for turn-by-turn navigation
