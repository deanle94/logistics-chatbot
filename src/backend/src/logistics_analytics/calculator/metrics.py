"""THE FORMULAS. Every metric in ``docs/business-definition.md``, and nothing else.

This module and ``dimensions.py`` are the only two places in the codebase where a business
definition may appear (architecture Decision 1); ``tests/test_no_formula_outside_calculator.py``
fails the build if one shows up anywhere else.

**Why these are SQL expressions and not Python loops (decision D18).** The calculator owns
the *expression*; the data layer owns the *connection*. Building the aggregate in SQL means
PostgreSQL does the arithmetic over the rows it already has, and the definition still lives
in exactly one file. The alternative — pulling 400 rows into Python and summing them here —
keeps the same single home for the formula but stops working the moment the dataset grows,
and it would make the calculator the slow path for every chat question in Slice 2. The cost
of D18 is that this layer imports SQLAlchemy, so the import-linter contract that used to
forbid it was replaced by one that lets the calculator *describe* a query while still
forbidding it to *run* one.

**Why the rounding happens here (decision D13).** A rate rounded by the dashboard and the
same rate rounded by the chat would eventually print two different numbers for one
question. S2.3 requires that no digit appears in the agent's prose that is absent from the
tool result, so the tool result has to be the already-rounded number. Rounding is part of
the definition, not part of the presentation.

**Why three statuses are excluded from every rate.** ``docs/business-definition.md``: the
row states no delivery outcome. ``in_transit`` has not finished, ``canceled`` never
shipped, and ``exception`` says something went wrong rather than whether it arrived late.
All three still count in total orders — they are excluded from the *denominator*, not from
the dataset.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from sqlalchemy import ColumnElement, Numeric, cast, func

from logistics_analytics.calculator.models import Metric
from logistics_analytics.data.models import Order

#: The two statuses that state a delivery outcome. Every rate below divides by these and
#: only these.
DELIVERY_OUTCOMES: tuple[str, ...] = ("delivered", "delayed")

#: Decimals each rate is rounded to. Both rates are percentages (D19b).
#: Two for the delay rate, so a one-in-ten-thousand difference between two carriers is
#: still visible in the sort; one for the on-time rate, because S1.1 and the design both
#: pin the KPI card to "84.7%".
RATE_DECIMALS = 2
PERCENT_DECIMALS = 1


def _order_count() -> ColumnElement[Any]:
    """Total orders: every row, whatever its status."""
    return func.count()


def _delivered_orders() -> ColumnElement[Any]:
    """Delivered orders: ``status = delivered``, counted in the same pass as everything else.

    ``FILTER`` rather than a second query, so one row of SQL answers the whole KPI card and
    the two stacked-bar series come back aligned on the same buckets by construction.
    """
    return func.count().filter(Order.status == "delivered")


def _delayed_orders() -> ColumnElement[Any]:
    """Delayed orders: ``status = delayed`` only. ``exception`` is not late, it is unknown."""
    return func.count().filter(Order.status == "delayed")


def _finished_orders() -> ColumnElement[Any]:
    """The denominator of every rate: the orders that have a delivery outcome.

    Not exported as a ``Metric`` because it is not a number anyone asks for; it exists so
    the two rates below cannot each invent their own denominator.
    """
    return func.count().filter(Order.status.in_(DELIVERY_OUTCOMES))


def _delay_rate() -> ColumnElement[Any]:
    """Share of finished orders that arrived late, as a percentage.

    A percentage rather than a 0-1 ratio (decision D19b), for the same reason
    :func:`_on_time_rate` is one: it is the same ratio read from the other end, and two
    scales for one quantity is the drift architecture Decision 1 exists to prevent. It also
    keeps the digits out of the browser - under D13 the dashboard and the Slice 2 chat must
    print the identical number, which they cannot do if React multiplies by 100.

    Two decimals, not one: it carries exactly the information the old 4-decimal ratio did.

    ``nullif`` turns a zero denominator into NULL instead of a division error: a carrier
    with nothing finished has no delay rate, which is a different answer from zero and
    must not sort to the top of the "worst carrier" chart.
    """
    return func.round(
        100 * cast(_delayed_orders(), Numeric) / func.nullif(_finished_orders(), 0),
        RATE_DECIMALS,
    )


def _on_time_rate() -> ColumnElement[Any]:
    """On-time delivery rate as a percentage: delivered over (delivered + delayed).

    The same ratio as :func:`_delay_rate` read from the other end, sharing one denominator
    so the two can never contradict each other. Returned as a percentage rather than a
    ratio because that is the unit the KPI card prints (D13).
    """
    return func.round(
        100 * cast(_delivered_orders(), Numeric) / func.nullif(_finished_orders(), 0),
        PERCENT_DECIMALS,
    )


def _avg_delivery_time() -> ColumnElement[Any]:
    """Mean days from order to delivery, over the rows that have both dates.

    The 30 rows with no delivery date drop out on their own: subtracting from NULL gives
    NULL and ``avg`` ignores NULLs. Counting them as zero would be a silent lie, and
    excluding them with an explicit WHERE would also remove them from every other metric
    in the same query.
    """
    return func.round(
        cast(func.avg(Order.delivery_date - Order.order_date), Numeric),
        PERCENT_DECIMALS,
    )


def _quantity() -> ColumnElement[Any]:
    """Units ordered — the demand measure Slice 3's forecast is built on.

    ``coalesce`` because a bucket with no rows should report zero units, not NULL: unlike
    a rate, "nothing was ordered" really is zero.
    """
    return func.coalesce(func.sum(Order.quantity), 0)


#: The one lookup from a metric name to its definition. Callable-valued rather than
#: expression-valued because a SQLAlchemy element is stateful once composed; building a
#: fresh one per query keeps two concurrent requests from sharing a construct.
METRIC_EXPRESSIONS: Mapping[Metric, Callable[[], ColumnElement[Any]]] = {
    Metric.ORDER_COUNT: _order_count,
    Metric.DELIVERED_ORDERS: _delivered_orders,
    Metric.DELAYED_ORDERS: _delayed_orders,
    Metric.DELAY_RATE: _delay_rate,
    Metric.ON_TIME_RATE: _on_time_rate,
    Metric.AVG_DELIVERY_TIME: _avg_delivery_time,
    Metric.QUANTITY: _quantity,
}
