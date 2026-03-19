# stripe_routes.py
import os, json, stripe, logging
from flask import Blueprint, request, session, redirect, url_for, jsonify, render_template, flash
from PolicyEdge import mongo, YOUR_DOMAIN, stripe_keys  # import your app config
import bcrypt
from datetime import datetime

logger = logging.getLogger(__name__)
stripe_bp = Blueprint('stripe', __name__)

# -----------------------------
# Helper: log user events
# -----------------------------
def log_user_event(username, email, event_name, extra=None):
    data = {
        "username": username,
        "email": email,
        "event": event_name,
        "timestamp": datetime.utcnow()
    }
    if extra:
        data.update(extra)
    mongo.db.user_logs.insert_one(data)

# -----------------------------
# Stripe checkout for new user
# -----------------------------
@stripe_bp.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    stripe.api_key = stripe_keys['secret_key']

    username = request.form["username"]
    email = request.form["email"]
    password1 = request.form["password1"]
    password2 = request.form["password2"]

    # Validate registration
    errors = validate_registration(username, email, password1, password2)
    if errors:
        for error in errors:
            flash(error)
        return render_template('register.html')

    # Hash password and create user
    hashed = bcrypt.hashpw(password2.encode('utf-8'), bcrypt.gensalt())
    user_data = {
        'username': username,
        'email': email,
        'password': hashed,
        'stripe_id': [],
        'issues': [],
        'agendaUnique_id': [],
        'subscriptionActive': False
    }
    mongo.db.User.insert_one(user_data)
    mongo.db.stripe_user.insert_one({
        'username': username,
        'email': email,
        'stripeCustomerId': [],
        'stripeSubscriptionId': []
    })

    # Set session
    session.update({'username': username, 'email': email})

    # Log registration and checkout start
    log_user_event(username, email, "registration_completed")
    log_user_event(username, email, "checkout_started")

    return create_stripe_checkout_session(email)

# -----------------------------
# Stripe checkout for existing user
# -----------------------------
@stripe_bp.route('/create-checkout-session2', methods=['POST'])
def create_checkout_session2():
    stripe.api_key = stripe_keys['secret_key']

    if "username" not in session:
        return redirect(url_for("login"))

    email = session["email"]
    username = session["username"]
    existing_customer_id = get_user_stripe_customer(email)

    # Log checkout started
    log_user_event(username, email, "checkout_started")

    return create_stripe_checkout_session(email, existing_customer_id)

# -----------------------------
# Stripe Customer Portal
# -----------------------------
@stripe_bp.route('/create-portal-session', methods=['POST'])
def customer_portal():
    stripe.api_key = stripe_keys['secret_key']

    checkout_session_id = request.form.get('session_id')
    checkout_session = stripe.checkout.Session.retrieve(checkout_session_id)

    portal_session = stripe.billing_portal.Session.create(
        customer=checkout_session.customer,
        return_url=YOUR_DOMAIN,
    )
    return redirect(portal_session.url, code=303)

# -----------------------------
# Stripe Webhook for event tracking
# -----------------------------
@stripe_bp.route('/webhook', methods=['POST'])
def webhook_received():
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    payload = request.data
    sig_header = request.headers.get('stripe-signature')

    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        else:
            event = json.loads(payload)
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        return jsonify({'status': 'error'}), 400

    event_type = event['type']
    data = event['data']['object']

    # Log and handle events
    if event_type == 'checkout.session.completed':
        email = data.get('customer_email')
        mongo.db.User.update_one({'email': email}, {'$set': {'subscriptionActive': True}})
        log_user_event(None, email, "checkout_completed", {"stripe_session_id": data.get('id')})
        logger.info(f"Checkout completed for {email}")

    elif event_type == 'checkout.session.expired':
        email = data.get('customer_email')
        log_user_event(None, email, "checkout_expired", {"stripe_session_id": data.get('id')})
        logger.info(f"Checkout expired for {email}")

    elif event_type == 'customer.subscription.created':
        customer_id = data.get('customer')
        mongo.db.User.update_one({'stripe_id': customer_id}, {'$set': {'subscriptionActive': True}})
        log_user_event(None, None, "subscription_created", {"customer_id": customer_id})
        logger.info(f"Subscription created for {customer_id}")

    elif event_type == 'customer.subscription.updated':
        customer_id = data.get('customer')
        status = data.get('status')
        active_status = status in ['active', 'trialing']
        mongo.db.User.update_one({'stripe_id': customer_id}, {'$set': {'subscriptionActive': active_status}})
        log_user_event(None, None, "subscription_updated", {"customer_id": customer_id, "status": status})
        logger.info(f"Subscription updated for {customer_id}: {status}")

    elif event_type == 'customer.subscription.deleted':
        customer_id = data.get('customer')
        mongo.db.User.update_one({'stripe_id': customer_id}, {'$set': {'subscriptionActive': False}})
        log_user_event(None, None, "subscription_deleted", {"customer_id": customer_id})
        logger.info(f"Subscription canceled for {customer_id}")

    return jsonify({'status': 'success'})