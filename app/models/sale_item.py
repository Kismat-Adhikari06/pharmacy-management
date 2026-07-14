from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SaleItem(Base):
    """A single line-item within a sale."""

    __tablename__ = "sale_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sales.id"), nullable=False
    )
    batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("batches.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    selling_price: Mapped[float] = mapped_column(Float, nullable=False)
    discount: Mapped[float] = mapped_column(Float, default=0.0)

    sale: Mapped["Sale"] = relationship(  # noqa: F821
        "Sale", back_populates="items"
    )
    batch: Mapped["Batch"] = relationship(  # noqa: F821
        "Batch", back_populates="sale_items"
    )

    def __repr__(self) -> str:
        return f"<SaleItem(id={self.id}, qty={self.quantity})>"
