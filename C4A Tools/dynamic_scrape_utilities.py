import asyncio
import json
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

async def go_to_station(station_id):
    browser_config = BrowserConfig(
        headless=True,
        cache_mode=CacheMode.ENABLED,
    )

    async with AsyncWebCrawler(
        browser_config=browser_config,
    ) as crawler:
        url = "https://txdot.public.ms2soft.com/tcds/tsearch.asp?loc=Txdot&mod=TCDS"

        # Build a run config so BrowserManager can allocate a page/context
        run_cfg = CrawlerRunConfig(url=url)

        # Get a Playwright page via crawl4ai's BrowserManager
        page, context = await crawler.crawler_strategy.browser_manager.get_page(run_cfg)

        # Navigate to the search page
        try:
            await page.goto(url, wait_until="domcontentloaded")
        except Exception:
            await page.goto(url)

        # Wait for the Quick Search section (best-effort)
        try:
            await crawler.crawler_strategy.smart_wait(page, "css:h2", timeout=10000)
        except Exception:
            pass

        # Fill the input and submit (try form submit, button click, or dispatch Enter)
        js_fill_submit = (
            '''
            (value) => {
             const findInput = () => {
               const byId = document.getElementById('locationIdInput');
               if (byId) return byId;
               const h2s = Array.from(document.querySelectorAll('h2'));
               const h2 = h2s.find(el => el.textContent && el.textContent.trim() === 'Quick Search');
               if (h2) return h2.parentElement.querySelector('#locationIdInput');
               return null;
             }
             const input = findInput();
             if (!input) return {filled:false, submitted:false};
             input.focus();
             input.value = value;
             input.dispatchEvent(new Event('input', {bubbles:true}));
             input.dispatchEvent(new Event('change', {bubbles:true}));
             // Try to submit via for
             if (input.form) { input.form.submit(); return {filled:true, submitted:true, method:'form.submit'}; 
             // Try to find a nearby submit butto
             const btn = (input.closest('form') && input.closest('form').querySelector('button[type=submit],input[type=submit]')) || input.parentElement.querySelector('button, input[type=button]')
             if (btn) { btn.click(); return {filled:true, submitted:true, method:'button.click'}; 
             // Fallback: dispatch Enter key event
             input.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', keyCode:13, which:13, bubbles:true}))
             input.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', keyCode:13, which:13, bubbles:true}))
             return {filled:true, submitted:false, method:'enter'}
            }
            '''
        )

        resp = await crawler.crawler_strategy.adapter.evaluate(page, js_fill_submit, station_id)

        return {"result": resp, "station_id": station_id, "url": url}
    

# async def extract_aadt_css_based():
#     schema = {

#     }

async def main():
    station_id = "S133"
    result = await go_to_station(station_id)
    print(json.dumps(result, indent=2))