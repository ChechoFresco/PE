# helpers.py
import re
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from collections import Counter
import logging
from itsdangerous import URLSafeTimedSerializer

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # or DEBUG


UNSUBSCRIBE_SALT = "email-unsubscribe"


def make_unsubscribe_token(secret_key, email):
    """Create a signed, time-limited unsubscribe token for an email address."""
    return URLSafeTimedSerializer(secret_key, salt=UNSUBSCRIBE_SALT).dumps(email)


def load_unsubscribe_token(secret_key, token, max_age_days=365):
    """Decode an unsubscribe token, raising on invalid/expired tokens."""
    return URLSafeTimedSerializer(secret_key, salt=UNSUBSCRIBE_SALT).loads(
        token, max_age=60 * 60 * 24 * max_age_days
    )


def to_table_agenda(doc):
    """Convert a Mongo Agenda doc into the uppercase dict shape templates expect."""
    doc_id = str(doc.get("_id", "")) if doc else ""
    return {
        "ID": doc_id,
        "_id": doc_id,
        "County": doc.get("County", ""),
        "City": doc.get("City", ""),
        "Date": doc.get("Date", ""),
        "Num": doc.get("Num", ""),
        "MeetingType": doc.get("MeetingType", ""),
        "ItemType": doc.get("ItemType", ""),
        "Description": doc.get("Description", ""),
    }


def to_item_dict(doc):
    """Convert a Mongo Agenda doc to the lowercase dict used by the item page."""
    return {
        "id": str(doc.get("_id", "")),
        "city": doc.get("City", ""),
        "county": doc.get("County", ""),
        "date": doc.get("Date", ""),
        "num": doc.get("Num", ""),
        "meeting_type": doc.get("MeetingType", ""),
        "item_type": doc.get("ItemType", ""),
        "description": doc.get("Description", ""),
    }


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

def get_user_saved_agendas(mongo, username, days_back=60, days_forward=30):
    """Get agendas matching user's saved issues"""
    if not username:
        return []

    today = int(date.today().strftime('%Y%m%d'))
    start_date = int((date.today() + relativedelta(days=-days_back)).strftime('%Y%m%d'))
    end_date = int((date.today() + relativedelta(days=days_forward)).strftime('%Y%m%d'))

    print(f"Searching agendas from {start_date} to {end_date} for user {username}")

    user_data = mongo.db.User.find_one({'username': username}, {'_id': 0, 'issues': 1})

    if not user_data or not user_data.get('issues'):
        print("No saved issues found")
        return []

    agendas = []

    for issue in user_data['issues']:
        print("Checking issue:", issue)
        
        # Grab values from issue
        searchWord = issue.get('searchWord', '').strip()
        city = issue.get('City', '').strip()
        committee = issue.get('Committee', '').strip()
        county = issue.get('County', '').strip()

        # If the saved issue was just a keyword search
        if county == 'Issue':
            county = ''
            city = ''
            committee = ''

        # Keyword filter: case-insensitive substring match on Description
        text_query = {}
        if searchWord:
            text_query = {'Description': {'$regex': re.escape(searchWord), '$options': 'i'}}

        # Build the MongoDB query
        query = {
            '$and': [
                {"MeetingType": {'$regex': committee, '$options': 'i'}},
                {"City": {'$regex': city, '$options': 'i'}},
                {"County": {'$regex': county, '$options': 'i'}},
                {"Date": {'$gte': start_date, '$lte': end_date}}
            ]
        }

        if text_query:
            query['$and'].append(text_query)

        # Fetch results
        results = mongo.db.Agenda.find(query).sort('Date', -1)
        for agenda in results:
            print("Agenda:", agenda.get('Description', ''), agenda.get('Date', ''))
            agendas.append(agenda)

    print(f"Total agendas found: {len(agendas)}")
    return agendas

# -------------------------------
# HELPER: GET COUNTY AGENDAS
# -------------------------------
def get_county_agendas(mongo, county_name, weeks_back=16):
    """Fetch City Council agendas for a specific county in the last `weeks_back` weeks"""
    date_threshold = int((date.today() + relativedelta(weeks=-weeks_back)).strftime('%Y%m%d'))

    try:
        agenda_items = mongo.db.Agenda.find({
            '$and': [
                {'Date': {'$gte': date_threshold}},
                {'MeetingType': {'$regex': 'City Council', '$options': 'i'}},
                {'County': {'$regex': county_name, '$options': 'i'}},
                {'Description': {'$regex': '.{6}'}},
                {
                    '$and': [
                        {"Description": {'$not': {'$regex': "minute"}}},
                        {"Description": {'$not': {'$regex': "warrant"}}}
                    ]
                }
            ]
        }).sort('Date', -1)

        return list(agenda_items)

    except Exception as e:
        return []
    
def int2date(agDate: int) -> str:
    """Convert integer date (YYYYMMDD) to formatted string (Month Day, Year)"""
    try:
        dt = datetime.strptime(str(agDate), '%Y%m%d')
        return dt.strftime('%B %d, %Y')
    except (ValueError, TypeError):
        return "Invalid Date"
