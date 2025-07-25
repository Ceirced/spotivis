import os
from datetime import datetime

from flask import render_template, redirect, url_for, request, abort
from flask_login import current_user
import stripe


from app import db
from app.public import bp
from app.models import Payment


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    return render_template("public/index.html", title="Home")


@bp.route("/stripe/event", methods=["POST"])
def new_event():
    event = None
    payload = request.data
    signature = request.headers["STRIPE_SIGNATURE"]

    try:
        event = stripe.Webhook.construct_event(
            payload, signature, os.environ["STRIPE_WEBHOOK_SECRET"]
        )
    except Exception as e:
        # the payload could not be verified
        abort(400)

    if event["type"] == "checkout.session.completed":
        session = stripe.checkout.Session.retrieve(
            event["data"]["object"].id, expand=["line_items"]
        )
        user_id = session.metadata.user_id
        user_email = session.metadata.user_email
        amount = session.amount_total / 100  # Stripe amounts are in cents
        currency = session.currency.upper()
        stripe_payment_id = session.payment_intent
        status = session.payment_status
        created = session.created

        # transform the created timestamp to a datetime object
        created = datetime.fromtimestamp(created)

        stripe_customer_email = session.customer_details.email
        stripe_customer_name = session.customer_details.name
        stripe_customer_address_country = session.customer_details.address.country

        # Save the payment in the database
        payment = Payment(
            user_id=user_id,
            user_email=user_email,
            amount=amount,
            currency=currency,
            stripe_payment_id=stripe_payment_id,
            status=status,
            created=created,
            stripe_customer_email=stripe_customer_email,
            stripe_customer_name=stripe_customer_name,
            stripe_customer_address_country=stripe_customer_address_country,
        )
        db.session.add(payment)
        db.session.commit()

    return {"success": True}
