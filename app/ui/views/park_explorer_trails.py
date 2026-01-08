import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

def get_difficulty_color(diff: str):
    if not diff: return "gray"
    d = diff.lower()
    if "easy" in d: return "green"
    if "moderate" in d: return "orange"
    if "hard" in d or "strenuous" in d: return "red"
    return "gray"

def render_trails_browser(park_code: str, static_data):
    st.subheader(f"Hiking Trails in {park_code.upper()}")
    
    trails = static_data.get("trails", [])
    if not trails:
        st.info("No trail data available.")
        return

    # 1. Prepare Data Frame
    clean_rows = []
    for t in trails:
        item = t if isinstance(t, dict) else t.model_dump()
        
        # Extract Lat/Lon safely
        lat, lon = None, None
        loc = item.get("location")
        if loc and isinstance(loc, dict):
            lat = loc.get("lat")
            lon = loc.get("lon")
        
        # Extract Image
        img_url = None
        if item.get("images") and len(item["images"]) > 0:
            img_url = item["images"][0].get("url")

        # Skip trails without a valid difficulty classification
        difficulty = item.get("difficulty")
        if not difficulty or difficulty.lower() == "unknown":
            continue
        
        clean_rows.append({
            "name": item.get("name"),
            "difficulty": difficulty,
            "length": item.get("length_miles"),
            "elevation": item.get("elevation_gain_ft"),
            "rating": item.get("alltrails_rating"),
            "reviews": item.get("alltrails_review_count"),
            "lat": lat,
            "lon": lon,
            "desc": item.get("description"),
            "raw_listing_description": item.get("raw_listing_description"),
            "raw_body_text": item.get("raw_body_text"),
            "estimated_time_hours": item.get("estimated_time_hours"),
            "img_alt": None if not img_url else (item.get("images")[0].get("altText") if item.get("images") and len(item.get("images"))>0 and item.get("images")[0].get("altText") else None),
            "img_caption": None if not img_url else (item.get("images")[0].get("caption") if item.get("images") and len(item.get("images"))>0 and item.get("images")[0].get("caption") else None),
            "url_nps": item.get("nps_url"),
            "url_at": item.get("alltrails_url"),
            "img": img_url,
            "route_type": item.get("route_type"),
            "popularity_rank": item.get("popularity_rank"),
            "wheelchair": item.get("is_wheelchair_accessible", False),
            "kid_friendly": item.get("is_kid_friendly", False),
            "pet_friendly": item.get("is_pet_friendly", False)
        })
        
    df = pd.DataFrame(clean_rows)

    # 2. Filters
    with st.expander("🔍 Filter Trails", expanded=False):
        c1, c2, c3, c4, c5 = st.columns(5)
        
        # Difficulty Filter
        diff_filter = c1.multiselect("Difficulty", ["Easy", "Moderate", "Strenuous"])
        
        # Length Filter
        min_len = c2.slider("Min Length (mi)", 0.0, 20.0, 0.0)
        
        # Accessibility Filters (NEW)
        wheelchair_only = c3.checkbox("♿ Accessible")
        kid_friendly_only = c4.checkbox("👶 Kid Friendly")
        pet_friendly_only = c5.checkbox("🐕 Pet Friendly")

    # Apply Filters
    filtered = df.copy()
    if diff_filter:
        filtered = filtered[filtered["difficulty"].isin(diff_filter)]
    if min_len > 0:
        filtered = filtered[(filtered["length"] >= min_len) | (filtered["length"].isna())]
    if wheelchair_only:
        filtered = filtered[filtered["wheelchair"] == True]
    if kid_friendly_only:
        filtered = filtered[filtered["kid_friendly"] == True]
    if pet_friendly_only:
        filtered = filtered[filtered["pet_friendly"] == True]

    # 3. Map (Valid coords only)
    map_df = filtered[(filtered["lat"].notnull()) & (filtered["lat"] != 0.0)]
    
    if not map_df.empty:
        st.markdown(f"### 🗺️ Trail Map ({len(map_df)} locations)")
        
        # Center map
        m = folium.Map(location=[map_df["lat"].mean(), map_df["lon"].mean()], zoom_start=11)
        
        # Prepare Layers
        layers = {
            "Easy": folium.FeatureGroup(name='<span style="color:green">●</span> Easy'),
            "Moderate": folium.FeatureGroup(name='<span style="color:orange">●</span> Moderate'),
            "Strenuous": folium.FeatureGroup(name='<span style="color:red">●</span> Strenuous')
        }
        
        # Determine strict layer mapping
        def get_layer_key(diff_str):
            if not diff_str: return "Moderate" # Default
            d = diff_str.lower()
            if "easy" in d: return "Easy"
            if "hard" in d or "strenuous" in d: return "Strenuous"
            return "Moderate"

        for _, row in map_df.iterrows():
            color = get_difficulty_color(row["difficulty"])
            layer_key = get_layer_key(row["difficulty"])
            
            # Build rating string with optional reviews link
            if pd.notna(row['rating']) and pd.notna(row['reviews']) and row['url_at']:
                rating_str = f"{row['rating']} ⭐ <a href='{row['url_at']}?reviews=true' target='_blank'>Latest Reviews ({int(row['reviews'])})</a>"
            elif pd.notna(row['rating']) and pd.notna(row['reviews']):
                rating_str = f"{row['rating']} ⭐ ({int(row['reviews'])} Latest Reviews)"
            elif pd.notna(row['rating']):
                rating_str = f"{row['rating']} ⭐"
            else:
                rating_str = "N/A"
            
            # Build trail URL for popup
            popup_trail_url = row['url_nps'] if pd.notna(row['url_nps']) and row['url_nps'] else row['url_at'] if pd.notna(row['url_at']) and row['url_at'] else None
            
            # Build trail name with optional link
            if popup_trail_url:
                trail_name_html = f"<a href='{popup_trail_url}' target='_blank' style='text-decoration:none;color:#1a73e8;'><b>{row['name']}</b></a>"
            else:
                trail_name_html = f"<b>{row['name']}</b>"
            
            popup_html = f"""
            {trail_name_html}<br>
            {row['difficulty']} | {row['length'] or '?'} mi<br>
            Rating: {rating_str}
            """
            
            marker = folium.Marker(
                [row["lat"], row["lon"]],
                popup=folium.Popup(popup_html, max_width=200),
                tooltip=row["name"],
                icon=folium.Icon(color=color, icon="person-hiking", prefix='fa')
            )
            
            # Add to specific layer
            marker.add_to(layers[layer_key])
            
        # Add Layers to Map in Order
        for title in ["Easy", "Moderate", "Strenuous"]:
            layers[title].add_to(m)
            
        folium.LayerControl(collapsed=False).add_to(m)
            
        st_folium(m, width="100%", height=450)
    
    st.divider()

    # 4. List View - Top Rated Trails First
    st.markdown("### 🏆 Top Rated Trails")
    
    with st.expander("View Details", expanded=True):
        # Get top trails by popularity_rank, then by rating
        top_trails = pd.DataFrame()
        if 'popularity_rank' in filtered.columns:
            top_trails = filtered.dropna(subset=['popularity_rank']).sort_values('popularity_rank')
        
        if top_trails.empty and 'rating' in filtered.columns:
            # Fallback: sort by rating if no popularity_rank
            top_trails = filtered[pd.notna(filtered['rating'])].sort_values('rating', ascending=False)
        
        if top_trails.empty:
            # Fallback: just take first trails from filtered
            top_trails = filtered.head(15)
        else:
            top_trails = top_trails.head(15)
        
        if not top_trails.empty:
            for idx, (_, row) in enumerate(top_trails.iterrows(), 1):
                # Top Trail Card Layout (Full Details)
                c1, c2 = st.columns([1, 4])
                
                # Image Column
                with c1:
                    if row["img"]:
                        st.image(row["img"], use_container_width=True)
                    else:
                        st.caption("No Image")
                
                # Info Column
                with c2:
                    # Build title with optional rank badge and accessibility icons
                    # Determine which URL to use for title link
                    trail_url = row['url_nps'] if row['url_nps'] else row['url_at']
                    
                    if trail_url:
                        title = f"#### [{row['name']}]({trail_url})"
                    else:
                        title = f"#### {row['name']}"
                    
                    if row['wheelchair']:
                        title += " ♿"
                    if row['kid_friendly']:
                        title += " 👶"
                    if row['pet_friendly']:
                        title += " 🐕"
                    
                    st.markdown(title)
                    
                    # Show rank separately if available
                    if pd.notna(row.get('popularity_rank')):
                        st.caption(f"**Rank #{int(row['popularity_rank'])}**")
                    
                    # Metrics line with embedded reviews link
                    metrics = []
                    metrics.append(f"**{row['difficulty']}**")
                    if pd.notna(row['length']) and row['length'] > 0:
                        metrics.append(f"📏 {row['length']} mi")
                    if pd.notna(row['elevation']) and row['elevation'] > 0:
                        metrics.append(f"⛰️ {int(row['elevation'])} ft")
                    if row['route_type']:
                        metrics.append(f"🔄 {row['route_type']}")
                    
                    if pd.notna(row['rating']):
                        if pd.notna(row['reviews']) and row['url_at']:
                            # Embed reviews link
                            metrics.append(f"⭐ {row['rating']} ([{int(row['reviews'])} reviews]({row['url_at']}?reviews=true))")
                        elif pd.notna(row['reviews']):
                            metrics.append(f"⭐ {row['rating']} ({int(row['reviews'])} reviews)")
                        else:
                            metrics.append(f"⭐ {row['rating']}")
                    
                    st.caption(" • ".join(metrics))
                    
                    # Description (full for top trails) - prefer clean then NPS listing/body then image alt/caption
                    desc_choices = [row.get('desc'), row.get('raw_listing_description'), row.get('raw_body_text'), row.get('img_alt'), row.get('img_caption')]
                    desc_text = next((d for d in desc_choices if d and str(d).strip()), None)
                    if desc_text:
                        # Limit length for card
                        out = desc_text if len(desc_text) <= 800 else desc_text[:800].rsplit(' ',1)[0] + '...'
                        st.write(out)
                
                st.divider()
    
    # 5. Difficulty Buckets (Minimal - No Descriptions)
    st.markdown("### 🥾 Browse by Difficulty")
    
    # Sort order
    order = ["Easy", "Moderate", "Strenuous"]
    
    for level in order:
        subset = filtered[filtered["difficulty"] == level]
        if subset.empty: continue
        
        with st.expander(f"**{level}** ({len(subset)})", expanded=False):
            # Use columns for compact layout
            cols = st.columns(3)
            col_idx = 0
            
            for _, row in subset.iterrows():
                with cols[col_idx % 3]:
                    # Minimal Trail Card (No Image, No Description)
                    # Title with accessibility icons + embedded URL
                    trail_url = row['url_nps'] if row['url_nps'] else row['url_at']
                    
                    if trail_url:
                        title = f"**[{row['name']}]({trail_url})**"
                    else:
                        title = f"**{row['name']}**"
                    
                    if row['wheelchair']:
                        title += " ♿"
                    if row['kid_friendly']:
                        title += " 👶"
                    if row['pet_friendly']:
                        title += " 🐕"
                    st.markdown(title)
                    
                    # Metrics line (compact) with embedded reviews link
                    metrics = []
                    if pd.notna(row['length']) and row['length'] > 0:
                        metrics.append(f"📏 {row['length']} mi")
                    if pd.notna(row['elevation']) and row['elevation'] > 0:
                        metrics.append(f"⛰️ {int(row['elevation'])} ft")
                    if row['route_type']:
                        metrics.append(f"🔄 {row['route_type']}")
                    if pd.notna(row['rating']):
                        if pd.notna(row['reviews']) and row['url_at']:
                            # Embed reviews link
                            metrics.append(f"⭐ {row['rating']} ([{int(row['reviews'])} reviews]({row['url_at']}?reviews=true))")
                        elif pd.notna(row['reviews']):
                            metrics.append(f"⭐ {row['rating']} ({int(row['reviews'])} reviews)")
                        else:
                            metrics.append(f"⭐ {row['rating']}")
                    
                    if metrics:
                        st.caption(" • ".join(metrics))
                    
                    st.divider()
                
                col_idx += 1