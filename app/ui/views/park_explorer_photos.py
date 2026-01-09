import streamlit as st

def get_tag_html(text, tag_type="default"):
    """
    Renders a styled pill badge.
    """
    if tag_type == "time":
        bg_color, text_color = "#eff6ff", "#1d4ed8" # Blue
        icon = "🕒"
    elif tag_type == "season":
        bg_color, text_color = "#f0fdf4", "#15803d" # Green
        icon = "📅"
    else:
        bg_color, text_color = "#f3f4f6", "#374151"
        icon = "🔹"

    return (
        f'<span style="'
        f'background-color: {bg_color}; color: {text_color}; '
        f'padding: 4px 10px; border-radius: 12px; font-size: 12px; '
        f'font-weight: 600; margin-right: 6px; display: inline-block; margin-bottom: 4px;'
        f'">{icon} {text}</span>'
    )

def classify_and_render_tags(spot):
    """
    Heuristic to separate mixed-up tags into Time vs Season
    since the scraper might have dumped everything into 'best_time_of_day'.
    """
    # 1. Gather all potential tags
    raw_times = getattr(spot, "best_time_of_day", [])
    raw_seasons = getattr(spot, "best_seasons", [])
    
    # Flatten just in case
    all_tags = set(raw_times + raw_seasons)
    
    # 2. Define buckets
    time_bucket = []
    season_bucket = []
    
    # Keywords for detection
    season_keywords = [
        "spring", "summer", "fall", "autumn", "winter",
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
        "year", "round"
    ]
    
    for tag in all_tags:
        clean_tag = tag.lower()
        if any(k in clean_tag for k in season_keywords):
            season_bucket.append(tag)
        else:
            time_bucket.append(tag)
            
    # 3. Render Time Row
    if time_bucket:
        st.markdown(
            "<div style='font-size:0.75em; color:#6b7280; font-weight:700; margin-bottom:4px; letter-spacing:0.05em; margin-top:8px;'>BEST TIME</div>", 
            unsafe_allow_html=True
        )
        html = "".join([get_tag_html(t, "time") for t in sorted(time_bucket)])
        st.markdown(html, unsafe_allow_html=True)

    # 4. Render Season Row
    if season_bucket:
        st.markdown(
            "<div style='font-size:0.75em; color:#6b7280; font-weight:700; margin-bottom:4px; letter-spacing:0.05em; margin-top:8px;'>BEST SEASON</div>", 
            unsafe_allow_html=True
        )
        html = "".join([get_tag_html(s, "season") for s in sorted(season_bucket)])
        st.markdown(html, unsafe_allow_html=True)


def render_photo_spots(photo_spots):
    st.markdown("### 📸 Best Photography Spots")
    st.caption("Top rated locations ordered by popularity.")

    if not photo_spots:
        st.info("No photography data found.")
        return

    # Sort by rank
    sorted_spots = sorted(photo_spots, key=lambda x: getattr(x, 'rank', 999) or 999)

    cols = st.columns(3)
    
    for idx, spot in enumerate(sorted_spots):
        col = cols[idx % 3]
        
        with col:
            with st.container(border=True):
                # Image
                img = getattr(spot, "image_url", None)
                if not img or "http" not in img:
                    safe_name = spot.name.replace(" ", "+")
                    img = f"https://placehold.co/600x400/EEE/31343C?text={safe_name}"
                st.image(img, use_container_width=True)
                
                # Header
                rank = getattr(spot, "rank", None)
                rank_str = f"#{rank} " if rank else ""
                st.subheader(f"{rank_str}{spot.name}")
                
                # Desc
                desc = getattr(spot, "description", "")
                if desc:
                    st.markdown(f"<span style='color:#555; font-size:0.9em'>{desc}</span>", unsafe_allow_html=True)

                # --- SMART TAG RENDERER ---
                classify_and_render_tags(spot)
                # --------------------------

                # Tips
                tips = getattr(spot, "tips", [])
                if tips:
                    st.write("")
                    with st.expander("💡 Pro Tips", expanded=False):
                        for tip in tips:
                            st.markdown(f"- {tip}")

                # Footer
                src = getattr(spot, "source_url", None)
                if src:
                    st.markdown(
                        f"<div style='margin-top:4px; margin-bottom:4px;'>"
                        f"<a href='{src}' target='_blank' style='"
                        f"display: inline-block; padding: 8px 8px; "
                        f"background: linear-gradient(135deg, #3b82f6, #2563eb); color: white; "
                        f"border-radius: 8px; font-size: 0.85em; font-weight: 600; "
                        f"text-decoration: none; box-shadow: 0 2px 4px rgba(37,99,235,0.3);'>"
                        f"📖 Read Guide ↗</a>"
                        f"</div>", 
                        unsafe_allow_html=True
                    )
