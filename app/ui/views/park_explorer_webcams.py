import streamlit as st
from app.models import Webcam

def render_webcams_grid(webcams: list[Webcam]):
    if not webcams:
        st.info("No webcams found for this park.")
        return

    st.markdown(f"### 📷 Park Webcams ({len(webcams)})")
    st.write("Live views and current conditions from around the park.")

    # Filter by status if needed, but usually we show all 'Active' ones
    active_cams = [w for w in webcams if w.status == "Active"]
    
    # Deduplicate by Title
    deduped = {}
    for cam in active_cams:
        if cam.title not in deduped:
            deduped[cam.title] = cam
        else:
            # Logic: Prefer one with isStreaming=True, or one with imageUrl if curr doesn't have it
            current = deduped[cam.title]
            
            # If new one is streaming and current is not, take new one
            if cam.isStreaming and not current.isStreaming:
                deduped[cam.title] = cam
            # If both/neither match stream status, prefer one with an image URL
            elif not current.imageUrl and cam.imageUrl:
                deduped[cam.title] = cam
                
    active_cams = list(deduped.values())


    if not active_cams:
        st.warning("No active webcams available.")
        if webcams:
            with st.expander("Show Inactive Webcams"):
                for w in webcams:
                    st.write(f"- {w.title} ({w.status})")
        return

    # Grid Layout
    cols = st.columns(2)
    
    for i, cam in enumerate(active_cams):
        with cols[i % 2]:
            with st.container(border=True):
                # Header
                st.subheader(cam.title)
                
                # Tags
                if cam.isStreaming:
                    st.write("`🔴 Live Stream`")
                
                # Image/Stream (Preview)
                if cam.imageUrl:
                    # Robust relative URL check just in case
                    img_url = cam.imageUrl
                    if img_url.startswith("/"):
                        img_url = f"https://www.nps.gov{img_url}"
                    
                    # Fix potential double-prefix data errors
                    if "https://www.nps.govhttps://www.nps.gov" in img_url:
                        img_url = img_url.replace("https://www.nps.govhttps://www.nps.gov", "https://www.nps.gov")
                        
                    st.image(img_url, caption=cam.title, use_container_width=True)

                # Link & Iframe
                if cam.url:
                    # Allow embedding for all cams (some static ones update frequently on the page)
                    with st.expander("🌐 View on NPS Site (Embed)", expanded=True):
                        try:
                            # Attempt to embed the NPS page
                            st.components.v1.iframe(cam.url, height=500, scrolling=True)
                            st.caption("If the view doesn't load, use the external link below.")
                        except Exception as e:
                            st.error(f"Could not load view: {e}")
                    
                    st.link_button("Open in New Tab", cam.url)


