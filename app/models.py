from typing import Optional

from sqlalchemy import (
    String,
    select,
)
import sqlalchemy.orm as so
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

from app import db
from app import login


class User(UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(String(64), index=True, unique=True)
    email: so.Mapped[str] = so.mapped_column(String(120), index=True, unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(String(256))

    payments: so.WriteOnlyMapped[list["Payment"]] = so.relationship(
        "Payment", back_populates="user"
    )
    confirmed = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return "<User(id='%s', username='%s', email='%s', confirmed='%s')>" % (
            self.id,
            self.username,
            self.email,
            self.confirmed,
        )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_friends_with(self, other_user_id):
        friendship = FriendRequest.query.filter(
            (
                (FriendRequest.sender_id == self.id)
                & (FriendRequest.receiver_id == other_user_id)
                & (FriendRequest.status == "accepted")
            )
            | (
                (FriendRequest.sender_id == other_user_id)
                & (FriendRequest.receiver_id == self.id)
                & (FriendRequest.status == "accepted")
            )
        ).first()
        return friendship is not None

    @staticmethod
    def new_user(username, email, password):
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user

    @staticmethod
    def get_user_by_name(username):
        return db.session.scalar(select(User).where(User.username == username))

    @property
    def friends(self):
        sent_accepted = FriendRequest.query.filter_by(
            sender_id=self.id, status="accepted"
        ).all()
        received_accepted = FriendRequest.query.filter_by(
            receiver_id=self.id, status="accepted"
        ).all()

        friends_ids = set(
            [req.receiver_id for req in sent_accepted]
            + [req.sender_id for req in received_accepted]
        )

        return User.query.filter(User.id.in_(friends_ids))


class FriendRequest(db.Model):
    request_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(
        db.Enum("pending", "accepted", "declined", name="status_enum"),
        default="pending",
    )
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    db.UniqueConstraint("sender_id", "receiver_id")


@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_email = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.DECIMAL(10, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    created = db.Column(
        db.DateTime, nullable=False, default=db.func.current_timestamp()
    )
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user = db.relationship("User", back_populates="payments")
    stripe_payment_id = db.Column(db.String(150), nullable=False, unique=True)
    status = db.Column(db.String(50), nullable=False)
    stripe_customer_email = db.Column(db.String(100))
    stripe_customer_name = db.Column(db.String(100))
    stripe_customer_address_country = db.Column(db.String(20))
    __table_args__ = (db.UniqueConstraint("stripe_payment_id"),)

    def __repr__(self):
        return f"<Payment {self.id} - {self.amount} {self.currency}>"
