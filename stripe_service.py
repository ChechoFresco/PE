import os
import json
import stripe
import re
from flask import current_app, redirect, flash, url_for, request, jsonify
from pymongo import MongoClient

# Mongo connection (you can also pass in mongo from main app)
mongo = None  # will set from PolicyEdge.py

# Set your Stripe keys from env
stripe.api_key = os.environ.get("SECRET_KEY")

def init(mongo_client):
    """Initialize the mongo client from main app"""
    global mongo
    mongo = mongo_client

def get_user_stripe_customer(email):
    """Retrieve existing Stripe customer ID for a user"""
    user = mongo.db.User.find_one({'email': email, 'stripe_customer_id': {'$exists': True}})
    if user and user.get('stripe_customer_id'):
        return user['stripe_customer_id']
    return None

def create_checkout_session(email, your_domain, existing_customer_id=None):
    """Create Stripe checkout session for subscription payments"""
    try:
        # Get or create customer
        if existing_customer_id:
            customer = existing_customer_id
        else:
            customer_obj = stripe.Customer.create(
                description="PolicyEdge subscriber",
                email=email
            )
            customer = customer_obj.id
            mongo.db.User.update_one(
                {'email': email},
                {'$set': {'stripe_customer_id': customer}}
            )

        price_id = os.environ.get("STRIPE_MONTH_PRICE_ID")
        if not price_id:
            raise ValueError("Missing STRIPE_MONTH_PRICE_ID")

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            customer=customer,
            success_url=f"{your_domain}success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{your_domain}cancel"
        )
        return redirect(session.url, code=303)

    except Exception as e:
        current_app.logger.error(f"Stripe checkout error: {e}")
        flash('Error creating checkout session. Please try again.')
        return redirect(url_for('register'))

def handle_webhook(request_data, request_headers, your_domain, env):
    """Handle Stripe webhook events"""
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    try:
        if env == "production" and webhook_secret:
            signature = request_headers.get('stripe-signature')
            event = stripe.Webhook.construct_event(
                payload=request_data,
                sig_header=signature,
                secret=webhook_secret
            )
        else:
            event = json.loads(request_data)
    except Exception as e:
        current_app.logger.error(f"Webhook signature verification failed: {e}")
        return jsonify({'status': 'error'}), 400

    data = event['data']['object']
    event_type = event['type']

    # Handle main events
    if event_type == 'checkout.session.completed':
        customer_id = data.get('customer')
        mongo.db.User.update_one(
            {'stripe_customer_id': customer_id},
            {'$set': {'subscriptionActive': True}}
        )

    elif event_type == 'customer.subscription.created':
        subscription_id = data.get('id')
        customer_id = data.get('customer')
        mongo.db.User.update_one(
            {'stripe_customer_id': customer_id},
            {'$set': {
                'stripe_subscription_id': subscription_id,
                'subscriptionActive': True
            }}
        )

    elif event_type == 'customer.subscription.updated':
        customer_id = data.get('customer')
        status = data.get('status')
        status_mapping = {
            'active': True, 'trialing': True,
            'past_due': False, 'canceled': False,
            'unpaid': False, 'incomplete': False
        }
        if status in status_mapping:
            mongo.db.User.update_one(
                {'stripe_customer_id': customer_id},
                {'$set': {'subscriptionActive': status_mapping[status]}}
            )

    elif event_type == 'customer.subscription.deleted':
        customer_id = data.get('customer')
        mongo.db.User.update_one(
            {'stripe_customer_id': customer_id},
            {'$set': {
                'subscriptionActive': False,
                'stripe_subscription_id': None
            }}
        )

    return jsonify({'status': 'success'})

def validate_registration(username, email, password1, password2):
    errors = []

    if mongo.db.User.find_one({"username": username}):
        errors.append('There already is a user by that name')

    if mongo.db.User.find_one({"email": email}):
        errors.append('This email already exists in our user database')

    if ' ' in username:
        errors.append('Please no whitespaces in username')

    if not re.match(r'^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$', email):
        errors.append('Please use a valid email address')

    if password1 != password2:
        errors.append('Passwords should match!')

    if len(password1) < 8:
        errors.append('Please make sure password is longer than 8 characters')

    return errors