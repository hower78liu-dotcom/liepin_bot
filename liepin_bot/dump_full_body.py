import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state="auth.json")
        page = await context.new_page()
        print("Navigating...")
        await page.goto("https://h.liepin.com/search/getConditionItem")
        await page.wait_for_load_state("networkidle")
        
        search_input = page.locator('input[placeholder*="职位/公司/行业"], input[placeholder*="搜职位"], .search-item input').first
        await search_input.fill("Java")
        await page.keyboard.press("Enter")
        await asyncio.sleep(2)
        
        # Click city 成都 with force to bypass interception
        try:
            city_block = page.locator('span:has-text("期望城市："), span:has-text("目前城市：")').locator("..").first
            city_label = city_block.locator('label:has-text("成都"), .tag-label-group label:has-text("成都")').first
            if await city_label.is_visible():
                await city_label.click(timeout=3000, force=True)
                await asyncio.sleep(2)
        except Exception as e:
            print(f"City click failed: {e}")
            
        html = await page.evaluate('document.body.innerHTML')
        with open("full_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("Write successful to full_page.html")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
