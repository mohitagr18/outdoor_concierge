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
        return "darkblue", "star"
    elif "food" in cat_lower or "restaurant" in cat_lower or "dining" in cat_lower:
        return "orange", "utensils"
    elif "lodging" in cat_lower or "hotel" in cat_lower or "motel" in cat_lower:
        return "purple", "bed"
    elif "camping" in cat_lower or "rv" in cat_lower:
        return "darkgreen", "campground" # darker green to distinguish from EV
    elif "store" in cat_lower or "market" in cat_lower or "supplies" in cat_lower:
        return "red", "shopping-cart"
    elif "hospital" in cat_lower or "urgent" in cat_lower or "clinic" in cat_lower or "medical" in cat_lower:
        return "darkred", "kit-medical"
    else:
        return "gray", "info-circle"

# Emoji Map for Headers
CATEGORY_EMOJIS = {
    "gas": "⛽", "station": "⛽",
    "ev": "🔌", "charge": "🔌",
    "food": "🍽️", "restaurant": "🍽️",
    "lodging": "🛏️", "hotel": "🛏️",
    "store": "🛒", "supplies": "🛒", "market": "🛒",
    "medical": "🏥", "hospital": "🏥",
    "entrance": "🌟", "hub": "🌟"
}

def get_emoji(cat_name):
    cat_lower = cat_name.lower()
    for key, emoji in CATEGORY_EMOJIS.items():
        if key in cat_lower:
            return emoji
    return "🔹"

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
     background-color:white; opacity:0.9; padding: 10px; border-radius: 5px; color: black;">
     <b>Legend</b><br>
     <i class="fa fa-star" style="color:darkblue"></i> &nbsp; Park Hub / Entrance<br>
     <i class="fa fa-gas-pump" style="color:blue"></i> &nbsp; Gas<br>
     <i class="fa fa-charging-station" style="color:green"></i> &nbsp; EV Charging<br>
     <i class="fa fa-utensils" style="color:orange"></i> &nbsp; Food<br>
     <i class="fa fa-bed" style="color:purple"></i> &nbsp; Lodging<br>
     <i class="fa fa-shopping-cart" style="color:red"></i> &nbsp; Store<br>
     <i class="fa fa-kit-medical" style="color:darkred"></i> &nbsp; Medical<br>
     </div>
     '''
    m.get_root().html.add_child(folium.Element(legend_html))

    # PLOT POINTS - Group by CATEGORY now (User Request)
    # We will collect markers per category across ALL hubs
    category_markers = {} # { "Gas Station": [markers...], ... }

    for hub_name, categories in amenities_data.items():
        for category, items in categories.items():
            # Normalize Category Name for grouping (e.g. "Gas Station" vs "gas station")
            # We use the raw category from data but might want to capitalize
            cat_label = category.title()
            # Special case for our injected entrance
            if category == "Park Entrance":
                cat_label = "🌟 Park Entrances"
            else:
                 # Add emoji for layer list
                 emoji = get_emoji(category)
                 cat_label = f"{emoji} {cat_label}"

            if cat_label not in category_markers:
                category_markers[cat_label] = []

            color, icon_name = get_category_icon(category)
            
            for item_data in items:
                am = Amenity(**item_data) if isinstance(item_data, dict) else item_data
                
                if am.latitude and am.longitude:
                    # Fix Link logic (same as before)
                    if am.address and am.address.lower() != "n/a":
                         import urllib.parse
                         safe_address = urllib.parse.quote(am.address)
                         gmaps_link = f"https://www.google.com/maps/search/?api=1&query={safe_address}"
                    else:
                         search_query = f"{am.latitude},{am.longitude}"
                         gmaps_link = f"https://www.google.com/maps/search/?api=1&query={search_query}"
                    
                    rating_str = f"{am.rating} ⭐ ({am.rating_count or 0} reviews)" if am.rating else "No ratings"

                    popup_html = f"""
                    <div style="width:180px">
                        <b>{am.name}</b><br>
                        <span style="color:gray; font-size:12px">{am.address or ''}</span><br>
                        <span style="color:gray">{category}</span><br>
                        <span style="font-size:12px">{rating_str}</span><br>
                        <a href="{gmaps_link}" target="_blank">Open in Maps ↗</a>
                    </div>
                    """
                    
                    marker = folium.Marker(
                        [am.latitude, am.longitude],
                        popup=folium.Popup(popup_html, max_width=220),
                        tooltip=f"{am.name} - {rating_str}",
                        icon=folium.Icon(color=color, icon=icon_name, prefix='fa')
                    )
                    category_markers[cat_label].append(marker)

    # Sort categories to ensure distinct order (Entrances first, then alpha)
    sorted_cats = sorted(category_markers.keys(), key=lambda x: (0 if "Entrance" in x else 1, x))

    for cat_label in sorted_cats:
        fg = folium.FeatureGroup(name=cat_label)
        for marker in category_markers[cat_label]:
            marker.add_to(fg)
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
                     emoji = get_emoji(cat)
                     # improved header styling
                     st.markdown(f"#### {emoji} {cat}")
                     
                     for item in items[:5]:
                         am = Amenity(**item) if isinstance(item, dict) else item
                         
                         if am.address and am.address.lower() != "n/a":
                             import urllib.parse
                             safe_address = urllib.parse.quote(am.address)
                             gmaps_link = f"https://www.google.com/maps/search/?api=1&query={safe_address}"
                         elif am.latitude and am.longitude:
                             gmaps_link = f"https://www.google.com/maps/search/?api=1&query={am.latitude},{am.longitude}"
                         else:
                             gmaps_link = am.google_maps_url or "#"

                         rating_display = f"{am.rating}⭐ ({am.rating_count or 0})" if am.rating else ""
                         # Clean address display (no underscores/italics)
                         addr_display = am.address if am.address and am.address != "N/A" else ""
                         
                         # Format: Name (Link)
                         # Rating (Count)
                         # Address
                         st.markdown(f"""
                         <div style="margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid rgba(128, 128, 128, 0.2);">
                             <a href="{gmaps_link}" target="_blank" style="font-weight:600; font-size:1.05em; text-decoration:none;">{am.name}</a><br>
                             <span style="font-size:0.9em;">{rating_display}</span><br>
                             <span style="font-size:0.85em; opacity: 0.8;">{addr_display}</span>
                         </div>
                         """, unsafe_allow_html=True)
