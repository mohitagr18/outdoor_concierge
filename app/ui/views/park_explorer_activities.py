import streamlit as st
from app.models import ThingToDo
from app.ui.components import render_card

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
            # Prepare Data for Card
            
            # Tags
            tags = []
            if item.doFeesApply: tags.append("💲 Fee")
            if item.isReservationRequired: tags.append("📅 Reserv. Req.")
            if item.arePetsPermitted: tags.append("🐾 Pets OK")
            else: tags.append("🚫 No Pets")
            
            # Description (Truncated)
            desc = item.shortDescription[:100] + "..." if len(item.shortDescription) > 100 else item.shortDescription
            
            # Details Content
            details = item.longDescription if item.longDescription else item.shortDescription
            if item.location:
                details += f"\n\n**Location:** Lat: {item.location.lat}, Lon: {item.location.lon}"
            if item.season:
                details += f"\n\n**Season:** {', '.join(item.season)}"
                
            # Render
            render_card(
                title=item.title,
                image_url=item.images[0].url if item.images else None,
                subtitle=f"⏱️ {item.duration}" if item.duration else None,
                description=desc,
                tags=tags,
                details_content=details
            )
