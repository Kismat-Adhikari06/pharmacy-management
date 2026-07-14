from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Batch(Base):
    """A specific batch of a medicine with its own expiry and pricing."""

    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    medicine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("medicines.id"), nullable=False
    )
    batch_number: Mapped[str] = mapped_column(String(100), nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    purchase_price: Mapped[float] = mapped_column(Float, nullable=False)
    selling_price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=0)

    medicine: Mapped["Medicine"] = relationship(  # noqa: F821
        "Medicine", back_populates="batches"
    )
    purchase_items: Mapped[list["PurchaseItem"]] = relationship(  # noqa: F821
        "PurchaseItem", back_populates="batch"
    )
    sale_items: Mapped[list["SaleItem"]] = relationship(  # noqa: F821
        "SaleItem", back_populates="batch"
    )

    def __repr__(self) -> str:
        return f"<Batch(id={self.id}, batch={self.batch_number!r})>"
