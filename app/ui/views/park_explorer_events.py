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
    
    # Sort events by date if possible (optional, but good for UX)
    # final_events.sort(key=lambda x: x.date_start)

    if not final_events:
        st.info("No events found.")
        return

    st.caption(f"Showing {len(final_events)} distinct events")

    for event in final_events:
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 3, 1])
            
            # Date Badge
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
                
                # Date Range & Specific Dates
                date_range_str = ""
                if event.date_start:
                    try:
                        d_start = datetime.strptime(event.date_start, "%Y-%m-%d").strftime("%b %d, %Y")
                        date_range_str = f"**Range:** {d_start}"
                        if event.date_end:
                            d_end = datetime.strptime(event.date_end, "%Y-%m-%d").strftime("%b %d, %Y")
                            date_range_str += f" - {d_end}"
                    except:
                        date_range_str = f"**Range:** {event.date_start}"
                        if event.date_end: date_range_str += f" - {event.date_end}"
                
                if date_range_str:
                    st.write(f"📅 {date_range_str}")

                if len(e_dates) > 0:
                     # Helper to format dates
                     def fmt_d(d):
                         try: return datetime.strptime(d, "%Y-%m-%d").strftime("%b %d, %Y")
                         except: return d
                     
                     if len(e_dates) <= 1:
                         # Single date matched start date usually, so maybe redundant if range is shown
                         # But let's show it if it differs or just to be safe
                         pass
                     elif len(e_dates) <= 10:
                         # Show all inline
                         dates_str = ", ".join([fmt_d(d) for d in e_dates])
                         st.write(f"**Specific Dates:** {dates_str}")
                     else:
                         # Show summary and expander with grid layout
                         with st.expander(f"View all {len(e_dates)} occurrence dates"):
                             # formatted_dates = [fmt_d(d) for d in e_dates]
                             cols = st.columns(4)
                             for i, d in enumerate(e_dates):
                                 cols[i % 4].write(fmt_d(d))

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
                # Filter out any existing fee/free tags to prevent duplicates during re-runs
                base_tags = [t for t in getattr(event, "tags", []) if t not in ["🆓 Free", "💲 Fee Applies"]]
                tags = base_tags.copy()
                
                # Fee Logic: Mutually exclusive tags
                if event.is_free:
                    tags.append("🆓 Free")
                elif getattr(event, "fee_info", None): 
                    tags.append("💲 Fee Applies")
                    
                st.write(" ".join([f"`{t}`" for t in tags]))
                
                # Show fee info text if available (clarifies "Free with park admission")
                fee_text = getattr(event, "fee_info", None)
                if fee_text and event.is_free:
                     st.caption(f"*{fee_text}*")

            # Image
            with c3:
                imgs = getattr(event, "images", [])
                if imgs:
                    img_url = imgs[0].url
                    # Safety check for stale objects with relative URLs
                    if img_url.startswith("/"):
                        img_url = f"https://www.nps.gov{img_url}"
                    st.image(img_url, use_container_width=True)
