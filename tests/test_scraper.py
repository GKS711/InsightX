import asyncio
import logging
import sys
import os

# Ensure src can be imported when running this script directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.scraper_service import ScraperService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    service = ScraperService()
    # Demo URL: 用台北 101 (公開地標) 作為 scraper smoke test
    # 真實 demo 請替換成你要分析的店家網址，或透過環境變數注入
    url = os.getenv(
        "TEST_STORE_URL",
        "https://www.google.com/maps/place/Taipei+101/@25.0339,121.5644,17z/",
    )
    
    print(f"Testing scraper with URL: {url}")
    try:
        result = await service.scrape_url(url)
        print("Scraping Result Status:", result.get("status"))
        raw_text = result.get("raw_text", "")
        print(f"Extracted Text Length: {len(raw_text)}")
        print("--- Text Preview ---")
        print(raw_text[:1000])
        print("--- End Preview ---")
    except Exception as e:
        print(f"Scraping Failed with error:")
        print(e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
