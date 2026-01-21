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
    
    url = "https://www.google.com/maps/place/Pizza+Shalom+%E6%9F%B4%E7%87%92%E7%AA%AF%E7%83%A4%E6%8A%AB%E8%96%A9/@24.8294946,121.0264991,17z/data=!4m8!3m7!1s0x346837d8ac8c2283:0x87892d179da342bf!8m2!3d24.8294946!4d121.0264991!9m1!1b1!16s%2Fg%2F11kccf84lx?entry=ttu&g_ep=EgoyMDI2MDExMy4wIKXMDSoASAFQAw%3D%3D"
    
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
        print(f"Response type: {type(analysis_result)}")
        print(f"Response:\n{analysis_result}")
        
        # Try to parse as JSON
        import json
        if isinstance(analysis_result, str):
            # Clean markdown code blocks
            cleaned = analysis_result.replace("```json", "").replace("```", "").strip()
            print(f"\nCleaned response:\n{cleaned}")
            
            try:
                parsed = json.loads(cleaned)
                print(f"\n✅ Successfully parsed JSON:")
                print(json.dumps(parsed, indent=2, ensure_ascii=False))
            except json.JSONDecodeError as je:
                print(f"\n❌ JSON parse error: {je}")
        else:
            print(f"Response is not a string: {analysis_result}")
            
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
