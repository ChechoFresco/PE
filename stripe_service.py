import os
import json
import re
import stripe

from flask import (
    current_app,
    redirect,
    flash,
    url_for,
    jsonify
)

db = None
User = None


def init(database, user_model):
    global db, User

    db = database
    User = user_model
    stripe.api_key = os.environ.get("SECRET_KEY")


def get_user_stripe_customer(email):
    user = (
        User.query
        .filter(db.func.lower(User.email) == email.lower())
        .first()
    )

    if user:
        return user.stripe_customer_id

    return None


def create_checkout_session(
    email,
    your_domain,
    existing_customer_id=None
):
    try:
        user = (
            User.query
            .filter(db.func.lower(User.email) == email.lower())
            .first()
        )

        if not user:
            raise ValueError("User does not exist")

        customer_id = (
            existing_customer_id
            or user.stripe_customer_id
        )

        if not customer_id:
            customer = stripe.Customer.create(
                description="PolicyEdge subscriber",
                email=email
            )

            customer_id = customer.id
            user.stripe_customer_id = customer_id
            db.session.commit()

        price_id = os.environ.get("STRIPE_MONTH_PRICE_ID")

        if not price_id:
            raise ValueError("Missing STRIPE_MONTH_PRICE_ID")

        domain = your_domain.rstrip("/")

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1
                }
            ],
            mode="subscription",
            customer=customer_id,
            success_url=(
                f"{domain}/success"
                "?session_id={CHECKOUT_SESSION_ID}"
            ),
            cancel_url=f"{domain}/cancel"
        )

        return redirect(checkout_session.url, code=303)

    except Exception as error:
        db.session.rollback()

        current_app.logger.error(
            "Stripe checkout error: %s",
            error
        )

        flash(
            "Error creating checkout session. "
            "Please try again."
        )

        return redirect(url_for("register"))


def handle_webhook(
    request_data,
    request_headers,
    your_domain,
    env
):
    webhook_secret = os.environ.get(
        "STRIPE_WEBHOOK_SECRET"
    )

    try:
        if env == "production" and webhook_secret:
            signature = request_headers.get(
                "stripe-signature"
            )

            event = stripe.Webhook.construct_event(
                payload=request_data,
                sig_header=signature,
                secret=webhook_secret
            )
        else:
            event = json.loads(request_data)

    except Exception as error:
        current_app.logger.error(
            "Webhook verification failed: %s",
            error
        )

        return jsonify({"status": "error"}), 400

    data = event["data"]["object"]
    event_type = event["type"]

    customer_id = data.get("customer")

    user = None

    if customer_id:
        user = User.query.filter_by(
            stripe_customer_id=customer_id
        ).first()

    if user:
        if event_type == "checkout.session.completed":
            user.subscription_active = True

            if data.get("subscription"):
                user.stripe_subscription_id = data.get(
                    "subscription"
                )

        elif event_type == "customer.subscription.created":
            user.stripe_subscription_id = data.get("id")
            user.subscription_active = True

        elif event_type == "customer.subscription.updated":
            user.stripe_subscription_id = data.get("id")

            user.subscription_active = (
                data.get("status") in ["active", "trialing"]
            )

        elif event_type == "customer.subscription.deleted":
            user.subscription_active = False
            user.stripe_subscription_id = None

        db.session.commit()

    return jsonify({"status": "success"})


def validate_registration(
    username,
    email,
    password1,
    password2
):
    errors = []

    username = username.strip()
    email = email.strip().lower()

    existing_username = (
        User.query
        .filter(
            db.func.lower(User.username)
            == username.lower()
        )
        .first()
    )

    existing_email = (
        User.query
        .filter(
            db.func.lower(User.email)
            == email
        )
        .first()
    )

    if existing_username:
        errors.append(
            "There already is a user by that name"
        )

    if existing_email:
        errors.append(
            "This email already exists in our user database"
        )

    if " " in username:
        errors.append(
            "Please no whitespaces in username"
        )

    if not re.match(
        r"^[A-Za-z0-9.\+_-]+@[A-Za-z0-9._-]+\.[A-Za-z]+$",
        email
    ):
        errors.append(
            "Please use a valid email address"
        )

    if password1 != password2:
        errors.append("Passwords should match!")

    if len(password1) < 8:
        errors.append(
            "Please make sure password is longer "
            "than 8 characters"
        )

    return errors