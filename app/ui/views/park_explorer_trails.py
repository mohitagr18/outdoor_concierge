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
            "url_nps": item.get("nps_url"),
            "url_at": item.get("alltrails_url"),
            "img": img_url,
            "route_type": item.get("route_type"),
            "popularity_rank": item.get("popularity_rank"),
            "wheelchair": item.get("is_wheelchair_accessible", False),
            "kid_friendly": item.get("is_kid_friendly", False)
        })
        
    df = pd.DataFrame(clean_rows)

    # 2. Filters
    with st.expander("🔍 Filter Trails", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        
        # Difficulty Filter
        diff_filter = c1.multiselect("Difficulty", ["Easy", "Moderate", "Strenuous"])
        
        # Length Filter
        min_len = c2.slider("Min Length (mi)", 0.0, 20.0, 0.0)
        
        # Accessibility Filters (NEW)
        wheelchair_only = c3.checkbox("♿ Accessible Only")
        kid_friendly_only = c4.checkbox("👶 Kid Friendly Only")

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

    # 3. Map (Valid coords only)
    map_df = filtered[(filtered["lat"].notnull()) & (filtered["lat"] != 0.0)]
    
    if not map_df.empty:
        st.markdown(f"### 🗺️ Trail Map ({len(map_df)} locations)")
        
        # Center map
        m = folium.Map(location=[map_df["lat"].mean(), map_df["lon"].mean()], zoom_start=11)
        
        # ADD LEGEND (FIX #1)
        legend_html = '''
         <div style="position: fixed; 
         bottom: 50px; left: 50px; width: 150px; height: 130px; 
         border:2px solid grey; z-index:9999; font-size:14px;
         background-color:white; opacity:0.9; padding: 10px; border-radius: 5px;">
         <b>Difficulty</b><br>
         <i class="fa fa-map-marker" style="color:green"></i> &nbsp; Easy<br>
         <i class="fa fa-map-marker" style="color:orange"></i> &nbsp; Moderate<br>
         <i class="fa fa-map-marker" style="color:red"></i> &nbsp; Strenuous<br>
         </div>
         '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        for _, row in map_df.iterrows():
            color = get_difficulty_color(row["difficulty"])
            
            # Build rating string with optional reviews link
            if pd.notna(row['rating']) and pd.notna(row['reviews']) and row['url_at']:
                rating_str = f"{row['rating']} ⭐ <a href='{row['url_at']}?reviews=true' target='_blank'>Latest Reviews ({int(row['reviews'])})</a>"
            elif pd.notna(row['rating']) and pd.notna(row['reviews']):
                rating_str = f"{row['rating']} ⭐ ({int(row['reviews'])} Latest Reviews)"
            elif pd.notna(row['rating']):
                rating_str = f"{row['rating']} ⭐"
            else:
                rating_str = "N/A"
            
            popup_html = f"""
            <b>{row['name']}</b><br>
            {row['difficulty']} | {row['length'] or '?'} mi<br>
            Rating: {rating_str}
            """
            
            folium.Marker(
                [row["lat"], row["lon"]],
                popup=folium.Popup(popup_html, max_width=200),
                tooltip=row["name"],
                icon=folium.Icon(color=color, icon="person-hiking", prefix='fa')
            ).add_to(m)
            
        st_folium(m, width="100%", height=450)
    
    st.divider()

    # 4. List View - Top Rated Trails First
    st.markdown("### 🏆 Top Rated Trails")
    
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
                # Rank + Title with accessibility icons
                rank_badge = f"**#{int(row['popularity_rank'])}**" if pd.notna(row['popularity_rank']) else ""
                title = f"#### {rank_badge} {row['name']}" if rank_badge else f"#### {row['name']}"
                if row['wheelchair']:
                    title += " ♿"
                if row['kid_friendly']:
                    title += " 👶"
                st.markdown(title)
                
                # Metrics line
                metrics = []
                metrics.append(f"**{row['difficulty']}**")
                if pd.notna(row['length']) and row['length'] > 0:
                    metrics.append(f"📏 {row['length']} mi")
                if pd.notna(row['elevation']) and row['elevation'] > 0:
                    metrics.append(f"⛰️ {int(row['elevation'])} ft")
                if row['route_type']:
                    metrics.append(f"🔄 {row['route_type']}")
                if pd.notna(row['rating']):
                    if pd.notna(row['reviews']):
                        metrics.append(f"⭐ {row['rating']} ({int(row['reviews'])} reviews)")
                    else:
                        metrics.append(f"⭐ {row['rating']}")
                
                st.caption(" • ".join(metrics))
                
                # Description (full for top trails)
                if row['desc']:
                    st.write(row['desc'])
                
                # Links section
                links = []
                if row['url_nps']: links.append(f"[NPS Guide]({row['url_nps']})")
                if row['url_at']: links.append(f"[AllTrails]({row['url_at']})")
                if row['url_at'] and pd.notna(row['reviews']): links.append(f"[Latest Reviews ({int(row['reviews'])})]({row['url_at']}?reviews=true)")
                
                if links:
                    st.markdown(" | ".join(links))
            
            st.divider()
    
    # 5. Difficulty Buckets (Minimal - No Descriptions)
    st.markdown("### 🥾 Browse by Difficulty")
    
    # Sort order
    order = ["Easy", "Moderate", "Strenuous"]
    
    for level in order:
        subset = filtered[filtered["difficulty"] == level]
        if subset.empty: continue
        
        with st.expander(f"**{level}** ({len(subset)})", expanded=False):
            for _, row in subset.iterrows():
                # Minimal Trail Card (No Image, No Description)
                # Title with accessibility icons
                title = f"#### {row['name']}"
                if row['wheelchair']:
                    title += " ♿"
                if row['kid_friendly']:
                    title += " 👶"
                st.markdown(title)
                
                # Metrics line (compact)
                metrics = []
                if pd.notna(row['length']) and row['length'] > 0:
                    metrics.append(f"📏 {row['length']} mi")
                if pd.notna(row['elevation']) and row['elevation'] > 0:
                    metrics.append(f"⛰️ {int(row['elevation'])} ft")
                if row['route_type']:
                    metrics.append(f"🔄 {row['route_type']}")
                if pd.notna(row['rating']):
                    if pd.notna(row['reviews']):
                        metrics.append(f"⭐ {row['rating']} ({int(row['reviews'])} reviews)")
                    else:
                        metrics.append(f"⭐ {row['rating']}")
                
                if metrics:
                    st.caption(" • ".join(metrics))
                
                # Links section only (no description)
                links = []
                if row['url_nps']: links.append(f"[NPS Guide]({row['url_nps']})")
                if row['url_at']: links.append(f"[AllTrails]({row['url_at']})")
                if row['url_at'] and pd.notna(row['reviews']): links.append(f"[Latest Reviews ({int(row['reviews'])})]({row['url_at']}?reviews=true)")
                
                if links:
                    st.caption(" | ".join(links))
                
                st.divider()