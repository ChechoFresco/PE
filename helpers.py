# helpers.py
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from collections import Counter
import logging
from sqlalchemy import or_

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # or DEBUG


def get_date_threshold(weeks=-2):
    """Get date threshold in YYYYMMDD format for database queries"""
    return int((date.today() + relativedelta(weeks=weeks)).strftime('%Y%m%d'))

def handle_issue_operation(db, User, username, form_data, operation, subscription_active=False, free_limit=3):
    """Handle adding or removing issues from user's saved list"""
    primeKey = form_data.get('primary_search', '').strip()
    county = form_data.get('select', '')

    city_field_map = {
        'LA County': 'selectLA',
        'Orange County': 'selectOC',
        'Riverside County': 'selectRS',
        'San Bernardino County': 'selectSB',
        'San Diego County': 'selectSD',
    }

    city = form_data.get(city_field_map.get(county, ''), '')
    committee = form_data.get('selectLACM', '') or form_data.get('selectLBCM', '')

    if county in ['LA Committees', 'Long Beach Committees']:
        original_county = county
        county = 'LA County'
        city = 'Los Angeles' if original_county == 'LA Committees' else 'Long Beach'
        committee = form_data.get('selectLACM', '') or form_data.get('selectLBCM', '')

    issue_data = {
        "searchWord": primeKey,
        "City": city,
        "Committee": committee,
        "County": county,
    }

    current_user = User.query.filter_by(username=username).first()
    if not current_user:
        return False

    issues = current_user.issues or []

    print("operation:", operation)
    print("subscription_active:", subscription_active)
    print("free_limit:", free_limit)
    print("current issues count:", len(issues))
    print("issue_data:", issue_data)
    print("issues:", issues)

    if operation == 'Add':
        if issue_data in issues:
            return True

        if not subscription_active and len(issues) >= free_limit:
            return False

        issues.append(issue_data)
        current_user.issues = issues
        db.session.commit()
        return True

    elif operation == 'Delete':
        updated_issues = [
            issue for issue in issues
            if not (
                issue.get("searchWord") == issue_data["searchWord"]
                and issue.get("City") == issue_data["City"]
                and issue.get("Committee") == issue_data["Committee"]
                and issue.get("County") == issue_data["County"]
            )
        ]
        current_user.issues = updated_issues
        db.session.commit()
        return True

    return False


def get_user_saved_agendas(User, Agenda, username, days_back=7, days_forward=30):
    """Get agendas matching user's saved issues"""
    if not username:
        return []

    today = int(date.today().strftime('%Y%m%d'))
    start_date = int((date.today() + relativedelta(days=-days_back)).strftime('%Y%m%d'))
    end_date = int((date.today() + relativedelta(days=days_forward)).strftime('%Y%m%d'))

    print(f"Searching agendas from {start_date} to {end_date} for user {username}")

    user_data = (
        User.query
        .filter_by(username=username)
        .first()
    )

    if not user_data or not user_data.issues:
        print("No saved issues found")
        return []

    agendas = []

    for issue in user_data.issues:
        print("Checking issue:", issue)

        searchWord = (issue.get('searchWord') or '').strip()
        city = (issue.get('City') or '').strip()
        committee = (issue.get('Committee') or '').strip()
        county = (issue.get('County') or '').strip()

        # If the saved issue was just a keyword search
        if county == 'Issue':
            county = ''
            city = ''
            committee = ''

        query = (
            Agenda.query
            .filter(Agenda.date >= start_date)
            .filter(Agenda.date <= end_date)
            .filter(Agenda.description.isnot(None))
            .filter(Agenda.description != "")
        )

        if searchWord:
            query = query.filter(Agenda.description.ilike(f"%{searchWord}%"))

        if committee:
            query = query.filter(Agenda.meeting_type.ilike(f"%{committee}%"))

        if city:
            query = query.filter(Agenda.city.ilike(f"%{city}%"))

        if county:
            query = query.filter(Agenda.county.ilike(f"%{county}%"))

        results = query.order_by(Agenda.date.desc()).all()

        for agenda in results:
            agendas.append({
                "id": agenda.id,
                "County": agenda.county,
                "City": agenda.city,
                "Date": agenda.date,
                "Num": agenda.num,
                "MeetingType": agenda.meeting_type,
                "ItemType": agenda.item_type,
                "Description": agenda.description,
                "Topics": []
            })

    print(f"Total agendas found: {len(agendas)}")
    return agendas


    
def int2date(agDate: int) -> str:
    """Convert integer date (YYYYMMDD) to formatted string (Month Day, Year)"""
    try:
        dt = datetime.strptime(str(agDate), '%Y%m%d')
        return dt.strftime('%B %d, %Y')
    except (ValueError, TypeError):
        return "Invalid Date"