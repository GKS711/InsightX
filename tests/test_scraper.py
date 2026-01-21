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
    url = "https://www.google.com/maps/place/Pizza+Shalom+%E6%9F%B4%E7%87%92%E7%AA%AF%E7%83%A4%E6%8A%AB%E8%96%A9/@24.8294946,121.0264991,17z/data=!4m8!3m7!1s0x346837d8ac8c2283:0x87892d179da342bf!8m2!3d24.8294946!4d121.0264991!9m1!1b1!16s%2Fg%2F11kccf84lx?entry=ttu&g_ep=EgoyMDI2MDExMy4wIKXMDSoASAFQAw%3D%3D"
    
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
