"""
InsightX YouTube 留言爬蟲服務 v1.2（v2.0.0 + fallback）

架構：主／備雙層，零瀏覽器。
  主：YouTube Data API v3（需要 YOUTUBE_API_KEY，免費 10k units/day）
  備：youtube-comment-downloader（無需 API key，專門抓留言的輕量 library）

Fallback 觸發條件：
  - 沒有 YOUTUBE_API_KEY
  - 官方 API 回傳 403（quota exceeded / key 無效 / 留言被關閉）
  - 使用者將環境變數 YOUTUBE_FALLBACK_MODE 設為 "force-fallback"
    （為相容舊值，"force-ytdlp" 也接受）

關閉 fallback：
  - 設 YOUTUBE_FALLBACK_MODE=off

為什麼從 yt-dlp 換成 youtube-comment-downloader：
  - yt-dlp 是下載工具，max_comments 在新版對 YouTube 的新 JS runtime 不再穩定
    遵守，會在大留言影片上無限翻頁（實測 2026.03.17 版）
  - youtube-comment-downloader 是 generator，可精確拿到 N 則就停
  - 單一職責：專門抓留言，沒有影片解析的額外成本

回傳 shape 對齊 ScraperService，讓下游 LLM 可以共用。
"""

import os
import re
import json
import urllib.parse
import urllib.request
from dotenv import load_dotenv

load_dotenv()

YT_API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeScraper:
    """YouTube 單支影片留言爬蟲（官方 API 主，yt-dlp 備）。"""

    def __init__(self):
        self._api_key = os.getenv("YOUTUBE_API_KEY", "")
        self._fallback_mode = os.getenv("YOUTUBE_FALLBACK_MODE", "auto").strip().lower()
        # auto = 官方失敗才走 yt-dlp（預設）
        # force-ytdlp = 強制用 yt-dlp
        # off = 只用官方，失敗直接報錯

    # ══════════════════════════════════════════════════════════════
    #  公開介面（保留原本的 scrape_video 名稱，routes.py 不用改）
    # ══════════════════════════════════════════════════════════════

    async def scrape_video(self, url: str, max_comments: int = 200) -> dict:
        """
        爬取單支 YouTube 影片的留言（自動選擇資料來源）。

        Returns:
            dict，shape 對齊 ScraperService._serper_scrape() 的輸出。
            額外：video_data["source"] = "official_api" | "yt-dlp"
        """
        video_id = self._extract_video_id(url)
        if not video_id:
            return self._err(url, f"無法從網址提取 video_id：{url}")

        # 強制 yt-dlp
        if self._fallback_mode == "force-ytdlp":
            print(f"\n[YT] 使用 yt-dlp 模式（YOUTUBE_FALLBACK_MODE=force-ytdlp）")
            return await self._scrape_via_ytdlp(url, video_id, max_comments)

        # 沒有 API key：直接 fallback（除非 off）
        if not self._api_key:
            if self._fallback_mode == "off":
                return self._err(
                    url,
                    "YOUTUBE_API_KEY 未設定，且 YOUTUBE_FALLBACK_MODE=off。"
                    "請在 .env 設定 YOUTUBE_API_KEY，或移除 YOUTUBE_FALLBACK_MODE。"
                )
            print(f"\n[YT] 未設定 YOUTUBE_API_KEY，自動切換到 yt-dlp 備用模式")
            return await self._scrape_via_ytdlp(url, video_id, max_comments)

        # 主要路徑：官方 API
        print(f"\n{'='*55}")
        print(f"[YT] 主要路徑：YouTube Data API v3（video_id={video_id}）")
        print(f"{'='*55}")
        result = await self._scrape_via_official_api(url, video_id, max_comments)

        # 官方失敗 且 允許 fallback
        if result["status"] == "error" and self._fallback_mode != "off":
            print(f"\n[YT] 官方 API 失敗（{result.get('error')}），自動切換到 yt-dlp 備用模式")
            fallback_result = await self._scrape_via_ytdlp(url, video_id, max_comments)
            if fallback_result["status"] != "error":
                return fallback_result
            # 兩個都失敗：回傳較有資訊的那一個
            return result if result.get("error") else fallback_result

        return result

    # ══════════════════════════════════════════════════════════════
    #  路徑 1：YouTube Data API v3（官方）
    # ══════════════════════════════════════════════════════════════

    async def _scrape_via_official_api(self, url: str, video_id: str, max_comments: int) -> dict:
        # 影片資訊
        video_info = await self._fetch_video_info(video_id)
        if not video_info:
            return self._err(
                url,
                f"官方 API 找不到影片 {video_id}（可能已刪除、設為私人、或 API key 無效）"
            )

        title = video_info.get("title", "")
        print(f"[YT] 影片：{title}")
        print(f"[YT] 頻道：{video_info.get('channel_title', '')}")
        print(f"[YT] 觀看 {video_info.get('view_count', 0):,} · "
              f"讚 {video_info.get('like_count', 0):,} · "
              f"留言 {video_info.get('comment_count', 0):,}")

        comments = await self._fetch_comments(video_id, max_comments)
        print(f"[YT] 官方 API 抓到 {len(comments)} 則留言")

        if not comments:
            # 沒留言可能是「關閉留言」或「API 403 quota exceeded」
            # 交給 fallback 判斷（上層會看 status="error" 決定是否 fallback）
            return self._err(
                url,
                "官方 API 未能抓到任何留言（可能 quota 用盡、留言區關閉、或只含回覆無 top-level comments）"
            )

        video_info["source"] = "official_api"
        return self._build_ok_result(url, title, video_info, comments)

    async def _fetch_video_info(self, video_id: str) -> dict:
        """videos.list — quota 1 unit"""
        params = {
            "part": "snippet,statistics",
            "id": video_id,
            "key": self._api_key,
        }
        data = await self._yt_api_get("videos", params)
        if not data or not data.get("items"):
            return {}

        item = data["items"][0]
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})

        return {
            "video_id": video_id,
            "title": snippet.get("title", ""),
            "channel_title": snippet.get("channelTitle", ""),
            "channel_id": snippet.get("channelId", ""),
            "description": snippet.get("description", "")[:500],
            "published_at": snippet.get("publishedAt", ""),
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
        }

    async def _fetch_comments(self, video_id: str, max_comments: int) -> list:
        """commentThreads.list 分頁 — quota 1 unit / 頁"""
        comments = []
        page_token = None
        page_num = 0
        max_per_page = 100

        while len(comments) < max_comments:
            page_num += 1
            params = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": min(max_per_page, max_comments - len(comments)),
                "order": "relevance",
                "textFormat": "plainText",
                "key": self._api_key,
            }
            if page_token:
                params["pageToken"] = page_token

            print(f"[YT] 官方 API 第 {page_num} 頁...")
            data = await self._yt_api_get("commentThreads", params)
            if not data:
                break

            items = data.get("items", [])
            if not items:
                break

            for item in items:
                top = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                text = top.get("textDisplay", "") or top.get("textOriginal", "")
                if not text or not text.strip():
                    continue
                comments.append({
                    "text": text.strip(),
                    "author": top.get("authorDisplayName", ""),
                    "like_count": int(top.get("likeCount", 0)),
                    "published_at": top.get("publishedAt", ""),
                })

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return comments

    async def _yt_api_get(self, endpoint: str, params: dict) -> dict:
        import asyncio
        return await asyncio.to_thread(self._sync_yt_api_get, endpoint, params)

    def _sync_yt_api_get(self, endpoint: str, params: dict) -> dict:
        url = f"{YT_API_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")[:500]
            except Exception:
                pass
            print(f"[YT] ❌ 官方 API {endpoint} HTTP {e.code}：{body}")
            return {}
        except Exception as e:
            print(f"[YT] ❌ 官方 API {endpoint} 例外：{e}")
            return {}

    # ══════════════════════════════════════════════════════════════
    #  路徑 2：youtube-comment-downloader（備用，無 API key）
    # ══════════════════════════════════════════════════════════════
    #  方法名保留 _scrape_via_ytdlp 是為了讓上層 dispatch 邏輯不用改
    #  （YOUTUBE_FALLBACK_MODE=force-ytdlp 等環境變數值仍相容）
    #  但實際 library 已從 yt-dlp 換成 youtube-comment-downloader：
    #    - yt-dlp 2026.03.17 版的 max_comments 在大留言影片會無限翻頁
    #    - youtube-comment-downloader 是 generator，可精確取 N 則就停
    #    - 單一職責、更輕量、更穩定
    # ══════════════════════════════════════════════════════════════

    async def _scrape_via_ytdlp(self, url: str, video_id: str, max_comments: int) -> dict:
        """
        用 youtube-comment-downloader 抓留言 + oEmbed 補影片 metadata。
        無需 API key；generator 模式可精確拿到 N 則就停。
        """
        try:
            from youtube_comment_downloader import (
                YoutubeCommentDownloader,
                SORT_BY_POPULAR,
            )
        except ImportError:
            return self._err(
                url,
                "youtube-comment-downloader 未安裝。請在 venv 執行：pip install youtube-comment-downloader"
            )

        import asyncio
        import itertools

        # ── 1. 先拿影片 metadata（oEmbed，無需 API key）──
        video_info = await asyncio.to_thread(self._fetch_meta_via_oembed, video_id)
        title = video_info.get("title", "") or f"YouTube 影片 {video_id}"
        print(f"[Fallback] 影片：{title}")
        if video_info.get("channel_title"):
            print(f"[Fallback] 頻道：{video_info['channel_title']}")

        # ── 2. 抓留言 ──
        def _run():
            downloader = YoutubeCommentDownloader()
            gen = downloader.get_comments(video_id, sort_by=SORT_BY_POPULAR)
            # generator — islice 拿到 max_comments 則就停，不會無限翻頁
            return list(itertools.islice(gen, max_comments))

        try:
            print(f"[Fallback] 開始抓留言（target={max_comments}）...")
            raw_comments = await asyncio.to_thread(_run)
        except Exception as e:
            return self._err(
                url,
                f"youtube-comment-downloader 抓取失敗：{type(e).__name__}: {e}"
            )

        print(f"[Fallback] 抓到 {len(raw_comments)} 則 top-level 留言")

        video_info["video_id"] = video_id
        video_info["source"] = "yt-dlp"  # 保留既有標籤（下游 raw_text header 用）

        if not raw_comments:
            return {
                "url": url,
                "raw_text": "",
                "store_name": title,
                "review_count": 0,
                "reviews_structured": [],
                "rating": str(video_info.get("like_count", 0)),
                "rating_count": str(video_info.get("view_count", 0)),
                "platform": "youtube",
                "video_data": video_info,
                "status": "no_comments",
                "error": "備用 library 未抓到任何留言（影片可能關閉了留言區）",
            }

        comments = []
        for c in raw_comments:
            text = (c.get("text") or "").strip()
            if not text:
                continue
            comments.append({
                "text": text,
                "author": c.get("author") or "",
                "like_count": self._parse_votes(c.get("votes", 0)),
                "published_at": c.get("time") or "",  # 相對時間字串（如 "3 years ago"）
            })

        return self._build_ok_result(url, title, video_info, comments)

    @staticmethod
    def _parse_votes(votes) -> int:
        """youtube-comment-downloader 的 votes 欄位可能是 int、''、'1.2K'、'3M' 等格式。"""
        if not votes:
            return 0
        if isinstance(votes, int):
            return votes
        s = str(votes).strip().upper().replace(",", "")
        if not s:
            return 0
        try:
            if s.endswith("K"):
                return int(float(s[:-1]) * 1_000)
            if s.endswith("M"):
                return int(float(s[:-1]) * 1_000_000)
            return int(float(s))
        except ValueError:
            return 0

    def _fetch_meta_via_oembed(self, video_id: str) -> dict:
        """
        用 oEmbed 拿影片標題 + 頻道名稱（無 API key、無 quota）。
        view_count / like_count oEmbed 不提供，所以備用模式下這兩個欄位會是 0。
        """
        oembed_url = (
            "https://www.youtube.com/oembed"
            f"?url=https://www.youtube.com/watch?v={video_id}&format=json"
        )
        empty = {
            "title": "",
            "channel_title": "",
            "channel_id": "",
            "description": "",
            "published_at": "",
            "view_count": 0,
            "like_count": 0,
            "comment_count": 0,
        }
        try:
            req = urllib.request.Request(oembed_url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return {
                **empty,
                "title": data.get("title", ""),
                "channel_title": data.get("author_name", ""),
            }
        except Exception as e:
            print(f"[Fallback] ⚠️ oEmbed 取不到影片資訊（{type(e).__name__}），繼續抓留言")
            return empty

    # ══════════════════════════════════════════════════════════════
    #  共用輸出組裝
    # ══════════════════════════════════════════════════════════════

    def _build_ok_result(self, url: str, title: str, video_info: dict, comments: list) -> dict:
        raw_text = self._format_comments_for_llm(title, video_info, comments)
        return {
            "url": url,
            "raw_text": raw_text,
            "store_name": title,
            "review_count": len(comments),
            "reviews_structured": [
                {
                    "text": c["text"],
                    "rating": c["like_count"],
                    "author": c["author"],
                    "date": c["published_at"],
                }
                for c in comments
            ],
            "rating": str(video_info.get("like_count", 0)),
            "rating_count": str(video_info.get("view_count", 0)),
            "platform": "youtube",
            "video_data": video_info,
            "status": "ok",
            "error": None,
        }

    # ══════════════════════════════════════════════════════════════
    #  Video ID 解析
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    def _extract_video_id(url: str) -> str:
        """支援 watch?v=、youtu.be、/shorts/、/embed/、/v/、純 ID"""
        if not url:
            return ""
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", url.strip()):
            return url.strip()

        try:
            parsed = urllib.parse.urlparse(url)
        except Exception:
            return ""

        if "youtu.be" in parsed.netloc:
            vid = parsed.path.lstrip("/").split("/")[0]
            return vid if re.fullmatch(r"[A-Za-z0-9_-]{11}", vid) else ""

        if "youtube.com" not in parsed.netloc and "youtube" not in parsed.netloc:
            return ""

        qs = urllib.parse.parse_qs(parsed.query)
        if "v" in qs and qs["v"]:
            vid = qs["v"][0]
            return vid if re.fullmatch(r"[A-Za-z0-9_-]{11}", vid) else ""

        m = re.search(r"/(?:shorts|embed|v)/([A-Za-z0-9_-]{11})", parsed.path)
        if m:
            return m.group(1)

        return ""

    # ══════════════════════════════════════════════════════════════
    #  輸出格式化
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    def _format_comments_for_llm(title: str, video_info: dict, comments: list) -> str:
        source_tag = video_info.get("source", "")
        source_label = {"official_api": "官方 API", "yt-dlp": "yt-dlp 備用"}.get(source_tag, "")
        header = (
            f"【YouTube 影片：{title}】\n"
            f"頻道：{video_info.get('channel_title', '')}\n"
            f"觀看：{video_info.get('view_count', 0):,} · "
            f"讚：{video_info.get('like_count', 0):,} · "
            f"留言：{video_info.get('comment_count', 0):,}"
            + (f" · 來源：{source_label}" if source_label else "")
            + f"\n\n以下是觀眾留言：\n{'='*55}\n"
        )
        lines = []
        for i, c in enumerate(comments, 1):
            likes = f"👍{c['like_count']}" if c["like_count"] else ""
            lines.append(f"\n[{i}] {c['author']} {likes}\n{c['text']}\n")
        return header + "".join(lines)

    # ══════════════════════════════════════════════════════════════
    #  錯誤回傳
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    def _err(url: str, msg: str) -> dict:
        print(f"[YT] ❌ {msg}")
        return {
            "url": url,
            "raw_text": "",
            "store_name": "",
            "review_count": 0,
            "reviews_structured": [],
            "rating": "",
            "rating_count": "",
            "platform": "youtube",
            "video_data": {},
            "status": "error",
            "error": msg,
        }


# ══════════════════════════════════════════════════════════════════
#  URL 類型偵測（給 ScraperService 用）
# ══════════════════════════════════════════════════════════════════

def is_youtube_url(url: str) -> bool:
    if not url:
        return False
    u = url.lower()
    return (
        "youtube.com/watch" in u
        or "youtube.com/shorts" in u
        or "youtube.com/embed" in u
        or "youtu.be/" in u
        or "m.youtube.com/watch" in u
    )
