import asyncio
import json
import os
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, JsonCssExtractionStrategy

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

async def go_to_station(station_id, url):
    browser_config = BrowserConfig(
        headless=False,
        # java_script_enabled=True,
    )

    schema_path = os.path.join(SCRIPT_DIR, 'tcds_extraction_schema.json')
    with open(schema_path, 'r') as f:
        schema = json.load(f)

    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.DISABLED,
        extraction_strategy=JsonCssExtractionStrategy(schema, verbose=True),
        delay_before_return_html=5.0,
        process_iframes=True,
        wait_until = "networkidle",
        # remove_overlay_elements=True,
        # wait_for=".FormRowLabel"
        # js_code = js_code,
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        
        result = await crawler.arun(url=url, config=crawler_config)

        if result.success:
            extracted_data = json.loads(result.extracted_content)
            return extracted_data
        else:
            print(f"Crawl failed: {result.error_message}")
            return None
    

async def main():
    station_id = "S133"
    url = f'https://txdot.public.ms2soft.com/tcds/tsearch.asp?loc=Txdot&mod=tcds&local_id={station_id}'  
    result = await go_to_station(station_id, url)
    if result:
        print(json.dumps(result))

if __name__ == "__main__":
    asyncio.run(main())