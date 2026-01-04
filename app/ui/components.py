import streamlit as st
from datetime import datetime
try:
    from app.models import Event
except ImportError:
    # Fallback for circular import or testing if needed, though mostly expected to work
    pass

def render_card(
    title: str,
    image_url: str | None = None,
    subtitle: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    key_vals: dict[str, str] | None = None,
    details_content: str | None = None, 
):
    """
    Renders a vertical card layout used for Things to Do, Places, etc.
    """
    with st.container(border=True):
        # Image
        if image_url:
            # Handle relative NPS URLs
            if image_url.startswith("/"):
                image_url = f"https://www.nps.gov{image_url}"
            st.image(image_url, use_container_width=True)
        
        # Title
        st.subheader(title)
        
        # Subtitle
        if subtitle:
            st.caption(subtitle)
        
        # Description
        if description:
            st.write(description)
            
        # Key-Values (e.g. Location: x,y)
        if key_vals:
            for k, v in key_vals.items():
                st.write(f"**{k}:** {v}")
            
        # Tags
        if tags:
            st.write("  \n".join([f"`{t}`" for t in tags]))
            
        # Details Popover
        if details_content:
            with st.popover("More Details", use_container_width=True):
                st.markdown(f"### {title}")
                if image_url:
                    st.image(image_url)
                st.markdown(details_content, unsafe_allow_html=True)

def render_event_card(event):
    """
    Renders a specialized horizontal card for Events with Date Badge.
    Args:
        event: app.models.Event object
    """
    with st.container(border=True):
        c1, c2, c3 = st.columns([1, 3, 1])
        
        # Date Badge (Column 1)
        with c1:
            e_dates = getattr(event, "dates", [])
            # Badge Logic
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

        # Details (Column 2)
        with c2:
            st.subheader(event.title)
            
            # Date Range
            date_range_str = ""
            if event.date_start:
                try:
                    d_start = datetime.strptime(event.date_start, "%Y-%m-%d").strftime("%b %d, %Y")
                    date_range_str = f"**Range:** {d_start}"
                    if event.date_end:
                        d_end = datetime.strptime(event.date_end, "%Y-%m-%d").strftime("%b %d, %Y")
                        date_range_str += f" - {d_end}"
                except:
                     # Fallback if parsing fails
                     date_range_str = f"**Range:** {event.date_start}"
                     if event.date_end: date_range_str += f" - {event.date_end}"
            
            if date_range_str:
                st.write(f"📅 {date_range_str}")

            # Specific Dates expansion logic
            if len(e_dates) > 0:
                 def fmt_d(d):
                     try: return datetime.strptime(d, "%Y-%m-%d").strftime("%b %d, %Y")
                     except: return d
                 
                 if len(e_dates) <= 10 and len(e_dates) > 1:
                     dates_str = ", ".join([fmt_d(d) for d in e_dates])
                     st.write(f"**Specific Dates:** {dates_str}")
                 elif len(e_dates) > 10:
                     with st.expander(f"View all {len(e_dates)} occurrence dates"):
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
            base_tags = [t for t in getattr(event, "tags", []) if t not in ["🆓 Free", "💲 Fee Applies"]]
            tags = base_tags.copy()
            if event.is_free: tags.append("🆓 Free")
            elif getattr(event, "fee_info", None): tags.append("💲 Fee Applies")
            
            st.write(" ".join([f"`{t}`" for t in tags]))
            
            fee_text = getattr(event, "fee_info", None)
            if fee_text and event.is_free:
                 st.caption(f"*{fee_text}*")

        # Image (Column 3)
        with c3:
            imgs = getattr(event, "images", [])
            if imgs:
                img_url = imgs[0].url
                if img_url.startswith("/"):
                    img_url = f"https://www.nps.gov{img_url}"
                st.image(img_url, use_container_width=True)
