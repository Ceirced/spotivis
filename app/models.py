from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from flask_security.models import fsqla_v3 as fsqla
from sqlalchemy import DECIMAL, ForeignKey, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    payments: Mapped[list[Payment]] = relationship("Payment", back_populates="user")

    def __repr__(self):
        return (
            f"<User(id='{self.id}', username='{self.username}', email='{self.email}')>"
        )

    def is_friends_with(self, other_user_id: int) -> bool:
        friendship = db.session.scalar(
            select(FriendRequest).where(
                (
                    (
                        (FriendRequest.sender_id == self.id)
                        & (FriendRequest.receiver_id == other_user_id)
                    )
                    | (
                        (FriendRequest.sender_id == other_user_id)
                        & (FriendRequest.receiver_id == self.id)
                    )
                )
                & (FriendRequest.status == "accepted")
            )
        )
        return friendship is not None

    @staticmethod
    def get_user_by_name(username: str) -> User | None:
        return db.session.scalar(select(User).where(User.username == username))

    @property
    def friends(self):
        sent_accepted = db.session.scalars(
            select(FriendRequest).where(
                (FriendRequest.sender_id == self.id)
                & (FriendRequest.status == "accepted")
            )
        ).all()

        received_accepted = db.session.scalars(
            select(FriendRequest).where(
                (FriendRequest.receiver_id == self.id)
                & (FriendRequest.status == "accepted")
            )
        ).all()

        friends_ids = set(
            [req.receiver_id for req in sent_accepted]
            + [req.sender_id for req in received_accepted]
        )

        return db.session.scalars(select(User).where(User.id.in_(friends_ids))).all()


class FriendRequestStatus(Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"


class FriendRequest(Model):
    request_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    receiver_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    status: Mapped[FriendRequestStatus] = mapped_column(
        default=FriendRequestStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(default=db.func.current_timestamp())
    UniqueConstraint("sender_id", "receiver_id")


class Payment(Model):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_email: Mapped[str] = mapped_column(String(100))
    amount: Mapped[Decimal] = mapped_column(DECIMAL(10, 2))
    currency: Mapped[str] = mapped_column(String(3))
    created: Mapped[datetime] = mapped_column(
        db.DateTime, default=db.func.current_timestamp()
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE")
    )
    user: Mapped[User | None] = relationship("User", back_populates="payments")
    stripe_payment_id: Mapped[str] = mapped_column(String(150), unique=True)
    status: Mapped[str] = mapped_column(String(50))
    stripe_customer_email: Mapped[str | None] = mapped_column(String(100))
    stripe_customer_name: Mapped[str | None] = mapped_column(String(100))
    stripe_customer_address_country: Mapped[str | None] = mapped_column(String(20))

    def __repr__(self):
        return f"<Payment {self.id} - {self.amount} {self.currency}>"
