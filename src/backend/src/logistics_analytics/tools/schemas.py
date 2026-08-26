"""S2.1 — the only thing the model is allowed to fill in.

This module is the whitelist. Every field is typed with the calculator's own vocabulary
(:class:`Metric`, :class:`GroupBy`), so "what may be asked for" and "what can be computed"
are literally the same objects and cannot drift into two lists that disagree. Anything the
enums do not name is a ``ValidationError`` before a statement is built, which is the
promise decision D10 made when it deferred parameter validation to this slice.

Dimension *values* are pattern-checked rather than enumerated, for two reasons. The gate in
``tests/test_no_formula_outside_calculator.py`` forbids this layer from spelling out a
status literal, and an unrecognised value is already a defined outcome: an empty result is
a valid answer with the parameters echoed (D15). The pattern is the guard that stops an
injection-shaped string from being echoed back as though it were a real filter.

Every field also carries a ``description``. Those descriptions reach the model inside the
tool's JSON schema, which is where a tool-specific fact belongs — a system prompt that has
to be edited whenever a tool changes is a prompt doing the tool's job.
"""

from __future__ import annotations

import datetime
from enum import StrEnum
from typing import Annotated

from annotated_types import Len
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from logistics_analytics.calculator.models import METRIC_GLOSS, RATE_METRICS, GroupBy, Metric

#: A dimension value as the model may write it.
#:
#: Deliberately narrow: it must start with a letter or digit, and from there only letters,
#: digits, spaces, dots, underscores and hyphens are legal. Every value in the shipped
#: dataset fits (``Royal Mail``, ``US-E``, ``PAPER-0197``, ``in_transit``), while quotes,
#: semicolons, angle brackets, ``$``, ``*`` and a leading ``../`` do not. SQLAlchemy would
#: bind those safely anyway, so this is defence in depth — its real value is that a string
#: which can never match a row fails loudly at the edge instead of returning a confidently
#: empty answer that reads like a fact.
FilterValue = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}$")]

#: The metric gloss, rendered once for the parameter description the model reads.
METRIC_HELP = "; ".join(f"{metric.value} is {gloss}" for metric, gloss in METRIC_GLOSS.items())

#: The one key an in-domain refusal hands back. Deliberately *not* an answer envelope: the
#: agent's enforce node is the single place a refusal envelope is ever built (agent-design
#: rule 4 / D23), so the refusal layers cannot drift into shapes that merely look alike. It
#: lives here rather than in ``query_tool`` because two tools now refuse — the refusal
#: sentinel and the forecast tool on insufficient history — and the same constant is
#: spelled out in ``agent/nodes.py`` because ``agent/`` may not import this package
#: (rule 5).
REFUSAL_REASON_KEY = "refusal_reason"


class DateRangeSymbol(StrEnum):
    """Relative periods the model may name without doing any date arithmetic.

    Agent-design rule 3: date maths is computation, and the AI never computes. The model
    emits one of these symbols and ``query_tool`` resolves it against today's date, so the
    concrete window is decided by code and is echoed back as real dates.

    The set is closed on purpose — a model-invented period cannot reach the resolver.
    """

    LAST_MONTH = "last_month"
    LAST_3_MONTHS = "last_3_months"
    LAST_6_MONTHS = "last_6_months"
    LAST_12_MONTHS = "last_12_months"


class MissingInfo(StrEnum):
    """The only things a follow-up question may ask for.

    Closed rather than a free string (agent-design D3). The one thing that repeatedly went
    wrong against the real model was asking the user for a period they never restricted;
    an unstated filter is not missing information, it means every order on record, and an
    enum makes "which period do you mean?" unaskable rather than merely discouraged.

    ``SKU`` joined in Slice 3: a forecast without a product code is the one case where a
    filter genuinely is the missing parameter, because the forecast tool requires it.
    """

    METRIC = "metric"
    TIME_BUCKET = "time_bucket"
    SKU = "sku"


class QueryToolParams(BaseModel):
    """A validated question: which figures, split how, over which rows.

    Frozen and ``extra="forbid"``. Frozen because the same object is echoed back as the
    explanation, so a handler that could mutate it mid-flight would describe a query that
    never ran. ``forbid`` because silently dropping a hallucinated parameter would let the
    model believe it had filtered when it had not.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    metrics: Annotated[list[Metric], Len(1, 2)] = Field(
        description=(
            "Which figures to count. " + METRIC_HELP + ". Ask for two together only to set "
            "two outcomes against each other; only counts may be paired."
        ),
    )
    group_by: GroupBy = Field(
        default=GroupBy.NONE,
        description="How to split the figures. Leave as none for one figure over every order.",
    )
    date_from: datetime.date | None = Field(
        default=None,
        description=(
            "Inclusive start, as a real date. Leave both dates unset to count every order "
            "on record - that is the normal case and never a reason to ask the user."
        ),
    )
    date_to: datetime.date | None = Field(
        default=None,
        description="Inclusive end, as a real date. See date_from about leaving it unset.",
    )
    date_range: DateRangeSymbol | None = Field(
        default=None,
        description=(
            "A period named relative to today, when the customer said so in words. Only "
            "used when neither date_from nor date_to is given; never work the dates out "
            "yourself."
        ),
    )
    carrier: FilterValue | None = Field(default=None, description="Keep one carrier only.")
    status: FilterValue | None = Field(default=None, description="Keep one order state only.")
    sku: FilterValue | None = Field(default=None, description="Keep one product code only.")
    product_category: FilterValue | None = Field(
        default=None, description="Keep one product category only."
    )
    region: FilterValue | None = Field(default=None, description="Keep one region only.")
    warehouse: FilterValue | None = Field(default=None, description="Keep one warehouse only.")

    @model_validator(mode="after")
    def _pair_must_be_counts(self) -> QueryToolParams:
        """A pair is drawn as one stacked bar, so both halves must be counts of rows.

        Found against the real model rather than reasoned about: asked to compare the two
        delivery outcomes per month it requested two rates, which stacks two percentages on
        one axis and means nothing. Saying so in the prompt did not hold it. Rejecting it
        here does, because the tool node hands the error back and the model corrects itself
        inside the same turn.
        """
        if len(self.metrics) == 2 and any(metric in RATE_METRICS for metric in self.metrics):
            message = "two figures may only be compared when both are counts of orders"
            raise ValueError(message)
        return self


class ForecastToolParams(BaseModel):
    """A validated forecast request: which product, how many months ahead.

    Everything else about the forecast — the history query, the window, the buffer — is
    the calculator's and is deliberately not a parameter: a model that could vary the
    window would be choosing the method, and the AI never computes.

    Frozen and ``extra="forbid"`` for the same reasons as :class:`QueryToolParams`; the
    horizon bounds make a two-year extrapolation from a 3-month window unrequestable
    rather than merely discouraged.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    sku: FilterValue = Field(
        description=(
            "The product code to forecast, exactly as the customer said it. Required - "
            "ask a follow-up rather than guessing one."
        ),
    )
    horizon: int = Field(
        default=4,
        ge=1,
        le=12,
        description="How many months ahead to project. Use the default when unstated.",
    )


class FollowUpParams(BaseModel):
    """The structured question asked when one required parameter is genuinely missing.

    Structured rather than free text (agent-design D3): a free-text follow-up could smuggle
    an invented number before any tool has run, and at that point the no-invented-digit
    check has no tool result to check it against. The validator below makes that rule code
    instead of a prompt hope.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    missing_info: MissingInfo = Field(description="Which of the two askable things is missing.")
    question: str = Field(
        description="One short question for the customer. It must contain no digit."
    )
    options: list[str] = Field(
        default_factory=list, description="The valid values for that parameter."
    )

    @model_validator(mode="after")
    def _question_states_no_figure(self) -> FollowUpParams:
        """No tool has run yet, so any digit here would be one nothing can vouch for."""
        if any(character.isdigit() for character in self.question):
            message = "a follow-up question must contain no digit"
            raise ValueError(message)
        return self


class RefusalParams(BaseModel):
    """The in-domain refusal: the question is about these orders, the parameters are not.

    Separate from the classifier's out-of-domain verdict but emitted as the same envelope
    (agent-design rule 4), so the interface treats both refusals identically.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: str = Field(
        description=(
            "One sentence saying what cannot be done, then two things you can help with "
            "instead. State no figure."
        )
    )
