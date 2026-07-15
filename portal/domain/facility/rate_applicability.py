"""
Declarative JSON applicability rules for FacilityRentalRate selection (hours-only v1).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Any, Literal, Optional, Union

import ujson
from pydantic import BaseModel, Field, TypeAdapter, ValidationError, model_validator


@dataclass(frozen=True)
class RateSelectionContext:
    """Inputs available when evaluating whether a rate applies."""

    billed_hours: Decimal


class HoursGteRule(BaseModel):
    """billed_hours >= value."""

    op: Literal["hours_gte"]
    value: Decimal


class HoursLtRule(BaseModel):
    """billed_hours < value."""

    op: Literal["hours_lt"]
    value: Decimal


class HoursRangeRule(BaseModel):
    """billed_hours in [min, max) or [min, max] depending on max_exclusive."""

    op: Literal["hours_range"]
    min: Decimal = Field(default=Decimal("0"))
    max: Decimal
    max_exclusive: bool = True

    @model_validator(mode="after")
    def validate_bounds(self) -> HoursRangeRule:
        if self.min < 0 or self.max < 0:
            raise ValueError("hours_range min/max must be >= 0")
        if self.min >= self.max:
            raise ValueError("hours_range min must be < max")
        return self


LeafRule = Annotated[
    Union[HoursGteRule, HoursLtRule, HoursRangeRule],
    Field(discriminator="op"),
]


class AllRule(BaseModel):
    """Match when every child rule matches."""

    all: list["RuleNode"] = Field(..., min_length=1)


class AnyRule(BaseModel):
    """Match when at least one child rule matches."""

    any: list["RuleNode"] = Field(..., min_length=1)


class NotRule(BaseModel):
    """Match when child rule does not match."""

    not_: RuleNode = Field(..., alias="not")

    model_config = {"populate_by_name": True}


RuleNode = Annotated[
    Union[LeafRule, AllRule, AnyRule, NotRule],
    Field(),
]

# Rebuild forward refs for recursive models.
AllRule.model_rebuild()
AnyRule.model_rebuild()
NotRule.model_rebuild()

_rule_adapter: TypeAdapter[RuleNode] = TypeAdapter(RuleNode)


def coerce_applicability_from_db(raw: Any) -> Optional[dict[str, Any]]:
    """Normalize asyncpg JSONB values (dict or JSON string) for application use."""
    if raw is None:
        return None
    if isinstance(raw, str):
        if not raw.strip():
            return None
        try:
            raw = ujson.loads(raw)
        except ujson.JSONDecodeError:
            return None
    if isinstance(raw, dict):
        return raw or None
    return None


def parse_applicability(raw: Any) -> Optional[dict[str, Any]]:
    """
    Validate applicability JSON and return a plain dict for storage.
    None means always eligible. Raises ValidationError on invalid shape.
    """
    if raw is None:
        return None
    coerced = coerce_applicability_from_db(raw)
    if coerced is None:
        if raw is None or raw == "" or raw == {}:
            return None
        raise ValueError("applicability must be a JSON object or null")
    parsed = _rule_adapter.validate_python(coerced)
    return parsed.model_dump(by_alias=True, mode="json")


def matches_applicability(rule: Optional[dict[str, Any] | BaseModel | str], ctx: RateSelectionContext) -> bool:
    """Return True if rule is None/empty or evaluates true against ctx."""
    if isinstance(rule, str):
        rule = coerce_applicability_from_db(rule)
    if rule is None:
        return True
    if isinstance(rule, BaseModel):
        node = rule
    else:
        if not rule:
            return True
        try:
            node = _rule_adapter.validate_python(rule)
        except ValidationError:
            return False
    return _eval_node(node, ctx)


def _eval_node(node: BaseModel, ctx: RateSelectionContext) -> bool:
    if isinstance(node, HoursGteRule):
        return ctx.billed_hours >= node.value
    if isinstance(node, HoursLtRule):
        return ctx.billed_hours < node.value
    if isinstance(node, HoursRangeRule):
        if ctx.billed_hours < node.min:
            return False
        if node.max_exclusive:
            return ctx.billed_hours < node.max
        return ctx.billed_hours <= node.max
    if isinstance(node, AllRule):
        return all(_eval_node(child, ctx) for child in node.all)
    if isinstance(node, AnyRule):
        return any(_eval_node(child, ctx) for child in node.any)
    if isinstance(node, NotRule):
        return not _eval_node(node.not_, ctx)
    return False
