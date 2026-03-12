import asyncio
from playwright.async_api import async_playwright
import os

AUTH_FILE = "auth.json"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False) # Must be False to match
        context = await browser.new_context(storage_state=AUTH_FILE)
        page = await context.new_page()
        
        await page.goto("https://h.liepin.com/search/getConditionItem")
        await page.wait_for_load_state("networkidle")
        
        # Fill Job title
        search_input = page.locator('input[placeholder*="职位/公司/行业"], input[placeholder*="搜职位"], .search-item input').first
        await search_input.fill("资深Java架构师")
        await page.keyboard.press("Enter")
        await asyncio.sleep(2)
        
        # Click city
        city_block = page.locator('span:has-text("期望城市："), span:has-text("目前城市：")').locator("..").first
        city_label = city_block.locator(f'label:has-text("成都"), .tag-label-group label:has-text("成都")').first
        if await city_label.is_visible():
            await city_label.click()
            await asyncio.sleep(2)
        
        # Find "保存条件"
        save_btn = page.locator('text="保存条件"').first
        if await save_btn.is_visible():
            # Get parent div html
            html = await save_btn.evaluate('el => el.parentElement.outerHTML')
            with open("debug_tags.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("Successfully saved debug_tags.html")
        else:
            print("Could not find 保存条件!!!")

if __name__ == "__main__":
    asyncio.run(main())
