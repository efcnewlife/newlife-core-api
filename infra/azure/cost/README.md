# Azure inventory and cost estimate

Itemized Canada East estimate for the [Azure deployment plan](../../../docs/azure-deployment.md) ([ADR 0039](../../../docs/adr/0039-azure-deployment-and-release-direction.md)). It lists selected, shared, variable, free, unknown, excluded, outside-grant, and rejected alternative items.

| File | Purpose |
| --- | --- |
| `estimate.csv` | Every resource and assumption, one row each |
| `account-inputs.csv` | Account facts the operator collects from the Azure portal; blank means not yet supplied |
| `../../../scripts/azure_cost_estimate.py` | Offline validator and calculator (standard library only) |

## Execution boundary

Agents may author and review Bicep, source code, CSV estimates, workflow definitions, operator scripts, documentation, and offline tests only. Every Azure account or resource operation must be performed by a human operator. Agents must not sign in to Azure, inspect the live account, run Azure what-if/apply, create/update/delete resources, change DNS/RBAC/secrets/firewalls, push/pull images through ACR, deploy apps, run migrations against Azure databases, restore data, or trigger Azure-affecting workflows. Main/tag CI may validate/build and retain artifacts outside Azure, but must not automatically perform Azure operations. Do not give unattended CI Azure credentials. Public documentation/pricing research and local tests without live Azure access are allowed. Human execution and live verification must be explicitly attributed and must not be claimed complete without operator-supplied evidence.

The agent used public list prices only. No Azure account was inspected. Every live grant, capacity, and pricing check below is still pending.

## Commands

Run from the repository root.

```bash
# Validate and print totals (no network access)
uv run python scripts/azure_cost_estimate.py

# After editing quantities, usage, or prices: recompute monthly_usd and annual_usd, then validate
uv run python scripts/azure_cost_estimate.py --write

# Offline tests for the validator and the shipped CSV
uv run pytest tests/scripts/test_azure_cost_estimate.py -q
```

`python3 scripts/azure_cost_estimate.py` also works without uv (Python 3.14+).

Success starts with `CSV valid: parsed and recomputed offline (no Azure access).` and ends with a `Budget gate:` line. Exit code `0` means the CSV is valid. Exit code `1` prints `CSV invalid:` and one line per problem, each naming the row id.

The budget gate stays `BLOCKED` while any account input is blank, any baseline price is `unknown` or `unverified`, or the forecast exceeds the grant. Do not create paid resources while it says `BLOCKED`.

## Results on 2026-11-10

| Scenario | USD/month | USD/year | Status |
| --- | ---: | ---: | --- |
| **baseline** (selected fixed + variable) | **130.97** | **1,571.64** | Selected |
| shared-redis | 118.56 | 1,422.72 | Under consideration |
| shared-app-service-plan | 117.83 | 1,413.96 | Rejected |
| azure-cache-for-redis-c0 | 149.95 | 1,799.40 | Rejected |
| private-endpoints (original design) | 161.87 | 1,942.44 | Rejected for cost |
| container-apps-shared-environment | 234.78 | 2,817.31 | Rejected |
| container-apps-separate-environments | 333.33 | 3,999.91 | Rejected |

The baseline is USD 125.69/month fixed plus USD 5.28/month of variable usage assumptions. The nominal headroom is **USD 428.36/year** against a USD 2,000 grant, before tax and before any spend from other resources on the grant.

Network decision (2026-11-10, user): the baseline has no Private Endpoints, Private DNS zones, or VNet integration. The `private-endpoints` scenario adds them back for comparison (USD 30.90/month).

- PostgreSQL uses public access with a firewall allowlist: every App Service possible outbound IP plus explicit operator IPs, with TLS. App Service outbound IPs are shared with other customers on the same deployment unit and can change, so the allowlist admits more than this app. Password and TLS remain the main protection. A fixed outbound IP would need a NAT Gateway, which costs more than the Private Endpoints it replaces.
- Managed Redis has no IP allowlist. Public access is either open to all networks or off. Both instances are open to all networks and rely on access keys or Entra authentication with TLS.
- `shared-redis` (staging uses the production instance) is under consideration, not selected. Managed Redis has database 0 only, so staging would need key prefixes, and staging tests would share production memory, rate limits, and authentication state.

Compared with the plan's original USD 1,876/year, the CSV also adds metric alerts, Static Web Apps bandwidth, and alert emails. It charges logs and egress without assuming the shared free allowances are unused.

Findings from the public price list:

- Static Web Apps has no Canada region. The CSV uses `eastus2` as a placement-exception candidate; the operator picks the region.
- A new Container Apps `Environment Management Hour` meter (USD 0.10/hour, effective 2026-11-01) appears in Canada East. It is marked `unverified` in the rejected Container Apps scenarios. Without it they would cost about USD 187 and USD 162 per month.
- Managed Redis is priced per node. Staging is assumed to bill one node and production with HA two nodes. Both rows are `unverified` until the calculator confirms this.

## Column reference

| Column | Meaning |
| --- | --- |
| `id` | Unique row id, referenced by `replaces` and `allowance_group` |
| `inclusion` | `selected` (fixed recurring), `variable` (usage assumption), `alternative` (rejected plan), `excluded`, `outside_grant` (not billed through Azure), or `allowance` (free included quantity) |
| `scenario` | `baseline` for selected and variable rows; the plan name for alternative rows; blank otherwise |
| `environment` | `staging`, `production`, or `shared` |
| `category`, `resource`, `service`, `sku`, `region` | What the row is and where it runs |
| `quantity` | Number of billed units (nodes, endpoints, apps) |
| `usage_per_month` | Billable amount per unit per month, in `unit` (730 hours per month) |
| `unit` | Billing unit, such as `hour`, `GB-month`, or `10K operations` |
| `unit_price_usd` | USD list price per `unit`. Blank when the price is unknown; never 0 for unknown |
| `allowance_group`, `allowance_per_month` | Free included quantity used by this row, taken from the `allowance` row named in the group |
| `monthly_usd`, `annual_usd` | Computed by `--write`: `max(quantity x usage - allowance, 0) x unit_price`, rounded to 4 decimals; annual is monthly x 12 |
| `price_status` | `public` (official list price), `unverified` (list price exists but billing behavior or availability is not confirmed; counted), `free` (documented no charge; price 0), or `unknown` (no price; not counted) |
| `replaces` | For alternative rows: the baseline row ids that the plan replaces, separated by `;` |
| `checked_date` | Date the price was checked (YYYY-MM-DD) |
| `source_url` | Official public source |
| `notes` | Retail meter name, assumptions, and caveats |

Rules the validator enforces:

- Totals are recomputed from quantity, usage, allowance, and unit price. A stored value that disagrees is an error.
- Unknown prices must be blank and are listed separately; they are never added as 0.
- Alternative scenarios are the baseline minus `replaces` rows plus the scenario's rows. They never change the baseline.
- An allowance can be applied only up to its limit across all rows in a scenario. Only per-resource allowances (PostgreSQL backup, ACR Basic storage) are applied. Shared free allowances (egress, Log Analytics, metric alerts, emails, Static Web Apps bandwidth) are not applied, because other resources on the account may already use them.

Prices come from the public [Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices) and the pricing pages in `source_url`. The meter name in `notes` lets you find the same line in the calculator. Example check:

```bash
curl -s -G 'https://prices.azure.com/api/retail/prices' \
  --data-urlencode "\$filter=serviceName eq 'Azure App Service' and armRegionName eq 'canadaeast' and skuName eq 'B1' and priceType eq 'Consumption'"
```

## Operator checklist (human only)

The agent does not perform any of these steps. This ticket creates no Azure resources.

1. **Open the CSV** in a spreadsheet. Filter `scenario` = `baseline` and check `environment` staging, production, and shared. Confirm App Service Plans, PostgreSQL with its firewall allowlist, Redis, ACR, four Static Web Apps, DNS, Blob, Key Vault, logs, and egress are present. Alternative and excluded rows are not in the baseline.
2. **Check each row** for region, SKU, quantity, USD unit price, and `checked_date`. Open `source_url`, or find the `notes` meter in the [Azure pricing calculator](https://azure.microsoft.com/en-us/pricing/calculator/). Confirm the two `unverified` Redis rows in the calculator.
3. **Collect account facts** in the Azure portal and fill `account-inputs.csv`. Do not put credentials, tokens, or personal data in either CSV.

   | Key | Where to find it |
   | --- | --- |
   | `grant_annual_usd` | Confirm the user-reported 2000 in the grant or sponsorship page |
   | `grant_remaining_usd`, `grant_expiry_date` | Grant or sponsorship balance page |
   | `months_remaining` | Months from today to the expiry date; round a part month up |
   | `existing_monthly_spend_usd` | Cost Management, current monthly spend of everything else on the grant |
   | `spending_limit_behavior` | Subscription spending-limit setting and what happens when credit runs out |
   | `eligible_services_confirmed` | Grant terms: all selected services are covered |
   | `canada_east_capacity_confirmed` | Portal create blades or quota page for Linux B1, PostgreSQL B1ms, Managed Redis B0 with and without HA |
   | `static_web_apps_region` | Region you choose for the four Static Web Apps |
   | `public_dns_zone_billed_to_grant` | Cost Management, existing `efcnewlife.com` zone charge |
   | `defender_for_cloud_plans` | Defender for Cloud, environment settings |
   | `free_allowances_used_elsewhere` | Cost Management usage for egress, Log Analytics, metric alerts, and emails |
   | `tax_treatment` | Invoice or billing profile; then replace the unknown tax row with a price |

4. **Recompute locally** after any edit: `uv run python scripts/azure_cost_estimate.py --write`. Confirm `CSV valid`, and that the baseline total matches your calculator total within rounding.
5. **Compare** the remaining grant with existing spend plus the baseline forecast. The script prints `Account headroom` once the account inputs are filled. If any row is still unknown or unverified, or the forecast exceeds the grant (or USD 2,000/year), stop before creating paid resources and report the gap on the issue.

Provisioning order for later tickets, also human only: shared ACR and identities, then PostgreSQL, Redis, Storage, and Key Vault, then App Service Plans and Web Apps, then the PostgreSQL firewall allowlist from the Web Apps' possible outbound IPs, then the Static Web Apps, then DNS, TLS, and monitoring.

### Done when

- [ ] The CSV opens and parses, and `uv run python scripts/azure_cost_estimate.py` reproduces the baseline total.
- [ ] Actual grant data, remaining unknown or unverified items, and budget headroom are recorded. No Azure resources were created for this ticket.

### If something does not match

Post the row id, the source, and the difference on the issue, and ask for a CSV correction. Do not create resources first and estimate later.

After your review, reply on the issue with the CSV version (commit), environment, time of the check, and the result. Do not paste secrets or personal data.
