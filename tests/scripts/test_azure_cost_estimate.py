"""
Offline checks for the Azure cost estimate CSV validator.
"""

import csv
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.azure_cost_estimate import ACCOUNT_COLUMNS, ESTIMATE_COLUMNS, EstimateError, build_report, main

DEFAULT_ROW = {
    "inclusion": "selected",
    "scenario": "baseline",
    "environment": "production",
    "category": "compute",
    "resource": "Core API App Service Plan",
    "service": "Azure App Service",
    "sku": "Linux B1",
    "region": "canadaeast",
    "quantity": "1",
    "usage_per_month": "730",
    "unit": "hour",
    "unit_price_usd": "0.018",
    "allowance_group": "",
    "allowance_per_month": "0",
    "monthly_usd": "13.1400",
    "annual_usd": "157.6800",
    "price_status": "public",
    "replaces": "",
    "checked_date": "2026-11-10",
    "source_url": "https://azure.microsoft.com/en-us/pricing/details/app-service/linux/",
    "notes": "",
}


def _row(row_id: str, **overrides: str) -> dict[str, str]:
    return {"id": row_id, **DEFAULT_ROW, **overrides}


def _write_estimate(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ESTIMATE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_account(path: Path, values: dict[str, str] | None = None) -> Path:
    values = values or {}
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ACCOUNT_COLUMNS)
        writer.writeheader()
        for key in ("grant_annual_usd", "grant_remaining_usd", "grant_expiry_date", "months_remaining", "existing_monthly_spend_usd"):
            writer.writerow({"key": key, "value": values.get(key, ""), "notes": ""})
    return path


@pytest.fixture
def account_path(tmp_path: Path) -> Path:
    return _write_account(tmp_path / "account.csv", {"grant_annual_usd": "2000"})


def test_baseline_totals_combine_selected_fixed_and_variable_rows(tmp_path: Path, account_path: Path) -> None:
    estimate = _write_estimate(
        tmp_path / "estimate.csv",
        [
            _row("api-plan-production"),
            _row(
                "blob-reads-production",
                inclusion="variable",
                category="storage",
                quantity="1",
                usage_per_month="10",
                unit="10K operations",
                unit_price_usd="0.0044",
                monthly_usd="0.0440",
                annual_usd="0.5280",
            ),
        ],
    )

    report = build_report(estimate, account_path)

    baseline = report.scenario("baseline")
    assert baseline.fixed_monthly == Decimal("13.14")
    assert baseline.variable_monthly == Decimal("0.044")
    assert baseline.total_monthly == Decimal("13.184")
    assert baseline.total_annual == Decimal("158.208")


def test_stored_monthly_or_annual_cost_that_does_not_recompute_is_rejected(tmp_path: Path, account_path: Path) -> None:
    estimate = _write_estimate(tmp_path / "estimate.csv", [_row("api-plan-staging", monthly_usd="13.0000"), _row("api-plan-production", annual_usd="150.0000")])

    with pytest.raises(EstimateError) as error:
        build_report(estimate, account_path)

    assert any("api-plan-staging" in problem and "monthly_usd" in problem and "13.1400" in problem for problem in error.value.problems)
    assert any("api-plan-production" in problem and "annual_usd" in problem and "157.6800" in problem for problem in error.value.problems)


def test_unknown_price_is_listed_separately_and_not_added_as_zero(tmp_path: Path, account_path: Path) -> None:
    estimate = _write_estimate(
        tmp_path / "estimate.csv",
        [
            _row("api-plan-production"),
            _row("sales-tax", environment="shared", category="tax", price_status="unknown", unit_price_usd="", monthly_usd="", annual_usd=""),
        ],
    )

    baseline = build_report(estimate, account_path).scenario("baseline")

    assert baseline.total_monthly == Decimal("13.14")
    assert baseline.unknown_ids == ("sales-tax",)


@pytest.mark.parametrize(
    ("price_status", "unit_price", "expected"),
    [("unknown", "0", "unknown price must be blank"), ("free", "0.01", "free price must be 0"), ("public", "0", "priced row must be greater than 0")],
)
def test_price_status_must_agree_with_the_unit_price(tmp_path: Path, account_path: Path, price_status: str, unit_price: str, expected: str) -> None:
    estimate = _write_estimate(
        tmp_path / "estimate.csv", [_row("vnet-production", price_status=price_status, unit_price_usd=unit_price, monthly_usd="", annual_usd="")]
    )

    with pytest.raises(EstimateError) as error:
        build_report(estimate, account_path)

    assert any("vnet-production" in problem and expected in problem for problem in error.value.problems)


def test_alternative_scenario_swaps_replaced_rows_and_stays_out_of_baseline(tmp_path: Path, account_path: Path) -> None:
    estimate = _write_estimate(
        tmp_path / "estimate.csv",
        [
            _row("api-plan-staging", environment="staging"),
            _row("api-plan-production"),
            _row(
                "shared-api-plan",
                inclusion="alternative",
                scenario="shared-app-service-plan",
                environment="shared",
                replaces="api-plan-staging;api-plan-production",
                unit_price_usd="0.018",
            ),
            _row("nat-gateway", inclusion="excluded", scenario="", unit_price_usd="0.045", monthly_usd="32.8500", annual_usd="394.2000"),
        ],
    )

    report = build_report(estimate, account_path)

    assert report.scenario("baseline").total_monthly == Decimal("26.28")
    assert report.scenario("shared-app-service-plan").total_monthly == Decimal("13.14")
    assert report.scenario("shared-app-service-plan").delta_monthly == Decimal("-13.14")


def test_alternative_must_replace_existing_baseline_rows(tmp_path: Path, account_path: Path) -> None:
    estimate = _write_estimate(
        tmp_path / "estimate.csv",
        [_row("api-plan-production"), _row("shared-api-plan", inclusion="alternative", scenario="shared-app-service-plan", replaces="api-plan-missing")],
    )

    with pytest.raises(EstimateError) as error:
        build_report(estimate, account_path)

    assert any("shared-api-plan" in problem and "api-plan-missing" in problem for problem in error.value.problems)


def _allowance(row_id: str, limit: str) -> dict[str, str]:
    return _row(
        row_id,
        inclusion="allowance",
        scenario="",
        environment="shared",
        category="registry",
        quantity="1",
        usage_per_month=limit,
        unit="GB-month",
        unit_price_usd="",
        price_status="free",
        monthly_usd="",
        annual_usd="",
    )


def _acr_storage(row_id: str, usage: str, allowance: str, monthly: str, annual: str) -> dict[str, str]:
    return _row(
        row_id,
        inclusion="variable",
        environment="shared",
        category="registry",
        usage_per_month=usage,
        unit="GB-month",
        unit_price_usd="0.1",
        allowance_group="acr-basic-included-storage",
        allowance_per_month=allowance,
        monthly_usd=monthly,
        annual_usd=annual,
    )


def test_included_allowance_reduces_billable_usage(tmp_path: Path, account_path: Path) -> None:
    estimate = _write_estimate(
        tmp_path / "estimate.csv", [_allowance("acr-basic-included-storage", "10"), _acr_storage("acr-storage", "12", "10", "0.2000", "2.4000")]
    )

    assert build_report(estimate, account_path).scenario("baseline").variable_monthly == Decimal("0.2")


def test_allowance_cannot_be_applied_beyond_its_limit_across_rows(tmp_path: Path, account_path: Path) -> None:
    estimate = _write_estimate(
        tmp_path / "estimate.csv",
        [
            _allowance("acr-basic-included-storage", "10"),
            _acr_storage("acr-storage-api", "8", "8", "0.0000", "0.0000"),
            _acr_storage("acr-storage-tools", "8", "8", "0.0000", "0.0000"),
        ],
    )

    with pytest.raises(EstimateError) as error:
        build_report(estimate, account_path)

    assert any("acr-basic-included-storage" in problem and "16" in problem and "10" in problem for problem in error.value.problems)


def test_allowance_cannot_exceed_the_rows_own_usage(tmp_path: Path, account_path: Path) -> None:
    estimate = _write_estimate(
        tmp_path / "estimate.csv", [_allowance("acr-basic-included-storage", "10"), _acr_storage("acr-storage", "4", "10", "0.0000", "0.0000")]
    )

    with pytest.raises(EstimateError) as error:
        build_report(estimate, account_path)

    assert any("acr-storage" in problem and "allowance_per_month" in problem for problem in error.value.problems)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"inclusion": "maybe"}, "inclusion 'maybe'"),
        ({"environment": "dev"}, "environment 'dev'"),
        ({"price_status": "guess"}, "price_status 'guess'"),
        ({"quantity": "two"}, "quantity 'two' is not a non-negative number"),
        ({"quantity": ""}, "quantity is required"),
        ({"checked_date": "10/11/2026"}, "checked_date"),
        ({"source_url": "azure pricing page"}, "source_url"),
        ({"scenario": "container-apps"}, "scenario"),
    ],
)
def test_malformed_row_is_rejected_with_its_id(tmp_path: Path, account_path: Path, overrides: dict[str, str], expected: str) -> None:
    estimate = _write_estimate(tmp_path / "estimate.csv", [_row("api-plan-production", **overrides)])

    with pytest.raises(EstimateError) as error:
        build_report(estimate, account_path)

    assert any("api-plan-production" in problem and expected in problem for problem in error.value.problems), error.value.problems


def test_duplicate_ids_are_rejected(tmp_path: Path, account_path: Path) -> None:
    estimate = _write_estimate(tmp_path / "estimate.csv", [_row("api-plan-production"), _row("api-plan-production")])

    with pytest.raises(EstimateError) as error:
        build_report(estimate, account_path)

    assert any("duplicate id 'api-plan-production'" in problem for problem in error.value.problems)


def test_missing_column_is_rejected_before_rows_are_read(tmp_path: Path, account_path: Path) -> None:
    estimate = tmp_path / "estimate.csv"
    estimate.write_text("id,inclusion\napi-plan-production,selected\n")

    with pytest.raises(EstimateError) as error:
        build_report(estimate, account_path)

    assert any("missing columns" in problem and "unit_price_usd" in problem for problem in error.value.problems)


def test_grant_check_is_blocked_until_the_operator_supplies_account_facts(tmp_path: Path, account_path: Path) -> None:
    estimate = _write_estimate(tmp_path / "estimate.csv", [_row("api-plan-production")])

    grant = build_report(estimate, account_path).grant

    assert grant.nominal_annual_headroom == Decimal("1842.32")
    assert grant.account_headroom is None
    assert grant.missing_inputs == ("grant_remaining_usd", "grant_expiry_date", "months_remaining", "existing_monthly_spend_usd")
    assert grant.blocked


def test_grant_check_passes_when_account_facts_cover_the_baseline(tmp_path: Path) -> None:
    estimate = _write_estimate(tmp_path / "estimate.csv", [_row("api-plan-production")])
    account = _write_account(
        tmp_path / "account.csv",
        {
            "grant_annual_usd": "2000",
            "grant_remaining_usd": "1900",
            "grant_expiry_date": "2027-11-30",
            "months_remaining": "12",
            "existing_monthly_spend_usd": "1.00",
        },
    )

    grant = build_report(estimate, account).grant

    assert grant.account_headroom == Decimal("1730.32")
    assert grant.blocked_reasons == ()


@pytest.mark.parametrize(
    ("estimate_overrides", "account_values", "expected"),
    [
        ({}, {"grant_remaining_usd": "100"}, "forecast exceeds remaining grant"),
        ({"unit_price_usd": "0.25", "monthly_usd": "182.5000", "annual_usd": "2190.0000"}, {}, "baseline exceeds annual grant"),
    ],
)
def test_grant_check_blocks_when_the_forecast_exceeds_the_grant(
    tmp_path: Path, estimate_overrides: dict[str, str], account_values: dict[str, str], expected: str
) -> None:
    estimate = _write_estimate(tmp_path / "estimate.csv", [_row("api-plan-production", **estimate_overrides)])
    values = {"grant_annual_usd": "2000", "grant_remaining_usd": "1900", "grant_expiry_date": "2027-11-30", "months_remaining": "12"}
    account = _write_account(tmp_path / "account.csv", {**values, "existing_monthly_spend_usd": "0", **account_values})

    grant = build_report(estimate, account).grant

    assert any(expected in reason for reason in grant.blocked_reasons), grant.blocked_reasons


def test_unknown_baseline_price_blocks_the_grant_check(tmp_path: Path) -> None:
    estimate = _write_estimate(
        tmp_path / "estimate.csv", [_row("api-plan-production"), _row("sales-tax", price_status="unknown", unit_price_usd="", monthly_usd="", annual_usd="")]
    )
    values = {"grant_annual_usd": "2000", "grant_remaining_usd": "1900", "grant_expiry_date": "2027-11-30", "months_remaining": "12"}
    account = _write_account(tmp_path / "account.csv", {**values, "existing_monthly_spend_usd": "0"})

    assert any("sales-tax" in reason for reason in build_report(estimate, account).grant.blocked_reasons)


def test_non_numeric_account_value_is_rejected(tmp_path: Path) -> None:
    estimate = _write_estimate(tmp_path / "estimate.csv", [_row("api-plan-production")])
    account = _write_account(tmp_path / "account.csv", {"grant_annual_usd": "2000", "grant_remaining_usd": "about 1900"})

    with pytest.raises(EstimateError) as error:
        build_report(estimate, account)

    assert any("grant_remaining_usd" in problem for problem in error.value.problems)


def test_cli_prints_valid_totals_and_the_budget_gate(tmp_path: Path, account_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    estimate = _write_estimate(tmp_path / "estimate.csv", [_row("api-plan-production")])

    exit_code = main(["--estimate", str(estimate), "--account", str(account_path)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "CSV valid" in output
    assert "baseline" in output and "13.14" in output and "157.68" in output
    assert "Budget gate: BLOCKED" in output


def test_cli_reports_problems_and_fails_for_an_invalid_csv(tmp_path: Path, account_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    estimate = _write_estimate(tmp_path / "estimate.csv", [_row("api-plan-production", monthly_usd="1.0000")])

    exit_code = main(["--estimate", str(estimate), "--account", str(account_path)])

    assert exit_code == 1
    assert "api-plan-production: monthly_usd" in capsys.readouterr().err


def test_cli_write_recomputes_stored_costs(tmp_path: Path, account_path: Path) -> None:
    estimate = _write_estimate(tmp_path / "estimate.csv", [_row("api-plan-production", monthly_usd="", annual_usd="")])

    assert main(["--estimate", str(estimate), "--account", str(account_path), "--write"]) == 0

    with estimate.open(newline="") as handle:
        record = next(csv.DictReader(handle))
    assert (record["monthly_usd"], record["annual_usd"]) == ("13.1400", "157.6800")
    assert main(["--estimate", str(estimate), "--account", str(account_path)]) == 0


def test_unverified_price_is_counted_but_flagged(tmp_path: Path, account_path: Path) -> None:
    estimate = _write_estimate(tmp_path / "estimate.csv", [_row("redis-production", price_status="unverified")])

    baseline = build_report(estimate, account_path).scenario("baseline")

    assert baseline.total_monthly == Decimal("13.14")
    assert baseline.unverified_ids == ("redis-production",)


def test_unverified_baseline_price_blocks_the_grant_check(tmp_path: Path) -> None:
    estimate = _write_estimate(tmp_path / "estimate.csv", [_row("redis-production", price_status="unverified")])
    values = {"grant_annual_usd": "2000", "grant_remaining_usd": "1900", "grant_expiry_date": "2027-11-30", "months_remaining": "12"}
    account = _write_account(tmp_path / "account.csv", {**values, "existing_monthly_spend_usd": "0"})

    assert any("unverified" in reason and "redis-production" in reason for reason in build_report(estimate, account).grant.blocked_reasons)


COST_DIR = Path(__file__).resolve().parents[2] / "infra" / "azure" / "cost"


def test_shipped_estimate_is_valid_and_covers_the_selected_inventory() -> None:
    report = build_report(COST_DIR / "estimate.csv", COST_DIR / "account-inputs.csv")
    with (COST_DIR / "estimate.csv").open(newline="") as handle:
        baseline_ids = {record["id"] for record in csv.DictReader(handle) if record["scenario"] == "baseline"}

    required = {
        *(f"api-plan-{env}" for env in ("staging", "production")),
        *(f"pg-compute-{env}" for env in ("staging", "production")),
        *(f"redis-{env}" for env in ("staging", "production")),
        *(f"pg-firewall-allowlist-{env}" for env in ("staging", "production")),
        *(f"swa-{app}-{env}" for app in ("portal", "booking") for env in ("staging", "production")),
        "acr-basic",
        "public-dns-zone",
        "blob-storage-production",
        "key-vault-production",
        "log-analytics-ingestion",
        "internet-egress",
    }
    assert required <= baseline_ids
    assert not {record_id for record_id in baseline_ids if record_id.startswith("private-endpoint-")}
    assert {"shared-app-service-plan", "container-apps-separate-environments", "container-apps-shared-environment", "private-endpoints", "shared-redis"} <= set(
        report.scenarios
    )


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1"])
def test_non_finite_or_negative_number_is_rejected(tmp_path: Path, account_path: Path, value: str) -> None:
    estimate = _write_estimate(tmp_path / "estimate.csv", [_row("api-plan-production", unit_price_usd=value)])

    with pytest.raises(EstimateError) as error:
        build_report(estimate, account_path)

    assert any("api-plan-production" in problem and "unit_price_usd" in problem for problem in error.value.problems)


def test_compact_date_is_rejected(tmp_path: Path, account_path: Path) -> None:
    estimate = _write_estimate(tmp_path / "estimate.csv", [_row("api-plan-production", checked_date="20261110")])

    with pytest.raises(EstimateError) as error:
        build_report(estimate, account_path)

    assert any("checked_date" in problem for problem in error.value.problems)


def test_row_with_missing_or_extra_fields_is_rejected(tmp_path: Path, account_path: Path) -> None:
    estimate = _write_estimate(tmp_path / "estimate.csv", [_row("api-plan-production")])
    with estimate.open("a") as handle:
        handle.write("short-row,selected,baseline\n")

    with pytest.raises(EstimateError) as error:
        build_report(estimate, account_path)

    assert any("line 3" in problem and "fields" in problem for problem in error.value.problems)


def test_negative_account_number_is_rejected(tmp_path: Path) -> None:
    estimate = _write_estimate(tmp_path / "estimate.csv", [_row("api-plan-production")])
    account = _write_account(tmp_path / "account.csv", {"grant_annual_usd": "2000", "months_remaining": "-3"})

    with pytest.raises(EstimateError) as error:
        build_report(estimate, account)

    assert any("months_remaining" in problem for problem in error.value.problems)


def test_cli_write_reports_missing_columns_instead_of_crashing(tmp_path: Path, account_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    estimate = tmp_path / "estimate.csv"
    estimate.write_text("id,inclusion\napi-plan-production,selected\n")

    assert main(["--estimate", str(estimate), "--account", str(account_path), "--write"]) == 1
    assert "missing columns" in capsys.readouterr().err
