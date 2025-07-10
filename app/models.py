from __future__ import annotations
from typing import TYPE_CHECKING

from sqlalchemy import select
import sqlalchemy.orm as so
from flask_security.models import fsqla_v3 as fsqla

from app import db

fsqla.FsModels.set_db_info(db)


# fix, see here https://github.com/python/mypy/issues/8603
if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model
else:
    Model = db.Model


class Role(Model, fsqla.FsRoleMixin):
    pass


class User(Model, fsqla.FsUserMixin):
    payments: so.WriteOnlyMapped[list[Payment]] = so.relationship(
        "Payment", back_populates="user"
    )

    def __repr__(self):
        return "<User(id='%s', username='%s', email='%s', confirmed='%s')>" % (
            self.id,
            self.username,
            self.email,
            self.confirmed,
        )

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


class FriendRequest(Model):
    request_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(
        db.Enum("pending", "accepted", "declined", name="status_enum"),
        default="pending",
    )
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    db.UniqueConstraint("sender_id", "receiver_id")


class Payment(Model):
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
