from urllib.parse import urljoin

from flask import render_template, url_for, redirect, abort, request
from flask_login import login_required, current_user  # type: ignore
import stripe
from flask_wtf import FlaskForm  # type: ignore

from app.main import bp


@bp.before_request
@login_required
def before_request():
    pass


@bp.route("/flash-message", methods=["GET"])
def flash_messages():
    return render_template("partials/_flash-messages.html")


@bp.route("/")
def index():
    # redirect to first index
    return redirect(url_for("first.index"))


@bp.route("/invest", methods=["GET"])
def invest():
    # stripe product of a lifetime subscription to my saas app

    form = FlaskForm()

    return render_template("invest/invest.html", form=form)


@bp.route("/invest/<int:product_id>", methods=["POST"])
def buy_product(product_id):
    # stripe payment
    products = [
        {
            "name": "5 year Subscription",
            "price": 1500,
            "currency": "eur",
            "description": "A 5 year subscription to this awesome service",
        }
    ]
    if product_id == 1:
        product = products[0]
    else:
        # return 404
        abort(404)

    checkout_session = stripe.checkout.Session.create(
        line_items=[
            {
                "price_data": {
                    "product_data": {
                        "name": product["name"],
                    },
                    "unit_amount": product["price"],
                    "currency": "eur",
                },
                "quantity": 1,
            },
        ],
        payment_method_types=["card"],
        mode="payment",
        success_url=urljoin(request.host_url, url_for("main.order_success")),
        cancel_url=urljoin(request.host_url, url_for("main.order_cancel")),
        metadata={"user_id": current_user.id, "user_email": current_user.email},
    )
    return redirect(checkout_session.url)


@bp.route("/order_success")
def order_success():
    return render_template("invest/order_success.html")


@bp.route("/order_cancel")
def order_cancel():
    return render_template("invest/order_cancel.html")
