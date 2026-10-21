from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DocumentRecord(Base):
    """One Corpus document. The table is created by migration 0002, this maps it."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("source_type IN ('encyclopedia', 'textbook')", name="documents_source_type_check"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
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
