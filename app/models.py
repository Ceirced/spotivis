from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from flask_security.models import fsqla_v3 as fsqla
from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
    select,
)
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
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
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
                & (FriendRequest.status == FriendRequestStatus.ACCEPTED)
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
                & (FriendRequest.status == FriendRequestStatus.ACCEPTED)
            )
        ).all()

        received_accepted = db.session.scalars(
            select(FriendRequest).where(
                (FriendRequest.receiver_id == self.id)
                & (FriendRequest.status == FriendRequestStatus.ACCEPTED)
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


class FriendRequest(TimestampMixin, Model):
    request_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    receiver_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    status: Mapped[FriendRequestStatus] = mapped_column(
        default=FriendRequestStatus.PENDING
    )
    UniqueConstraint("sender_id", "receiver_id")


class UploadedFile(TimestampMixin, Model):
    __tablename__ = "uploaded_files"

    uuid: Mapped[str] = mapped_column(
        String(36),
        default=uuid.uuid4,
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(String(255))
    file_size: Mapped[int] = mapped_column(db.BigInteger)

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    user: Mapped[User] = relationship("User", back_populates="uploaded_files")

    # Date range from the parquet data
    data_start_date: Mapped[datetime | None]
    data_end_date: Mapped[datetime | None]

    preprocessing_jobs: Mapped[list[PreprocessingJob]] = relationship(
        "PreprocessingJob", back_populates="uploaded_file", cascade="all, delete-orphan"
    )

    @property
    def size_mb(self) -> float:
        return round(self.file_size / (1024 * 1024), 2)

    def __repr__(self):
        return f"<UploadedFile {self.uuid} - {self.name}>"

    @property
    def preprocessed(self) -> bool:
        return any(job.status == "completed" for job in self.preprocessing_jobs)

    @property
    def enriched(self) -> bool:
        return any(
            job.status == "completed"
            for prep_job in self.preprocessing_jobs
            for job in prep_job.enrichment_jobs
        )


class PreprocessingJob(Model):
    __tablename__ = "preprocessing_jobs"

    uuid: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    task_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    file_uuid: Mapped[str] = mapped_column(
        ForeignKey("uploaded_files.uuid", ondelete="CASCADE")
    )
    uploaded_file: Mapped[UploadedFile] = relationship(
        "UploadedFile", back_populates="preprocessing_jobs"
    )

    status: Mapped[str] = mapped_column(String(50), default="pending")
    started_at: Mapped[datetime] = mapped_column(
        db.DateTime, default=db.func.current_timestamp()
    )
    completed_at: Mapped[datetime | None]

    # File paths for the generated graph data
    edges_file: Mapped[str | None] = mapped_column(String(500))
    nodes_file: Mapped[str | None] = mapped_column(String(500))

    final_nodes: Mapped[int | None]
    final_edges: Mapped[int | None]
    time_periods: Mapped[int | None]

    # Publishing
    published: Mapped[bool | None] = mapped_column(default=False)
    published_at: Mapped[datetime | None]

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(db.Text)

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
    task_id: Mapped[str] = mapped_column(String(255), unique=True)
    preprocessing_job_id: Mapped[str] = mapped_column(
        ForeignKey("preprocessing_jobs.uuid")
    )
    preprocessing_job: Mapped[PreprocessingJob] = relationship(
        back_populates="enrichment_jobs"
    )

    status: Mapped[str] = mapped_column(String(50), default="pending")
    started_at: Mapped[datetime] = mapped_column(
        db.DateTime, default=db.func.current_timestamp()
    )
    completed_at: Mapped[datetime | None]

    # Output file path for the enriched data
    output_file: Mapped[str | None] = mapped_column(String(500))

    # Statistics
    total_playlists: Mapped[int | None]
    found_count: Mapped[int | None]
    not_found_count: Mapped[int | None]

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(db.Text)

    def __repr__(self):
        return f"<PlaylistEnrichmentJob {self.uuid} - {self.status}>"


class CombinedPreprocessingJob(Model):
    __tablename__ = "combined_preprocessing_jobs"

    uuid: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # References to the two preprocessing jobs being combined
    first_job_id: Mapped[str] = mapped_column(
        ForeignKey("preprocessing_jobs.uuid", ondelete="CASCADE")
    )
    first_job: Mapped[PreprocessingJob] = relationship(foreign_keys=[first_job_id])

    second_job_id: Mapped[str] = mapped_column(
        ForeignKey("preprocessing_jobs.uuid", ondelete="CASCADE")
    )
    second_job: Mapped[PreprocessingJob] = relationship(foreign_keys=[second_job_id])

    # Task and status tracking
    task_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    started_at: Mapped[datetime] = mapped_column(
        db.DateTime, default=db.func.current_timestamp()
    )
    completed_at: Mapped[datetime | None]

    # Combined output files
    edges_file: Mapped[str | None] = mapped_column(String(500))
    nodes_file: Mapped[str | None] = mapped_column(String(500))

    # Statistics
    total_nodes: Mapped[int | None]
    total_edges: Mapped[int | None]
    nodes_from_first: Mapped[int | None]
    nodes_from_second: Mapped[int | None]
    new_nodes: Mapped[int | None]
    # Date ranges from the combined data
    first_start_date: Mapped[datetime | None]
    first_end_date: Mapped[datetime | None]
    second_start_date: Mapped[datetime | None]
    second_end_date: Mapped[datetime | None]

    # Publishing
    published: Mapped[bool | None] = mapped_column(default=False)
    published_at: Mapped[datetime | None]
    # Error tracking
    error_message: Mapped[str | None] = mapped_column(db.Text)
    # User reference
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    user: Mapped[User] = relationship("User")

    def __repr__(self):
        return f"<CombinedPreprocessingJob {self.uuid} - {self.status}>"
