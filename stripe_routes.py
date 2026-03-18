# stripe_routes.py
import os, json, stripe, logging
from flask import Blueprint, request, session, redirect, url_for, jsonify, render_template
from werkzeug.utils import secure_filename
from PolicyEdge import mongo, YOUR_DOMAIN, stripe_keys  # import your app config

logger = logging.getLogger(__name__)
stripe_bp = Blueprint('stripe', __name__)

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
    
    # Create user account
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
    
    # Set session and redirect to checkout
    session.update({'username': username, 'email': email})
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
    existing_customer_id = get_user_stripe_customer(email)
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
# Stripe Webhook
# -----------------------------
@stripe_bp.route('/webhook', methods=['POST'])
def webhook_received():
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    request_data = json.loads(request.data)
    
    if webhook_secret:
        signature = request.headers.get('stripe-signature')
        try:
            event = stripe.Webhook.construct_event(
                payload=request.data, 
                sig_header=signature, 
                secret=webhook_secret
            )
            data = event['data']
        except Exception as e:
            logger.error(f"Webhook verification failed: {e}")
            return jsonify({'status': 'error'}), 400
        event_type = event['type']
    else:
        data = request_data['data']
        event_type = request_data['type']

    # Handle Stripe events
    handle_stripe_event(event_type, data)
    return jsonify({'status': 'success'})


# -----------------------------
# Event Handler
# -----------------------------
def handle_stripe_event(event_type, data):
    if event_type == 'checkout.session.completed':
        logger.info("Payment succeeded!")

    elif event_type == 'customer.created':
        customer_id = data.object.id
        customer_email = data.object.email
        mongo.db.User.update_one({'email': customer_email}, {'$push': {'stripe_id': customer_id}})
        mongo.db.stripe_user.update_one({'email': customer_email}, {'$push': {'stripeCustomerId': customer_id}})
        logger.info(f"New Stripe customer created: {customer_email}")

    elif event_type == 'customer.subscription.created':
        subscription_id = data.object.id
        customer_id = data.object.customer
        mongo.db.stripe_user.update_one({'stripeCustomerId': customer_id}, {'$push': {'stripeSubscriptionId': subscription_id}})
        mongo.db.User.update_one({'stripe_id': customer_id}, {'$set': {'subscriptionActive': True}})
        logger.info(f"New subscription created for customer: {customer_id}")

    elif event_type == 'customer.subscription.updated':
        subscription = data.object
        customer_id = subscription.customer
        status_mapping = {
            'active': True, 'trialing': True, 'past_due': False,
            'canceled': False, 'unpaid': False, 'incomplete': False
        }
        status = subscription.status
        if status in status_mapping:
            mongo.db.User.update_one({'stripe_id': customer_id}, {'$set': {'subscriptionActive': status_mapping[status]}})
            logger.info(f"Subscription updated for {customer_id}: {status}")

    elif event_type == 'customer.subscription.deleted':
        customer_id = data.object.customer
        mongo.db.User.update_one({'stripe_id': customer_id}, {'$set': {'subscriptionActive': False}})
        logger.info(f"Subscription canceled for customer: {customer_id}")