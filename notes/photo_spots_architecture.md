# Photo Spots Functionality

## Overview
The **Photo Spots** feature aggregates expert photography advice for National Parks by finding, reading, and structuring data from high-quality photography blogs. This allows the application to provide "insider tips" (best times, specific compositions) that aren't typically found in standard NPS data.

## Core Script: `fetch_photo_spots.py`
This standalone script runs on-demand to populate the data fixtures for a specific park.

### Workflow
1.  **Configuration**: The script reads the `PARK_CODE` from the environment (default: `ZION`). It uses an internal map to translate this code into a full search query (e.g., `ZION` -> "Zion National Park").
2.  **Discovery (Serper API)**:
    *   Searches Google for query: *"best photography spots {Park Name} guide blog"*
    *   Retrieves the top organic search results, prioritizing high-quality guides.
3.  **Acquisition (Firecrawl)**:
    *   Visits the discovered blog URLs.
    *   Scrapes the page content and converts it into clean Markdown, stripping away ads and navigation.
4.  **Extraction (Gemini 1.5 Flash)**:
    *   Passes the Markdown content to Gemini.
    *   Uses a strict Pydantic schema to extract a list of `PhotoSpot` objects containing:
        *   `name`: Name of the specific location.
        *   `best_time`: Ideal lighting conditions (Sunrise, Sunset, Milky Way, etc.).
        *   `tips`: Specific advice on composition, gear, or seasonality.
5.  **Storage**:
    *   Deduplicates spots based on name.
    *   Saves the final structured JSON to `data_samples/ui_fixtures/{PARK_CODE}/photo_spots.json`.

### Tech Stack
*   **Search**: Google Serper API
*   **Scraping**: Firecrawl (Markdown mode)
*   **AI/Extraction**: Google Gemini 1.5 Flash (Structured Output)
*   **Validation**: Pydantic

## Usage
```bash
# Fetch spots for a specific park
PARK_CODE=YOSE python fetch_photo_spots.py
```
