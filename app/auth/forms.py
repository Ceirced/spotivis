from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Regexp,
    Length,
    ValidationError,
    InputRequired,
)
import sqlalchemy as sa

from app import db
from app.models import User


class LoginForm(FlaskForm):
    username = StringField(
        "Username or Email ",
        validators=[DataRequired()],
        render_kw={"autocomplete": "username", "autofocus": True},
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired()],
        render_kw={"autocomplete": "current-password"},
    )
    submit = SubmitField("Sign In")


class RegistrationForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(1, 64),
            Regexp(
                "^[A-Za-z][A-Za-z0-9_.]*$",
                0,
                "Usernames must have only letters, numbers, dots or " "underscores",
            ),
        ],
    )
    email = StringField(
        "Email",
        validators=[DataRequired(), Length(1, 64), Email()],
        render_kw={"autocomplete": "username", "autofocus": True},
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), InputRequired(), Length(min=8, max=64)],
        render_kw={"autocomplete": "new-password"},
    )
    password2 = PasswordField(
        "Repeat Password",
        validators=[DataRequired(), EqualTo("password"), Length(min=8, max=64)],
        render_kw={"autocomplete": "new-password"},
    )
    submit = SubmitField("Register")

    def validate_username(self, username):
        user = db.session.scalar(sa.select(User).where(User.username == username.data))
        if user is not None:
            raise ValidationError("Please use a different username.")

    def validate_email(self, email):
        user = db.session.scalar(sa.select(User).where(User.email == email.data))
        if user is not None:
            raise ValidationError("Please use a different email address.")
