"""
Validate and total the Azure cost estimate CSV offline.

This script reads local CSV files only. It never contacts Azure.
"""

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

ESTIMATE_COLUMNS: tuple[str, ...] = (
    "id",
    "inclusion",
    "scenario",
    "environment",
    "category",
    "resource",
    "service",
    "sku",
    "region",
    "quantity",
    "usage_per_month",
    "unit",
    "unit_price_usd",
    "allowance_group",
    "allowance_per_month",
    "monthly_usd",
    "annual_usd",
    "price_status",
    "replaces",
    "checked_date",
    "source_url",
    "notes",
)
ACCOUNT_COLUMNS: tuple[str, ...] = ("key", "value", "notes")
COST_DIR = Path(__file__).resolve().parents[1] / "infra" / "azure" / "cost"
BASELINE = "baseline"
MONTHS_PER_YEAR = Decimal(12)
STORED_PLACES = Decimal("0.0001")
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
PRICED_STATUSES = frozenset({"public", "unverified"})
PRICE_STATUSES = PRICED_STATUSES | {"free", "unknown"}
BASELINE_INCLUSIONS = frozenset({"selected", "variable"})
INCLUSIONS = BASELINE_INCLUSIONS | {"alternative", "excluded", "outside_grant", "allowance"}
ACCOUNT_NUMBERS = ("grant_annual_usd", "grant_remaining_usd", "months_remaining", "existing_monthly_spend_usd")
REQUIRED_ACCOUNT_KEYS = (*ACCOUNT_NUMBERS, "grant_expiry_date")
ENVIRONMENTS = frozenset({"staging", "production", "shared"})
FIXED_INCLUSIONS = frozenset({"selected", "alternative"})


class EstimateError(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class EstimateRow:
    id: str
    inclusion: str
    scenario: str
    replaces: tuple[str, ...]
    unit: str
    usage: Decimal
    allowance_group: str
    allowance: Decimal
    price_status: str
    monthly: Decimal | None


@dataclass(frozen=True)
class ScenarioTotal:
    name: str
    fixed_monthly: Decimal
    variable_monthly: Decimal
    unknown_ids: tuple[str, ...]
    unverified_ids: tuple[str, ...]
    delta_monthly: Decimal

    @property
    def total_monthly(self) -> Decimal:
        return self.fixed_monthly + self.variable_monthly

    @property
    def total_annual(self) -> Decimal:
        return self.total_monthly * MONTHS_PER_YEAR


@dataclass(frozen=True)
class GrantCheck:
    annual_grant: Decimal
    nominal_annual_headroom: Decimal
    account_headroom: Decimal | None
    missing_inputs: tuple[str, ...]
    blocked_reasons: tuple[str, ...]

    @property
    def blocked(self) -> bool:
        return bool(self.blocked_reasons)


@dataclass(frozen=True)
class Report:
    scenarios: dict[str, ScenarioTotal]
    grant: GrantCheck

    def scenario(self, name: str) -> ScenarioTotal:
        return self.scenarios[name]


def _number(raw: str) -> Decimal | None:
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    return value if value.is_finite() and value >= 0 else None


def _is_date(raw: str) -> bool:
    if not DATE_PATTERN.fullmatch(raw):
        return False
    try:
        date.fromisoformat(raw)
    except ValueError:
        return False
    return True


def _decimal(record: dict[str, str], column: str, problems: list[str]) -> Decimal | None:
    raw = record[column].strip()
    if not raw:
        return None
    value = _number(raw)
    if value is None:
        problems.append(f"{record['id']}: {column} {raw!r} is not a non-negative number")
    return value


def _read_records(path: Path, columns: tuple[str, ...], problems: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or ())
        missing = [column for column in columns if column not in fieldnames]
        if missing:
            raise EstimateError([f"{path.name}: missing columns {', '.join(missing)}"])
        records = []
        for record in reader:
            if None in record or None in record.values():
                problems.append(f"{path.name} line {reader.line_num}: expected {len(fieldnames)} fields")
                continue
            records.append(record)
    return fieldnames, records


def _stored(value: Decimal) -> Decimal:
    return value.quantize(STORED_PLACES, rounding=ROUND_HALF_UP)


def _check_stored(record: dict[str, str], monthly: Decimal | None, problems: list[str]) -> None:
    for column, factor in (("monthly_usd", Decimal(1)), ("annual_usd", MONTHS_PER_YEAR)):
        expected = None if monthly is None else _stored(monthly * factor)
        actual = _decimal(record, column, problems)
        if actual != expected:
            shown = "blank" if expected is None else str(expected)
            problems.append(f"{record['id']}: {column} is {record[column]!r}, recomputed {shown}")


def _check_price_status(record: dict[str, str], unit_price: Decimal | None, problems: list[str]) -> None:
    status = record["price_status"]
    if status == "unknown" and unit_price is not None:
        problems.append(f"{record['id']}: unknown price must be blank, never 0")
    elif status == "free" and unit_price != 0:
        problems.append(f"{record['id']}: free price must be 0")
    elif status in PRICED_STATUSES and (unit_price is None or unit_price <= 0):
        problems.append(f"{record['id']}: priced row must be greater than 0; use free or unknown instead")


def _check_fields(record: dict[str, str], problems: list[str]) -> None:
    row_id = record["id"]
    for column, allowed in (("inclusion", INCLUSIONS), ("environment", ENVIRONMENTS), ("price_status", PRICE_STATUSES)):
        if record[column] not in allowed:
            problems.append(f"{row_id}: {column} {record[column]!r} is not one of {', '.join(sorted(allowed))}")
    for column in ("quantity", "usage_per_month"):
        if not record[column].strip():
            problems.append(f"{row_id}: {column} is required")
    inclusion, scenario = record["inclusion"], record["scenario"]
    if inclusion in BASELINE_INCLUSIONS and scenario != BASELINE:
        problems.append(f"{row_id}: scenario must be {BASELINE!r} for {inclusion} rows")
    elif inclusion == "alternative" and scenario in ("", BASELINE):
        problems.append(f"{row_id}: scenario must name the alternative plan")
    elif inclusion not in BASELINE_INCLUSIONS | {"alternative"} and scenario:
        problems.append(f"{row_id}: scenario must be blank for {inclusion} rows")
    if not _is_date(record["checked_date"]):
        problems.append(f"{row_id}: checked_date {record['checked_date']!r} is not YYYY-MM-DD")
    if (record["source_url"] or record["price_status"] != "unknown") and not record["source_url"].startswith("https://"):
        problems.append(f"{row_id}: source_url must be an https:// link to the public source")


def _parse_row(record: dict[str, str], problems: list[str]) -> EstimateRow:
    row_id = record["id"]
    _check_fields(record, problems)
    unit_price = _decimal(record, "unit_price_usd", problems)
    quantity = _decimal(record, "quantity", problems) or Decimal(0)
    usage = quantity * (_decimal(record, "usage_per_month", problems) or Decimal(0))
    allowance = _decimal(record, "allowance_per_month", problems) or Decimal(0)
    if allowance > usage:
        problems.append(f"{row_id}: allowance_per_month {allowance} exceeds the row's usage {usage}")
    if allowance and not record["allowance_group"]:
        problems.append(f"{row_id}: allowance_per_month needs an allowance_group")
    monthly = None
    if record["inclusion"] == "allowance":
        if unit_price is not None:
            problems.append(f"{row_id}: allowance rows define a free limit and must leave unit_price_usd blank")
    else:
        _check_price_status(record, unit_price, problems)
        if record["price_status"] != "unknown" and unit_price is not None:
            monthly = max(usage - allowance, Decimal(0)) * unit_price
    return EstimateRow(
        id=row_id,
        inclusion=record["inclusion"],
        scenario=record["scenario"],
        replaces=tuple(item for item in record["replaces"].split(";") if item),
        unit=record["unit"],
        usage=usage,
        allowance_group=record["allowance_group"],
        allowance=allowance,
        price_status=record["price_status"],
        monthly=monthly,
    )


def _read_rows(path: Path, problems: list[str]) -> list[EstimateRow]:
    rows = []
    for record in _read_records(path, ESTIMATE_COLUMNS, problems)[1]:
        row = _parse_row(record, problems)
        _check_stored(record, row.monthly, problems)
        rows.append(row)
    seen: set[str] = set()
    for row in rows:
        if row.id in seen:
            problems.append(f"duplicate id {row.id!r}")
        seen.add(row.id)
    return rows


def _sum(rows: list[EstimateRow], inclusions: frozenset[str]) -> Decimal:
    return sum((row.monthly for row in rows if row.inclusion in inclusions and row.monthly is not None), Decimal(0))


def _scenario_rows(rows: list[EstimateRow]) -> dict[str, list[EstimateRow]]:
    baseline = [row for row in rows if row.inclusion in BASELINE_INCLUSIONS]
    alternatives: dict[str, list[EstimateRow]] = {}
    for row in rows:
        if row.inclusion == "alternative":
            alternatives.setdefault(row.scenario, []).append(row)
    scenarios = {BASELINE: baseline}
    for name, added in alternatives.items():
        replaced = {item for row in added for item in row.replaces}
        scenarios[name] = [row for row in baseline if row.id not in replaced] + added
    return scenarios


def _check_replacements(rows: list[EstimateRow], problems: list[str]) -> None:
    baseline_ids = {row.id for row in rows if row.inclusion in BASELINE_INCLUSIONS}
    for row in rows:
        if row.inclusion == "alternative":
            problems.extend(f"{row.id}: replaces {item!r}, which is not a selected or variable row" for item in row.replaces if item not in baseline_ids)


def _check_allowances(rows: list[EstimateRow], scenario_rows: dict[str, list[EstimateRow]], problems: list[str]) -> None:
    limits = {row.id: row for row in rows if row.inclusion == "allowance"}
    for row in rows:
        if row.allowance_group and row.allowance_group not in limits:
            problems.append(f"{row.id}: allowance_group {row.allowance_group!r} has no allowance row")
        elif row.allowance_group and limits[row.allowance_group].unit != row.unit:
            problems.append(f"{row.id}: unit {row.unit!r} does not match allowance {row.allowance_group!r} unit {limits[row.allowance_group].unit!r}")
    for name, members in scenario_rows.items():
        for group, limit in limits.items():
            applied = sum((row.allowance for row in members if row.allowance_group == group), Decimal(0))
            if applied > limit.usage:
                problems.append(f"{group}: scenario {name!r} applies {applied} of a {limit.usage} {limit.unit} allowance")


def _total(name: str, rows: list[EstimateRow], baseline_monthly: Decimal) -> ScenarioTotal:
    fixed = _sum(rows, FIXED_INCLUSIONS)
    variable = _sum(rows, frozenset({"variable"}))
    return ScenarioTotal(
        name=name,
        fixed_monthly=fixed,
        variable_monthly=variable,
        unknown_ids=tuple(row.id for row in rows if row.monthly is None),
        unverified_ids=tuple(row.id for row in rows if row.price_status == "unverified"),
        delta_monthly=fixed + variable - baseline_monthly,
    )


def _read_account(path: Path, problems: list[str]) -> dict[str, str]:
    values = {record["key"]: record["value"].strip() for record in _read_records(path, ACCOUNT_COLUMNS, problems)[1]}
    for key in REQUIRED_ACCOUNT_KEYS:
        if key not in values:
            problems.append(f"{path.name}: missing key {key!r}")
    for key in ACCOUNT_NUMBERS:
        if values.get(key) and _number(values[key]) is None:
            problems.append(f"{path.name}: {key} {values[key]!r} is not a non-negative number")
    if values.get("grant_expiry_date") and not _is_date(values["grant_expiry_date"]):
        problems.append(f"{path.name}: grant_expiry_date {values['grant_expiry_date']!r} is not YYYY-MM-DD")
    return values


def _grant_check(baseline: ScenarioTotal, account: dict[str, str]) -> GrantCheck:
    missing = tuple(key for key, value in account.items() if not value)
    annual_grant = Decimal(account.get("grant_annual_usd") or 0)
    nominal = annual_grant - baseline.total_annual
    reasons = []
    if missing:
        reasons.append(f"account inputs not supplied: {', '.join(missing)}")
    if baseline.unknown_ids:
        reasons.append(f"baseline has unknown prices: {', '.join(baseline.unknown_ids)}")
    if baseline.unverified_ids:
        reasons.append(f"baseline has unverified prices: {', '.join(baseline.unverified_ids)}")
    if nominal < 0:
        reasons.append(f"baseline exceeds annual grant by {-nominal:.2f} USD/year")
    account_headroom = None
    if all(account.get(key) for key in ("grant_remaining_usd", "months_remaining", "existing_monthly_spend_usd")):
        forecast = (baseline.total_monthly + Decimal(account["existing_monthly_spend_usd"])) * Decimal(account["months_remaining"])
        account_headroom = Decimal(account["grant_remaining_usd"]) - forecast
        if account_headroom < 0:
            reasons.append(f"forecast exceeds remaining grant by {-account_headroom:.2f} USD")
    return GrantCheck(
        annual_grant=annual_grant, nominal_annual_headroom=nominal, account_headroom=account_headroom, missing_inputs=missing, blocked_reasons=tuple(reasons)
    )


def build_report(estimate_path: Path, account_path: Path) -> Report:
    problems: list[str] = []
    rows = _read_rows(estimate_path, problems)
    _check_replacements(rows, problems)
    scenario_rows = _scenario_rows(rows)
    _check_allowances(rows, scenario_rows, problems)
    account = _read_account(account_path, problems)
    if problems:
        raise EstimateError(problems)
    baseline_monthly = _sum(scenario_rows[BASELINE], BASELINE_INCLUSIONS)
    scenarios = {name: _total(name, members, baseline_monthly) for name, members in scenario_rows.items()}
    return Report(scenarios=scenarios, grant=_grant_check(scenarios[BASELINE], account))


def _recompute(path: Path) -> list[str]:
    problems: list[str] = []
    fieldnames, records = _read_records(path, ESTIMATE_COLUMNS, problems)
    for record in records:
        monthly = _parse_row(record, problems).monthly
        record["monthly_usd"] = "" if monthly is None else str(_stored(monthly))
        record["annual_usd"] = "" if monthly is None else str(_stored(monthly * MONTHS_PER_YEAR))
    if not problems:
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(records)
    return problems


def _money(value: Decimal) -> str:
    return f"{value:,.2f}"


def _print_report(report: Report) -> None:
    print("CSV valid: parsed and recomputed offline (no Azure access).")
    print()
    print(f"{'Scenario (USD)':<38}{'Fixed/mo':>10}{'Variable/mo':>13}{'Total/mo':>10}{'Total/yr':>11}{'vs baseline/mo':>16}")
    for scenario in report.scenarios.values():
        print(
            f"{scenario.name:<38}{_money(scenario.fixed_monthly):>10}{_money(scenario.variable_monthly):>13}"
            f"{_money(scenario.total_monthly):>10}{_money(scenario.total_annual):>11}{_money(scenario.delta_monthly):>16}"
        )
        print(f"  unknown, not counted: {', '.join(scenario.unknown_ids) or 'none'}")
        print(f"  unverified, counted: {', '.join(scenario.unverified_ids) or 'none'}")
    grant = report.grant
    print()
    print(f"Annual grant: {_money(grant.annual_grant)} USD; nominal headroom after baseline: {_money(grant.nominal_annual_headroom)} USD/year")
    if grant.account_headroom is None:
        print("Account headroom: pending operator-supplied account inputs")
    else:
        print(f"Account headroom (remaining grant minus forecast to expiry): {_money(grant.account_headroom)} USD")
    print(f"Budget gate: {'BLOCKED' if grant.blocked else 'OPEN'}")
    for reason in grant.blocked_reasons:
        print(f"  - {reason}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and total the Azure cost estimate CSV offline.")
    parser.add_argument("--estimate", type=Path, default=COST_DIR / "estimate.csv")
    parser.add_argument("--account", type=Path, default=COST_DIR / "account-inputs.csv")
    parser.add_argument("--write", action="store_true", help="rewrite monthly_usd and annual_usd from the other columns before validating")
    args = parser.parse_args(argv)
    try:
        if args.write and (problems := _recompute(args.estimate)):
            raise EstimateError(problems)
        report = build_report(args.estimate, args.account)
    except EstimateError as error:
        print("CSV invalid:", file=sys.stderr)
        for problem in error.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    _print_report(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
