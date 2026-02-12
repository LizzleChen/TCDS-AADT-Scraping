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
    

async def crawl_stations(station_ids, headless=True, output_file=None):
    """Crawl one or more stations and return all results."""
    browser_config = BrowserConfig(headless=headless)
    all_results = {}

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for i, station_id in enumerate(station_ids, 1):
            print(f"[{i}/{len(station_ids)}] Crawling {station_id}...")
            data = await go_to_station(station_id, crawler)
            if data:
                all_results[station_id] = data

    if output_file:
        out_path = os.path.join(SCRIPT_DIR, output_file)
        with open(out_path, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f"Results saved to {out_path}")

    return all_results


async def main():
    station_ids = ["S133"]

    results = await crawl_stations(station_ids, headless=False, output_file="output.json")
    if not results:
        print("No results extracted.")


if __name__ == "__main__":
    asyncio.run(main())