# jobs.py
from datetime import date
from flask import render_template
from flask_mail import Message
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import logging

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")


# -----------------------------
# JOB FUNCTIONS
# -----------------------------
def check4Issues2email(app, User, Agenda, db):
    """Background job to check for issues and send email notifications to users."""
    with app.app_context():
        today = int(date.today().strftime("%Y%m%d"))

        users = (
            User.query
            .filter(User.email.isnot(None))
            .filter(User.email != "")
            .filter(User.subscription_active.is_(True))
            .all()
        )

        logger.info(f"Processing {len(users)} users for email notifications")

        for user in users:
            try:
                process_user_email_notifications(app, user, today, Agenda, db)
            except Exception as e:
                logger.error(f"Error processing user {user.username}: {e}")


def process_user_email_notifications(app, user, today, Agenda, db):
    """Process and send email notifications for a single user."""
    username = user.username
    email = user.email

    if not email or not user.subscription_active:
        return

    issues = user.issues or []
    if not issues:
        return

    seen_agenda_ids = set(user.agenda_unique_ids or [])
    agendas_by_search_term = {}

    for issue in issues:
        search_term = (issue.get("searchWord") or "").strip()
        if not search_term:
            continue

        city = (issue.get("City") or "").strip()
        county = (issue.get("County") or "").strip()
        committee = (issue.get("Committee") or "").strip()

        query = Agenda.query.filter(
            Agenda.date >= today,
            Agenda.description.isnot(None),
            Agenda.description != ""
        )

        query = query.filter(Agenda.description.ilike(f"%{search_term}%"))

        if city:
            query = query.filter(Agenda.city.ilike(f"%{city}%"))

        if county:
            query = query.filter(Agenda.county.ilike(f"%{county}%"))

        if committee:
            query = query.filter(Agenda.meeting_type.ilike(f"%{committee}%"))

        matching_agendas = query.all()

        for agenda in matching_agendas:
            if agenda.id in seen_agenda_ids:
                continue

            agenda_data = {
                "id": agenda.id,
                "County": agenda.county,
                "City": agenda.city,
                "Date": agenda.date,
                "Num": agenda.num,
                "MeetingType": agenda.meeting_type,
                "ItemType": agenda.item_type,
                "Description": agenda.description,
                "searchWord": search_term,
                "matchedSearchTerm": search_term
            }

            agendas_by_search_term.setdefault(search_term, []).append(agenda_data)

            seen_agenda_ids.add(agenda.id)

        if agendas_by_search_term:
            user.agenda_unique_ids = list(seen_agenda_ids)
            db.session.commit()

    if agendas_by_search_term:
        send_agenda_email(app, username, email, agendas_by_search_term)


def send_agenda_email(app, username, email, agendas_by_search_term):
    """Send email notification about new matching agendas."""
    try:
        total_agendas = sum(len(a) for a in agendas_by_search_term.values())
        subject = f"You have {total_agendas} new agenda items from Policy Edge"
        msg = Message(subject, sender="AgendaPreciado@gmail.com", recipients=[email])

        logger.info(f"Sending email to {username} ({total_agendas} items)")

        msg.html = render_template(
            "schedEmail.html",
            username=username,
            agendas_by_search_term=agendas_by_search_term,
            total_agendas=total_agendas
        )

        with app.open_resource("static/logo.png") as fp:
            msg.attach(
                filename="logo.png",
                content_type="image/png",
                data=fp.read()
            )

        from PolicyEdge import mail
        mail.send(msg)

        logger.info(f"✓ Email successfully sent to {username}")

    except Exception as e:
        logger.error(f"✗ Failed to send email to {username}: {e}")


# -----------------------------
# SCHEDULER SETUP
# -----------------------------
def start_scheduler(app, User, Agenda, db):
    """Start background jobs for PolicyEdge."""
    scheduler.add_job(
        func=lambda: check4Issues2email(app, User, Agenda, db),
        trigger="interval",
        minutes=60,
        id="check4Issues2email",
        replace_existing=True
    )
    scheduler.start()
    logger.info("Background scheduler started with jobs")

    atexit.register(shutdown_scheduler)
    return scheduler


def shutdown_scheduler():
    """Gracefully shutdown the scheduler when app exits."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler shut down successfully")