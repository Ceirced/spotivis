from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy.orm as so
from flask_security.models import fsqla_v3 as fsqla
from sqlalchemy import DECIMAL, ForeignKey, String, select

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
    payments: so.Mapped[list[Payment]] = so.relationship(
        "Payment", back_populates="user"
    )

    def __repr__(self):
        return "<User(id='%s', username='%s', email='%s')>" % (
            self.id,
            self.username,
            self.email,
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

    id: so.Mapped[int] = so.mapped_column(primary_key=True, autoincrement=True)
    user_email: so.Mapped[str] = so.mapped_column(String(100), nullable=False)
    amount: so.Mapped[Decimal] = so.mapped_column(DECIMAL(10, 2), nullable=False)
    currency: so.Mapped[str] = so.mapped_column(String(3), nullable=False)
    created: so.Mapped[datetime] = so.mapped_column(
        db.DateTime, nullable=False, default=db.func.current_timestamp()
    )
    user_id: so.Mapped[int | None] = so.mapped_column(
        ForeignKey("user.id"), nullable=True
    )
    user: so.Mapped[User | None] = so.relationship("User", back_populates="payments")
    stripe_payment_id: so.Mapped[str] = so.mapped_column(
        String(150), nullable=False, unique=True
    )
    status: so.Mapped[str] = so.mapped_column(String(50), nullable=False)
    stripe_customer_email: so.Mapped[str | None] = so.mapped_column(String(100))
    stripe_customer_name: so.Mapped[str | None] = so.mapped_column(String(100))
    stripe_customer_address_country: so.Mapped[str | None] = so.mapped_column(
        String(20)
    )

    __table_args__ = (db.UniqueConstraint("stripe_payment_id"),)

    def __repr__(self):
        return f"<Payment {self.id} - {self.amount} {self.currency}>"


class UploadedFile(Model):
    __tablename__ = "uploaded_files"

    id: so.Mapped[int] = so.mapped_column(primary_key=True, autoincrement=True)
    filename: so.Mapped[str] = so.mapped_column(
        String(255), nullable=False, unique=True
    )
    original_filename: so.Mapped[str] = so.mapped_column(String(255), nullable=False)
    file_size: so.Mapped[int] = so.mapped_column(db.BigInteger, nullable=False)
    uploaded_at: so.Mapped[datetime] = so.mapped_column(
        db.DateTime, nullable=False, default=db.func.current_timestamp()
    )
    user_id: so.Mapped[int | None] = so.mapped_column(
        ForeignKey("user.id"), nullable=True
    )
    user: so.Mapped[User | None] = so.relationship("User", backref="uploaded_files")

    preprocessing_jobs: so.Mapped[list[PreprocessingJob]] = so.relationship(
        "PreprocessingJob", back_populates="uploaded_file", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<UploadedFile {self.id} - {self.original_filename}>"


class PreprocessingJob(Model):
    __tablename__ = "preprocessing_jobs"

    uuid: so.Mapped[str] = so.mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    task_id: so.Mapped[str] = so.mapped_column(String(255), nullable=False, unique=True)
    uploaded_file_id: so.Mapped[int] = so.mapped_column(
        ForeignKey("uploaded_files.id"), nullable=False
    )
    uploaded_file: so.Mapped[UploadedFile] = so.relationship(
        "UploadedFile", back_populates="preprocessing_jobs"
    )

    status: so.Mapped[str] = so.mapped_column(
        String(50), nullable=False, default="pending"
    )
    started_at: so.Mapped[datetime] = so.mapped_column(
        db.DateTime, nullable=False, default=db.func.current_timestamp()
    )
    completed_at: so.Mapped[datetime | None] = so.mapped_column(
        db.DateTime, nullable=True
    )

    # File paths for the generated graph data
    edges_file: so.Mapped[str | None] = so.mapped_column(String(500), nullable=True)
    nodes_file: so.Mapped[str | None] = so.mapped_column(String(500), nullable=True)

    final_nodes: so.Mapped[int | None] = so.mapped_column(db.Integer, nullable=True)
    final_edges: so.Mapped[int | None] = so.mapped_column(db.Integer, nullable=True)
    time_periods: so.Mapped[int | None] = so.mapped_column(db.Integer, nullable=True)

    # Error tracking
    error_message: so.Mapped[str | None] = so.mapped_column(db.Text, nullable=True)

    def __repr__(self):
        return f"<PreprocessingJob {self.uuid} - {self.status}>"
