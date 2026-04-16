from datetime import datetime, timezone, timedelta

from sqlalchemy import String, DateTime, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

ISTANBUL_TZ = timezone(timedelta(hours=3))


class QueueItem(Base):
    __tablename__ = "queue_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="waiting")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(ISTANBUL_TZ)
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="item",
        order_by="Comment.created_at",
        cascade="all, delete-orphan",
    )


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("queue_items.id"), nullable=False
    )
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(ISTANBUL_TZ)
    )
    item: Mapped["QueueItem"] = relationship("QueueItem", back_populates="comments")
