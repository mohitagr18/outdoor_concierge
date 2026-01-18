# Session Notes: 2026-01-18 - Chat Context & Park Support Enhancements

## Summary

Major improvements to the AI Park Ranger chat functionality, focusing on context management, multi-part query handling, and expanded national park support.

---

## 1. Fixed Park Context Inheritance Bug

### Problem
When users asked about a specific trail (e.g., "Reviews for The Narrows"), the chat correctly identified Zion. However, follow-up questions would incorrectly default back to Yosemite (the dropdown default) instead of staying on Zion.

### Root Cause
Two issues identified:
1. `parse_user_intent()` in `llm_service.py` didn't receive current session context
2. `main.py` always overwrote session context with dropdown selection before every query

### Fix Applied

#### `app/services/llm_service.py`
- Added `current_park_code` parameter to `parse_user_intent()`
- Updated prompt to:
  - Provide context hint about current park
  - Instruct LLM to output `null` for park_code when no park is explicitly mentioned
  - Never guess/hallucinate park codes
- Added examples for follow-up questions

```python
def parse_user_intent(self, query: str, current_park_code: str = None) -> LLMParsedIntent:
    context_hint = ""
    if current_park_code:
        context_hint = f"\n        CURRENT CONTEXT: The user is currently viewing {current_park_code.upper()} park."
```

#### `app/orchestrator.py`
- Now passes `ctx.current_park_code` to intent parser
- Added friendly message when no park is available

#### `main.py`
- Changed from always overwriting context to only using dropdown as fallback
- Added sync: dropdown updates to match park inferred from conversation

```python
# Before: Always overwrote
st.session_state.session_context.current_park_code = st.session_state.selected_park

# After: Only fallback
if not st.session_state.session_context.current_park_code:
    st.session_state.session_context.current_park_code = st.session_state.selected_park
```

---

## 2. Fixed Multi-Part Query Handling (Equipment + Rental Locations)

### Problem
Queries like "What equipment do I need for The Narrows and where can I rent it from nearby?" weren't including amenity data because they were routed to `entity_lookup` which filtered out amenities.

### Fix Applied

#### `app/services/llm_service.py`
- Added `include_amenities` parameter to `_build_data_context()`
- Entity lookup handler now detects equipment/rental keywords
- Preserves amenities in context when `include_amenities=True`
- Enhanced prompt with rental/gear instructions

```python
amenity_keywords = ["rent", "buy", "purchase", "get", "equipment", "gear", "supplies", 
                   "where can", "nearby", "shop", "store", "outfitter"]
needs_amenities = any(kw in query_lower for kw in amenity_keywords)

data_context = self._build_data_context(
    ...,
    include_amenities=needs_amenities
)
```

---

## 3. Dynamic Park Name Mapping

### Problem
When the LLM returned "glacier" as the park code, the normalization wasn't mapping it correctly to "glac" (Glacier National Park). This caused the system to either fail to find the park or map to the wrong park (e.g., "glacier" → "glba" Glacier Bay).

### Fix Applied

#### `app/orchestrator.py`
Replaced hardcoded park name map with dynamic approach:

1. **Auto-generates mappings** from `SUPPORTED_PARKS`:
   - Park code itself: `"glac"` → `"glac"`
   - Full name without suffix: `"glacier"` → `"glac"`
   - Compressed name: `"glacierbay"` → `"glba"`

2. **Conflict detection**: 
   - First-word shortcuts only added if unique (no conflict)
   - E.g., "yosemite" is unique, but "glacier" conflicts with "glacier bay"

3. **Explicit aliases** for commonly searched terms:
   - `"glacier"` → `"glac"` (more common than Glacier Bay)
   - `"grand canyon"` → `"grca"`
   - `"grand teton"` / `"teton"` → `"grte"`
   - `"smoky mountains"` / `"smokies"` → `"grsm"`
   - `"death valley"` → `"deva"`
   - `"rainier"` → `"mora"`

---

## 4. Comprehensive Data Requirement Checks

### Problem
When users asked about parks with partial data (e.g., basic info but no trails), the system would still attempt to generate responses, leading to hallucinated content or generic answers.

### Fix Applied

#### `app/orchestrator.py`
Added `DATA_REQUIREMENTS` configuration that maps query types to required data files:

```python
DATA_REQUIREMENTS = {
    "trails": {
        "files": ["trails_v2.json"],
        "keywords": ["trail", "hike", "plan", "itinerary", "trip", "day"],
        "response_types": ["itinerary", "list_options"],
        "emoji": "🥾",
        "name": "trail data",
        "description": "trail recommendations and itineraries"
    },
    "photos": {
        "files": ["photo_spots.json"],
        "keywords": ["photo", "sunrise", "sunset", "camera", "viewpoint"],
        "emoji": "📸",
        ...
    },
    "drives": {
        "files": ["scenic_drives.json"],
        "keywords": ["drive", "road", "scenic", "car", "auto tour"],
        "emoji": "🚗",
        ...
    },
    "amenities": {
        "files": ["consolidated_amenities.json"],
        "keywords": ["gas", "restaurant", "rent", "gear", "pharmacy", "nearby"],
        "emoji": "🏪",
        ...
    }
}
```

### Behavior
For each query, the system:
1. Checks if required data files exist for that query type
2. If missing, **blocks the query** with a helpful message:
   > "I'd love to help with **photography location recommendations** for **Glacier National Park**! However, I don't have the **photo spot data** loaded yet. 📸
   >
   > **To get this information:**
   > 1. Go to the **🔭 Park Explorer** tab
   > 2. Select **Glacier National Park** from the dropdown
   > 3. Click the **🚀 Fetch Park Data** button"

3. For non-blocked queries with some missing data, appends an informational notice

---

## 5. Added Handling for Unsupported/Unloaded Parks

### Problem
When users asked about parks without loaded data (e.g., Death Valley), the chat gave a generic or confusing response.

### Fix Applied

#### `app/orchestrator.py`
Added checks after park code is resolved:

1. **Unsupported Parks** (not in `SUPPORTED_PARKS`):
   - Shows friendly message listing supported parks
   
2. **Supported but Unloaded Parks** (in list but no data):
   - Guides user to Park Explorer tab with step-by-step instructions
   
3. **Partial Data** (basic data exists but missing critical files):
   - Blocks queries that need missing data
   - Appends notice for other queries

#### `main.py` (User's additional changes)
- Added check for `EXPLORER_CRITICAL_FILES`
- Shows appropriate warning for partial vs. no data states

---

## 6. Expanded National Park Support

### Change
Updated `app/config.py` to include all **63 US National Parks** (alphabetically by park name).

### Parks with Full Data Support (✅)
- Bryce Canyon National Park (`brca`)
- Grand Canyon National Park (`grca`)
- Yosemite National Park (`yose`)
- Zion National Park (`zion`)

### All Other Parks
Listed alphabetically from Acadia to Zion. Users can select any park in Park Explorer and click "Fetch Park Data" to load data.

---

## Files Modified

| File | Changes |
|------|---------|
| `app/services/llm_service.py` | Context-aware intent parsing, multi-part query handling, include_amenities flag |
| `app/orchestrator.py` | Dynamic park mapping, comprehensive data requirement checks, block queries when data missing |
| `main.py` | Context inheritance fix, dropdown sync, partial data detection |
| `app/config.py` | Added all 63 US National Parks |

---

## Testing Recommendations

### Context Inheritance
1. Ask "Reviews for The Narrows"
2. Ask follow-up "What else can I do there?" → Should stay on Zion

### Multi-Part Queries
- "What equipment do I need for The Narrows and where can I rent it from nearby?"
- Should include both trail info AND nearby rental shops

### Unsupported Parks
- Ask "Tell me about Death Valley"
- Should guide user to fetch data via Park Explorer tab

### Data Requirement Blocking
| Query | Missing Data | Expected |
|-------|--------------|----------|
| "Plan a trip to Glacier" | trails_v2.json | Block + guide to fetch |
| "Best photo spots at Glacier" | photo_spots.json | Block + guide to fetch |
| "Scenic drives in Glacier" | scenic_drives.json | Block + guide to fetch |
| "Where can I get gas near Glacier" | consolidated_amenities.json | Block + guide to fetch |

### Park Name Normalization
| Input | Expected Code |
|-------|---------------|
| "glacier" | glac |
| "glacier bay" | glba |
| "grand canyon" | grca |
| "grand teton" | grte |
| "death valley" | deva |
| "yellowstone" | yell |

---

## Architecture Notes

### Intent Parsing Flow
```
User Query → parse_user_intent(query, current_park_code)
                    ↓
         LLM extracts intent + park_code (or null)
                    ↓
         Normalize park code (dynamic mapping)
                    ↓
         Context Merge: final_park_code = intent.park_code OR ctx.current_park_code
                    ↓
         Check data requirements for query type
                    ↓
         Block if required data missing, else proceed
```

### Park Data States
1. **Unsupported**: Not in SUPPORTED_PARKS dict
2. **No Data**: In dict but `has_basic_data()` returns False
3. **Partial Data**: Basic data exists but missing some files
4. **Full Data**: All files available

### Data Requirement Matrix
| Query Type | Required Files | Keywords |
|------------|---------------|----------|
| Trails/Itineraries | trails_v2.json | trail, hike, plan, trip |
| Photography | photo_spots.json | photo, sunrise, sunset, camera |
| Scenic Drives | scenic_drives.json | drive, road, scenic, car |
| Amenities | consolidated_amenities.json | gas, restaurant, rent, gear |

---

## Future Considerations

1. **Auto-fetch option**: Could trigger data fetch automatically from chat
2. **Progressive loading**: Load basic data immediately, enrich asynchronously
3. **Weather data check**: Add weather to DATA_REQUIREMENTS when needed
4. **Smarter LLM prompts**: For parks with partial data, modify prompts to not hallucinate missing info

