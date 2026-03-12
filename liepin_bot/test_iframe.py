from loguru import logger
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://h.liepin.com/account/login")
        await asyncio.sleep(2)
        
        pwd_tab = page.locator("text='密码登录'").first
        if await pwd_tab.is_visible():
            await pwd_tab.click()
            await asyncio.sleep(1)

        await page.locator('input[placeholder*="手机号"], input[name="loginName"]').first.type("13940861948")
        await page.locator('input[placeholder*="密码"], input[name="userPwd"]').first.type("QWER@78asdf")
        await page.locator('button.quick-login-btn, button:has-text("登 录")').first.click()

        logger.info("等待验证码弹出中...")
        await asyncio.sleep(4)

        try:
            iframe_el = await page.wait_for_selector('#tcaptcha_iframe', timeout=6000)
            frame = await iframe_el.content_frame()
            logger.info(">>> 找到 iframe! 当前 iframe 内元素分析：")
            
            # 打印里面所有的 div 看看
            divs = await frame.locator('div').all()
            for idx, div in enumerate(divs):
                 class_name = await div.get_attribute("class")
                 id_name = await div.get_attribute("id")
                 if class_name or id_name:
                      if "bg" in str(class_name).lower() or "bg" in str(id_name).lower() or "slide" in str(class_name).lower() or "slide" in str(id_name).lower() or "tc" in str(class_name).lower() or "tc" in str(id_name).lower():
                           logger.info(f"[DIV] id='{id_name}' class='{class_name}'")

        except Exception as e:
            logger.info("拦截 iframe 失败:", e)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
