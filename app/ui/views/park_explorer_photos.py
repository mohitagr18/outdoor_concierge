import streamlit as st

def get_time_badge_style(time_str):
    """
    Returns (bg_color, text_color) based on the time of day
    to create distinct visual badges.
    """
    t = time_str.lower()
    if "sunrise" in t or "dawn" in t:
        return "#fff7ed", "#c2410c"  # Orange-ish
    if "sunset" in t or "dusk" in t:
        return "#fff1f2", "#be123c"  # Red/Pink-ish
    if "night" in t or "milky way" in t or "star" in t:
        return "#f5f3ff", "#6d28d9"  # Violet/Dark
    if "golden" in t:
        return "#fefce8", "#a16207"  # Gold/Yellow
    if "mid" in t or "day" in t or "noon" in t:
        return "#eff6ff", "#1d4ed8"  # Blue
    
    # Default Gray
    return "#f3f4f6", "#374151"

def render_photo_spots(photo_spots):
    """
    Renders a masonry-style grid of photography spots.
    Expects a list of PhotoSpot Pydantic objects.
    """
    st.markdown("### 📸 Best Photography Spots")
    st.caption("Curated locations for the best lighting and compositions.")

    if not photo_spots:
        st.info("No photography guides available for this park yet.")
        return

    # Create a 3-column layout for a masonry-like effect
    cols = st.columns(3)
    
    for idx, spot in enumerate(photo_spots):
        col = cols[idx % 3]
        
        with col:
            with st.container(border=True):
                # 1. Image (Fallback to placeholder if None)
                # Access attribute directly instead of .get()
                image_url = getattr(spot, "image_url", None)
                
                if not image_url:
                    # Clean placeholder with spot name
                    safe_name = spot.name.replace(" ", "+")
                    image_url = f"https://placehold.co/600x400/EEE/31343C?text={safe_name}"
                
                st.image(image_url, use_container_width=True)
                
                # 2. Title & Description
                st.subheader(spot.name)
                # Use getattr for safety, though Pydantic guarantees field existence
                desc = getattr(spot, "description", "")
                st.markdown(f"<small>{desc}</small>", unsafe_allow_html=True)
                
                st.write("") # Spacer
                
                # 3. Best Time Badges
                best_times = getattr(spot, "best_time_of_day", [])
                badges_html = ""
                for time in best_times:
                    bg, txt = get_time_badge_style(time)
                    badges_html += (
                        f'<span style="background-color:{bg}; color:{txt}; '
                        f'padding:4px 8px; border-radius:12px; font-size:12px; '
                        f'margin-right:4px; font-weight:600; display:inline-block; margin-bottom:4px;">'
                        f'{time}</span>'
                    )
                
                if badges_html:
                    st.markdown(badges_html, unsafe_allow_html=True)
                    st.write("") # Spacer
                
                # 4. Pro Tips Expander
                tips = getattr(spot, "tips", [])
                if tips:
                    with st.expander("💡 Pro Tips", expanded=False):
                        for tip in tips:
                            st.markdown(f"- {tip}")
