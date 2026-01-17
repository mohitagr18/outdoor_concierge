# Review Display Debugging - Technical Notes

## Date: January 16, 2026

## Summary
Fixed multiple issues preventing trail reviews from displaying correctly in the chat interface.

---

## Issue #1: Session Context Park Code Not Synced

### Problem
When users asked questions like "What are the reviews for Bridalveil Falls trail?" without mentioning the park name, the system returned zero trails.

### Root Cause
In `main.py`, the `SessionContext` was initialized with `current_park_code=None` and never synced with the UI dropdown selection (`st.session_state.selected_park`). This caused the Orchestrator to take an early-exit path with empty trails.

### Fix
Added one line in `main.py` before creating `OrchestratorRequest`:
```python
st.session_state.session_context.current_park_code = st.session_state.selected_park
```

### File Changed
- `main.py` (line ~140)

---

## Issue #2: Strict Trail Name Matching

### Problem
Trail name matching failed for variations like:
- "Bridalveil Falls trail" vs "Bridalveil Fall Trailhead" (plural/singular)
- "Cathedral Lakes Trail" vs "Cathedral Lakes Trailhead" (suffix variations)

### Root Cause
The LLM service and review scraper used exact substring matching:
```python
if tgt.lower() in t.name.lower()
```
This failed when "falls" didn't match "fall" or when suffixes differed.

### Fix
Created `app/utils/fuzzy_match.py` with intelligent matching:
1. Removes common suffixes (trail, trailhead, hike, path, loop)
2. Requires ALL significant words (>3 chars) to match
3. Handles plural/singular (falls↔fall, lakes↔lake)

### Files Changed
- **NEW** `app/utils/fuzzy_match.py`
- **NEW** `app/utils/__init__.py`
- `app/orchestrator.py` - import and use in auto-targeting
- `app/services/llm_service.py` - import and use in context filtering
- `app/services/review_scraper.py` - import and use in trail lookup

---

## Issue #3: Review Images Not Displaying

### Problem
Reviews had `visible_image_urls` with valid AllTrails image URLs, but images weren't shown in chat.

### Root Cause
The LLM prompt for review display (in `llm_service.py`) didn't mention images:
```python
"List reviews using this format: **[Author Name]** | [Date] | [Rating]★ followed by quoted text."
```
The LLM followed the format exactly and ignored image URLs in the context.

### Fix
Updated the review display prompt to explicitly instruct including images:
```python
"4. IMPORTANT: If a review has images (markdown format ![](...)), INCLUDE them in your response."
```

### File Changed
- `app/services/llm_service.py` (lines ~240-260)

---

## Issue #4: Review Extraction Not Capturing Images

### Problem
Newly scraped reviews had empty `visible_image_urls: []` even when AllTrails pages had images.

### Root Cause
The LLM extraction prompt showed an example with empty arrays:
```python
OUTPUT JSON: { "reviews": [ { ..., "visible_image_urls": [] } ] }
```
This guided the LLM to always return empty image arrays.

### Fix
Updated the extraction prompt to instruct finding images:
```python
"IMPORTANT: Look for image URLs in each review. AllTrails reviews often include user photos.
- Image URLs typically contain: images.alltrails.com, cdn-assets.alltrails.com
- Include ALL image URLs found within each review's content"
```

### File Changed
- `app/services/llm_service.py` (`extract_reviews_from_text` method, lines ~1189-1205)

---

## Debugging Approach

### Logging Added
Added comprehensive logging throughout the pipeline to trace issues:

1. **Orchestrator** (`orchestrator.py`):
   - `✅ Using park code: {park_code}` - confirms park resolution
   - `🔍 REVIEW REQUEST - Intent targets: [...]` - shows what user asked for
   - `📝 Final scrape targets list: [...]` - shows scrape targets
   - `✅ RESOLVED Review Targets for LLM Context: [...]` - final targets for LLM
   - `📊 Trails in cache with reviews: [...]` - which trails have reviews
   - `📤 CALLING LLM with N trails` - how many trails passed to LLM

2. **LLM Service** (`llm_service.py`):
   - `🔍 CONTEXT FILTER - Showing only targets: [...]` - filtering active
   - `🔍 Input trails count: N` - before filtering
   - `✅ Filtered trails count: N` - after filtering
   - `🎯 Filtered trail names: [...]` - which trails made it through
   - Per-trail: `- TrailName: has_reviews=True/False, count=N`

3. **Review Scraper** (`review_scraper.py`):
   - `Fuzzy matched 'X' to 'Y'` - shows fuzzy matching in action
   - `🕷️ Scraping reviews for 'X' from {url}` - scrape starting
   - `✅ Found N reviews. updating cache.` - extraction success

---

## Key Learnings

1. **Session state must be explicitly synced** - Streamlit's session state for context tracking needs manual sync with UI state.

2. **Fuzzy matching needs boundaries** - Too loose (80% match) caused false positives. Required 100% of significant words to match.

3. **LLM follows instructions literally** - If the prompt says "format as X", it won't include Y even if Y is in the context. Be explicit about ALL desired outputs.

4. **Scraping limitations** - Firecrawl converts pages to markdown, but dynamically-loaded content (like lazy-loaded images) may not be captured reliably.

---

## Files Modified (Summary)

| File | Changes |
|------|---------|
| `main.py` | Sync session context park code |
| `app/orchestrator.py` | Fuzzy matching import, comprehensive logging |
| `app/services/llm_service.py` | Fuzzy matching, updated prompts for images |
| `app/services/review_scraper.py` | Fuzzy matching for trail lookup |
| `app/utils/fuzzy_match.py` | **NEW** - Fuzzy trail name matching |
| `app/utils/__init__.py` | **NEW** - Package init |
