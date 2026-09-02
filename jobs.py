# jobs.py
from datetime import date
from flask import current_app as app, render_template
from flask_mail import Message
from helpers import make_unsubscribe_token
import os
import logging

logger = logging.getLogger(__name__)

# -----------------------------
# INSERT-DRIVEN EMAIL PROCESSING
# -----------------------------
def _matches_issue(agenda, issue, today):
    """Does this newly inserted agenda doc match a user's saved issue?"""
    search_term = (issue.get('searchWord') or '').strip()
    if not search_term:
        return False

    description = agenda.get('Description') or ''
    if search_term.lower() not in description.lower():
        return False

    committee = (issue.get('Committee') or '').strip()
    city = (issue.get('City') or '').strip()
    county = (issue.get('County') or '').strip()

    if committee and committee.lower() not in (agenda.get('MeetingType') or '').lower():
        return False
    if city and city.lower() not in (agenda.get('City') or '').lower():
        return False
    if county and county.lower() not in (agenda.get('County') or '').lower():
        return False
    if not agenda.get('Date') or agenda.get('Date') < today:
        return False
    return True


def process_new_agendas(mongo, mail, new_agendas):
    """Match newly inserted agenda documents against users' saved issues and
    send one digest email per user. Called by the change-stream watcher."""
    today = int(date.today().strftime('%Y%m%d'))
    users = list(mongo.db.User.find({
        'email': {'$exists': True, '$ne': ''},
        'subscriptionActive': True,
        'email_alerts_enabled': {'$ne': False}
    }))
    logger.info(f"Processing {len(new_agendas)} new agenda(s) for {len(users)} user(s)")

    for user in users:
        username = user.get('username')
        email = user.get('email')
        if not email:
            continue
        try:
            user_data = mongo.db.User.find_one(
                {'username': username},
                {'issues': 1, 'agendaUnique_id': 1, '_id': 0}
            )
            if not user_data or not user_data.get('issues'):
                continue

            # Clean old agenda IDs (keep only recent/future meetings)
            mongo.db.User.update_one(
                {'username': username},
                {'$pull': {'agendaUnique_id': {'Date': {'$lt': today}}}}
            )

            seen_ids = {a['_id'] for a in user_data.get('agendaUnique_id', [])}
            agendas_by_search_term = {}

            for issue in user_data['issues']:
                search_term = (issue.get('searchWord') or '').strip()
                if not search_term:
                    continue
                for agenda in new_agendas:
                    if agenda['_id'] in seen_ids:
                        continue
                    if not _matches_issue(agenda, issue, today):
                        continue
                    agenda_data = dict(agenda)
                    agenda_data['searchWord'] = search_term
                    agenda_data['matchedSearchTerm'] = search_term
                    agendas_by_search_term.setdefault(search_term, []).append(agenda_data)

                    mongo.db.User.update_one(
                        {'username': username},
                        {'$addToSet': {'agendaUnique_id': {
                            '_id': agenda['_id'],
                            'Date': agenda.get('Date')
                        }}}
                    )

            if agendas_by_search_term:
                send_agenda_email(username, email, agendas_by_search_term, mail)
        except Exception as e:
            logger.error(f"Error processing user {username}: {e}")


def send_agenda_email(username, email, agendas_by_search_term, mail):
    """Send email notification about new matching agendas"""
    try:
        total_agendas = sum(len(a) for a in agendas_by_search_term.values())
        subject = f'You have {total_agendas} new agenda items from Policy Edge'
        msg = Message(subject, sender='AgendaPreciado@gmail.com', recipients=[email])
        unsubscribe_url = (
            f"{app.config['YOUR_DOMAIN']}unsubscribe/"
            f"{make_unsubscribe_token(app.secret_key, email)}"
        )
        msg.extra_headers = {
            'List-Unsubscribe': f'<{unsubscribe_url}>',
            'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
        }

        logger.info(f"Sending email to {username} ({total_agendas} items)")

        msg.html = render_template(
            'schedEmail.html',
            username=username,
            agendas_by_search_term=agendas_by_search_term,
            total_agendas=total_agendas,
            unsubscribe_url=unsubscribe_url
        )

        with open(os.path.join(app.root_path, 'static', 'logo.png'), 'rb') as fp:
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

