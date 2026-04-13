"""
InsightX — 完整流程測試（Scrape → Gemini 分析）
用法：python dev/test_full_pipeline.py

測試從爬蟲到 AI 分析的完整 pipeline。
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from src.services.scraper_service import ScraperService
from src.services.llm_service import LLMService
import asyncio
import json


async def main():
    url = "https://maps.app.goo.gl/5TWNMUBjRJhoYTYW6"

    print("=" * 55)
    print("InsightX 完整流程測試：Scrape → Gemini")
    print("=" * 55)

    scraper = ScraperService()
    llm = LLMService()

    # Step 1: Scrape
    print("\n[1/2] 爬取評論中...")
    result = await scraper.scrape_url(url)

    if result.get('status') == 'failed':
        print(f"❌ 爬蟲失敗：{result.get('error')}")
        return

    raw_text = result['raw_text']
    print(f"✅ 爬取完成：{result.get('store_name')} · {len(raw_text)} 字元")

    # Step 2: Gemini Analysis
    print("\n[2/2] Gemini AI 分析中...")
    analysis = await llm.analyze_content(raw_text)

    if 'error' in analysis:
        print(f"❌ AI 分析失敗：{analysis['error']}")
        return

    print(f"✅ 分析完成")
    print(f"  店名：{analysis.get('store_name', '?')}")
    print(f"  正面：{[g['label'] for g in analysis.get('good', [])]}")
    print(f"  負面：{[b['label'] for b in analysis.get('bad', [])]}")

    print(f"\n{'='*55}")
    print("✅ Pipeline 測試通過！")


if __name__ == "__main__":
    asyncio.run(main())
