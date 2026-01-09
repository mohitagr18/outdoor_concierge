import streamlit as st
from typing import List, Any, Optional


# Keywords to identify road closure alerts
ROAD_KEYWORDS = ['road', 'drive', 'highway', 'hwy', 'route', 'tioga', 'glacier point', 'wawona']
CLOSURE_KEYWORDS = ['closed', 'closure', 'shut', 'blocked', 'impassable', 'not accessible']


def _get_road_closure_alerts(alerts: List[Any]) -> List[Any]:
    """Filter alerts that are specifically about road closures."""
    closure_alerts = []
    for alert in alerts:
        title = getattr(alert, 'title', '') or ''
        desc = getattr(alert, 'description', '') or ''
        combined = (title + ' ' + desc).lower()
        
        # Must mention BOTH a road AND a closure
        has_road = any(kw in combined for kw in ROAD_KEYWORDS)
        has_closure = any(kw in combined for kw in CLOSURE_KEYWORDS)
        
        if has_road and has_closure:
            closure_alerts.append(alert)
    
    return closure_alerts


def render_scenic_drives(scenic_drives: List[Any], alerts: Optional[List[Any]] = None):
    """
    Render scenic drives from scenic_drives.json fixture.
    Follows the same display pattern as Photo Spots.
    
    Args:
        scenic_drives: List of ScenicDrive objects
        alerts: Optional list of Alert objects to check for road closures
    """
    st.markdown("### 🚗 Scenic Drives")
    st.caption("Explore the park's most beautiful routes by car.")
    
    # Display road closure alerts if any
    if alerts:
        road_alerts = _get_road_closure_alerts(alerts)
        if road_alerts:
            for alert in road_alerts:
                title = getattr(alert, 'title', 'Road Alert')
                desc = getattr(alert, 'description', '')
                url = getattr(alert, 'url', None)
                
                # Build link HTML separately (only if URL exists and is not empty)
                link_html = ""
                if url and url.strip():
                    link_html = f'<div style="margin-top: 8px;"><a href="{url}" target="_blank" style="color: #b45309; font-size: 0.85em; font-weight: 600; text-decoration: none;">View Details ↗</a></div>'
                
                alert_html = (
                    f'<div style="background: linear-gradient(135deg, #fef3c7, #fde68a); border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 8px; margin-bottom: 16px;">'
                    f'<div style="font-weight: 700; color: #92400e; margin-bottom: 4px;">⚠️ {title}</div>'
                    f'<div style="font-size: 0.9em; color: #78350f;">{desc}</div>'
                    f'{link_html}'
                    f'</div>'
                )
                st.markdown(alert_html, unsafe_allow_html=True)
    
    if not scenic_drives:
        st.info("No scenic drive data available for this park. Run the fetch script to populate data.")
        return
    
    # Sort by rank
    sorted_drives = sorted(scenic_drives, key=lambda x: getattr(x, 'rank', 999) or 999)
    
    cols = st.columns(3)
    
    for idx, drive in enumerate(sorted_drives):
        col = cols[idx % 3]
        
        with col:
            with st.container(border=True):
                # Image
                img = getattr(drive, "image_url", None)
                if not img or "http" not in str(img):
                    safe_name = drive.name.replace(" ", "+")
                    img = f"https://placehold.co/600x400/EEE/31343C?text={safe_name}"
                st.image(img, use_container_width=True)
                
                # Header with rank
                rank = getattr(drive, "rank", None)
                rank_str = f"#{rank} " if rank else ""
                st.subheader(f"{rank_str}{drive.name}")
                
                # Badges row
                badges = []
                distance = getattr(drive, "distance_miles", None)
                if distance:
                    badges.append(f"📏 {distance} mi")
                drive_time = getattr(drive, "drive_time", None)
                if drive_time:
                    badges.append(f"⏱️ {drive_time}")
                best_time = getattr(drive, "best_time", None)
                if best_time:
                    badges.append(f"🌅 {best_time}")
                
                if badges:
                    st.caption(" • ".join(badges))
                
                # Description
                desc = getattr(drive, "description", "")
                if desc:
                    st.markdown(f"<span style='color:#555; font-size:0.9em'>{desc}</span>", unsafe_allow_html=True)
                
                # Highlights
                highlights = getattr(drive, "highlights", [])
                if highlights:
                    st.write("")
                    st.markdown(
                        "<div style='font-size:0.75em; color:#6b7280; font-weight:700; margin-bottom:4px; letter-spacing:0.05em;'>KEY STOPS</div>", 
                        unsafe_allow_html=True
                    )
                    highlights_html = ""
                    for h in highlights[:5]:  # Limit to 5
                        highlights_html += (
                            f'<span style="'
                            f'background-color: #f0fdf4; color: #15803d; '
                            f'padding: 4px 10px; border-radius: 12px; font-size: 12px; '
                            f'font-weight: 600; margin-right: 6px; display: inline-block; margin-bottom: 4px;'
                            f'">📍 {h}</span>'
                        )
                    st.markdown(highlights_html, unsafe_allow_html=True)
                
                # Tips
                tips = getattr(drive, "tips", [])
                if tips:
                    st.write("")
                    with st.expander("💡 Driving Tips", expanded=False):
                        for tip in tips:
                            st.markdown(f"- {tip}")
                
                # Footer with source
                src = getattr(drive, "source_url", None)
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
