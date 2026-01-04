import streamlit as st
from datetime import datetime
from app.models import Event
from app.ui.components import render_event_card

def render_events_list(events: list[Event], visit_date: datetime.date = None):
    # deduplicate logic: attributes to dict mapping
    # Key = Title, Value = Event object (augmented with all dates)
    deduped = {}
    
    for e in events:
        if e.title not in deduped:
            # Create a clone effectively
            deduped[e.title] = e
            # Ensure dates field is populated from ranges if empty
            if not getattr(e, "dates", []):
                # If no specific dates but has range, we rely on range display
                # But for deduplication we mainly aggregate 'dates' if they exist or just keep instances
                pass
        else:
            # Merge dates
            current = deduped[e.title]
            new_dates = getattr(e, "dates", [])
            current_dates = getattr(current, "dates", [])
            
            # Combine and sort unique dates
            all_dates = sorted(list(set(current_dates + new_dates)))
            try:
                current.dates = all_dates
            except ValueError:
                # Stale model schema in cache
                pass
            
            # If the current one doesn't have an image but the new one does, take it
            if not getattr(current, "images", []) and getattr(e, "images", []):
                try:
                    current.images = e.images
                except ValueError:
                    pass

    # Flatten back to list
    final_events = list(deduped.values())
    
    # Sort events by date if possible (optional, but good for UX)
    # final_events.sort(key=lambda x: x.date_start)

    if not final_events:
        st.info("No events found.")
        return

    st.caption(f"Showing {len(final_events)} distinct events")

    # Deduplicate/Filter Logic (Keep existing logic up to filtering)
    # ... (Actually I need to keep the dedup loop, only replace the rendering loop)

    for event in final_events:
        render_event_card(event)
