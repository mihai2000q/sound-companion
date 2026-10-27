from datetime import datetime

import uuid
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DocumentRecord(Base):
    """One Corpus document. The table is created by migration 0002, this maps it."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("source_type IN ('encyclopedia', 'textbook')", name="documents_source_type_check"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(Text)
    topics: Mapped[str] = mapped_column(Text, server_default="")  # pipe-delimited, '|a|b|'
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    url: Mapped[str] = mapped_column(Text, unique=True)
    license: Mapped[str] = mapped_column(Text)
    revision_id: Mapped[str] = mapped_column(Text)  # Wikipedia revision id, or git commit
    sections: Mapped[list[dict]] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    char_count: Mapped[int] = mapped_column(Integer)


class UsageLog(Base):
    """One row per model call (answer, rewrite, embed), with OpenRouter's `usage.cost` in credits."""

    __tablename__ = "usage_log"
    __table_args__ = (
        CheckConstraint("purpose IN ('answer','rewrite','embed','eval')", name="usage_log_purpose_check"),
        Index("usage_log_thread_idx", "thread_id"),
        Index("usage_log_request_idx", "request_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    thread_id: Mapped[str] = mapped_column(Text)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    purpose: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    completion_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    cost_credits: Mapped[Decimal] = mapped_column(Numeric(12, 8), server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
