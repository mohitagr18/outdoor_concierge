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
                tags = []
                if cam.isStreaming: tags.append("🔴 Live Stream")
                else: tags.append("📷 Static Image")
                st.write(" ".join([f"`{t}`" for t in tags]))
                
                # Image/Stream
                # Note: 'imageUrl' from adapter is the metadata image. 
                # For actual streams, we might need to iframe the 'url' or just link to it.
                # If it's a static image cam, 'imageUrl' usually updates.
                
                if cam.imageUrl:
                    # Robust relative URL check just in case
                    img_url = cam.imageUrl
                    if img_url.startswith("/"):
                        img_url = f"https://www.nps.gov{img_url}"
                        
                    st.image(img_url, caption=cam.title, use_container_width=True)
                else:
                    st.warning("No preview image available.")

                # Description
                with st.expander("Description"):
                    st.write(cam.description)
                
                # Link
                if cam.url:
                    st.link_button("View Live Feed on NPS.gov", cam.url)
