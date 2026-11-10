# Azure cost estimate

`estimate.csv` is the itemized Canada East cost estimate for the [Azure deployment plan](../../../docs/azure-deployment.md) ([ADR 0039](../../../docs/adr/0039-azure-deployment-and-release-direction.md)). Open it in any spreadsheet.

It uses public list prices checked on 2026-11-10 (pay-as-you-go, USD, 730 hours per month, no reservations). No Azure account was accessed. A human checks the account facts and creates every Azure resource.

## Totals

| Plan | USD/month | USD/year |
| --- | ---: | ---: |
| **Selected** | **130.98** | **1,571.78** |
| Option: staging shares the production Redis (under consideration) | 118.57 | 1,422.86 |
| Rejected: one App Service Plan for both environments | 117.84 | 1,414.10 |
| Rejected: Azure Cache for Redis C0 | 149.96 | 1,799.54 |
| Rejected for cost: original design with four Private Endpoints | 161.88 | 1,942.58 |
| Rejected: Container Apps, one shared environment | 234.78 | 2,817.38 |
| Rejected: Container Apps, separate environments | 333.33 | 3,999.98 |

Against the USD 2,000/year grant, the selected plan leaves about USD 428/year, before tax and before spend from other resources on the grant.

## How to read the CSV

- Each row: `quantity` x `unit_price_usd` = `monthly_usd`, and `monthly_usd` x 12 = `annual_usd`.
- `status`: `selected` is in the selected total. `option` rows belong to the alternative named in `option`; the matching `total-<option>` row shows that plan's total. `excluded` and `outside Azure` rows are never counted. `total` rows are the sums.
- `price_status`: `list price` is the official public price. `needs check` means the price exists, but the billing behavior is not confirmed. `free` is a documented zero charge. `unknown` has a blank price and is not counted; it is not zero.
- Free amounts are applied only where they belong to one resource (PostgreSQL backup, ACR storage). Account-wide free amounts (egress, logs, alerts, emails, Static Web Apps bandwidth) are not applied, because other resources may already use them.

## Before creating paid resources (human only)

- Check the remaining grant, its end date, and current spend from other resources (Azure Sponsorships page and Cost Management).
- Confirm the Managed Redis B0 price in the [pricing calculator](https://azure.microsoft.com/en-us/pricing/calculator/). The two Redis rows say `needs check`: one node for staging, two nodes for production HA.
- Find out whether tax applies. That row is `unknown`.
- Pick the Static Web Apps region. There is no Canada region; the CSV uses `eastus2`.
- Network: there are no Private Endpoints. PostgreSQL allows only the App Service outbound IPs plus your own IP, with TLS. Managed Redis has no IP allowlist, so it is open to all networks and protected by its access key or Entra login and TLS.

If the remaining grant does not cover the selected total plus other spend, stop and revisit the plan before creating resources.
