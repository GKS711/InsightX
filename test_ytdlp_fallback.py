"""
v2.0.1 fallback 驗證腳本 — 改用 youtube-comment-downloader

使用：
  source .venv/bin/activate
  python test_ytdlp_fallback.py [YouTube網址]

不帶參數預設測 3Blue1Brown 的「What is a neural network?」（留言正常）。
"""

import os
import sys
import asyncio

# 強制走備用路徑（即使有 YOUTUBE_API_KEY 也走 fallback）
os.environ["YOUTUBE_FALLBACK_MODE"] = "force-ytdlp"

# 確保 import 得到 library
try:
    import youtube_comment_downloader  # noqa: F401
    print("✅ youtube-comment-downloader 已安裝")
except ImportError:
    print("❌ 未安裝 youtube-comment-downloader，請先跑：")
    print("   pip install youtube-comment-downloader")
    sys.exit(1)

# 加入 src 到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.services.youtube_scraper import YouTubeScraper


async def main():
    test_url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "https://www.youtube.com/watch?v=aircAruvnKk"
    )
    # 3Blue1Brown「What is a neural network?」 — 留言量正常、無 spam 風暴

    print(f"\n{'#'*60}")
    print(f"# 測試影片：{test_url}")
    print(f"# 目標：20 則 top-level comment")
    print(f"# Fallback 模式：force-ytdlp（實際跑 youtube-comment-downloader）")
    print(f"{'#'*60}\n")

    scraper = YouTubeScraper()
    try:
        result = await scraper.scrape_video(test_url, max_comments=20)
    except Exception as e:
        print(f"\n❌ 例外：{type(e).__name__}: {e}")
        return

    print(f"\n{'='*60}")
    print(f"scrape_video 回傳摘要")
    print(f"{'='*60}")
    print(f"status         : {result.get('status')}")
    print(f"error          : {result.get('error')}")
    print(f"platform       : {result.get('platform')}")
    print(f"store_name     : {result.get('store_name')}")
    print(f"review_count   : {result.get('review_count')}")
    print(f"rating         : {result.get('rating')} (like_count)")
    print(f"rating_count   : {result.get('rating_count')} (view_count)")

    video_data = result.get("video_data", {}) or {}
    print(f"video_data.source : {video_data.get('source')}")

    reviews = result.get("reviews_structured") or []
    if reviews:
        print(f"\n前 3 則 top-level：")
        for i, r in enumerate(reviews[:3], 1):
            author = r.get("author", "")
            text = (r.get("text", "") or "")[:80]
            likes = r.get("rating", 0)
            print(f"  [{i}] {author} (👍{likes}): {text}")
        print(f"\n✅ youtube-comment-downloader 順利抓到留言")
    else:
        print(f"\n⚠️  沒有抓到留言")


if __name__ == "__main__":
    asyncio.run(main())
