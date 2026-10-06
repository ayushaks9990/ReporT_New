from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.embeddings import EMBEDDING_DIMENSIONS


def _id() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    reports: Mapped[list["Report"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    datasets: Mapped[list["Dataset"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120))
    original_filename: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(20), default="sales")
    status: Mapped[str] = mapped_column(String(24), default="ready", index=True)
    row_count: Mapped[int]
    columns: Mapped[list] = mapped_column(JSON, default=list)
    column_types: Mapped[dict] = mapped_column(JSON, default=dict)
    mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_rows: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    owner: Mapped[User] = relationship(back_populates="datasets")
    embedding_index: Mapped["EmbeddingIndex | None"] = relationship(
        cascade="all, delete-orphan", passive_deletes=True,
    )

    @property
    def embedding_status(self) -> str:
        if self.status != "ready":
            return "needs_mapping"
        return "ready" if self.embedding_index is not None else "pending"

    __table_args__ = (
        Index("idx_datasets_owner_created", "user_id", "created_at"),
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(180))
    report_type: Mapped[str] = mapped_column(String(40), index=True)
    dataset_id: Mapped[str | None] = mapped_column(String(36), index=True)
    content: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(80))
    report_filters: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    chart_data: Mapped[dict] = mapped_column(JSON, default=dict)
    insights: Mapped[list] = mapped_column(JSON, default=list)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner: Mapped[User] = relationship(back_populates="reports")
    evidence: Mapped["ReportEvidence | None"] = relationship(
        cascade="all, delete-orphan", passive_deletes=True,
    )

    @property
    def retrieval(self) -> dict:
        return self.evidence.payload if self.evidence else {}

    __table_args__ = (
        Index("idx_reports_owner_created", "user_id", "created_at"),
        Index("idx_reports_owner_favorite", "user_id", "favorite"),
    )


class EmbeddingIndex(Base):
    __tablename__ = "embedding_indexes"

    scope: Mapped[str] = mapped_column(String(80), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True,
    )
    dataset_id: Mapped[str | None] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), unique=True,
    )
    fingerprint: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(120))
    record_count: Mapped[int]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )


class RecordEmbedding(Base):
    __tablename__ = "record_embeddings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    index_scope: Mapped[str] = mapped_column(
        ForeignKey("embedding_indexes.scope", ondelete="CASCADE"), index=True,
    )
    record_key: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(20))
    document: Mapped[str] = mapped_column(Text)
    source_metadata: Mapped[dict] = mapped_column(JSON)
    region: Mapped[str] = mapped_column(Text, default="")
    quarter: Mapped[str] = mapped_column(Text, default="")
    product: Mapped[str] = mapped_column(Text, default="")
    channel: Mapped[str] = mapped_column(Text, default="")
    campaign_name_folded: Mapped[str] = mapped_column(Text, default="")
    # Render uses native pgvector. SQLite is a local development/test alternative.
    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS).with_variant(JSON(), "sqlite"),
    )

    __table_args__ = (
        UniqueConstraint("index_scope", "record_key", name="uq_embedding_source_record"),
    )


class ReportEvidence(Base):
    __tablename__ = "report_evidence"

    report_id: Mapped[str] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), primary_key=True,
    )
    payload: Mapped[dict] = mapped_column(JSON)
