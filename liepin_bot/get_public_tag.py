import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating to public search...")
        await page.goto("https://www.liepin.com/zhaopin/")
        await page.wait_for_load_state("domcontentloaded")
        
        search_input = page.locator('input[placeholder*="职位/公司/行业"]').first
        if await search_input.is_visible():
            await search_input.fill("Java")
            await page.keyboard.press("Enter")
            await asyncio.sleep(3)
            
            # 找到包含“清空筛选条件”或者“已选条件”的地方
            clear_btn = page.locator('text="清空筛选条件", text="保存条件"').first
            if await clear_btn.is_visible():
                html = await clear_btn.evaluate('el => el.parentElement.parentElement.outerHTML')
                with open("public_tags.html", "w", encoding="utf-8") as f:
                    f.write(html)
                print("Write successful to public_tags.html")
            else:
                print("Clear/Save button not found.")
        else:
            print("Search bar not found.")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
