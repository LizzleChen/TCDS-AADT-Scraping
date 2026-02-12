import asyncio
import json
import os
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, JsonCssExtractionStrategy

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

TCDS_BASE_URL = "https://txdot.public.ms2soft.com/tcds/tsearch.asp"


async def go_to_station(station_id, crawler):
    url = f"{TCDS_BASE_URL}?loc=Txdot&mod=tcds&local_id={station_id}"

    schema_path = os.path.join(SCRIPT_DIR, 'tcds_extraction_schema.json')
    with open(schema_path, 'r') as f:
        schema = json.load(f)

    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.DISABLED,
        extraction_strategy=JsonCssExtractionStrategy(schema, verbose=True),
        session_id="tcds_session",
        wait_until="networkidle",
        wait_for="css:#TCDS_TDETAIL_AADT_DIV table#tblTable4",
        delay_before_return_html=1.0,
        process_iframes=True,
    )

    result = await crawler.arun(url=url, config=crawler_config)

    if result.success:
        extracted_data = json.loads(result.extracted_content)
        return extracted_data
    else:
        print(f"Crawl failed for {station_id}: {result.error_message}")
        return None
    

async def main():
    station_id = "S133"

    browser_config = BrowserConfig(headless=False)
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await go_to_station(station_id, crawler)
        if result:
            print(json.dumps(result))

if __name__ == "__main__":
    asyncio.run(main())