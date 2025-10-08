import datetime
from typing import cast

from flask import flash, make_response, redirect, render_template, request, url_for
from flask_security import (
    check_and_update_authn_fresh,
    current_user as flask_current_user,
)
from flask_security.utils import logout_user
from flask_wtf import FlaskForm
from sqlalchemy import select

from app import db
from app.main.users import bp
from app.models import FriendRequest, FriendRequestStatus, User

current_user = cast(User, flask_current_user)


@bp.route("/", methods=["GET"])
def index():
    # get incoming friend requests
    incoming_requests = db.session.execute(
        select(FriendRequest, User)
        .join(User, User.id == FriendRequest.sender_id)
        .where(
            FriendRequest.receiver_id == current_user.id,
            FriendRequest.status == FriendRequestStatus.PENDING,
        )
    ).all()

    title = "Users"
    return render_template(
        "users/index.html",
        title=title,
        incoming_requests=incoming_requests,
        friends=current_user.friends,
    )


@bp.route("/search_users", methods=["POST"])
def search_users():
    # get the search term from the form with the name search
    # and return table rows with results
    search_term = request.form.get("search", type=str, default="").strip()

    if search_term == "":
        return render_template(
            "./partials/_search_table_rows.html",
            search_results=[],
        )

    users = db.session.scalars(
        select(User)
        .where(User.username.ilike(f"%{search_term}%"), User.id != current_user.id)
        .limit(5)
    ).all()

    search_results = [
        {
            "url": url_for("users.profile", username=user.username),
            "handle": user.username,
        }
        for user in users
    ]

    response = render_template(
        "./partials/_search_table_rows.html",
        search_results=search_results,
        color="gray",
        add_button=True,
    )
    return response


@bp.route("/<username>", methods=["GET"])
def profile(username):
    user = db.first_or_404(select(User).where(User.username == username))
    is_friend = current_user.is_friends_with(user.id)

    # Check if there's a pending friend request
    pending_request = False
    if current_user.is_authenticated and current_user.id != user.id:
        friend_request = db.session.scalar(
            select(FriendRequest).where(
                FriendRequest.sender_id == current_user.id,
                FriendRequest.receiver_id == user.id,
            )
        )
        if friend_request and friend_request.status == FriendRequestStatus.PENDING:
            pending_request = True

    return render_template(
        "users/profile.html",
        user=user,
        is_friend=is_friend,
        title=user.username,
        pending_request=pending_request,
    )


@bp.route("/send_friend_request", methods=["POST"])
def send_friend_request():
    # get the post parameters that are sent with the request they are not json
    receiver_id = request.form.get("receiver_id", type=int)
    sender_id = current_user.id
    receiver = db.session.get(User, receiver_id)
    if not receiver:
        return {"error": "User not found"}, 404
    if current_user.is_friends_with(receiver_id):
        return {"error": "Already friends"}, 400
    if sender_id == receiver_id:
        return {"error": "Cannot send friend request to self"}, 400

    existing_request = db.session.scalar(
        select(FriendRequest).where(
            FriendRequest.sender_id == sender_id,
            FriendRequest.receiver_id == receiver_id,
        )
    )
    if existing_request and existing_request.status != FriendRequestStatus.ACCEPTED:
        existing_request.status = FriendRequestStatus.PENDING
        existing_request.created_at = db.func.current_timestamp()
        db.session.commit()
        return {"message": "Friend request sent"}, 200
    elif existing_request and existing_request.status == FriendRequestStatus.ACCEPTED:
        return {"error": "Already friends"}, 400
    else:
        friend_request = FriendRequest(sender_id=sender_id, receiver_id=receiver_id)
        db.session.add(friend_request)
        db.session.commit()
        return {"message": "Friend request sent"}, 200


@bp.route("/accept_friend_request", methods=["POST"])
def accept_friend_request():
    request_id = request.form.get("request_id", type=int)
    friend_request = db.session.get(FriendRequest, request_id)
    if not friend_request:
        return {"error": "Friend request not found"}, 404
    if friend_request.receiver_id != current_user.id:
        return {"error": "Unauthorized"}, 403
    friend_request.status = FriendRequestStatus.ACCEPTED
    db.session.commit()

    # emtpy response
    response = make_response("", 204)
    response.headers["HX-Trigger"] = "friends_update"

    return response


@bp.route("/decline_friend_request", methods=["POST"])
def decline_friend_request():
    request_id = request.form.get("request_id", type=int)
    friend_request = db.session.get(FriendRequest, request_id)
    if not friend_request:
        return {"error": "Friend request not found"}, 404
    if friend_request.receiver_id != current_user.id:
        return {"error": "Unauthorized"}, 403
    friend_request.status = FriendRequestStatus.DECLINED
    db.session.commit()
    return {"message": "Friend request declined"}, 200


@bp.route("/friends", methods=["GET"])
def friends():
    return render_template(
        "users/partials/_friends.html",
        friends=current_user.friends,
    )


@bp.route("/friend-requests", methods=["GET"])
def friend_requests():
    incoming_requests = db.session.execute(
        select(FriendRequest, User)
        .join(User, User.id == FriendRequest.sender_id)
        .where(
            FriendRequest.receiver_id == current_user.id,
            FriendRequest.status == FriendRequestStatus.PENDING,
        )
    ).all()
    return render_template(
        "users/partials/_friend-requests.html", incoming_requests=incoming_requests
    )


@bp.route("/settings", methods=["GET"])
def settings():
    title = "Settings"
    delete_form = FlaskForm()
    return render_template("users/settings.html", title=title, delete_form=delete_form)


@bp.route("/delete-account", methods=["POST"])
def delete_account():
    """Delete the current user's account. Requires fresh login."""

    # Validate CSRF token
    form = FlaskForm()
    if not form.validate_on_submit():
        flash("Invalid request. Please try again.", "error")
        return redirect(url_for("users.settings"))

    # Check if the session is fresh (user recently logged in)
    if not check_and_update_authn_fresh(
        datetime.timedelta(seconds=10), grace=datetime.timedelta(seconds=10)
    ):
        flash("Please re-authenticate to delete your account.", "error")
        return redirect(url_for("security.verify", next=url_for("users.settings")))

    # Get the user object and delete it (this triggers database CASCADE)
    user = db.session.get(User, current_user.id)
    db.session.delete(user)
    db.session.commit()

    # Log out the user
    logout_user()

    flash("Your account has been successfully deleted.", "success")
    return redirect(url_for("security.login"))
