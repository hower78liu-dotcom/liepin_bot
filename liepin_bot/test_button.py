from loguru import logger
import asyncio
from playwright.async_api import async_playwright
import time

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined })
        """)
        page = await context.new_page()
        await page.goto("https://h.liepin.com/account/login")
        await asyncio.sleep(2)
        
        pwd_tab = page.locator("text='密码登录'").first
        if await pwd_tab.is_visible():
            await pwd_tab.click()
            await asyncio.sleep(1)

        logger.info("[DEBUG] 当前可见的 button 元素:")
        buttons = await page.locator("button").all()
        for idx, btn in enumerate(buttons):
            if await btn.is_visible():
                text = await btn.inner_text()
                classes = await btn.get_attribute("class")
                logger.info(f"[{idx}] 文本='{text}' class='{classes}'")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
