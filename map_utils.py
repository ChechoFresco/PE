# map_utils.py
import folium
from folium.features import DivIcon

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

def create_folium_map(geo_info):
    """Create a Folium map with circles and markers for agenda visualization"""
    folium_map = folium.Map(
        location=(34, -118), 
        zoom_start=9, 
        tiles="cartodbpositron", 
    )
    
    for city, state_id, county_name, lat, lon, issue_count, web_address in geo_info:
        # Add circle marker proportional to issue count
        folium.Circle(
            location=[lat, lon],
            popup=f"<a href='{web_address}' target='_blank'>{city} Agenda Link</a>",
            radius=float(issue_count) * 50,
            color='#5e7cff',
            fill=True,
            fill_color='#5e7cff'
        ).add_to(folium_map)
        
        # Add text marker with count
        folium.Marker(
            location=[lat, lon],
            icon=DivIcon(
                icon_size=(10, 10),
                icon_anchor=(15, 15),
                html=f'<div style="font-size: 10pt">{issue_count} {city}</div>'
            )
        ).add_to(folium_map)
    
    return folium_map