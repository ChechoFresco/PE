# map_utils.py
from folium import Map, Circle, Marker, Popup
from folium.features import DivIcon
from folium import Popup

def fetch_geo_info(mongo, city_issue_counts):
    """Fetch geo-location data from MongoDB for map generation"""
    geo_info = []
    for city, count in city_issue_counts.items():
        location_data = mongo.db.geoLoc.find_one({'city': city}, {'_id': 0})
        if location_data:
            geo_info.append((
                location_data['city'], 
                location_data['state_id'], 
                location_data['county_name'],
                location_data['lat'], 
                location_data['lng'], 
                str(count), 
                location_data['webAdress']
            ))
    return geo_info

def create_folium_map(geo_info, ALL_CITY_AGENDAS_CACHE):
    """
    geo_info: list of tuples (city, state_id, county_name, lat, lon, issue_count, web_address)
    ALL_CITY_AGENDAS_CACHE: dict mapping city -> dict with 'agendas' and 'topic_counts'
    """
    folium_map = Map(
        location=(34, -118), 
        zoom_start=9, 
        tiles="cartodbpositron"
    )
    
    for city, state_id, county_name, lat, lon, issue_count, web_address in geo_info:
        agendas = ALL_CITY_AGENDAS_CACHE.get(city, {}).get("agendas", [])

        if agendas:
            # Build HTML popup with multiple agenda items
            popup_html = f"""
            <div style="
                max-height:400px;
                width:400px;
                overflow:auto;
                background-color:#d1e2f5;
                color:#2F5755;
                padding:8px;
                border-radius:10px;
                font-family:Arial, sans-serif;
                font-size:13px;
            ">
                <h4 style="margin:0 0 6px 0; color:#2F5755;">{city}</h4>
            """

            for idx, agenda in enumerate(agendas[:5], 1):
                desc = agenda.get("Description", "")
                date = agenda.get("Date", "")
                topics = ", ".join(agenda.get("Topics", [])) if isinstance(agenda.get("Topics"), list) else agenda.get("Topics", "")
                
                popup_html += f"""
                <div style="margin-bottom:6px; padding-bottom:4px; border-bottom:1px solid #ff7a00;">
                    <p><b>{idx}.</b> {desc}</p>
                    <p><b>Date:</b> {date} | <b>Topics:</b> {topics}</p>
                </div>
                """

            popup_html += "</div>"

            popup = Popup(popup_html, max_width=400, min_width=300)

            # Circle marker with popup
            Circle(
                location=[lat, lon],
                radius=float(issue_count) * 50,
                color='#5e7cff',
                fill=True,
                fill_color='#5e7cff',
                popup=popup
            ).add_to(folium_map)
        
        # Small text marker with count (optional)
        Marker(
            location=[lat, lon],
            icon=DivIcon(
                icon_size=(10, 10),
                icon_anchor=(15, 15),
                html=f'<div style="font-size: 10pt">{issue_count} {city}</div>'
            )
        ).add_to(folium_map)
    
    return folium_map