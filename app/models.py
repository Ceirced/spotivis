from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from flask_security.models import fsqla_v3 as fsqla
from sqlalchemy import DateTime, ForeignKey, String, func, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import db

fsqla.FsModels.set_db_info(db)


# fix, see here https://github.com/python/mypy/issues/8603
if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model
else:
    Model = db.Model


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Role(Model, fsqla.FsRoleMixin):
    pass


class User(Model, fsqla.FsUserMixin):
    uploaded_files: Mapped[list[UploadedFile]] = relationship(
        "UploadedFile",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return (
            f"<User(id='{self.id}', username='{self.username}', email='{self.email}')>"
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
    sender_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    receiver_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    status = db.Column(
        db.Enum("pending", "accepted", "declined", name="status_enum"),
        default="pending",
    )
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    db.UniqueConstraint("sender_id", "receiver_id")


class UploadedFile(TimestampMixin, Model):
    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(db.BigInteger, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        db.DateTime, nullable=False, default=db.func.current_timestamp()
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    user: Mapped[User] = relationship("User", back_populates="uploaded_files")

    # Date range from the parquet data
    data_start_date: Mapped[datetime | None] = mapped_column(db.DateTime, nullable=True)
    data_end_date: Mapped[datetime | None] = mapped_column(db.DateTime, nullable=True)

    preprocessing_jobs: Mapped[list[PreprocessingJob]] = relationship(
        "PreprocessingJob", back_populates="uploaded_file", cascade="all, delete-orphan"
    )

    @property
    def size_mb(self) -> float:
        return round(self.file_size / (1024 * 1024), 2)

    def __repr__(self):
        return f"<UploadedFile {self.id} - {self.name}>"


class PreprocessingJob(Model):
    __tablename__ = "preprocessing_jobs"

    uuid: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    task_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    uploaded_file_id: Mapped[int] = mapped_column(
        ForeignKey("uploaded_files.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_file: Mapped[UploadedFile] = relationship(
        "UploadedFile", back_populates="preprocessing_jobs"
    )

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    started_at: Mapped[datetime] = mapped_column(
        db.DateTime, nullable=False, default=db.func.current_timestamp()
    )
    completed_at: Mapped[datetime | None] = mapped_column(db.DateTime, nullable=True)

    # File paths for the generated graph data
    edges_file: Mapped[str | None] = mapped_column(String(500), nullable=True)
    nodes_file: Mapped[str | None] = mapped_column(String(500), nullable=True)

    final_nodes: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    final_edges: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    time_periods: Mapped[int | None] = mapped_column(db.Integer, nullable=True)

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(db.Text, nullable=True)

    enrichment_jobs: Mapped[list[PlaylistEnrichmentJob]] = relationship(
        back_populates="preprocessing_job", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<PreprocessingJob {self.uuid} - {self.status}>"


class PlaylistEnrichmentJob(Model):
    __tablename__ = "playlist_enrichment_jobs"

    uuid: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    task_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    preprocessing_job_id: Mapped[str] = mapped_column(
        ForeignKey("preprocessing_jobs.uuid"), nullable=False
    )
    preprocessing_job: Mapped[PreprocessingJob] = relationship(
        back_populates="enrichment_jobs"
    )

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    started_at: Mapped[datetime] = mapped_column(
        db.DateTime, nullable=False, default=db.func.current_timestamp()
    )
    completed_at: Mapped[datetime | None] = mapped_column(db.DateTime, nullable=True)

    # Output file path for the enriched data
    output_file: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Statistics
    total_playlists: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    found_count: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    not_found_count: Mapped[int | None] = mapped_column(db.Integer, nullable=True)

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(db.Text, nullable=True)

    def __repr__(self):
        return f"<PlaylistEnrichmentJob {self.uuid} - {self.status}>"


class CombinedPreprocessingJob(Model):
    __tablename__ = "combined_preprocessing_jobs"

    uuid: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # References to the two preprocessing jobs being combined
    first_job_id: Mapped[str] = mapped_column(
        ForeignKey("preprocessing_jobs.uuid", ondelete="CASCADE"), nullable=False
    )
    first_job: Mapped[PreprocessingJob] = relationship(foreign_keys=[first_job_id])

    second_job_id: Mapped[str] = mapped_column(
        ForeignKey("preprocessing_jobs.uuid", ondelete="CASCADE"), nullable=False
    )
    second_job: Mapped[PreprocessingJob] = relationship(foreign_keys=[second_job_id])

    # Task and status tracking
    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    started_at: Mapped[datetime] = mapped_column(
        db.DateTime, nullable=False, default=db.func.current_timestamp()
    )
    completed_at: Mapped[datetime | None] = mapped_column(db.DateTime, nullable=True)

    # Combined output files
    edges_file: Mapped[str | None] = mapped_column(String(500), nullable=True)
    nodes_file: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Statistics
    total_nodes: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    total_edges: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    nodes_from_first: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    nodes_from_second: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    new_nodes: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    # Date ranges from the combined data
    first_start_date: Mapped[datetime | None] = mapped_column(
        db.DateTime, nullable=True
    )
    first_end_date: Mapped[datetime | None] = mapped_column(db.DateTime, nullable=True)
    second_start_date: Mapped[datetime | None] = mapped_column(
        db.DateTime, nullable=True
    )
    second_end_date: Mapped[datetime | None] = mapped_column(db.DateTime, nullable=True)
    # Error tracking
    error_message: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    # User reference
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    user: Mapped[User] = relationship("User")

    def __repr__(self):
        return f"<CombinedPreprocessingJob {self.uuid} - {self.status}>"
