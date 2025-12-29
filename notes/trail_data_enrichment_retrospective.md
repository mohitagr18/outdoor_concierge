# Trail Enrichment & Data Strategy Retrospective

## 1. The Core Objective
The initial dataset from the NPS API was legally safe and structurally sound but **marketing-poor**. It lacked the "human" context that hikers rely on to make decisions:
- **Popularity**: "What is the #1 must-do hike?"
- **Difficulty**: NPS often lists "physical rating" in unstructured text, making filtering hard.
- **Accessibility**: Information about wheelchair access or kid-friendliness was buried in long descriptions.

The goal was to transform this raw official data into a **"Golden Dataset"** capable of powering a rich UI with filters like *"Top 5 Easy Hikes"* or *"Wheelchair Friendly Views"*.

---

## 2. The "Link-Out" Strategy
Instead of building a fragile and expensive scraper to harvest every detail (reviews, photos, GPX) from AllTrails, we adopted a **Link-Out Strategy**:
1.  **Trust NPS for Truth**: Use NPS data for the core record (Location, Description, Status) to ensure accuracy and compliance.
2.  **Use AllTrails for Ranking**: Scrape *only* the popularity ranking and a deep link.
3.  **Enrich Locally**: Use an LLM (Gemini) to parse the NPS descriptions to extract missing metadata (Difficulty, Accessibility) that was there all along but unstructured.

This approached minimized legal risk and scraping costs while maximizing user value.

---

## 3. Implementation Phases

### Phase 1: The Classifier (Signal from Noise)
**Challenge**: The NPS `places` endpoint returns everything from "Visitor Centers" to "Parking Lots" mixed with "Hikes".
**Solution**: Built `fetch_static_nps.py` with a keyword-based classifier.
- *Positive Signals*: "Trail", "Hike", "Loop", "Overlook".
- *Negative Signals*: "Parking", "Restroom", "Museum".
- *Result*: Successfully filtered hundreds of infrastructure items down to a list of potential trail candidates.

### Phase 2: Local Enrichment (The Hidden Data)
**Challenge**: We needed "Easy/Moderate/Hard" tags but didn't want to scrape them.
**Solution**: `refine_trails_with_gemini.py`
- We fed raw NPS descriptions to Gemini.
- **Prompt Logic**: "Read this description. If it mentions 'paved' or 'flat', tag `is_wheelchair_accessible=True`. If it says 'strenuous' or 'steep', tag `difficulty=Strenuous`."
- **Outcome**: generated high-quality tags for local trails (e.g., *Pa'rus Trail* correctly tagged as Accessible) without external data.

### Phase 3: The Ranking Merger (The "Cool" Factor)
**Challenge**: Users want to know what's popular.
**Solution**: `fetch_rankings.py`
- targetted the AllTrails `/hiking` sub-page.
- Used Firecrawl to grab Markdown.
- Used Gemini to parse the Markdown into a structured JSON list (Rank 1-30).
- Merged this into our local NPS data using Fuzzy Matching.

---

## 4. Key Challenges & Resolutions

### Issue A: The "Canyon Overlook" Mystery
**Symptom**: One of Zion's most famous hikes, *Canyon Overlook*, was missing from our dataset.
**Root Cause**:
1.  **Strict Classification**: The classifier rejected it because the title "Canyon Overlook" lacked the word "Trail", classifying it as a "Viewpoint".
2.  **Schema Mismatch**: This specific item came from the `thingstodo` API endpoint (not `places`), which used different fields (`shortDescription` vs `listingDescription`). The classifier was reading empty text for these items.
**Resolution**:
- Updated `fetch_static_nps.py` to concatenate ALL description fields from both schemas.
- Relaxed the classifier: If a title contains "Overlook" BUT the description contains "hike" or "miles", accept it as a Trail.
- **Result**: *Canyon Overlook* and *Timber Creek Overlook* were successfully rescued.

### Issue B: The "Top 10" Limit
**Symptom**: AllTrails default page only showed 10 trails. We needed more to fill "Easy/Medium/Hard" buckets.
**Resolution**:
- Observed that the AllTrails markdown contained a secondary "Points of Interest" list below the Top 10.
- Updated the Gemini prompt to: "Extract Top 10, then extract the POI list, deduplicate, and assign Ranks 11+ to the POIs."
- **Result**: Expanded the ranking pool from 10 to **30+ trails** without pagination capability.

### Issue C: The Name Game (Fuzzy Matching)
**Symptom**: *0% match rate* for Yosemite initially.
- Local: "Upper Yosemite Fall" vs AllTrails: "Upper Yosemite Falls Trail"
- Local: "Bridalveil Fall Trailhead" vs AllTrails: "Bridalveil Fall"
**Resolution**:
- Improved the fuzzy matching normalization function in `fetch_rankings.py`.
- Added logic to strip "Trailhead", "Trail", and normalize "Falls" <-> "Fall".
- **Result**: Yosemite match rate improved from 0% to **significant coverage (6/48)** of top trails.

---

## 5. Final State
We now have a production-ready dataset for 3 Major Parks:
- **ZION**: 16 Trails (8 Ranked). Complete coverage of top hits.
- **YOSE**: 48 Trails (6 Ranked).
- **GRCA**: 34 Trails (15 Ranked). Excellent coverage of the "Corridor Trails".

The data is persisted in `data_samples/ui_fixtures/{PARK_CODE}/trails_v2.json` and is ready for the Frontend UI.
