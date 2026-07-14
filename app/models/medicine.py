from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Medicine(Base):
    """A medicine product tracked by the pharmacy."""

    __tablename__ = "medicines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    medicine_name: Mapped[str] = mapped_column(String(200), nullable=False)
    generic_name: Mapped[str | None] = mapped_column(String(200))
    company: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(100))
    barcode: Mapped[str | None] = mapped_column(String(50), unique=True)
    rack_location: Mapped[str | None] = mapped_column(String(50))
    minimum_stock: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    batches: Mapped[list["Batch"]] = relationship(  # noqa: F821
        "Batch", back_populates="medicine", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Medicine(id={self.id}, name={self.medicine_name!r})>"
