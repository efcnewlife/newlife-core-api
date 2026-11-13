# Azure 成本預估

[English](README.md)

`estimate.zh-TW.csv` 是 [Azure 部署計畫](../../../docs/azure-deployment.md)（[ADR 0039](../../../docs/adr/0039-azure-deployment-and-release-direction.md)）在加拿大中部（Canada Central，`canadacentral`）的逐項成本預估，用任何試算表都能打開。英文版是 `estimate.csv`，兩份數字相同。

價格是官方公開牌價：2026-11-10 查加拿大東部，2026-11-12 用公開的 [Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices) 重查加拿大中部。隨用隨付、美金、每月 730 小時、不含預購折扣。改區域是因為這個額度的訂用帳戶在加拿大東部不能建立 PostgreSQL（[ADR 0039](../../../docs/adr/0039-azure-deployment-and-release-direction.md)）。這份預估沒有登入或查詢任何 Azure 帳號。

只有 PostgreSQL 的價格變了：B1ms 運算從每小時 USD 0.0204 變 0.0185，儲存從每 GB-月 USD 0.138 變 0.1265，備份從每 GB-月 USD 0.114 變 0.105。其他原本在加拿大東部的項目，在加拿大中部價格一樣，已記錄為查過；`Global` 的項目（Private Endpoint、Load Balancer）不受區域影響。帳號資料的確認和所有 Azure 資源的建立，都由人來做。

## 總額

| 方案 | 每月 USD | 每年 USD |
| --- | ---: | ---: |
| **已選定** | **127.48** | **1,529.78** |
| 比較方案：staging 共用 production 的 Redis（考慮中） | 115.07 | 1,380.86 |
| 不採用：兩個環境共用一個 App Service Plan | 114.34 | 1,372.10 |
| 不採用：Azure Cache for Redis C0 | 146.46 | 1,757.54 |
| 因成本不採用：原設計（4 個 Private Endpoint） | 158.38 | 1,900.58 |
| 不採用：Container Apps，共用一個環境 | 231.28 | 2,775.38 |
| 不採用：Container Apps，兩個環境分開 | 329.83 | 3,957.98 |

以每年 USD 2,000 的額度來看，已選定方案一年約剩 USD 470。這還沒算稅，也沒算這筆額度上其他資源的花費。

## CSV 怎麼看

- 每一行：`數量` × `單價 (USD)` = `月費 (USD)`，`月費 (USD)` × 12 = `年費 (USD)`。
- `狀態`：
  - `已選定`：算進已選定方案的總額。
  - `比較方案`：屬於 `比較方案` 欄寫的那個方案；對應的 `total-<方案名稱>` 那一行是它的總額。
  - `不採用` 和 `不在 Azure 帳單`：都不計入。
  - `總計`：加總的結果。
- `價格狀態`：
  - `官方牌價`：官方公開價格。
  - `待確認`：有價格，但計費方式還沒確認。
  - `免費`：官方文件寫明不收費。
  - `未知`：價格空白，不計入總額。空白不代表 0。
- 免費額度只套用在專屬於單一資源的項目（PostgreSQL 備份、ACR 儲存）。整個帳戶共用的免費額度不套用，因為可能已被其他資源用掉，例如對外流量、日誌、警示、Email、Static Web Apps 流量。

## 建立付費資源前要確認（只能由人來做）

- 查剩餘額度、到期日，以及這筆額度上其他資源目前的花費（Azure Sponsorships 頁面和 Cost Management）。
- 在[價格計算機](https://azure.microsoft.com/en-us/pricing/calculator/)確認 Managed Redis B0 的價格。兩行 Redis 標示 `待確認`：staging 算 1 個節點，production 有 HA，算 2 個節點。
- 確認加拿大中部在這個額度的訂用帳戶支援 PostgreSQL 18 `Standard_B1ms`、Managed Redis `Balanced_B0`、Linux App Service `B1`。這一項還沒確認。
- 確認有沒有稅。稅那一行是 `未知`。
- 選 Static Web Apps 的區域。沒有加拿大區域，CSV 先用 `eastus2`。
- 網路：沒有 Private Endpoint。PostgreSQL 只允許 App Service 的對外 IP 加上你自己的 IP，並且要用 TLS。Managed Redis 沒有 IP 白名單，所以對所有網路開放，靠存取金鑰或 Entra 登入加 TLS 保護。

如果剩餘額度付不起「已選定總額 + 其他花費」，先停下來調整方案，再建立資源。
