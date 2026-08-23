"""The calculator's vocabulary: what may be asked, and what comes back.

This module holds no formula — only the words a caller is allowed to use. Keeping the
vocabulary separate from the definitions is what lets Slice 2's parameter validation be a
membership check against these enums rather than a second list that could drift from them.

Everything here is frozen (coding rule 13). A request object that a route handler could
mutate mid-flight would make the echoed parameters a description of something other than
the query that actually ran, which is the one thing the explainability panel must never do.
"""

from __future__ import annotations

import datetime
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

#: Wire and SQL label for the bucket column. Defined once so the query builder, the JSON
#: response and the front-end cannot disagree about what the x-axis key is called.
GROUP_LABEL = "group"


class Metric(StrEnum):
    """Every number the system knows how to compute.

    ``docs/requirement.md`` S1.2 lists six; ``ON_TIME_RATE`` is the seventh because the
    S1.1 KPI card needs it. It is defined here, alongside the others, rather than as a
    separate KPI-only calculation: on-time rate and delay rate are the same ratio read
    from opposite ends, and two implementations of one ratio is precisely the drift
    architecture Decision 1 exists to prevent.

    The values are the JSON keys the browser receives, so renaming one is a wire change.
    """

    ORDER_COUNT = "order_count"
    DELIVERED_ORDERS = "delivered_orders"
    DELAYED_ORDERS = "delayed_orders"
    DELAY_RATE = "delay_rate"
    ON_TIME_RATE = "on_time_rate"
    AVG_DELIVERY_TIME = "avg_delivery_time"
    QUANTITY = "quantity"


class GroupBy(StrEnum):
    """Every bucketing a metric may be split by.

    ``NONE`` is a real member rather than ``None`` so that "the whole dataset" is a
    choice a caller makes explicitly, and so the KPI query is the same code path as every
    chart query instead of a special case.
    """

    NONE = "none"
    WEEK = "week"
    MONTH = "month"
    CARRIER = "carrier"
    STATUS = "status"
    SKU = "sku"
    PRODUCT_CATEGORY = "product_category"
    REGION = "region"
    WAREHOUSE = "warehouse"


class Ordering(StrEnum):
    """How the rows come back.

    Only two orderings exist because only two questions are ever asked of a result: "how
    did this change over time" (by bucket) and "who is worst" (by value). Anything else
    is a sort the browser can do itself.
    """

    GROUP = "group"
    VALUE_DESC = "value_desc"


@dataclass(frozen=True)
class Filters:
    """Which rows a query considers. Every filter is optional and defaults to "all rows".

    The date range applies to ``order_date``, not ``delivery_date``: a manager asking
    about March means orders placed in March, and an undelivered order has no delivery
    date to filter on at all.
    """

    date_from: datetime.date | None = None
    date_to: datetime.date | None = None
    carrier: str | None = None
    status: str | None = None
    sku: str | None = None
    product_category: str | None = None
    region: str | None = None
    warehouse: str | None = None

    def applied(self) -> dict[str, str]:
        """Only the filters that were actually set, ready to echo back to the caller.

        Echoing the unset ones as nulls would make an unfiltered query look like a
        deliberate choice of eight "no" answers; the explainability panel should show
        what was asked for, not the shape of the request object.
        """
        candidates: dict[str, str | None] = {
            "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "carrier": self.carrier,
            "status": self.status,
            "sku": self.sku,
            "product_category": self.product_category,
            "region": self.region,
            "warehouse": self.warehouse,
        }
        return {name: value for name, value in candidates.items() if value is not None}


@dataclass(frozen=True)
class QuerySpec:
    """One complete question: which numbers, split how, over which rows, in what order.

    This object is the seam the whole system is built around. The dashboard builds it as
    a constant; Slice 2's agent will build it from validated parameters. Both then run
    through the same code, so the chat and the dashboard cannot disagree.
    """

    metrics: tuple[Metric, ...]
    group_by: GroupBy = GroupBy.NONE
    filters: Filters = field(default_factory=Filters)
    order: Ordering = Ordering.GROUP


@dataclass(frozen=True)
class ResultRow:
    """One bucket's answer. ``group`` is ``None`` for an ungrouped query.

    A value may be ``None`` where the definition does not apply to the bucket — a carrier
    with no finished orders has no delay rate. That is deliberately not coerced to zero:
    "no data" and "zero percent late" are different answers.
    """

    group: str | None
    values: Mapping[Metric, float | int | None]


@dataclass(frozen=True)
class QueryResult:
    """The rows, plus the spec that produced them.

    The spec travels with the result rather than being remembered by the caller, so the
    explanation shown next to a number can never describe a different query.
    """

    rows: tuple[ResultRow, ...]
    spec: QuerySpec


@dataclass(frozen=True)
class KpiValue:
    """A dashboard number with the unit it must be printed in.

    D13: the unit is part of the answer, not part of the template. It travels with the
    value so the dashboard card and the Slice 2 chat print identical text.
    """

    value: float
    unit: str | None


@dataclass(frozen=True)
class DashboardKpis:
    """The five KPIs of ``docs/requirement.md`` section 2.1, as one object.

    Named fields rather than a dict: the requirement lists exactly five, and a missing one
    is a checklist failure, so it should be a type error rather than a lookup that returns
    nothing at runtime.
    """

    total_orders: KpiValue
    delivered_orders: KpiValue
    delayed_orders: KpiValue
    on_time_rate: KpiValue
    average_delivery_time: KpiValue
