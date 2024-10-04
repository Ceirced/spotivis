from urllib.parse import urlsplit

from flask import render_template, redirect, url_for, flash, request
from flask_login import current_user, login_user, logout_user
import sqlalchemy as sa
from flask import current_app as app

from app import db
from app.auth import bp
from app.auth.forms import LoginForm
from app.models import User
from app.auth.forms import RegistrationForm


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(
                (User.username == form.username.data)
                | (User.email == form.username.data)
            )
        )
        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password")
            return redirect(url_for("auth.login"))
        login_user(user, remember=True)
        next_page = request.args.get("next")
        if not next_page or urlsplit(next_page).netloc != "":
            next_page = url_for("main.index")
        return redirect(next_page)
    return render_template("auth/login.html", title="Sign In", form=form)


@bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("main.index"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data.lower())
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        app.logger.info(f"User {user} registered")
        user.confirmed = True
        db.session.commit()
        login_user(user)
        return redirect(url_for("main.index"))

    return render_template("auth/register.html", title="Register", form=form)
