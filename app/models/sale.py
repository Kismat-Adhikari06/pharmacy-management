from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Sale(Base):
    """A completed sale (bill) to a customer."""

    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bill_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    sale_date: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    discount: Mapped[float] = mapped_column(Float, default=0.0)
    vat_amount: Mapped[float] = mapped_column(Float, default=0.0)
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)

    items: Mapped[list["SaleItem"]] = relationship(  # noqa: F821
        "SaleItem", back_populates="sale", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Sale(id={self.id}, bill={self.bill_number!r})>"
