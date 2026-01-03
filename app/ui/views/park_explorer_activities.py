import streamlit as st
from app.models import ThingToDo

def render_activities_grid(activities: list[ThingToDo]):
    if not activities:
        st.info("No activities found for this park.")
        return

    # Filter logic: Exclude "Hiking" activities or items with "Trail" in title
    # as these belong in the Trails tab.
    filtered_activities = []
    for item in activities:
        is_hike = False
        # Check title
        if "trail" in item.title.lower():
            is_hike = True
        
        # Check activities list
        if not is_hike and item.activities:
            for act in item.activities:
                if act.get("name", "").lower() == "hiking":
                    is_hike = True
                    break
        
        if not is_hike:
            filtered_activities.append(item)
    
    if not filtered_activities:
        st.info("No non-hiking activities found.")
        return

    # Grid Layout
    cols = st.columns(3)
    
    for i, item in enumerate(filtered_activities):
        with cols[i % 3]:
            # Card Container
            with st.container(border=True):
                # Image
                if item.images:
                    img_url = item.images[0].url
                    if img_url.startswith("/"):
                        img_url = f"https://www.nps.gov{img_url}"
                    st.image(img_url, use_container_width=True)
                
                # Title & Duration
                st.subheader(item.title)
                if item.duration:
                    st.caption(f"⏱️ {item.duration}")
                
                # Description (Truncated)
                desc = item.shortDescription[:100] + "..." if len(item.shortDescription) > 100 else item.shortDescription
                st.write(desc)
                
                # Tags/Metadata
                tags = []
                if item.doFeesApply: tags.append("💲 Fee")
                if item.isReservationRequired: tags.append("📅 Reserv. Req.")
                if item.arePetsPermitted: tags.append("🐾 Pets OK")
                else: tags.append("🚫 No Pets")
                
                if tags:
                    st.write("  \n".join([f"`{t}`" for t in tags]))
                
                # Popover Details
                with st.popover("More Details", use_container_width=True):
                    st.markdown(f"### {item.title}")
                    if item.images:
                        st.image(item.images[0].url)
                    
                    st.markdown(item.longDescription if item.longDescription else item.shortDescription, unsafe_allow_html=True)
                    
                    if item.location:
                        st.write(f"**Location:** Lat: {item.location.lat}, Lon: {item.location.lon}")
                    
                    if item.season:
                        st.write(f"**Season:** {', '.join(item.season)}")
