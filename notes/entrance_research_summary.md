# Entrance Identification Research & Data Audit Summary
**Date:** 2025-12-28

## Objective
To identify a reliable, programmatic method for extracting national park entrance coordinates from NPS `places.json` data. This is required to facilitate "nearby amenity" searches (e.g., searching for gas stations near a park entrance).

## Work Performed
1.  **Data Capture Audit:** Reviewed all captured data points across NPS, WeatherAPI, and Serper clients to ensure comprehensive coverage.
2.  **Pattern Analysis:** Examined `places.json` and `visitorcenters.json` for specific parks (Yosemite, Zion, Grand Canyon) to find common patterns for entrance locations.

## Issues Encountered

### 1. Inconsistent Naming Conventions
*   **Issue:** While Yosemite (YOSE) explicitly includes "Entrance" in the entries' titles (e.g., "Arch Rock Entrance"), other parks like Zion (ZION) do not. Zion often nests this information in descriptions or relies on Visitor Center locations.
*   **Impact:** A simple text search for "Entrance" in the `title` field is insufficient and brittle.

### 2. Data Mismatch (Critical)
*   **Issue:** The directory `data_samples/nps/GRCA/` was found to contain data for **Bandelier National Monument** (`parkCode: band`) instead of the Grand Canyon.
*   **Evidence:** `park_details.json` and `places.json` in that directory list "Bandelier" and coordinates for New Mexico (approx. lat 35.7), whereas Grand Canyon is in Arizona.
*   **Impact:** Any analysis assuming this was Grand Canyon data would be incorrect. However, since Bandelier is a valid NPS unit, it served as a useful third test case for our logic.

## Resolutions & Strategy

### 1. Unified Identification Strategy
We determined that searching for specific **amenities** is the most robust method for identifying entrances across different parks.
*   **Key Signal:** The amenity string `"Entrance Passes for Sale"` is consistently present in the `amenities` list for entrance stations and visitor centers at entrances across all observed parks (YOSE, ZION, and the Bandelier sample).
*   **Secondary Signals:**
    *   **Visitor Centers:** Almost always act as proxies for entrances.
    *   **Title Keywords:** "Entrance Station", "Automated Entrance".

### 2. Artifact Creation
*   Created `entrance_identification_strategy.md` in the artifacts directory. This document outlines the logic:
    ```python
    if "Entrance Passes for Sale" in place.amenities:
        return True
    elif "Entrance" in place.title:
        return True
    ```

## Next Steps
1.  **Fix Data Fetching:** The script for fetching `GRCA` data needs to be verified to ensure it pulls the correct park code (`grca`).
2.  **Implementation:** Create a helper utility in `app/utils/` or `app/clients/nps_client.py` that implements the `is_likely_entrance()` logic to return a list of coordinates for a given park.
