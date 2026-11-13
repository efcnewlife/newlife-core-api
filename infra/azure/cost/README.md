# Azure cost estimate

[繁體中文](README.zh-TW.md) · Chinese CSV: `estimate.zh-TW.csv`

`estimate.csv` is the itemized Canada Central (`canadacentral`) cost estimate for the [Azure deployment plan](../../../docs/azure-deployment.md) ([ADR 0039](../../../docs/adr/0039-azure-deployment-and-release-direction.md)). Open it in any spreadsheet.

It uses public list prices checked on 2026-11-10 for Canada East and rechecked for Canada Central on 2026-11-12 with the public [Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices) (pay-as-you-go, USD, 730 hours per month, no reservations). The region moved because PostgreSQL provisioning is restricted in Canada East for the grant subscription ([ADR 0039](../../../docs/adr/0039-azure-deployment-and-release-direction.md)). No Azure account was accessed.

Only PostgreSQL prices changed: B1ms compute USD 0.0204 to 0.0185/hour, storage USD 0.138 to 0.1265/GB-month, and backup USD 0.114 to 0.105/GB-month. Every other Canada East row has the same Canada Central price and was recorded as checked; the `Global` rows (Private Endpoint, Load Balancer) do not depend on the region. A human checks the account facts and creates every Azure resource.

## Totals

| Plan | USD/month | USD/year |
| --- | ---: | ---: |
| **Selected** | **127.48** | **1,529.78** |
| Option: staging shares the production Redis (under consideration) | 115.07 | 1,380.86 |
| Rejected: one App Service Plan for both environments | 114.34 | 1,372.10 |
| Rejected: Azure Cache for Redis C0 | 146.46 | 1,757.54 |
| Rejected for cost: original design with four Private Endpoints | 158.38 | 1,900.58 |
| Rejected: Container Apps, one shared environment | 231.28 | 2,775.38 |
| Rejected: Container Apps, separate environments | 329.83 | 3,957.98 |

Against the USD 2,000/year grant, the selected plan leaves about USD 470/year, before tax and before spend from other resources on the grant.

## How to read the CSV

- Each row: `quantity` x `unit_price_usd` = `monthly_usd`, and `monthly_usd` x 12 = `annual_usd`.
- `status`: `selected` is in the selected total. `option` rows belong to the alternative named in `option`; the matching `total-<option>` row shows that plan's total. `excluded` and `outside Azure` rows are never counted. `total` rows are the sums.
- `price_status`: `list price` is the official public price. `needs check` means the price exists, but the billing behavior is not confirmed. `free` is a documented zero charge. `unknown` has a blank price and is not counted; it is not zero.
- Free amounts are applied only where they belong to one resource (PostgreSQL backup, ACR storage). Account-wide free amounts (egress, logs, alerts, emails, Static Web Apps bandwidth) are not applied, because other resources may already use them.

## Before creating paid resources (human only)

- Check the remaining grant, its end date, and current spend from other resources (Azure Sponsorships page and Cost Management).
- Confirm the Managed Redis B0 price in the [pricing calculator](https://azure.microsoft.com/en-us/pricing/calculator/). The two Redis rows say `needs check`: one node for staging, two nodes for production HA.
- Confirm Canada Central supports PostgreSQL 18 `Standard_B1ms`, Managed Redis `Balanced_B0`, and Linux App Service `B1` in the grant subscription. This is still pending.
- Find out whether tax applies. That row is `unknown`.
- Pick the Static Web Apps region. There is no Canada region; the CSV uses `eastus2`.
- Network: there are no Private Endpoints. PostgreSQL allows only the App Service outbound IPs plus your own IP, with TLS. Managed Redis has no IP allowlist, so it is open to all networks and protected by its access key or Entra login and TLS.

If the remaining grant does not cover the selected total plus other spend, stop and revisit the plan before creating resources.
