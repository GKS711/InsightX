"""
InsightX — Serper API 爬蟲測試
用法：python dev/test_serper_scraper.py

測試 Serper API 的評論爬取功能（含分頁）。
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from src.services.scraper_service import ScraperService
import asyncio


async def main():
    url = "https://maps.app.goo.gl/5TWNMUBjRJhoYTYW6"  # 全家便利商店

    print("=" * 55)
    print("InsightX 爬蟲測試（Serper API v13.1）")
    print(f"URL：{url}")
    print("=" * 55)

    serper_key = os.getenv("SERPER_API_KEY", "")
    if not serper_key:
        print("❌ SERPER_API_KEY 未設定！請在 .env 中填入")
        return

    print(f"✅ SERPER_API_KEY 已設定（{serper_key[:8]}...）\n")

    scraper = ScraperService()
    result = await scraper.scrape_url(url)

    print(f"\n{'='*55}")
    print(f"店名：{result.get('store_name', '未知')}")
    print(f"狀態：{result.get('status', '')}")
    print(f"評論數：{result.get('review_count', 0)}")
    print(f"文字長度：{len(result.get('raw_text', ''))} 字元")

    raw = result.get('raw_text', '')
    reviews = [l for l in raw.split('\n\n') if l.startswith('顧客評論')]
    if reviews:
        print(f"\n前 3 則評論：")
        for i, r in enumerate(reviews[:3]):
            print(f"  {i+1}. {r[:80]}...")

    print(f"{'='*55}")
    print("✅ 通過" if len(reviews) > 0 else "❌ 失敗（0 則評論）")


if __name__ == "__main__":
    asyncio.run(main())
