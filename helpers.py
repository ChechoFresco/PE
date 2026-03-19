# helpers.py
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from collections import Counter

def get_date_threshold(weeks=-2):
    """Get date threshold in YYYYMMDD format for database queries"""
    return int((date.today() + relativedelta(weeks=weeks)).strftime('%Y%m%d'))

def handle_issue_operation(mongo, user, form_data, operation):
    """Handle adding or removing issues from user's saved list"""
    primeKey = form_data.get('primary_search', '').strip()
    county = form_data.get('select', '')
    city_field_map = {
        'LA County': 'selectLA', 'Orange County': 'selectOC', 
        'Riverside County': 'selectRS', 'San Bernardino County': 'selectSB'
    }
    
    city = form_data.get(city_field_map.get(county, ''), '')
    committee = form_data.get('selectLACM', '') or form_data.get('selectLBCM', '')
    
    # Handle LA/Long Beach committees specially
    if county in ['LA Committees', 'Long Beach Committees']:
        county = 'LA County'
        city = 'Los Angeles' if 'LA Committees' in form_data else 'Long Beach'
        committee = form_data.get('selectLACM', '') or form_data.get('selectLBCM', '')

    issue_data = {
        "searchWord": primeKey,
        "City": city,
        "Committee": committee,
        "County": county,
    }
    
    # Use $push for Add, $pull for Delete
    operation = '$push' if operation == 'Add' else '$pull'
    mongo.db.User.update_one(
        {'username': user},
        {operation: {'issues': issue_data}}
    )

def get_user_saved_agendas(mongo, user, days_back=60, days_forward=30):
    """Get agendas matching user's saved issues"""
    today = int(date.today().strftime('%Y%m%d'))
    start_date = int((date.today() + relativedelta(days=-days_back)).strftime('%Y%m%d'))
    end_date = int((date.today() + relativedelta(days=days_forward)).strftime('%Y%m%d'))
    
    # Get user's saved issues
    user_data = mongo.db.User.find_one(
        {'username': user}, 
        {'_id': 0, 'issues': 1}
    )
    
    if not user_data or not user_data.get('issues'):
        return []
    
    agendas = []
    for issue in user_data['issues']:
        query = {
            '$and': [
                {"MeetingType": {'$regex': issue.get('Committee', ''), '$options': 'i'}},
                {"City": {'$regex': issue.get('City', ''), '$options': 'i'}},
                {"County": {'$regex': issue.get('County', ''), '$options': 'i'}},
                {'Description': {"$regex": issue.get('searchWord', ''), '$options': 'i'}},
                {'Date': {'$lte': end_date, '$gte': start_date}}
            ]
        }
        matching_agendas = list(mongo.db.Agenda.find(query).sort('Date', -1))
        agendas.extend(matching_agendas)
    
    return agendas

def int2date(agDate: int) -> str:
    """Convert integer date (YYYYMMDD) to formatted string (Month Day, Year)"""
    try:
        dt = datetime.strptime(str(agDate), '%Y%m%d')
        return dt.strftime('%B %d, %Y')
    except (ValueError, TypeError):
        return "Invalid Date"