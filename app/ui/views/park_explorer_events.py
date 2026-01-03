import streamlit as st
from datetime import datetime
from app.models import Event

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

    # Filter Controls
    col1, col2 = st.columns([1, 3])
    with col1:
        filter_date = st.checkbox("Show only during my visit", value=True if visit_date else False)
    
    # Filter Logic
    display_events = final_events
    if filter_date and visit_date:
        filtered = []
        v_str = visit_date.strftime("%Y-%m-%d")
        for e in final_events:
            # Check explicit dates list if available
            e_dates = getattr(e, "dates", [])
            if e_dates:
                if v_str in e_dates:
                    filtered.append(e)
                    continue
            
            # Check ranges
            if e.date_start <= v_str:
                end = e.date_end if e.date_end else e.date_start
                if end >= v_str:
                    filtered.append(e)
                    
        display_events = filtered

    if not display_events:
        st.info("No events scheduled for this period.")
        return

    st.caption(f"Showing {len(display_events)} distinct events")

    for event in display_events:
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 3, 1])
            
            # Date Badge (Logic: Show 'Multiple Dates' or specific range)
            with c1:
                e_dates = getattr(event, "dates", [])
                if len(e_dates) > 1:
                     st.markdown(f"""
                    <div style="text-align: center; border: 1px solid #ddd; border-radius: 5px; padding: 5px; background-color: #f9f9f9;">
                        <div style="font-size: 1.0em; font-weight: bold; color: #2c3e50;">Multiple</div>
                        <div style="font-size: 1.4em; font-weight: bold;">Dates</div>
                        <div style="font-size: 0.8em; color: #7f8c8d;">{len(e_dates)} occurrences</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    # Single date logic
                    try:
                        dt = datetime.strptime(event.date_start, "%Y-%m-%d")
                        st.markdown(f"""
                        <div style="text-align: center; border: 1px solid #ddd; border-radius: 5px; padding: 5px;">
                            <div style="font-size: 1.2em; font-weight: bold; color: #d35400;">{dt.strftime('%b')}</div>
                            <div style="font-size: 1.8em; font-weight: bold;">{dt.strftime('%d')}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    except:
                        st.write(event.date_start)

            # Details
            with c2:
                st.subheader(event.title)
                
                # Show Dates List if multiple
                if len(e_dates) > 1:
                     # Show first few dates
                     readable_dates = []
                     for d in e_dates[:5]: # Cap at 5
                         try:
                             readable_dates.append(datetime.strptime(d, "%Y-%m-%d").strftime("%b %d"))
                         except: pass
                     
                     dates_str = ", ".join(readable_dates)
                     if len(e_dates) > 5: dates_str += ", ..."
                     st.write(f"📅 **Upcoming:** {dates_str}")

                # Times
                if event.times:
                    times_str = ", ".join([f"{t.get('timestart')} - {t.get('timeend')}" for t in event.times])
                    st.write(f"🕒 {times_str}")
                
                # Location
                if event.location:
                    st.write(f"📍 {event.location}")
                
                # Description
                with st.expander("Description"):
                    st.markdown(event.description, unsafe_allow_html=True)
                
                # Tags
                tags = getattr(event, "tags", []).copy()
                if event.is_free: tags.append("🆓 Free")
                if getattr(event, "fee_info", None): tags.append("💲 Fee Applies")
                st.write(" ".join([f"`{t}`" for t in tags]))

            # Image
            with c3:
                imgs = getattr(event, "images", [])
                if imgs:
                    st.image(imgs[0].url, use_container_width=True)
