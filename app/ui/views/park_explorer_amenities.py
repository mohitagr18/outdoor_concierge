import streamlit as st
import folium
from streamlit_folium import st_folium
from app.models import Amenity

def get_category_icon(category: str):
    """Returns a (color, icon_name) tuple for Folium based on category."""
    cat_lower = category.lower()
    
    # Specific Mapping
    if "gas" in cat_lower or "station" in cat_lower:
        return "blue", "gas-pump"
    elif "ev" in cat_lower or "charge" in cat_lower or "tesla" in cat_lower:
        return "green", "charging-station"
    elif "entrance" in cat_lower or "hub" in cat_lower:
        return "black", "map-pin"
    elif "food" in cat_lower or "restaurant" in cat_lower or "dining" in cat_lower:
        return "orange", "utensils"
    elif "lodging" in cat_lower or "hotel" in cat_lower or "motel" in cat_lower:
        return "purple", "bed"
    elif "camping" in cat_lower or "rv" in cat_lower:
        return "darkgreen", "campground" # darker green to distinguish from EV
    elif "store" in cat_lower or "market" in cat_lower:
        return "red", "shopping-cart"
    elif "hospital" in cat_lower or "urgent" in cat_lower or "clinic" in cat_lower or "medical" in cat_lower:
        return "darkred", "kit-medical"
    else:
        return "gray", "info-circle"

def render_amenities_dashboard(park_code: str, orchestrator):
    st.subheader(f"Services & Amenities near {park_code.upper()}")
    
    if not orchestrator:
        st.warning("Backend offline.")
        return

    with st.spinner("Locating nearby services..."):
        amenities_data = orchestrator.get_park_amenities(park_code)
    
    if not amenities_data:
        st.info(f"No amenity data found for {park_code}.")
        return

    # Initialize Map (Default Center)
    start_lat, start_lon = 37.8651, -119.5383 
    
    # Try to center on the first valid point found
    for hub_vals in amenities_data.values():
        for items in hub_vals.values():
            if items:
                 item = items[0]
                 am = Amenity(**item) if isinstance(item, dict) else item
                 if am.latitude:
                     start_lat, start_lon = am.latitude, am.longitude
                     break
        if start_lat != 37.8651: break

    m = folium.Map(location=[start_lat, start_lon], zoom_start=11)

    # LEGEND (Updated)
    legend_html = '''
     <div style="position: fixed; 
     bottom: 50px; left: 50px; width: 170px; height: 230px; 
     border:2px solid grey; z-index:9999; font-size:14px;
     background-color:white; opacity:0.9; padding: 10px; border-radius: 5px;">
     <b>Legend</b><br>
     <i class="fa fa-map-pin" style="color:black"></i> &nbsp; Park Hub / Entrance<br>
     <i class="fa fa-gas-pump" style="color:blue"></i> &nbsp; Gas<br>
     <i class="fa fa-charging-station" style="color:green"></i> &nbsp; EV Charging<br>
     <i class="fa fa-utensils" style="color:orange"></i> &nbsp; Food<br>
     <i class="fa fa-bed" style="color:purple"></i> &nbsp; Lodging<br>
     <i class="fa fa-shopping-cart" style="color:red"></i> &nbsp; Store<br>
     <i class="fa fa-kit-medical" style="color:darkred"></i> &nbsp; Medical<br>
     </div>
     '''
    m.get_root().html.add_child(folium.Element(legend_html))

    # PLOT POINTS
    for hub_name, categories in amenities_data.items():
        fg = folium.FeatureGroup(name=hub_name)
        
        # 1. Plot the "Hub" itself (Approximate location based on first amenity)
        # We try to find a representative location for the hub
        hub_lat, hub_lon = None, None
        
        for category, items in categories.items():
            color, icon_name = get_category_icon(category)
            
            for item_data in items:
                am = Amenity(**item_data) if isinstance(item_data, dict) else item_data
                
                if am.latitude and am.longitude:
                    # Capture first valid coord as hub location if not set
                    if not hub_lat:
                        hub_lat, hub_lon = am.latitude, am.longitude

                    # Fix Link
                    gmaps_link = am.google_maps_url
                    if not gmaps_link:
                        search_query = f"{am.latitude},{am.longitude}"
                        gmaps_link = f"https://www.google.com/maps/search/?api=1&query={search_query}"
                    
                    rating_str = f"{am.rating} ⭐ ({am.rating_count or 0})" if am.rating else "N/A"

                    popup_html = f"""
                    <div style="width:160px">
                        <b>{am.name}</b><br>
                        <span style="color:gray">{category}</span><br>
                        Rating: {rating_str}<br>
                        <a href="{gmaps_link}" target="_blank">Open in Maps ↗</a>
                    </div>
                    """
                    
                    folium.Marker(
                        [am.latitude, am.longitude],
                        popup=folium.Popup(popup_html, max_width=200),
                        tooltip=f"{am.name} ({category}) - {rating_str}",
                        icon=folium.Icon(color=color, icon=icon_name, prefix='fa')
                    ).add_to(fg)
        
        # Add explicit Hub Marker if we found coords
        if hub_lat:
            folium.Marker(
                [hub_lat, hub_lon],
                popup=f"<b>{hub_name}</b><br>Approximate Hub Center",
                tooltip=hub_name,
                icon=folium.Icon(color="black", icon="map-pin", prefix='fa')
            ).add_to(fg)

        fg.add_to(m)

    folium.LayerControl().add_to(m)
    st_folium(m, width="100%", height=500)

    # List View (Below)
    st.divider()
    st.markdown("### 📍 Service Details")
    for hub_name, categories in amenities_data.items():
        with st.expander(f"**{hub_name}** List", expanded=False):
             cols = st.columns(3)
             for idx, (cat, items) in enumerate(categories.items()):
                 with cols[idx % 3]:
                     st.markdown(f"**{cat}**")
                     for item in items[:5]:
                         am = Amenity(**item) if isinstance(item, dict) else item
                         
                         gmaps_link = am.google_maps_url or f"https://www.google.com/maps/search/?api=1&query={am.latitude},{am.longitude}"
                         rating_display = f"{am.rating}⭐" if am.rating else ""
                         
                         st.markdown(f"- [{am.name}]({gmaps_link}) {rating_display}")
