"""SQLAlchemy models for the logistics dataset.

One table, mapped one-to-one onto the CSV columns. Slice 0 deliberately adds no derived
columns and no business meaning: "delayed", on-time rate and every other definition
belong to the calculator layer from Slice 1 onward (architecture Decision 1). Storing a
derived column here would create a second home for a formula.

``delivery_date`` is nullable because 30 of the 400 rows have not been delivered yet;
modelling it as required would force the seeder to invent a value.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for every table in the application."""


class Order(Base):
    """A single logistics order, exactly as it appears in ``mock_logistics_data.csv``."""

    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str | None] = mapped_column(String(32))
    order_date: Mapped[datetime.date | None] = mapped_column(Date)
    delivery_date: Mapped[datetime.date | None] = mapped_column(Date)
    carrier: Mapped[str | None] = mapped_column(String(64))
    origin_city: Mapped[str | None] = mapped_column(String(128))
    destination_city: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str | None] = mapped_column(String(32), index=True)
    sku: Mapped[str | None] = mapped_column(String(64), index=True)
    product_category: Mapped[str | None] = mapped_column(String(64), index=True)
    quantity: Mapped[int | None] = mapped_column(Integer)
    unit_price_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    order_value_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    is_promo: Mapped[bool | None] = mapped_column(Boolean)
    promo_discount_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    region: Mapped[str | None] = mapped_column(String(32), index=True)
    warehouse: Mapped[str | None] = mapped_column(String(32), index=True)
