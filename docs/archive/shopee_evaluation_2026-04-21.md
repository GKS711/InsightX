# 蝦皮模式可行性評估與放棄紀錄

> **日期**：2026-04-21
> **版本**：InsightX v3.0.0
> **決策**：正式放棄蝦皮商品模式，專案回歸 2 模式（Google Maps + YouTube）
> **紀錄位置**：此檔（repo 追蹤，永久保留）；CLAUDE.md 底部保留短摘要並連回此檔

## 決策摘要

使用者的四條件組合讓蝦皮 TW 爬蟲無可行路徑：

1. **完全免費**（不付費服務、不額外申請 key）
2. **客戶自架**（不在我方伺服器代跑）
3. **使用者端免人類驗證**（不讓終端使用者解 CAPTCHA）
4. **每天 20+ 商品**（不能太慢）

2025+ 的蝦皮 TW WAF（`AF-AC-ENC-DAT` 動態加密 header、`error=90309999`）把符合這四條件的所有路徑堵死。

## 評估過的 8 條路線（皆不可行）

| 路線 | 測試結果 | 不可行原因 |
|------|----------|-------------|
| **Chrome Cache**（讀使用者 Chrome 已驗證 cookies） | 技術可行 | 違反條件 3：每商品要先在使用者端完成人類驗證一次 |
| **Playwright persistent context** | 新 profile 直接被擋 | 必須手動養 cookies，違反客戶自架可行性 |
| **Mobile App API** | `error=90309999` | 需要 AF-AC-ENC-DAT 動態 header |
| **curl_cffi**（chrome131 impersonate） | HTTP/2 指紋被擋 | 同上，header 過不了 |
| **Scrapeless**（唯一官方支援 shopee.tw） | 技術可行 | 使用者不想另外申請 key；付費（\$29-49/月） |
| **ScraperAPI** | `ultra_premium=true` 才能過 | 25 credits/req，trial 7 天後即付費，違反條件 1 |
| **ScrapingBee** | 不產生 AF-AC 編碼 header | 直打 API 仍被擋 |
| **Apify** | 絕大多數 actor 不支援 TW | 即使有也非免費方案 |

## 已清理的專案內容（2026-04-21）

### 刪除的檔案
- `src/services/shopee_scraper.py`（~1,300 行）
- `probe_shopee.py`、`debug_shopee_probe.py`
- `.shopee_cache/`（整個資料夾）
- `tests/test_shopee_smoke.py`
- `scripts/shopee_refresh_cache.js`
- `src/static/index.html.v3-backup-20260419`（含蝦皮 Tab 的舊版前端快照）

### 移除的依賴（`pyproject.toml`）
- `playwright`
- `apify-client`
- `curl_cffi`

### 移除的環境變數
- `SHOPEE_*`、`SCRAPELESS_*`、`SCRAPERAPI_*`、`SCRAPINGBEE_*`、`APIFY_*`

### 清理的檔案
- `src/main.py`：移除 CORS（原為蝦皮 CDN 而設）
- `src/api/routes.py`：移除 shopee 分支、Chrome Bridge endpoints
- `src/services/scraper_service.py`：移除 shopee import 與 dispatch
- `src/services/llm_service.py`：9 個方法移除 shopee 分支（702 → 505 行）
- `src/static/index.html`：移除第 3 Tab、MODE_CONFIG.shopee、label maps
- `CLAUDE.md`：重寫成 v3.0.0 無蝦皮版本（在 repo 外，gitignored）

## 未來若要重啟的檢查清單

1. **先確認四條件是否鬆動**：
   - 付費方案可接受嗎？
   - 使用者願意每商品解人類驗證嗎？
   - 客戶願意把蝦皮抓取放在我方伺服器嗎？

2. **若付費可接受**：
   - 優先評估 [Scrapeless](https://scrapeless.com) starter plan（\$29-49/月）— 唯一官方支援 `shopee.tw`
   - 或走 [Shopee Open Platform](https://open.shopee.com) 官方 API — 需認證賣家身份

3. **實作前先跑 WAF 實況 probe**：蝦皮風控會隨時間變化，任何重啟都要先驗證當下狀況再投入開發。

## 版本標記

- v3.0.0 保留版本號（對齊 git 歷史）
- `CLAUDE.md` 與 `pyproject.toml` 均標註 v3.0.0
- 此檔是唯一的 tracked 評估紀錄
