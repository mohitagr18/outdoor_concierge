import streamlit as st
import folium
from streamlit_folium import st_folium
from app.models import Amenity
import datetime

# --- 1. STYLING (Unchanged) ---
def inject_custom_css():
    # Font Awesome CDN for icons
    st.markdown('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">', unsafe_allow_html=True)
    
    st.markdown("""
        <style>
        .metric-card {
            background-color: #ffffff;
            border-radius: 12px;
            padding: 20px 12px;
            text-align: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            color: #333;
            height: 100%;
            min-height: 300px;
            border: 1px solid #e5e7eb;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .metric-value { font-size: 42px; font-weight: 700; display: block; line-height: 1.2; margin: 8px 0; }
        .metric-label { font-size: 18px; color: #666; }
        
        .dark-card {
            background-color: #1e293b;
            border-radius: 12px;
            padding: 24px;
            color: white;
            height: 100%;
        }
        
        .alert-banner {
            color: white;
            padding: 16px 24px;
            border-radius: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        }
        </style>
    """, unsafe_allow_html=True)

# --- 2. COMPONENTS (Alerts & Stats Unchanged) ---
def render_alert_section(alerts):
    alert_list = []
    if isinstance(alerts, list):
        alert_list = alerts
    elif isinstance(alerts, dict):
        if "data" in alerts: alert_list = alerts["data"]
        else: alert_list = list(alerts.values())

    if not alert_list:
        st.markdown("""
        <div class="alert-banner" style="background: linear-gradient(90deg, #10b981 0%, #059669 100%);">
            <div><div style="font-weight:700;">No Active Alerts</div><div>Park conditions are normal.</div></div>
        </div>
        """, unsafe_allow_html=True)
        return

    # Determine Severity Color
    has_danger = False
    has_caution = False
    for a in alert_list:
        cat = (a.get('category', '') if isinstance(a, dict) else getattr(a, 'category', '')).lower()
        if "danger" in cat or "closure" in cat:
            has_danger = True
            break
        if "caution" in cat or "warning" in cat:
            has_caution = True
            
    if has_danger:
        bg_style = "background: linear-gradient(90deg, #ef4444 0%, #b91c1c 100%);"
    elif has_caution:
        bg_style = "background: linear-gradient(90deg, #f59e0b 0%, #d97706 100%);"
    else:
        bg_style = "background: linear-gradient(90deg, #3b82f6 0%, #1d4ed8 100%);"

    count = len(alert_list)
    top_alert = alert_list[0]
    
    title = "Alert"
    if isinstance(top_alert, dict): title = top_alert.get('title', 'Alert')
    elif hasattr(top_alert, 'title'): 
        t = getattr(top_alert, 'title')
        title = t if not callable(t) else "Active Alert"
    
    st.markdown(f"""
        <div class="alert-banner" style="{bg_style}">
            <div>
                <div style="font-weight: 700; font-size: 18px;">{count} Active Alerts</div>
                <div style="font-size: 14px; opacity: 0.9;">{title}...</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    with st.expander(f"View details for {count} alerts"):
        for alert in alert_list:
            t = alert.get('title', 'Alert') if isinstance(alert, dict) else getattr(alert, 'title', 'Alert')
            d = alert.get('description', '') if isinstance(alert, dict) else getattr(alert, 'description', '')
            cat = alert.get('category', 'Info') if isinstance(alert, dict) else getattr(alert, 'category', 'Info')
            url = alert.get('url') if isinstance(alert, dict) else getattr(alert, 'url', None)

            if url:
                t = f"[{t}]({url})"
            
            cat_lower = str(cat).lower()
            if "danger" in cat_lower or "closure" in cat_lower: st.error(f"**{t}**\n\n{d}")
            elif "caution" in cat_lower or "warning" in cat_lower: st.warning(f"**{t}**\n\n{d}")
            else: st.info(f"**{t}**\n\n{d}")

def render_stat_cards(static_data):
    trails = len(static_data.get("trails", []))
    photos = len(static_data.get("photo_spots", []))
    camps = len(static_data.get("campgrounds", []))
    # Activities is list of dicts usu.
    activities = len(static_data.get("things_to_do", []))
    webcams = len(static_data.get("webcams", []))
    
    # Row 1: Trails, Photos, Campgrounds
    c1, c2, c3 = st.columns(3)
    
    with c1: 
        st.markdown(f"""
        <a href="?view=trails" target="_self" style="text-decoration:none;">
            <div class="metric-card">
                <div style="font-size:48px; margin-bottom:8px;">⛰️</div>
                <span class="metric-value">{trails}</span>
                <span class="metric-label">Trails</span>
            </div>
        </a>
        """, unsafe_allow_html=True)
        
    with c2: 
        st.markdown(f"""
        <a href="?view=photos" target="_self" style="text-decoration:none;">
            <div class="metric-card">
                <div style="font-size:48px; margin-bottom:8px;">📸</div>
                <span class="metric-value">{photos}</span>
                <span class="metric-label">Photo Spots</span>
            </div>
        </a>
        """, unsafe_allow_html=True)

    with c3: 
        st.markdown(f"""
        <a href="?view=camping" target="_self" style="text-decoration:none;">
            <div class="metric-card">
                <div style="font-size:48px; margin-bottom:8px;">⛺</div>
                <span class="metric-value">{camps}</span>
                <span class="metric-label">Campgrounds</span>
            </div>
        </a>
        """, unsafe_allow_html=True)
    
    st.write("") # Spacer
    
    # Row 2: Activities, Webcams
    c4, c5 = st.columns(2)
    
    with c4: 
        st.markdown(f"""
        <a href="?view=activities" target="_self" style="text-decoration:none;">
            <div class="metric-card">
                <div style="font-size:48px; margin-bottom:8px;">🧗</div>
                <span class="metric-value">{activities}</span>
                <span class="metric-label">Things to Do</span>
            </div>
        </a>
        """, unsafe_allow_html=True)
        
    with c5: 
        st.markdown(f"""
        <a href="?view=webcams" target="_self" style="text-decoration:none;">
            <div class="metric-card">
                <div style="font-size:48px; margin-bottom:8px;">📹</div>
                <span class="metric-value">{webcams}</span>
                <span class="metric-label">Webcams</span>
            </div>
        </a>
        """, unsafe_allow_html=True)

# --- 3. WEATHER FIX (HTML Cleanup) ---
def render_weather_full_width(weather_data):
    """Expanded weather widget taking full width."""
    if not weather_data:
        st.markdown('<div class="dark-card">Weather Unavailable (No Data)</div>', unsafe_allow_html=True)
        return

    # A. Data Extraction
    is_dict = isinstance(weather_data, dict)
    
    if is_dict:
        # Check for flat format (from daily cache) vs nested format (from API)
        if "current_temp_f" in weather_data:
            # Flat format from daily cache
            temp = weather_data.get("current_temp_f", "--")
            cond = weather_data.get("current_condition", "Unknown")
            wind = weather_data.get("wind_mph", "--")
            hum = weather_data.get("humidity", "--")
        else:
            # Nested format from API
            curr = weather_data.get("current", {})
            temp = curr.get("temp_f", "--")
            
            cond_raw = curr.get("condition", "Unknown")
            cond = cond_raw.get("text", "Unknown") if isinstance(cond_raw, dict) else str(cond_raw)
                
            wind = curr.get("wind_mph", "--")
            hum = curr.get("humidity", "--")
        
        forecast_list = weather_data.get("forecast_days") or weather_data.get("forecast", [])
    else:
        temp = getattr(weather_data, "current_temp_f", "--")
        cond = getattr(weather_data, "current_condition", "Unknown")
        wind = getattr(weather_data, "wind_mph", "--")
        hum = getattr(weather_data, "humidity", "--")
        forecast_list = getattr(weather_data, "forecast", [])

    # B. Forecast HTML Construction
    forecasts_html_str = ""
    
    if forecast_list:
        if isinstance(forecast_list, dict):
            forecast_list = forecast_list.get("forecastday", [])

        # Build list of HTML strings
        items_html = []
        for day in forecast_list[:3]:
            # Normalize Day Object
            if hasattr(day, "date"): # Pydantic
                d_date = day.date
                d_cond = day.condition.lower()
                d_high = day.maxtemp_f
                d_low = day.mintemp_f
            elif isinstance(day, dict): # Dict
                d_date = day.get("date", "")
                c_raw = day.get("condition", "")
                d_cond = (c_raw.get("text", "") if isinstance(c_raw, dict) else str(c_raw)).lower()
                d_high = day.get("maxtemp_f", day.get("high_f", "--"))
                d_low = day.get("mintemp_f", day.get("low_f", "--"))
            else:
                continue

            # Date Formatting
            try:
                date_obj = datetime.datetime.strptime(str(d_date), "%Y-%m-%d")
                clean_date = date_obj.strftime("%a") # "Sat"
            except:
                clean_date = str(d_date)[:3]
            
            # Icon Logic
            icon = "☀️"
            if "cloud" in d_cond or "overcast" in d_cond: icon = "☁️"
            if "partly" in d_cond: icon = "⛅"
            if "rain" in d_cond or "drizzle" in d_cond: icon = "🌧️"
            if "snow" in d_cond: icon = "❄️"
            if "thunder" in d_cond: icon = "⛈️"
            
            try:
                high_val = int(float(d_high))
                low_val = int(float(d_low))
            except:
                high_val, low_val = "--", "--"
            
            # Use concise HTML string concatenation without newlines in the f-string to avoid breakage
            item = (
                f"<div style='text-align:center; min-width:60px;'>"
                f"<div style='font-size:20px;'>{icon}</div>"
                f"<div style='font-size:15px; font-weight:600; color:#cbd5e1;'>{clean_date}</div>"
                f"<div style='font-size:15px; color:#94a3b8;'>{high_val}°/{low_val}°</div>"
                f"</div>"
            )
            items_html.append(item)
            
        # Join all items
        if items_html:
            inner_content = "".join(items_html)
            forecasts_html_str = (
                f"<div style='border-left:1px solid #475569; padding-left:20px; margin-left:20px; "
                f"display:flex; gap:50px; align-items:center;'>"
                f"{inner_content}"
                f"</div>"
            )

    # C. Main Card HTML - Stacked Layout
    # Note: Indentation removed to prevent Markdown code block rendering
    main_html = f"""
<div class="dark-card" style="padding: 20px;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 20px;">
<div>
<div style="font-size:13px; color:#94a3b8; margin-bottom:2px;">Current Weather</div>
<div style="font-size:42px; font-weight:700; line-height:1.1;">{temp}°F</div>
<div style="font-size:16px; color:#e2e8f0; font-weight:600;">{cond}</div>
</div>
<div style="text-align:right; font-size:13px; color:#94a3b8;">
<div>Wind: {wind}mph</div>
<div>Humidity: {hum}%</div>
</div>
</div>
<div style="border-top: 1px solid #475569; margin-bottom: 15px;"></div>
<div style="display:flex; justify-content:space-around; align-items:center;">
{inner_content if items_html else '<div style="color:#94a3b8;">Forecast unavailable</div>'}
</div>
</div>
"""
    
    st.markdown(main_html, unsafe_allow_html=True)


def render_zonal_weather(zone_weather: dict, base_zone_name: str, weather_zones: list):
    """
    Render elevation-based weather for multiple zones.
    
    Args:
        zone_weather: Dict mapping zone_name -> ZonalForecast or dict
        base_zone_name: Name of the reference zone
        weather_zones: List of zone configs (WeatherZone objects or dicts)
    """
    if not zone_weather:
        st.markdown('<div class="dark-card">Weather Unavailable (No Zonal Data)</div>', unsafe_allow_html=True)
        return
    
    # Get zone configs for ordering and descriptions
    # Handle weather_zones being objects or dicts
    zone_configs = []
    for z in weather_zones:
        if isinstance(z, dict):
            zone_configs.append(z)
        else:
            # Assume Pydantic model
            zone_configs.append(z.model_dump() if hasattr(z, 'model_dump') else z.__dict__)
            
    zone_descriptions = {z["name"]: z.get("description", "") for z in zone_configs}
    
    # Sort zones by elevation ASCENDING (lowest elevation first)
    sorted_zones = []
    for zone_name, data in zone_weather.items():
        if hasattr(data, "elevation_ft"):
            elev = data.elevation_ft
        else:
            elev = data.get("elevation_ft", 0)
        sorted_zones.append((zone_name, data, elev))
    
    sorted_zones.sort(key=lambda x: x[2])  # Sort by elevation ascending
    
    # Get forecast from BASE zone for shared display
    base_forecast_list = []
    for zone_name, data, _ in sorted_zones:
        if zone_name == base_zone_name:
            if hasattr(data, "forecast"):
                base_forecast_list = getattr(data, "forecast", [])
            else:
                base_forecast_list = data.get("forecast", [])
            break
    
    # If no base zone found, use first zone's forecast
    if not base_forecast_list and sorted_zones:
        first_data = sorted_zones[0][1]
        if hasattr(first_data, "forecast"):
            base_forecast_list = getattr(first_data, "forecast", [])
        else:
            base_forecast_list = first_data.get("forecast", [])
    
    # Build zone cards - track if any estimates are used
    zone_cards_html = ""
    has_estimated_temps = False
    
    # First pass: get base zone temp and elevation for lapse rate calculations
    base_temp = None
    base_elev = None
    for zone_name, forecast, elev in sorted_zones:
        if zone_name == base_zone_name:
            if hasattr(forecast, "current_temp_f"):
                base_temp = forecast.current_temp_f
            else:
                base_temp = forecast.get("current_temp_f")
            base_elev = elev
            break
    
    for zone_name, forecast, _ in sorted_zones:
        # Extract data (handle both ZonalForecast model and dict)
        if hasattr(forecast, "current_temp_f"):
            current_temp = forecast.current_temp_f
            cond = forecast.current_condition
            elev = forecast.elevation_ft
            wind = getattr(forecast, "wind_mph", None)
            humidity = getattr(forecast, "humidity", None)
            zone_forecast = getattr(forecast, "forecast", [])
        else:
            current_temp = forecast.get("current_temp_f")
            cond = forecast.get("current_condition", "Unknown")
            elev = forecast.get("elevation_ft", 0)
            wind = forecast.get("wind_mph")
            humidity = forecast.get("humidity")
            zone_forecast = forecast.get("forecast", [])
        
        # Get today's high/low from forecast for validation
        high_temp = None
        low_temp = None
        if zone_forecast and len(zone_forecast) > 0:
            today = zone_forecast[0]
            if isinstance(today, dict):
                high_temp = today.get("maxtemp_f")
                low_temp = today.get("mintemp_f")
            else:
                high_temp = getattr(today, "maxtemp_f", None)
                low_temp = getattr(today, "mintemp_f", None)
        
        # Validate current_temp against forecast range
        # If outside range by more than 5°F, use estimation
        is_estimated = False
        display_temp = current_temp
        
        # Get avgtemp_f from base zone forecast for estimation
        base_avg_temp = None
        if base_forecast_list and len(base_forecast_list) > 0:
            base_today = base_forecast_list[0]
            if isinstance(base_today, dict):
                base_avg_temp = base_today.get("avgtemp_f")
            else:
                base_avg_temp = getattr(base_today, "avgtemp_f", None)
        
        if current_temp is not None and high_temp is not None and low_temp is not None:
            if current_temp > high_temp + 5 or current_temp < low_temp - 5:
                # Temperature seems off - use estimation
                if zone_name == base_zone_name:
                    # Base zone: use avgtemp_f directly (no * since it's actual forecast data)
                    if base_avg_temp is not None:
                        display_temp = float(base_avg_temp)
                        # Don't mark as estimated - avgtemp_f is real forecast data
                else:
                    # Other zones: calculate from base avgtemp_f + elevation adjustment
                    if base_avg_temp is not None and base_elev is not None:
                        # Lapse rate: ~3.5°F per 1000ft
                        elev_diff = elev - base_elev
                        temp_adjustment = (elev_diff / 1000) * 3.5
                        display_temp = float(base_avg_temp) - temp_adjustment
                        is_estimated = True
                        has_estimated_temps = True
        
        # Format temperature
        if display_temp is not None:
            temp_str = f"{float(display_temp):.0f}"
        else:
            temp_str = "--"
        
        # Add * for estimated temps
        estimated_marker = "*" if is_estimated else ""
        
        # Base zone badge
        base_badge = ""
        if zone_name == base_zone_name:
            base_badge = '<span style="background:#3b82f6; color:white; padding:2px 6px; border-radius:4px; font-size:10px; margin-left:8px;">BASE</span>'
        
        # Description - enhanced visibility with brighter color
        desc = zone_descriptions.get(zone_name, "")
        desc_html = f'<div style="font-size:12px; color:#a1b5d8; margin-top:4px;">{desc}</div>' if desc else ""
        
        # Wind and humidity line
        details_parts = []
        if wind is not None:
            details_parts.append(f'<i class="fa-solid fa-wind"></i> {wind:.0f} mph')
        if humidity is not None:
            details_parts.append(f"💧 {humidity}%")
        details_html = f'<div style="font-size:12px; color:#94a3b8; margin-top:4px;">{" • ".join(details_parts)}</div>' if details_parts else ""
        
        zone_cards_html += f"""
<div style="background:#1e293b; border-radius:8px; padding:12px; margin-bottom:8px;">
<div style="display:flex; justify-content:space-between; align-items:flex-start;">
<div>
<div style="font-weight:600; color:#e2e8f0;">{zone_name}{base_badge}</div>
<div style="font-size:12px; color:#94a3b8;">📍 {elev:,} ft</div>
{desc_html}
</div>
<div style="text-align:right;">
<div style="font-size:24px; font-weight:700; color:white;">{temp_str}°F{estimated_marker}</div>
<div style="font-size:13px; color:#cbd5e1;">{cond}</div>
{details_html}
</div>
</div>
</div>
"""
    
    # Build shared forecast section
    forecast_html = ""
    if base_forecast_list:
        forecast_items = []
        for day in base_forecast_list[:3]:
            if isinstance(day, dict):
                d_date = day.get("date", "")
                d_high = day.get("maxtemp_f", "--")
                d_low = day.get("mintemp_f", "--")
                c_raw = day.get("condition", "")
                d_cond = (c_raw.get("text", "") if isinstance(c_raw, dict) else str(c_raw)).lower()
            else:
                d_date = getattr(day, "date", "")
                d_high = getattr(day, "maxtemp_f", "--")
                d_low = getattr(day, "mintemp_f", "--")
                d_cond = getattr(day, "condition", "").lower()
            
            # Date formatting
            try:
                date_obj = datetime.datetime.strptime(str(d_date), "%Y-%m-%d")
                clean_date = date_obj.strftime("%a")
            except:
                clean_date = str(d_date)[:3]
            
            # Icon logic
            icon = "☀️"
            if "cloud" in d_cond or "overcast" in d_cond: icon = "☁️"
            if "partly" in d_cond: icon = "⛅"
            if "rain" in d_cond or "drizzle" in d_cond: icon = "🌧️"
            if "snow" in d_cond: icon = "❄️"
            if "thunder" in d_cond: icon = "⛈️"
            
            try:
                high_val = f"{float(d_high):.0f}"
                low_val = f"{float(d_low):.0f}"
            except:
                high_val, low_val = "--", "--"
            
            forecast_items.append(f'<div style="text-align:center; min-width:70px;"><div style="font-size:20px;">{icon}</div><div style="font-size:13px; font-weight:600; color:#cbd5e1;">{clean_date}</div><div style="font-size:12px; color:#94a3b8;">{high_val}°/{low_val}°</div></div>')
        
        if forecast_items:
            forecast_html = f"""
<div style="background:#0f172a; border-radius:8px; padding:12px; margin-top:12px;">
<div style="font-size:12px; color:#64748b; margin-bottom:8px;">📅 3-Day Forecast</div>
<div style="display:flex; justify-content:space-around; align-items:center;">
{"".join(forecast_items)}
</div>
</div>
"""
    
    # Info footnote - conditionally show estimated temps note
    estimated_note = "<br>* Estimated based on elevation" if has_estimated_temps else ""
    
    # Main container
    main_html = f"""
<div class="dark-card" style="padding:16px;">
<div style="font-size:24px; font-weight:600; color:#e2e8f0; margin-bottom:16px;">🌡️ Weather by Elevation</div>
{zone_cards_html}
{forecast_html}
<div style="font-size:12px; color:#a1b5d8; margin-top:12px; padding:10px; background:#0f172a; border-radius:6px; border-left:3px solid #3b82f6;">
ℹ️ Weather data from nearest weather stations. Temperature varies ~3.5°F per 1,000 ft elevation.{estimated_note}
</div>
</div>
"""
    
    st.markdown(main_html, unsafe_allow_html=True)


# --- 4. MAP HELPERS (Unchanged) ---
def get_category_icon(category: str):
    cat_lower = str(category).lower()
    if "gas" in cat_lower or "station" in cat_lower: return "blue", "gas-pump"
    if "ev" in cat_lower: return "green", "charging-station"
    if "entrance" in cat_lower: return "darkblue", "star"
    if "food" in cat_lower: return "orange", "utensils"
    if "lodging" in cat_lower: return "purple", "bed"
    if "camping" in cat_lower: return "darkgreen", "campground"
    if "store" in cat_lower or "supplies" in cat_lower: return "red", "shopping-cart"
    if "medical" in cat_lower: return "darkred", "medkit"
    return "gray", "info-circle"

def get_category_html_label(category: str):
    cat_title = "Park Entrance" if category == "Park Entrance" else str(category).title()
    color, icon = get_category_icon(category)
    return f'<i class="fa fa-{icon}" style="color:{color}"></i> &nbsp; {cat_title}'

def render_detailed_map(amenities_data):
    if not amenities_data: return None

    start_lat, start_lon = 39.8283, -98.5795
    found = False
    for hub_vals in amenities_data.values():
        for items in hub_vals.values():
            if items:
                am = Amenity(**items[0]) if isinstance(items[0], dict) else items[0]
                if am.latitude:
                    start_lat, start_lon = am.latitude, am.longitude
                    found = True
                    break
        if found: break

    m = folium.Map(location=[start_lat, start_lon], zoom_start=11)
    
    category_markers = {}
    for hub_name, categories in amenities_data.items():
        for category, items in categories.items():
            cat_label = get_category_html_label(category)
            if cat_label not in category_markers: category_markers[cat_label] = []
            
            color, icon_name = get_category_icon(category)
            for item_data in items:
                am = Amenity(**item_data) if isinstance(item_data, dict) else item_data
                if am.latitude and am.longitude:
                    gmaps = f"https://www.google.com/maps/search/?api=1&query={am.latitude},{am.longitude}"
                    # Show address with embedded link, fallback to coordinates link
                    if am.address and am.address.lower() != "n/a":
                        addr_link = f'<a href="{gmaps}" target="_blank">{am.address} ↗</a>'
                    else:
                        addr_link = f'<a href="{gmaps}" target="_blank">View on Maps ↗</a>'
                    popup = f"""<div style="width:180px"><b>{am.name}</b><br>{addr_link}</div>"""
                    
                    marker = folium.Marker(
                        [am.latitude, am.longitude],
                        popup=folium.Popup(popup, max_width=200),
                        tooltip=am.name,
                        icon=folium.Icon(color=color, icon=icon_name, prefix='fa')
                    )
                    category_markers[cat_label].append(marker)
    
    sorted_cats = sorted(category_markers.keys(), key=lambda x: (0 if "Entrance" in x else 1, x))
    for cat in sorted_cats:
        fg = folium.FeatureGroup(name=cat)
        for mk in category_markers[cat]: mk.add_to(fg)
        fg.add_to(m)
        
    folium.LayerControl(collapsed=False).add_to(m)
    return m

def render_in_park_map(static_data):
    if not static_data: return None
    
    places = static_data.get("places", [])
    campgrounds = static_data.get("campgrounds", [])
    
    # Categories to plot with OFFSETS (lat_offset, lon_offset)
    # Approx 0.0004 deg separation prevents exact overlap
    target_cats = {
        "Restroom": {"keywords": ["restroom", "toilet"], "exclude_keywords": [], "color": "darkblue", "icon": "restroom", "offset": (0.0000, 0.0000)},
        "Water": {"keywords": ["water", "bottle"], "exclude_keywords": [], "color": "blue", "icon": "tint", "offset": (0.0004, 0.0000)},
        "Food": {"keywords": ["food", "restaurant", "dining"], "exclude_keywords": ["food storage", "animal-safe"], "color": "orange", "icon": "utensils", "offset": (-0.0004, 0.0000)},
        "Picnic": {"keywords": ["picnic"], "exclude_keywords": [], "color": "green", "icon": "tree", "offset": (0.0000, 0.0004)},
        "Medical": {"keywords": ["first aid", "medical", "aed", "emergency"], "exclude_keywords": [], "color": "red", "icon": "medkit", "offset": (0.0000, -0.0004)},
        "Shuttle": {"keywords": ["shuttle", "bus"], "exclude_keywords": [], "color": "purple", "icon": "bus", "offset": (0.0004, 0.0004)},
    }
    
    # Prepare markers bucket
    device_markers = {k: [] for k in target_cats.keys()}
    device_markers["Camping"] = [] 
    
    def get_attr(obj, attr, default=None):
        return obj.get(attr, default) if isinstance(obj, dict) else getattr(obj, attr, default)
        
    start_lat, start_lon = 37.2, -113.0
    has_loc = False

    # 1. Process Campgrounds (Category: Camping)
    for camp in campgrounds:
        loc = get_attr(camp, "location")
        lat = get_attr(loc, "lat")
        lon = get_attr(loc, "lon")
        
        if lat and lon:
            if not has_loc: start_lat, start_lon = lat, lon; has_loc = True
                
            # Offset for Camping
            lat += -0.0004
            lon += -0.0004
            
            name = get_attr(camp, "name")
            desc = get_attr(camp, "description")[:100] + "..."
            popup = f"""<div style="width:180px"><b>{name}</b><br><span style="font-size:12px">{desc}</span></div>"""
            
            marker = folium.Marker(
                [lat, lon],
                popup=folium.Popup(popup, max_width=200),
                tooltip=name,
                icon=folium.Icon(color="green", icon="campground", prefix='fa')
            )
            device_markers["Camping"].append(marker)

    # 2. Process Places
    for place in places:
        loc = get_attr(place, "location")
        lat = get_attr(loc, "lat")
        lon = get_attr(loc, "lon")
        
        if not lat or not lon: continue
        if not has_loc: start_lat, start_lon = lat, lon; has_loc = True
            
        amenities = get_attr(place, "amenities", [])
        title = get_attr(place, "title")
        
        for cat_name, info in target_cats.items():
            match = False
            for am in amenities:
                am_lower = str(am).lower()
                
                # Check exclusions
                is_excluded = False
                for ex in info.get("exclude_keywords", []):
                    if ex in am_lower: is_excluded = True; break
                if is_excluded: continue
                
                # Check inclusions
                for kw in info["keywords"]:
                    if kw in am_lower: match = True; break
                if match: break
            
            if match:
                # Apply Offset
                off_lat, off_lon = info["offset"]
                p_lat = lat + off_lat
                p_lon = lon + off_lon
                
                
                url_html = ""
                # Safely get URL from place (pydantic model or dict)
                place_url = getattr(place, "url", None)
                if place_url:
                    url_html = f'<br><a href="{place_url}" target="_blank" style="color:blue; text-decoration:none;">Website &rarr;</a>'

                popup = f"""<div style="width:160px"><b>{title}</b><br><span style="color:gray">{cat_name}</span>{url_html}</div>"""
                marker = folium.Marker(
                    [p_lat, p_lon],
                    popup=folium.Popup(popup, max_width=200),
                    tooltip=f"{title} ({cat_name})",
                    icon=folium.Icon(color=info["color"], icon=info["icon"], prefix='fa')
                )
                device_markers[cat_name].append(marker)
                
    # Build Map
    m = folium.Map(location=[start_lat, start_lon], zoom_start=11)
    
    # Add Layers with HTML Labels
    for cat, markers in device_markers.items():
        if markers:
            # Determine color/icon for label
            if cat == "Camping":
                color, icon = "green", "campground"
            elif cat in target_cats:
                color = target_cats[cat]["color"]
                icon = target_cats[cat]["icon"]
            else:
                color, icon = "gray", "info-circle"
            
            # Create HTML label
            label = f'<i class="fa fa-{icon}" style="color:{color}"></i> &nbsp; {cat} ({len(markers)})'
            
            fg = folium.FeatureGroup(name=label)
            for mk in markers: mk.add_to(fg)
            fg.add_to(m)
            
    folium.LayerControl(collapsed=False).add_to(m)
    return m

def render_in_park_details(static_data):
    if not static_data: return
    
    st.markdown("### 🏕️ Campgrounds")
    campgrounds = static_data.get("campgrounds", [])
    
    for camp in campgrounds:
        name = getattr(camp, "name", "Campground")
        desc = getattr(camp, "description", "")
        images = getattr(camp, "images", [])
        img_url = images[0].url if images and hasattr(images[0], 'url') else None
        
        # Access attributes safely
        campsites = getattr(camp, "campsites", {})
        total = campsites.get("totalSites") if isinstance(campsites, dict) else "?"
        rv = campsites.get("rvOnly") if isinstance(campsites, dict) else "?"
        tent = campsites.get("tentOnly") if isinstance(campsites, dict) else "?"
        
        amenities = getattr(camp, "amenities", {})
        am_list = []
        if isinstance(amenities, dict):
            if "Yes" in str(amenities.get("toilets", "")): am_list.append("Toilets")
            if "Yes" in str(amenities.get("potableWater", "")): am_list.append("Water")
            if "Yes" in str(amenities.get("dumpStation", "")): am_list.append("Dump Station")
            if "Yes" in str(amenities.get("showers", "")): am_list.append("Showers")
        
        with st.expander(f"**{name}** ({total} sites)", expanded=False):
            c1, c2 = st.columns([1, 2])
            with c1:
                if img_url: st.image(img_url, use_container_width=True)
            with c2:
                st.write(desc)
                st.caption(f"**Sites:** {total} Total • {rv} RV-Only • {tent} Tent-Only")
                if am_list: st.info(" | ".join(am_list))
                
                # Accessibility
                access = getattr(camp, "accessibility", {})
                if isinstance(access, dict):
                    wh = access.get("wheelchairAccess")
                    if wh: st.write(f"**Accessibility:** {wh}")

    st.divider()
    
    # Other Categories
    places = static_data.get("places", [])
    
    # Reuse categories from map
    target_cats = {
        "Shuttle": {"keywords": ["shuttle", "bus"], "exclude_keywords": [], "icon": "bus", "color":"purple"},
        "Restroom": {"keywords": ["restroom", "toilet"], "exclude_keywords": [], "icon": "restroom", "color":"darkblue"},
        "Water": {"keywords": ["water", "bottle"], "exclude_keywords": [], "icon": "tint", "color":"blue"},
        "Food": {"keywords": ["food", "restaurant", "dining"], "exclude_keywords": ["food storage", "animal-safe"], "icon": "utensils", "color":"orange"},
        "Medical": {"keywords": ["first aid", "medical", "aed", "emergency"], "exclude_keywords": [], "icon": "medkit", "color":"red"},
    }
    
    grouped = {k: [] for k in target_cats.keys()}
    
    for place in places:
        amenities = getattr(place, "amenities", [])
        title = getattr(place, "title", "Place")
        url = getattr(place, "url", None)
        
        for cat_name, info in target_cats.items():
            match = False
            for am in amenities:
                am_lower = str(am).lower()
                
                # Check exclusions
                is_excluded = False
                for ex in info.get("exclude_keywords", []):
                    if ex in am_lower: is_excluded = True; break
                if is_excluded: continue
                
                # Check inclusions
                for kw in info["keywords"]:
                    if kw in am_lower: match = True; break
                if match: break
            
            if match:
                # Store tuple (Title, URL)
                grouped[cat_name].append((title, url))

    st.markdown("### 📍 Amenities List")
    cols = st.columns(3)
    idx = 0
    for cat, items in grouped.items():
        if items:
            with cols[idx % 3]:
                icon = target_cats[cat]["icon"]
                color = target_cats[cat]["color"]
                st.markdown(f'#### <i class="fa fa-{icon}" style="color:{color}"></i> &nbsp; {cat}', unsafe_allow_html=True)
                
                # Sort by title, items are (title, url) tuples
                sorted_items = sorted(list(set(items)), key=lambda x: x[0])
                
                for title_val, url_val in sorted_items:
                    if url_val:
                        st.markdown(f"- **[{title_val}]({url_val})**")
                    else:
                        st.markdown(f"- {title_val}")
                st.write("")
            idx += 1

# --- 5. MAIN RENDER ---
def render_essentials_dashboard(park_code, orchestrator, static_data, volatile_data=None):
    inject_custom_css()
    st.markdown('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">', unsafe_allow_html=True)
    
    # Data - use volatile_data passed from main.py (from daily cache)
    if volatile_data is None:
        volatile_data = {}
    
    weather = volatile_data.get("weather")
    zone_weather = volatile_data.get("zone_weather")  # NEW: Zonal weather dict
    alerts = volatile_data.get("alerts", [])
    
    # Get park details for zone config
    park_details = static_data.get("park_details")
    
    # Safe attribute access for ParkContext (or dict)
    base_zone_name = None
    weather_zones = []
    
    if park_details:
        if isinstance(park_details, dict):
            base_zone_name = park_details.get("base_weather_zone")
            weather_zones = park_details.get("weather_zones", [])
        else:
            base_zone_name = getattr(park_details, "base_weather_zone", None)
            weather_zones = getattr(park_details, "weather_zones", [])
    
    amenities_data = static_data.get("amenities_by_hub", {})
    if not amenities_data and hasattr(orchestrator, 'get_park_amenities'):
         amenities_data = orchestrator.get_park_amenities(park_code)

    render_alert_section(alerts)
    st.write("")
    
    # Split Layout: Weather (Left) vs Stats (Right)
    col_weather, col_stats = st.columns([1.8, 1])
    
    with col_weather:
        # Use zonal weather if available, otherwise fall back to regular weather
        if zone_weather and base_zone_name and len(zone_weather) > 0:
            render_zonal_weather(zone_weather, base_zone_name, weather_zones)
        else:
            render_weather_full_width(weather)
        
    with col_stats:
        render_stat_cards(static_data)

    st.write("")
    st.divider()
    
    # 1. Unified Toggle
    view_option = st.radio("Select View Layer", ["Hub Services", "In-Park Services"], horizontal=True, label_visibility="collapsed", key="essentials_toggle")
    
    st.subheader(f"🗺️ {view_option} Map")
    
    # 2. Map Rendering based on Toggle
    if view_option == "Hub Services":
        st.caption("Gas, Food, Lodging & Supplies near Park Hubs")
        m1 = render_detailed_map(amenities_data)
        if m1: st_folium(m1, height=500, use_container_width=True, key="map_hub")
        else: st.info("Map data unavailable.")
    else:
        st.caption("Restrooms, Water, Shuttle Stops, Camping & Medical inside the Park")
        m2 = render_in_park_map(static_data)
        if m2: st_folium(m2, height=500, use_container_width=True, key="map_park")
        else: st.info("In-Park data unavailable.")

    st.divider()
    st.subheader(f"📍 {view_option} Details")
    
    # 3. List Rendering based on Toggle
    if view_option == "Hub Services":
        if amenities_data:
            for hub_name, categories in amenities_data.items():
                with st.expander(f"**{hub_name}** List", expanded=False):
                     cols = st.columns(3)
                     for idx, (cat, items) in enumerate(categories.items()):
                         with cols[idx % 3]:
                             st.markdown(f"#### {get_category_html_label(cat)}", unsafe_allow_html=True)
                             for item in items[:5]:
                                 am = Amenity(**item) if isinstance(item, dict) else item
                                 
                                 if am.website:
                                     name_html = f'<a href="{am.website}" target="_blank" style="font-weight:600; font-size:1.05em; text-decoration:none;">{am.name}</a>'
                                 else:
                                     name_html = f'<span style="font-weight:600; font-size:1.05em;">{am.name}</span>'
                                     
                                 if am.address and am.address.lower() != "n/a":
                                     import urllib.parse
                                     safe = urllib.parse.quote(am.address)
                                     gmaps_link = f"https://www.google.com/maps/search/?api=1&query={safe}"
                                     addr_html = f'<a href="{gmaps_link}" target="_blank" style="font-size:0.85em; color:gray; text-decoration:none;">{am.address}</a>'
                                 elif am.latitude:
                                     gmaps_link = f"https://www.google.com/maps/search/?api=1&query={am.latitude},{am.longitude}"
                                     addr_html = f'<a href="{gmaps_link}" target="_blank" style="font-size:0.85em; color:gray; text-decoration:none;">View Map ↗</a>'
                                 else:
                                     addr_html = ""
                                     
                                 rating_display = f"{am.rating}⭐ ({am.rating_count or 0})" if am.rating else ""
                                 
                                 st.markdown(f"""
                                 <div style="margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid rgba(128, 128, 128, 0.2);">
                                     {name_html}<br>
                                     <span style="font-size:0.9em;">{rating_display}</span><br>
                                     {addr_html}
                                 </div>
                                 """, unsafe_allow_html=True)
    
    else: # In-Park Services
        render_in_park_details(static_data)
