"""
InsightX Google Maps 評論爬蟲服務 v13.1

架構：純 Serper API，零瀏覽器。
  1. 店名解析：HTTP redirect → Serper /search（短網址用）
  2. 評論爬取：Serper /maps + /reviews

不會開啟任何瀏覽器視窗，完全在背景執行。

v13.1 變更（v13 → v13.1）：
  - 完全移除 UC headless（Chrome 147 崩潰，且 headless 被 Google 偵測無法取得評論）
  - 新增 Serper /search 解析短網址（搜尋短網址本身，Google 會回傳店家資訊）
  - 100% API-based，不依賴任何瀏覽器
"""

import asyncio
import json
import os
import urllib.request
import urllib.parse
import re
import logging
import html as html_module

from dotenv import load_dotenv
load_dotenv()

from src.services.youtube_scraper import YouTubeScraper, is_youtube_url

logger = logging.getLogger(__name__)

# P3.12-R2 reverted（2026-04-23 使用者澄清）：原本想在後端 cap 50，但使用者澄清
# 「照樣抓所有 google 評論，只是 §04 UI 那邊有問題」。後端要餵給 LLM 的是「全部
# 含文字評論」（max_pages=20 仍是安全上限，實際被 Serper 自然 EOF 決定），
# 顯示限制改在前端 ReviewsSection 用 MAX_REVIEWS_DISPLAY = 50 控制。


class ScraperService:
    def __init__(self):
        self._serper_key = os.getenv("SERPER_API_KEY", "")
        self._youtube = YouTubeScraper()

    # ══════════════════════════════════════════════════════════════
    #  公開介面
    # ══════════════════════════════════════════════════════════════

    async def scrape_url(self, url: str) -> dict:
        """
        主入口：根據 URL 自動選擇爬蟲策略。
        YouTube → YouTube Data API v3（單支影片留言）
        Google Maps → Serper API（店家評論）
        其他 URL → 簡易 HTTP 爬取
        """
        # v2.0 新增：YouTube 影片留言分析
        if is_youtube_url(url):
            return await self._youtube.scrape_video(url)

        if "google.com/maps" in url or "goo.gl" in url or "maps.app" in url or "share.google" in url:
            return await self._scrape_google_maps_reviews(url)
        return await self._scrape_generic_url(url)

    async def resolve_store_name(self, url: str) -> str:
        """
        從 Google Maps URL 解析店家名稱。
        1. 如果是完整 URL，直接從 URL path 提取
        2. HTTP redirect（快速，部分短網址可用）
        3. Serper /search 搜尋短網址（Google 會回傳對應的店家）
        """
        # ── 方法 0：從完整 URL 提取 ─────────────────────────────
        m = re.search(r'/maps/place/([^/@?&]+)', url)
        if m:
            name = urllib.parse.unquote_plus(m.group(1)).replace('+', ' ').strip()
            if name and len(name) > 1:
                print(f"[resolve] ✅ 從 URL 提取店名：{name}")
                return name

        # ── 方法 1：HTTP redirect ───────────────────────────────
        print("[resolve] 嘗試 HTTP redirect...")
        name = await self._resolve_via_http(url)
        if name:
            return name

        # ── 方法 2：Serper /search ──────────────────────────────
        if self._serper_key:
            print("[resolve] 嘗試 Serper /search...")
            name = await self._resolve_via_serper_search(url)
            if name:
                return name

        print("[resolve] ❌ 無法解析店名")
        return ""

    # ══════════════════════════════════════════════════════════════
    #  Google Maps 爬蟲主流程
    # ══════════════════════════════════════════════════════════════

    async def _scrape_google_maps_reviews(self, url: str) -> dict:
        """Google Maps 評論爬蟲 v13.1。純 Serper API。"""

        if not self._serper_key:
            print("[scraper] ❌ SERPER_API_KEY 未設定，無法爬取評論")
            return {"url": url, "raw_text": "", "store_name": "", "status": "no_api_key"}

        # ── Step 1：解析店名 ─────────────────────────────────────
        store_name = await self.resolve_store_name(url)
        print(f"[scraper] 店名：{store_name!r}")

        if not store_name:
            print("[scraper] ❌ 無法解析店名，嘗試直接用短網址搜尋...")
            # 最後一招：直接用短網址當搜尋關鍵字
            store_name = url

        # ── Step 2：Serper API 爬取評論 ──────────────────────────
        print(f"[scraper] 🚀 Serper API 開始爬取...")
        try:
            result = await self._serper_scrape(store_name, url)
            review_count = result.get("review_count", 0)
            raw_text = result.get("raw_text", "")
            print(f"[scraper] Serper 結果：{review_count} 則評論，{len(raw_text)} 字元")

            if review_count > 0 and raw_text:
                result["status"] = "success"
                self._save_reviews_md(
                    result.get("store_name", store_name), url,
                    result.get("reviews_structured", []),
                    result.get("maps_data"),
                    "Serper"
                )
                return result
            else:
                print("[scraper] ⚠️ Serper 無評論結果")
        except Exception as e:
            print(f"[scraper] ⚠️ Serper 失敗：{e}")
            import traceback
            traceback.print_exc()

        return {"url": url, "raw_text": "", "store_name": store_name, "status": "no_reviews"}

    # ══════════════════════════════════════════════════════════════
    #  店名解析
    # ══════════════════════════════════════════════════════════════

    async def _resolve_via_http(self, url: str) -> str:
        """
        HTTP 解析短網址。多種 User-Agent 策略嘗試：
        1. requests + desktop UA（follow redirects）
        2. requests + mobile UA（Google 可能返回不同 redirect）
        3. requests + curl UA（最簡 client，可能觸發 301）
        4. 解析落地頁 HTML
        """
        import requests as req_lib

        user_agents = [
            ("desktop", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
            ("mobile", "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"),
            ("curl", "curl/8.0"),
        ]

        def try_resolve(short_url: str) -> str:
            last_html = ""

            for ua_name, ua_str in user_agents:
                try:
                    print(f"[resolve-http] 嘗試 {ua_name} UA...")
                    resp = req_lib.get(
                        short_url,
                        headers={"User-Agent": ua_str, "Accept-Language": "zh-TW,zh;q=0.9"},
                        timeout=10,
                        allow_redirects=True
                    )
                    final = resp.url
                    print(f"[resolve-http]   → {resp.status_code} {final[:120]}")

                    if "google.com/maps/place" in final:
                        return final

                    # 記錄最後的 HTML 供解析
                    if len(resp.text) > len(last_html):
                        last_html = resp.text
                except Exception as e:
                    print(f"[resolve-http]   {ua_name} 失敗：{e}")

            # 所有 UA 都沒拿到 maps/place URL，嘗試解析 HTML
            if last_html:
                print(f"[resolve-http] 嘗試從 HTML（{len(last_html)} bytes）解析...")
                name = self._extract_store_name_from_html(last_html)
                if name:
                    return f"NAME:{name}"

            return ""

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(try_resolve, url),
                timeout=30.0
            )
            if not result:
                return ""

            if result.startswith("NAME:"):
                name = result[5:]
                print(f"[resolve-http] ✅ 從 HTML 提取店名：{name}")
                return name

            m = re.search(r'/maps/place/([^/@?&]+)', result)
            if m:
                name = urllib.parse.unquote_plus(m.group(1)).replace('+', ' ').strip()
                if name and len(name) > 1:
                    print(f"[resolve-http] ✅ 從 URL 提取店名：{name}")
                    return name
        except asyncio.TimeoutError:
            print("[resolve-http] ⚠️ 超時")
        return ""

    def _extract_store_name_from_html(self, html: str) -> str:
        """從 redirect 頁面 HTML 中提取店名"""

        # 1. <title>
        title_m = re.search(r'<title>([^<]+)</title>', html)
        if title_m:
            title = title_m.group(1).strip()
            print(f"[html-parse] title：{title[:80]}")
            if self._is_valid_store_name(title):
                return title.split(" - ")[0].split(" · ")[0].strip()

        # 2. og:title
        og_m = re.search(r'<meta\s+(?:property|name)="og:title"\s+content="([^"]+)"', html, re.I)
        if og_m:
            og_title = html_module.unescape(og_m.group(1)).strip()
            print(f"[html-parse] og:title：{og_title[:80]}")
            if self._is_valid_store_name(og_title):
                return og_title.split(" - ")[0].strip()

        # 3. Google Maps place URL in HTML
        maps_url_m = re.search(
            r'(https?://(?:www\.)?google\.[a-z.]+/maps/place/[^\s"\'<>\\]+)', html
        )
        if maps_url_m:
            maps_url = maps_url_m.group(1)
            print(f"[html-parse] 找到 Maps URL：{maps_url[:100]}")
            place_m = re.search(r'/maps/place/([^/@?&]+)', maps_url)
            if place_m:
                name = urllib.parse.unquote_plus(place_m.group(1)).replace('+', ' ').strip()
                if self._is_valid_store_name(name):
                    return name

        # 4. JSON "name" field
        json_name_m = re.search(r'"name"\s*:\s*"([^"]{2,80})"', html)
        if json_name_m:
            name = json_name_m.group(1).strip()
            print(f"[html-parse] JSON name：{name}")
            if self._is_valid_store_name(name):
                return name

        print("[html-parse] 未找到有用資訊")
        return ""

    def _is_valid_store_name(self, name: str) -> bool:
        """檢查是否為有效的店家名稱（排除通用名稱）"""
        if not name or len(name) < 2:
            return False
        invalid = {"google", "google maps", "google 地圖", "google 地图",
                   "maps", "goo.gl", "maps.app", "sign in", "登入"}
        return name.lower().strip() not in invalid

    async def _resolve_via_serper_search(self, url: str) -> str:
        """用 Serper /search 搜尋短網址，Google 會回傳對應的店家資訊"""

        # 嘗試多種搜尋方式
        queries = [
            url,                          # 直接搜短網址
            f"google maps {url}",         # 加 google maps 前綴
        ]

        for query in queries:
            try:
                print(f"[resolve-serper] 搜尋：{query[:80]}")
                data = await self._call_serper("search", {"q": query, "gl": "tw", "hl": "zh-tw"})

                # DEBUG：印出回傳的頂層 key
                print(f"[resolve-serper] 回傳 keys：{list(data.keys())}")

                # 從 knowledgeGraph 取得店名
                kg = data.get("knowledgeGraph", {})
                if kg:
                    title = kg.get("title", "")
                    print(f"[resolve-serper] knowledgeGraph title：{title!r}")
                    if title:
                        return title

                # 從 organic 搜尋結果取得
                organic = data.get("organic", [])
                if organic:
                    print(f"[resolve-serper] organic[0]：title={organic[0].get('title','')!r}, link={organic[0].get('link','')[:80]}")

                for item in organic:
                    title = item.get("title", "")
                    link = item.get("link", "")
                    snippet = item.get("snippet", "")
                    print(f"[resolve-serper]   organic: title={title[:50]!r} link={link[:80]}")

                    # 找 Google Maps place 結果（必須是 /maps/place/ 不是首頁）
                    if "google.com/maps/place" in link:
                        name = title.split(" - ")[0].split(" · ")[0].strip()
                        if self._is_valid_store_name(name):
                            print(f"[resolve-serper] ✅ 從 organic 取得店名：{name}")
                            return name
                        # 也試試從 URL path 提取
                        place_m = re.search(r'/maps/place/([^/@?&]+)', link)
                        if place_m:
                            url_name = urllib.parse.unquote_plus(place_m.group(1)).replace('+', ' ').strip()
                            if self._is_valid_store_name(url_name):
                                print(f"[resolve-serper] ✅ 從 organic URL 取得店名：{url_name}")
                                return url_name

                # 從 places 結果取得
                places = data.get("places", [])
                if places:
                    title = places[0].get("title", "")
                    if title:
                        print(f"[resolve-serper] ✅ 從 places 取得店名：{title}")
                        return title

            except Exception as e:
                print(f"[resolve-serper] ⚠️ 搜尋失敗：{e}")

        print("[resolve-serper] ⚠️ 所有搜尋方式都未找到店名")
        return ""

    # ══════════════════════════════════════════════════════════════
    #  Serper API 核心
    # ══════════════════════════════════════════════════════════════

    async def _call_serper(self, endpoint: str, payload: dict) -> dict:
        """呼叫 Serper API"""
        def do_call() -> dict:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"https://google.serper.dev/{endpoint}",
                data=data,
                headers={"X-API-KEY": self._serper_key, "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))

        return await asyncio.to_thread(do_call)

    async def _serper_scrape(self, store_name: str, url: str = "") -> dict:
        """
        Serper API 取得評論資料。
        1. /maps 搜尋店家 → 基本資訊 + 少量評論
        2. /reviews 取得更多評論
        """

        # ── Step 1：/maps 搜尋店家 ──────────────────────────────
        maps_data = {}
        place_info = {}
        maps_reviews = []

        print(f"[Serper] /maps 搜尋：{store_name}")
        try:
            maps_data = await self._call_serper(
                "maps", {"q": store_name, "gl": "tw", "hl": "zh-tw"}
            )
            places = maps_data.get("places", [])
            if places:
                place_info = places[0]
                print(f"[Serper] ✅ 找到店家：{place_info.get('title', '')}（"
                      f"評分 {place_info.get('rating', '-')}，"
                      f"{place_info.get('ratingCount', '-')} 則評論）")

                for rev in place_info.get("reviews", []):
                    text = rev.get("snippet") or rev.get("text", "")
                    if text and len(text.strip()) > 3:
                        _user = rev.get("user") if isinstance(rev.get("user"), dict) else {}
                        maps_reviews.append({
                            "text": text.strip(),
                            "rating": rev.get("rating", 0),
                            "author": (
                                _user.get("name")
                                or rev.get("author")
                                or rev.get("name")
                                or rev.get("user_name")
                                or ""
                            ),
                            "time": rev.get("date", "") or rev.get("time", ""),
                        })
                print(f"[Serper] /maps 評論：{len(maps_reviews)} 則")
            else:
                print("[Serper] ⚠️ /maps 未找到匹配店家")
        except Exception as e:
            print(f"[Serper] ⚠️ /maps 失敗：{e}")

        # ── Step 2：/reviews 取得更多評論 ────────────────────────
        serper_reviews = []
        try:
            reviews_payload = {"q": store_name, "gl": "tw", "hl": "zh-tw", "num": 40}

            # 如果 /maps 回傳了 cid 或 place_id，優先使用
            cid = place_info.get("cid", "")
            place_id = place_info.get("placeId", "")
            if cid:
                reviews_payload["cid"] = cid
                print(f"[Serper] /reviews 使用 cid：{cid}")
            elif place_id:
                reviews_payload["placeId"] = place_id
                print(f"[Serper] /reviews 使用 placeId：{place_id}")

            # 分頁迴圈：嘗試用 page 參數取得所有評論
            page = 1
            max_pages = 20  # 安全上限
            seen_serper_texts = set()
            while page <= max_pages:
                current_payload = {**reviews_payload}
                if page > 1:
                    current_payload["page"] = page

                print(f"[Serper] /reviews 搜尋（page {page}）...")
                reviews_data = await self._call_serper("reviews", current_payload)

                # DEBUG：第一頁印出所有 key 看有沒有分頁 token
                if page == 1:
                    data_keys = list(reviews_data.keys())
                    print(f"[Serper] /reviews 回傳 keys：{data_keys}")

                raw_reviews = reviews_data.get("reviews", [])
                print(f"[Serper] /reviews page {page} 回傳：{len(raw_reviews)} 則評論")

                if not raw_reviews:
                    break

                for rev in raw_reviews:
                    text = rev.get("snippet") or rev.get("text", "")
                    if text and len(text.strip()) > 3:
                        text = text.strip()
                        key = text[:60]
                        if key in seen_serper_texts:
                            continue
                        seen_serper_texts.add(key)
                        _user = rev.get("user") if isinstance(rev.get("user"), dict) else {}
                        serper_reviews.append({
                            "text": text,
                            "rating": rev.get("rating", 0),
                            "author": (
                                _user.get("name")
                                or rev.get("author")
                                or rev.get("name")
                                or rev.get("user_name")
                                or ""
                            ),
                            "time": rev.get("date", "") or rev.get("time", ""),
                        })

                # DEBUG：第一頁第一則印出原始 shape，確認 author 路徑
                if page == 1 and raw_reviews:
                    _first = raw_reviews[0]
                    _author_resolved = serper_reviews[-1]["author"] if serper_reviews else ""
                    print(f"[Serper] DEBUG first review keys: {list(_first.keys())}, "
                          f"author.resolved='{_author_resolved}', "
                          f"user={_first.get('user')!r}")

                # 檢查是否有下一頁 token
                next_token = (reviews_data.get("nextPageToken")
                              or reviews_data.get("next_page_token")
                              or reviews_data.get("serpapi_pagination", {}).get("next_page_token", ""))
                if next_token:
                    print(f"[Serper] 找到 nextPageToken，繼續...")
                    reviews_payload["nextPageToken"] = next_token

                # 如果回傳少於 20 則，表示已經是最後一頁
                if len(raw_reviews) < 20:
                    break

                page += 1
        except Exception as e:
            print(f"[Serper] ⚠️ /reviews 失敗：{e}")

        # ── 合併評論（去重）────────────────────────────────────
        all_reviews = []
        seen_texts = set()

        for r in serper_reviews:
            key = r["text"][:60]
            if key not in seen_texts:
                seen_texts.add(key)
                all_reviews.append(r)

        for r in maps_reviews:
            key = r["text"][:60]
            if key not in seen_texts:
                seen_texts.add(key)
                all_reviews.append(r)

        print(f"[Serper] 合併後：{len(all_reviews)} 則不重複評論")

        # ── 組裝回傳 ─────────────────────────────────────────────
        final_store_name = place_info.get("title", "") or store_name
        rating = place_info.get("rating", "")
        rating_count = place_info.get("ratingCount", "")
        address = place_info.get("address", "")
        category = place_info.get("type", "") or place_info.get("category", "")

        lines = [f"【店家：{final_store_name}】Google Maps 顧客評論："]
        if rating:
            lines.append(f"Google 評分：{rating} 分（共 {rating_count} 則評論）")
        if address:
            lines.append(f"地址：{address}")
        if category:
            lines.append(f"類型：{category}")

        structured = []
        for r in all_reviews:
            txt = r["text"]
            rat = r.get("rating", 0)
            author = r.get("author", "")
            when = r.get("time", "") or r.get("date", "")
            if txt:
                star = f"（{rat}星）" if rat else ""
                lines.append(f"顧客評論{star}：{txt}")
            structured.append({
                "text": txt,
                "rating": rat,
                "author": author,
                "time": when,
            })

        with_text = sum(1 for r in all_reviews if r.get("text"))
        print(f"[Serper] 有文字評論：{with_text} 則 / 總共 {len(all_reviews)} 則")

        return {
            "url": url,
            "raw_text": "\n\n".join(lines),
            "store_name": final_store_name,
            "review_count": len(all_reviews),
            "total_reviews": rating_count,
            "reviews_structured": structured,
            "maps_data": maps_data,
            "rating": rating,
            "rating_count": rating_count,
            "address": address,
            "category": category,
            "platform": "google",
        }

    # ══════════════════════════════════════════════════════════════
    #  一般 URL 爬取
    # ══════════════════════════════════════════════════════════════

    async def _scrape_generic_url(self, url: str) -> dict:
        """非 Google Maps URL"""
        from bs4 import BeautifulSoup

        try:
            def fetch_url():
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                             "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    return resp.read().decode("utf-8", errors="ignore")

            html = await asyncio.to_thread(fetch_url)
            soup = BeautifulSoup(html, 'html.parser')
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text(separator='\n')
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            cleaned = '\n'.join(lines[:500])
            return {"url": url, "raw_text": cleaned, "store_name": "", "status": "success"}
        except Exception as e:
            return {"url": url, "raw_text": "", "store_name": "", "status": "failed", "error": str(e)}

    # ══════════════════════════════════════════════════════════════
    #  Reviews MD 輸出
    # ══════════════════════════════════════════════════════════════

    def _save_reviews_md(self, store_name: str, url: str, reviews: list,
                         maps_data: dict = None, source: str = "unknown"):
        """寫入 reviews_latest.md"""
        try:
            places = (maps_data or {}).get("places", [])
            p0 = places[0] if places else {}
            rating = p0.get("rating", "-")
            rating_cnt = p0.get("ratingCount", "-")
            address = p0.get("address", "-")
            category = p0.get("type", "-")

            lines = [
                f"# {store_name}",
                "",
                f"| 評分 | Google 評論總數 | 地址 | 類型 |",
                f"|------|----------------|------|------|",
                f"| {rating} ⭐ | {rating_cnt} 則 | {address} | {category} |",
                "",
                f"> 來源 URL：{url}",
                f"> 資料來源：{source}",
                "",
                f"## 顧客評論（{len(reviews)} 則）",
                "",
            ]

            if reviews:
                lines.append(f"| # | 作者 | 時間 | 評論內容 | 評分 |")
                lines.append(f"|---|------|------|---------|------|")
                for i, r in enumerate(reviews, 1):
                    if isinstance(r, dict):
                        text = str(r.get("text", "")).replace("|", "｜").replace("\n", " ")
                        rating_val = r.get("rating", "-")
                        author = str(r.get("author", "")).replace("|", "｜")[:30] or "—"
                        when = str(r.get("time", "") or r.get("date", "")).replace("|", "｜")[:20] or "—"
                    else:
                        text = str(r).replace("|", "｜").replace("\n", " ")
                        rating_val = "-"
                        author = "—"
                        when = "—"
                    lines.append(f"| {i} | {author} | {when} | {text[:200]} | {rating_val} |")
            else:
                lines.append("（無評論）")

            dump_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "reviews_latest.md")
            dump_path = os.path.normpath(dump_path)
            with open(dump_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            print(f"[DEBUG] reviews_latest.md 已更新（{source}，{len(reviews)} 則）→ {dump_path}")
        except Exception as e:
            print(f"[DEBUG] 寫入 reviews_latest.md 失敗: {e}")
