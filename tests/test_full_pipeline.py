import asyncio
import logging
import sys
import os

# Ensure src can be imported when running this script directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.scraper_service import ScraperService
from src.services.llm_service import LLMService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    scraper = ScraperService()
    llm = LLMService()
    
    # Demo URL: 用台北 101 (公開地標) 作為 smoke test
    # 真實 demo 請替換成你要分析的店家網址，或透過環境變數注入
    url = os.getenv(
        "TEST_STORE_URL",
        "https://www.google.com/maps/place/Taipei+101/@25.0339,121.5644,17z/",
    )
    
    print("="*60)
    print("TESTING COMPLETE PIPELINE: Scrape → LLM Analysis")
    print("="*60)
    
    # Step 1: Scrape
    print("\n[1/2] Scraping...")
    try:
        scrape_result = await scraper.scrape_url(url)
        if scrape_result['status'] == 'failed':
            print(f"❌ Scraping failed: {scrape_result.get('error')}")
            return
        
        raw_text = scrape_result['raw_text']
        print(f"✅ Scraped {len(raw_text)} characters")
        print(f"Preview: {raw_text[:200]}...")
    except Exception as e:
        print(f"❌ Scraping error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 2: Analyze with LLM
    print("\n[2/2] Analyzing with Gemini...")
    try:
        analysis_result = await llm.analyze_content(raw_text)
        print(f"✅ LLM Response received")
        print(f"Response type: {type(analysis_result).__name__}")

        # llm.analyze_content() 回傳已 parsed 的 dict（service 在內部處理了
        # JSON parse + markdown 救援），所以這邊預期 dict。如果之後 contract
        # 變回 string，這個 assertion 會立刻紅。
        import json
        if isinstance(analysis_result, dict):
            print(f"\n✅ Got dict from analyze_content():")
            print(json.dumps(analysis_result, indent=2, ensure_ascii=False))
            # 簡單 sanity check：應該有 store_name / good / bad 三個 key
            missing = [k for k in ("store_name", "good", "bad") if k not in analysis_result]
            if missing:
                print(f"\n⚠️  缺少預期 key：{missing}")
        else:
            print(f"❌ Unexpected return type: {type(analysis_result).__name__}")
            print(f"Value: {analysis_result!r}")

    except Exception as e:
        print(f"❌ LLM analysis error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "="*60)
    print("PIPELINE TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
