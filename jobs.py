# jobs.py
from datetime import date
from collections import Counter
from flask import current_app as app, render_template
from flask_mail import Mail, Message
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import logging

logger = logging.getLogger(__name__)

def check4Issues2email(mongo, mail):
    """Background job to check for issues and send email notifications to users"""
    with app.app_context():
        today = int(date.today().strftime('%Y%m%d'))
        
        users = list(mongo.db.User.find({
            'email': {'$exists': True, '$ne': ''},
            'subscriptionActive': True
        }))
        logger.info(f"Processing {len(users)} users for email notifications")
        
        for user in users:
            try:
                process_user_email_notifications(user, today, mongo, mail)
            except Exception as e:
                logger.error(f"Error processing user {user.get('username')}: {e}")


def process_user_email_notifications(user, today, mongo, mail):
    """Process and send email notifications for a single user"""
    username = user.get('username')
    email = user.get('email')

    if not email or not user.get('subscriptionActive'):
        return

    # Clean old agenda IDs
    mongo.db.User.update_one(
        {'username': username},
        {'$pull': {'agendaUnique_id': {'Date': {'$lt': today}}}}
    )

    user_data = mongo.db.User.find_one(
        {'username': username},
        {'issues': 1, 'agendaUnique_id': 1, '_id': 0}
    )

    if not user_data or not user_data.get('issues'):
        return

    issues = user_data['issues']
    seen_agenda_ids = {agenda['_id'] for agenda in user_data.get('agendaUnique_id', [])}
    agendas_by_search_term = {}
    
    for issue in issues:
        search_term = issue.get('searchWord', '')
        if not search_term:
            continue

        query = {
            '$and': [
                {"MeetingType": {'$regex': issue.get('Committee', ''), '$options': 'i'}},
                {"City": {'$regex': issue.get('City', ''), '$options': 'i'}},
                {"County": {'$regex': issue.get('County', ''), '$options': 'i'}},
                {'Description': {"$regex": search_term, '$options': 'i'}},
                {'Date': {'$gte': today}}
            ]
        }
        matching_agendas = list(mongo.db.Agenda.find(query))

        for agenda in matching_agendas:
            if agenda['_id'] not in seen_agenda_ids:
                agenda_data = dict(agenda)
                agenda_data['searchWord'] = search_term
                agenda_data['matchedSearchTerm'] = search_term
                agendas_by_search_term.setdefault(search_term, []).append(agenda_data)

                mongo.db.User.update_one(
                    {'username': username},
                    {'$addToSet': {'agendaUnique_id': {
                        '_id': agenda['_id'],
                        'Date': agenda['Date']
                    }}}
                )

    if agendas_by_search_term:
        send_agenda_email(username, email, agendas_by_search_term, mail)


def send_agenda_email(username, email, agendas_by_search_term, mail):
    """Send email notification about new matching agendas"""
    try:
        total_agendas = sum(len(a) for a in agendas_by_search_term.values())
        subject = f'You have {total_agendas} new agenda items from Policy Edge'
        msg = Message(subject, sender='AgendaPreciado@gmail.com', recipients=[email])

        logger.info(f"Sending email to {username} ({total_agendas} items)")

        msg.html = render_template(
            'schedEmail.html',
            username=username,
            agendas_by_search_term=agendas_by_search_term,
            total_agendas=total_agendas
        )

        with app.open_resource('/app/static/logo.png') as fp:
            msg.attach(
                filename="logo.png",
                content_type="image/png",
                data=fp.read(),
                disposition="inline",
                headers={"Content-ID": "<logo_png>"}
            )

        mail.send(msg)
        logger.info(f"✓ Email successfully sent to {username}")

    except Exception as e:
        logger.error(f"✗ Failed to send email to {username}: {e}")

