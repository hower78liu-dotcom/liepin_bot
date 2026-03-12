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
        
        search_input = page.locator('input[placeholder*="职位/公司/行业"]').first
        await search_input.fill("资深Java架构师")
        await page.keyboard.press("Enter")
        await asyncio.sleep(2)
        
        save_btn = page.locator('text="保存条件"').first
        if await save_btn.is_visible():
            # 获取 保存条件 父级 div 的 outerHTML，因为通常 tag 就在旁边
            html = await save_btn.evaluate('el => el.parentElement.parentElement.outerHTML')
            with open("found_tags.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("Write successful to found_tags.html")
        else:
            print("save_btn not visible")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
