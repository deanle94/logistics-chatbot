"""One-shot, idempotent seeder for the logistics dataset.

Run as a container that exits 0 (``python -m logistics_analytics.data.seed``). It is the
only component that connects as the owning role; the API never holds credentials that
can write.

Idempotency is "replace", not "append": every run deletes the table contents and reloads
the CSV, so running the seeder twice leaves exactly the same 400 rows. An
insert-if-missing strategy would leave stale rows behind whenever the source file
changed, which is a worse failure because it looks like success.
"""

from __future__ import annotations

import csv
import datetime
import logging
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, delete, insert, text
from sqlalchemy.orm import Session

from logistics_analytics.config import SeedSettings
from logistics_analytics.data.engine import create_database_engine
from logistics_analytics.data.models import Base, Order

logger = logging.getLogger(__name__)

DATE_COLUMNS = ("order_date", "delivery_date")
INTEGER_COLUMNS = ("quantity",)
DECIMAL_COLUMNS = ("unit_price_usd", "order_value_usd", "promo_discount_pct")
BOOLEAN_COLUMNS = ("is_promo",)

#: CSV columns that map onto the model. Anything else in the file is ignored rather
#: than silently dropped into a mismatched column.
MAPPED_COLUMNS = tuple(column.name for column in Order.__table__.columns)


def _parse_date(value: str) -> datetime.date | None:
    """Return an ISO date, or ``None`` for the 30 rows with no delivery yet."""
    if not value:
        return None
    return datetime.date.fromisoformat(value)


def _parse_decimal(value: str) -> Decimal | None:
    """Return a Decimal, or ``None`` when the cell is empty.

    Decimal rather than float because these are money columns and Slice 1 sums them.
    """
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        logger.error("could not parse decimal value: %r", value)
        raise


def _parse_row(raw: dict[str, str]) -> dict[str, Any]:
    """Convert one CSV record into model-shaped values."""
    row: dict[str, Any] = {}
    for column in MAPPED_COLUMNS:
        value = (raw.get(column) or "").strip()
        if column in DATE_COLUMNS:
            row[column] = _parse_date(value)
        elif column in INTEGER_COLUMNS:
            row[column] = int(value) if value else None
        elif column in DECIMAL_COLUMNS:
            row[column] = _parse_decimal(value)
        elif column in BOOLEAN_COLUMNS:
            row[column] = bool(int(value)) if value else None
        else:
            row[column] = value or None
    return row


def read_dataset(dataset_path: Path) -> list[dict[str, Any]]:
    """Read and type-convert every row of the source CSV."""
    with dataset_path.open(newline="", encoding="utf-8") as handle:
        return [_parse_row(raw) for raw in csv.DictReader(handle)]


def seed(engine: Engine, rows: list[dict[str, Any]], read_only_role: str) -> int:
    """Create the schema, replace the table contents, and grant read access.

    The GRANT is issued here, by the table's owner, rather than relying only on
    ``ALTER DEFAULT PRIVILEGES``: it makes the read-only role's access explicit and
    survives the table being recreated. Returns the number of rows loaded.
    """
    Base.metadata.create_all(engine)

    with Session(engine) as session, session.begin():
        session.execute(delete(Order))
        if rows:
            session.execute(insert(Order), rows)
        # Role names come from configuration, not from user input; quoting keeps the
        # identifier valid if it is ever given mixed case.
        session.execute(text(f'GRANT SELECT ON orders TO "{read_only_role}"'))

    return len(rows)


def main() -> int:
    """Entry point. Returns a process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    # pydantic-settings populates these from the environment at runtime; mypy cannot
    # see that, so the constructor looks like it is missing arguments.
    settings = SeedSettings()  # type: ignore[call-arg]

    rows = read_dataset(settings.dataset_path)
    logger.info("read %d rows from %s", len(rows), settings.dataset_path)

    engine = create_database_engine(settings.seed_database_url)
    loaded = seed(engine, rows, settings.read_only_role)
    logger.info("seeded %d rows into orders", loaded)
    return 0


if __name__ == "__main__":
    sys.exit(main())
