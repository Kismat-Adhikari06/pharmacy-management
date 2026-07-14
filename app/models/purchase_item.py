from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PurchaseItem(Base):
    """A single line-item within a purchase order."""

    __tablename__ = "purchase_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purchase_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("purchases.id"), nullable=False
    )
    batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("batches.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase_price: Mapped[float] = mapped_column(Float, nullable=False)

    purchase: Mapped["Purchase"] = relationship(  # noqa: F821
        "Purchase", back_populates="items"
    )
    batch: Mapped["Batch"] = relationship(  # noqa: F821
        "Batch", back_populates="purchase_items"
    )

    def __repr__(self) -> str:
        return f"<PurchaseItem(id={self.id}, qty={self.quantity})>"
