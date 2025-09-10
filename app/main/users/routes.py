from flask import make_response, render_template, request, url_for
from flask_security import current_user
from sqlalchemy import select

from app import db, htmx
from app.main.users import bp
from app.models import FriendRequest, User


@bp.route("/", methods=["GET"])
def index():
    # get incoming friend requests
    incoming_requests = db.session.execute(
        select(FriendRequest, User)
        .join(User, User.id == FriendRequest.sender_id)
        .filter(
            FriendRequest.receiver_id == current_user.id,
            FriendRequest.status == "pending",
        )
    ).all()

    title = "Users"
    if htmx.boosted:
        return render_template(
            "users/partials/_content.html",
            title=title,
            incoming_requests=incoming_requests,
            friends=current_user.friends,
        )
    return render_template(
        "users/index.html",
        title=title,
        incoming_requests=incoming_requests,
        friends=current_user.friends,
    )


@bp.route("/search_users", methods=["POST"])
def search_users():
    # get the search term from the form with the name search and return table rows with results
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
        friend_request = FriendRequest.query.filter_by(
            sender_id=current_user.id, receiver_id=user.id
        ).first()
        if friend_request and friend_request.status == "pending":
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
    data = request.form.to_dict()
    receiver_id = int(data.get("receiver_id"))

    sender_id = current_user.id
    receiver = User.query.get(receiver_id)
    if receiver is None:
        return {"error": "User not found"}, 404
    if current_user.is_friends_with(receiver_id):
        return {"error": "Already friends"}, 400
    if sender_id == receiver_id:
        return {"error": "Cannot send friend request to self"}, 400

    existing_request = FriendRequest.query.filter_by(
        sender_id=sender_id, receiver_id=receiver_id
    ).first()
    if existing_request and existing_request.status != "accepted":
        existing_request.status = "pending"
        existing_request.created_at = db.func.current_timestamp()
        db.session.commit()
        return {"message": "Friend request sent"}, 200
    elif existing_request and existing_request.status == "accepted":
        return {"error": "Already friends"}, 400
    else:
        friend_request = FriendRequest(sender_id=sender_id, receiver_id=receiver_id)
        db.session.add(friend_request)
        db.session.commit()
        return {"message": "Friend request sent"}, 200


@bp.route("/accept_friend_request", methods=["POST"])
def accept_friend_request():
    data = request.form.to_dict()
    request_id = int(data.get("request_id"))
    friend_request = FriendRequest.query.get(request_id)
    if friend_request is None:
        return {"error": "Friend request not found"}, 404
    if friend_request.receiver_id != current_user.id:
        return {"error": "Unauthorized"}, 403
    friend_request.status = "accepted"
    db.session.commit()

    # emtpy response
    response = make_response("", 204)
    response.headers["HX-Trigger"] = "friends_update"

    return response


@bp.route("/decline_friend_request", methods=["POST"])
def decline_friend_request():
    data = request.form.to_dict()
    request_id = int(data.get("request_id"))
    friend_request = FriendRequest.query.get(request_id)
    if friend_request is None:
        return {"error": "Friend request not found"}, 404
    if friend_request.receiver_id != current_user.id:
        return {"error": "Unauthorized"}, 403
    friend_request.status = "declined"
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
    incoming_requests = (
        db.session.query(FriendRequest, User)
        .join(User, User.id == FriendRequest.sender_id)
        .filter(
            FriendRequest.receiver_id == current_user.id,
            FriendRequest.status == "pending",
        )
        .all()
    )
    return render_template(
        "users/partials/_friend-requests.html", incoming_requests=incoming_requests
    )


@bp.route("/settings", methods=["GET"])
def settings():
    title = "Settings"
    if htmx.boosted:
        return render_template("users/partials/_settings_content.html", title=title)
    return render_template("users/settings.html", title=title)
