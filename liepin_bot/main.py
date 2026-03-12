import asyncio
import os
import random
import time
import pandas as pd
from playwright.async_api import async_playwright
import slider_solver
import sys
from loguru import logger

# [重构] 将项目根目录加入路径，确保能找到 Clean_source 包
BASE_PATH = r"D:\ljg\Antigravity"
if BASE_PATH not in sys.path:
    sys.path.append(BASE_PATH)

# 日志分级与落盘配置
logger.remove()
# 终端打印 INFO 级别以上（含时间格式、级别、模块函数名）
logger.add(sys.stdout, level="INFO", format="[{time:YYYY-MM-DD HH:mm:ss}] [{level}] [{module}/{function}] - {message}")
# 文件录制 DEBUG 级别以上，按天轮转
log_file_path = f"app_{time.strftime('%Y-%m-%d')}.log"
logger.add(log_file_path, level="DEBUG", format="[{time:YYYY-MM-DD HH:mm:ss}] [{level}] [{module}/{function}] - {message}", rotation="00:00")
sys.stdout.reconfigure(encoding='utf-8')

# 账号配置
USERNAME = "13940861948"
PASSWORD = "QWER@78asdf"
HUMAN_INTERVENTION = True # [Phase 9] 守护者机制：开启人机协作半自动接管模式

# 路径配置
from pathlib import Path
INPUT_EXCEL = Path("D:/ljg/Antigravity/Files/Input/Liepin/test_search.xlsx").as_posix()
OUTPUT_EXCEL = Path("D:/ljg/Antigravity/Files/Output/Get_result_leipin.xlsx").as_posix()
AUTH_FILE = (Path(__file__).parent / "auth.json").as_posix()

from LiepinSearch_Extractor import LiepinResumeExtractor
# 移除已删除的 condition_normalizer

async def random_delay(min_sec=1.5, max_sec=3.5):
    """全局随机延迟防风控"""
    await asyncio.sleep(random.uniform(min_sec, max_sec))

def get_core_keyword(raw_text: str) -> str:
    """精准截断第一个左括号（中/英文）之后的所有内容，并去除不可见空白字符"""
    import re
    if not isinstance(raw_text, str) or not str(raw_text).strip():
        return ""
    
    clean_text = re.sub(r'[\n\t\r]', ' ', str(raw_text))
    # 正则逻辑：^[^(\（]+ 匹配起始位置连续不是左括号的字符串片段
    match = re.search(r'^[^(\（]+', clean_text)
    
    if match:
        core_text = match.group(0).strip()
        if len(core_text) >= 2:
            return core_text
            
    # 如果正则未匹配或截取后太短（例如极端的开局即被包裹），回退去掉首尾空白字符的原词
    return clean_text.strip()

class LiepinBot:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.extractor = None
        self.consecutive_redirects = 0

    def _get_browser_context_options(self):
        """定义全环境内（有头/无头）全局一致的指纹特征与代理配置"""
        return {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
            "viewport": {"width": 1440, "height": 900},
            "locale": "zh-CN",
            "timezone_id": "Asia/Shanghai",
        }

    async def _apply_stealth(self, context):
        """向指定的 BrowserContext 统一注入防跨站反爬伪装特征"""
        base_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()
        stealth_path = os.path.join(base_dir, 'stealth.min.js')
        
        try:
            with open(stealth_path, 'r', encoding='utf-8') as f:
                stealth_script = f.read()
            await context.add_init_script(stealth_script)
            logger.debug("隐身：stealth.min.js 指纹伪装注入已就绪。")
        except FileNotFoundError:
            logger.warning("隐身：未找到 stealth.min.js，将使用降级版 webdriver 隐藏脚本(弱隐藏)！")
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """)

    async def init_browser(self, use_cache=False):
        if not self.playwright:
            self.playwright = await async_playwright().start()
        # 启动非无头浏览器并禁用自动化参数
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        # 加载环境一致性指纹
        context_options = self._get_browser_context_options()
        
        # 如果需要使用缓存则复用
        if use_cache and os.path.exists(AUTH_FILE):
            self.context = await self.browser.new_context(storage_state=AUTH_FILE, **context_options)
            logger.info("采用授权缓存装载验证 Context")
        else:
            self.context = await self.browser.new_context(**context_options)
            logger.info("采用空环境开启 Context 进行全新登录")

        # 挂载拦截器监控重定向行为
        self.context.on("response", self._global_response_handler)
        
        # 统一注入隐匿配置
        await self._apply_stealth(self.context)
        
        self.page = await self.context.new_page()
        self.extractor = LiepinResumeExtractor(self.page, OUTPUT_EXCEL)

    async def _global_response_handler(self, response):
        """全局路由哨兵：拦截异常重定向或者 401，防御死循环"""
        if response.status in [301, 302] and "passport.liepin.com" in response.headers.get("location", "").lower():
            self.consecutive_redirects += 1
            logger.warning(f"🚨 [全局安全拦截] 拦截到系统向 Passport 强制重定向！可能是 Session 丢失。累计发生次数: {self.consecutive_redirects}")
            if self.consecutive_redirects >= 3:
                logger.error("🛑 [风控锁死阻断] 检测到连续 > 3 次被猎聘防线轰回登录页，为规避帐号安全风险，将清除所有凭证并中断当前循环。")
                if os.path.exists(AUTH_FILE): 
                    try: os.remove(AUTH_FILE)
                    except: pass
                # 我们不再抛出异常，而是记录错误让协程在执行时自然短路
        elif response.status in [200]:
            # 一旦有任何正常的业务 200 返回，就降低警报阈值
            if "getConditionItem" in response.url or "api" in response.url:
                 self.consecutive_redirects = max(0, self.consecutive_redirects - 1)

    async def login(self):
        """执行密码登录与验证"""
        logger.info("[Login Step 1/6] 导航至猎聘登录页...")
        await self.page.goto("https://h.liepin.com/account/login")
        await random_delay()

        # 检测是否已经处于登录后的页面结构
        if "login" not in self.page.url:
            logger.info("[状态检查] 当前URL不存在login字符，认定为已经处于登录状态，跳过密码输入流程。")
            return True

        logger.info("[Login Step 2/6] 尝试切换密码登录模式")
        # 猎聘密码登录tab可能需要点击
        try:
            pwd_tab = self.page.locator("text='密码登录'").first
            if await pwd_tab.is_visible():
                 logger.debug("找到'密码登录'选项卡，正进行点击...")
                 await pwd_tab.click()
                 await random_delay(1, 2)
            else:
                 logger.debug("未找到'密码登录'选项卡，可能已在默认界面。")
        except Exception as e:
            logger.debug(f"切换密码登录异常 (可能无需切换): {e}")

        logger.info("[Login Step 3/6] 开始定位账户密码输入框")
        # 定位账户密码输入框并防瞬间填入
        try:
            username_input = self.page.locator('input[placeholder*="手机号"], input[name="loginName"]').first
            password_input = self.page.locator('input[placeholder*="密码"], input[name="userPwd"]').first

            logger.debug("填充用户名...")
            await username_input.type(USERNAME, delay=random.randint(100, 200))
            await random_delay(0.5, 1)
            logger.debug("填充密码...")
            await password_input.type(PASSWORD, delay=random.randint(100, 200))
            await random_delay(1, 2)

            login_btn = self.page.locator('button.quick-login-btn, button:has-text("登 录")').first
            logger.info("⏳ [Login Step 4/6] 提交登录表单...")
            await login_btn.click()
            
            logger.debug("提交完毕，等待页面响应并尝试激活滑块...")
            await self.page.mouse.move(0, 0)
            await asyncio.sleep(6)
        except Exception as e:
            logger.error(f"❌ [错误] 充填账户时发生错误: {e}")

        logger.info("[Login Step 5/6] 调用沙箱验证码检测逻辑...")
        await self.page.screenshot(path="debug_after_login_click.png")
        logger.debug("📸 已保存点击登录后的现场截图至 'debug_after_login_click.png'")
        
        # 调用验证码求解模块
        is_success = await slider_solver.solve_captcha_if_exists(self.page)
        
        logger.debug("再次等待页面结算跳转 (3秒)...")
        await asyncio.sleep(4)
        await self.page.screenshot(path="debug_final_login_result.png")
        
        is_still_login_page = await self.page.locator('text="密码登录"').first.is_visible()
        
        if is_success and not is_still_login_page:
            logger.info("[Login Step 6/6] ✅ 登录判定成功！正在保存 Cookie 和 LocalStorage 至 auth.json...")
            await self.context.storage_state(path=AUTH_FILE)
            await random_delay(2, 4)
            return True
        else:
            if HUMAN_INTERVENTION:
                logger.warning("🚨 [HUMAN] ⚠️ 检测到高级别风控（AI 打码线全线溃败）。将防线移交至架构师...")
                # 触发系统蜂鸣警报音
                print('\a') 
                print("\n\n" + "="*50)
                print("!!! 🚨 等待人工介入 🚨 !!!")
                print("由于验证码智能计算被阻击，程序已进入 Guardian 挂起状态。")
                print("请立即在弹出的有头浏览器中：")
                print("1. 手动将滑块拖曳至缺口处。")
                print("2. 您有 60 秒的有效时间操作，一旦滑动成功进入内页，程序将在一秒内感知识别并自动热更新 Session 进入自动循环。")
                print("="*50 + "\n\n")
                
                try:
                    # 利用非死等机制，监控后续业务页标志性元素
                    async def wait_until_login_bypassed():
                        start_time = time.time()
                        while time.time() - start_time < 60:
                            await asyncio.sleep(1)
                            if "login" not in self.page.url:
                                return True
                            # 有些情况还在login页但是其实框没了
                            is_login_box_visible = await self.page.locator('text="密码登录"').first.is_visible()
                            if not is_login_box_visible:
                                return True
                        return False

                    bypassed = await wait_until_login_bypassed()
                    
                    if bypassed:
                        logger.info("✅ [模块恢复] 感知到人工物理拨动滑块成功并完成跳转！正在重铸 Session Hot Patches...")
                        # [Phase 9] 实装热更新 - 手动换得的合法态立即固化
                        await self.context.storage_state(path=AUTH_FILE)
                        logger.info("✅ [复原系统] 获得通行证，准备重返流水线...")
                        return True
                    else:
                        logger.error("🛑 [超时] 60秒人工协作窗口已关闭，未侦测到实质性解困。登录宣告流产。")
                        return False
                        
                except Exception as ex:
                    logger.error(f"🛑 [异常] 守护者静默监控环路出错: {ex}")
                    return False
            else:
                logger.error(f"❌ [失败] 自动打码登录验证失败且系统未开启 HUMAN_INTERVENTION。当前留存页包含未登录特征。URL: {self.page.url}")
                return False

    async def execute_single_row_task(self, index, condition, raw_condition):
        """Phase 7: 原子化隔离单行任务，确保异常不蔓延且每次结束能回归原点"""
        # 前置校验已由调用方 execute_search 提前截断，此处保留原子任务的职能
        raw_job_title = str(condition.get("职位名称", ""))

        max_retries = 2
        for attempt in range(max_retries):
            try:
                # [Phase 5 降级修正案] 正则清洗，两步走策略
                raw_job_title = str(condition.get("职位名称", ""))
                clean_job_title = get_core_keyword(raw_job_title)
                
                if raw_job_title != clean_job_title:
                    logger.info(f"🔄 原始搜索词: {raw_job_title}")
                    logger.info(f"🧹 清洗后核心词: {clean_job_title}")
                    logger.info("ℹ️ 因 Phase 5 降级策略执行核心词搜索")
                
                # --- 第一步（默认）：执行清洗后的“职位名称”搜索 ---
                condition["职位名称"] = clean_job_title
                logger.info(f"🌀 [搜索层级] 第一步尝试: {clean_job_title}")
                await self.extractor.fill_search_condition(condition)
                hit_count = await self.extractor.process_list_and_save(condition)
                if hit_count is None: hit_count = 5 
                
                # --- 第二步（保底）：如果第一步结果为 0 且有原值，回退到对应的长文进行全文搜索 ---
                if hit_count == 0:
                    fallback_keyword = ""
                    # 首选：如果有“搜索关键词/摘要”字段
                    raw_summary = raw_condition.get("搜索关键词/摘要")
                    if pd.notna(raw_summary) and str(raw_summary).strip():
                        fallback_keyword = str(raw_summary).strip()
                        logger.warning(f"📉 [降维触发] 第一步命中 0 条。执行保底回退策略，自动切换至[搜索关键词/摘要]全文搜索：'{fallback_keyword}'")
                    elif raw_job_title != clean_job_title and raw_job_title:
                        fallback_keyword = raw_job_title
                        logger.warning(f"📉 [降维触发] 第一步命中 0 条。执行保底回退策略，搜索原词：'{fallback_keyword}'")
                        
                    if fallback_keyword:
                        # 重置搜索环境
                        await self.page.goto("https://h.liepin.com/search/getConditionItem")
                        await self.page.wait_for_load_state("networkidle")
                        await asyncio.sleep(1.0)
                        
                        condition["职位名称"] = fallback_keyword
                        await self.extractor.fill_search_condition(condition)
                        hit_count = await self.extractor.process_list_and_save(condition)
                
                # 跑通了，直接跳出重试循环
                break
                
            except Exception as e:
                logger.error(f"❌ 处理第 {index + 1} 条搜索条件时发生致命崩溃: {e}")
                
                # --- [Phase 6/10] 运行态会话自愈与表单防御 (Session Extractor Healing) ---
                current_url = self.page.url.lower()
                
                # [Phase 7/10] 判定是否是 DOM 结构体劫持或找不到输入框,或是 Tag 丢失
                is_hijacked = "CaptchaHijack" in str(e) or "Locator Error" in str(e) or "TagNotAppliedError" in str(e)
                
                if 'login' in current_url or 'passport' in current_url or is_hijacked:
                    logger.warning("🚨 [风控响应] 发现当前 URL 被踢回登录页或 DOM 遭遇劫持或失真！尝试启动自动救援流...")
                    
                    recovery_success = False
                    
                    if not is_hijacked:
                        # 如果是被踢回登录页，则清除 cookie 进行自动化密码/人工结合重新登录
                        try:
                            await self.context.clear_cookies()
                            if os.path.exists(AUTH_FILE): os.remove(AUTH_FILE)
                        except: pass
                        
                        # 强行阻塞唤起 GUI 登录
                        recovery_success = await self.login()
                    
                    if recovery_success:
                        logger.info("✅ [复原系统] 账号重新接管成功！正在重新导航回业务母港起点...")
                        try:
                            await self.page.goto("https://h.liepin.com/search/getConditionItem")
                            await self.page.wait_for_load_state("networkidle")
                        except Exception as nav_e:
                            logger.error(f"⚠️ [复原系统导航失败]: {nav_e}")
                            
                        if attempt < max_retries - 1:
                            logger.info(f"🔄 继续尝试重新爬取第 {index + 1} 条记录 (剩余重试 {max_retries - attempt - 1} 次)")
                            continue # 给一次重试本行的机会
                        else:
                            logger.error(f"🛑 [灾难] 第 {index + 1} 条记录已达到最大重连重爬上限，强制跳过本条！")
                            break
                    else:
                        if HUMAN_INTERVENTION:
                            logger.warning("🚨 [HUMAN] ⚠️ 自动修复流程崩溃或遭到拦截。正在等待人工风控接管 (Guardian)介入...")
                            print('\a') 
                            print("\n\n" + "="*50)
                            print("!!! 🚨 等待人工介入 🚨 !!!")
                            print("爬虫在执行搜索期间直接被系统阻断并踢回登录，或在底层被验证码透明劫持。")
                            print("请立即在弹出的有头浏览器中全手工完成验证码 或 点击登录 或 页面交互动作！")
                            print("您有 60 秒时间，一旦业务面输入框出现，即视为通过。")
                            print("="*50 + "\n\n")
                            
                            try:
                                async def wait_until_search_bypassed():
                                    start_time = time.time()
                                    while time.time() - start_time < 60:
                                        await asyncio.sleep(1)
                                        is_login = "login" in self.page.url or "passport" in self.page.url
                                        try:
                                            has_search_bar = await self.page.locator('input[placeholder*="职位/公司/行业"], input[placeholder*="搜职位"], .search-item input').first.is_visible()
                                        except:
                                            has_search_bar = False
                                            
                                        if not is_login and has_search_bar:
                                            return True
                                    return False
            
                                bypassed = await wait_until_search_bypassed()
                                
                                if bypassed:
                                    logger.info("✅ [模块恢复] 感知到架构师扫清路障！正在重铸 Session Hot Patches...")
                                    try:
                                        await self.context.storage_state(path=AUTH_FILE)
                                        await self.page.goto("https://h.liepin.com/search/getConditionItem")
                                        await self.page.wait_for_load_state("networkidle")
                                    except Exception as nav_e:
                                        logger.error(f"⚠️ [人工复原导航失败]: {nav_e}")
                                            
                                    if attempt < max_retries - 1:
                                        logger.info(f"🔄 继续尝试重新爬取第 {index + 1} 条记录 (最后重试机会)")
                                        continue 
                                    else:
                                        logger.error(f"🛑 [灾难] 第 {index + 1} 条记录人工复活后依旧失败达上限，跳过本条！")
                                        break
                                else:
                                    logger.error("🛑 [灾难] 60秒人工协作窗口已超时。单跳任务流产。")
                                    break
                            except Exception as ex:
                                logger.error(f"🛑 [异常] 守护者监控出错: {ex}")
                                break
                        else:
                            logger.error("🛑 [灾难] 重连流产且未开启 HUMAN_INTERVENTION。单跳任务流产。")
                            break
                break # 除了满足重连/恢复条件的 continue 以外，普通致命异常必须 break 掉重试循环以进入 finally 归零机制

    async def execute_search(self, start_index=0):
        """执行找人搜索核心逻辑 (支持断点游标)"""
        logger.info("🗺️ 导航至找人页面...")
        try:
            await self.page.goto("https://h.liepin.com/search/getConditionItem")
            await random_delay()
        except:
            pass
        
        if not os.path.exists(INPUT_EXCEL):
            logger.error(f"❌ 未找到输入文件 {INPUT_EXCEL}，退出执行。")
            return -1
            
        logger.info(f"📂 加载测试参数表格 {INPUT_EXCEL}")
        try:
            df = pd.read_excel(INPUT_EXCEL)
        except Exception as e:
            logger.error(f"❌ 无法读取参数表格 {INPUT_EXCEL}: {e}")
            return -1

        # === 重构：使用独立的 Clean_source 进行数据标准化 ===
        from Clean_source import DataProcessor
        from Clean_source.utils import handle_existing_output
        
        # 预检：处理输出文件冲突
        try:
            handle_existing_output(OUTPUT_EXCEL)
        except Exception as e:
            logger.error(f"❌ 预检失败，请检查文件是否被占用: {e}")
            return -1

        processor = DataProcessor(df)
        df_cleaned = processor.process()
        
        # 1. 任务流阻断校验：检查职位名称（搜索词）是否有效
        # 过滤掉职位名称为空的记录
        valid_tasks = df_cleaned[df_cleaned["职位名称"].apply(lambda x: bool(str(x).strip()) if pd.notna(x) and str(x).lower() != 'nan' else False)]
        total_valid = len(valid_tasks)
        
        if total_valid == 0:
            logger.critical("❌ [main] - 任务流阻断：未在数据源中发现有效搜索条件，任务强制中止。")
            return -1

        logger.info(f"📊 数据预处理完毕，共发现 {total_valid} 条合法搜索任务（总计 {len(df_cleaned)} 条记录）。")

        for index in range(start_index, len(df_cleaned)):
            row = df_cleaned.iloc[index]
            
            # 关键字段校验：空值拦截
            job_title = row.get("职位名称")
            if not job_title or not str(job_title).strip() or str(job_title).lower() == 'nan':
                logger.warning(f"⚠️ [main] - 跳过第 {index + 1} 条记录: Missing Key Field (职位名称为空或被过滤)")
                continue

            if self.page.is_closed():
                logger.error("🛑 侦测到主页面容器被强制关闭，中止后续迭代，抛出重启信号。")
                return index

            logger.info("=======================")
            logger.info(f"🔄 开始执行第 {index + 1} 条搜索条件")
            
            condition = row.to_dict()
            raw_condition = df.iloc[index].to_dict() # 保留原始数据引用（如需）
            
            try:
                # 调用原子任务
                await self.execute_single_row_task(index, condition, raw_condition)
                logger.info(f"✅ 第 {index+1} 条搜索条件流转完毕")
            except Exception as e:
                logger.error(f"🛑 单行任务外层意外挂起（此为兜底，保障整体不崩溃）：{e}")
                if "closed" in str(e).lower() or "timeout" in str(e).lower():
                    return index
            finally:
                # --- [Phase 10] 迭代自愈：防阻塞的 Reset 逻辑 ---
                logger.info("♻️ [Reset] 单跳数据逻辑结束，强制重启页面容器回到安全锚点...")
                try:
                    if not self.page.is_closed():
                        await asyncio.sleep(2)  # 等待前置操作余波散去
                        await self.page.goto("https://h.liepin.com/search/getConditionItem")
                        await self.page.wait_for_load_state("networkidle", timeout=10000)
                    else:
                        logger.error("🛑 致命失联：页面在 Reset 时已处于 closed 状态。")
                        return index
                except Exception as e:
                    logger.warning(f"⚠️ [Reset] 清洁复位时遇到卡顿或超时: {e}")
                    if "closed" in str(e).lower():
                        logger.error("🛑 致命失联：页面已处于 closed 状态，退出迭代。")
                        return index
                
                await random_delay(1.5, 3.5)
                
        # 跑完所有任务
        return -1

    async def precheck_auth(self):
        """增强型凭证预检逻辑，完全静默验证"""
        if not os.path.exists(AUTH_FILE):
            logger.debug("未发现本地 auth.json，必须执行密码登录。")
            return False
            
        # --- 新增: 本地文件24小时陈旧度探测 ---
        file_mod_time = os.path.getmtime(AUTH_FILE)
        current_time = time.time()
        if current_time - file_mod_time > 24 * 3600:
            logger.warning("⚠️ 发现 auth.json 距今已超过 24 小时。为规避反爬与重放攻击锁号风险，强制废弃旧凭据并唤醒重新登录。")
            try:
                os.remove(AUTH_FILE)
            except Exception as e:
                pass
            return False
            
        logger.info("探测到有效期内本地凭证，进行静默 HTTP 通透性预检...")
        if not self.playwright:
            self.playwright = await async_playwright().start()
            
        try:
            browser = await self.playwright.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
            context_options = self._get_browser_context_options()
            context = await browser.new_context(storage_state=AUTH_FILE, **context_options)
            
            await self._apply_stealth(context)
            page = await context.new_page()
            
            logger.debug("向测试接口 https://h.liepin.com/search/getConditionItem 抛出鉴权侦查")
            resp = await page.goto("https://h.liepin.com/search/getConditionItem", timeout=15000)
            await page.wait_for_load_state("domcontentloaded")
            
            if resp and resp.status == 200 and 'login' not in page.url and 'passport' not in page.url:
                try:
                    await page.wait_for_selector('input[placeholder*="职位/公司/行业"], input[placeholder*="搜职位"], .search-item input', timeout=4000)
                    logger.info("✅ 凭证预检通过 (正确加载HTML且元素渲染)，安全放行至业务核心。")
                    await browser.close()
                    return True
                except:
                    pass
            logger.warning("🧹 [WARN] Session 已失效，清理无效旧凭证避免沙盒污染...")
            await context.clear_cookies()
            try:
                 if os.path.exists(AUTH_FILE): os.remove(AUTH_FILE)
            except: pass
            
            await browser.close()
            return False
            
        except Exception as e:
            logger.error(f"静默预检抛出异常: {e}")
            return False

    def check_output_writable(self):
        """预检输出目录权限与文件锁定状态"""
        output_dir = Path(r"D:\ljg\Antigravity\Files\Output")
        try:
            # 强制创建 D:\ljg\Antigravity\Files\Output\ 及其子目录
            output_dir.mkdir(parents=True, exist_ok=True)
            # 测试目录下写入权限
            test_file = output_dir / "._write_test"
            with open(test_file, 'w') as f:
                f.write("test")
            test_file.unlink()
            
            # 测目标文件是否被外部独占打开
            if Path(OUTPUT_EXCEL).exists():
                try:
                    with open(OUTPUT_EXCEL, 'a') as f:
                        pass
                except PermissionError:
                    raise PermissionError(f"目标结果文件已被其他程序（如Excel）锁定，请关闭后重试：{OUTPUT_EXCEL}")
            
            logger.info(f"✅ [环境预检] 输出目录写权限与文件句柄均正常。")
            return True
        except Exception as e:
            logger.critical(f"❌ [main] - 任务流阻断：输出路径环境不满足写入条件！({e})")
            return False

    async def run(self):
        try:
            # 1. 启动初期预检：数据源文件必须存在
            if not os.path.exists(INPUT_EXCEL):
                logger.critical(f"❌ [main] - 任务流阻断：未在指定路径发现数据源文件 {INPUT_EXCEL}。程序强制终止。")
                raise FileNotFoundError(f"Missing source file: {INPUT_EXCEL}")

            # 2. 输出环境预检
            if not self.check_output_writable():
                raise PermissionError(f"输出环境阻塞。")

            is_auth_valid = await self.precheck_auth()
            await self.init_browser(use_cache=is_auth_valid)
            
            if not is_auth_valid:
                logger.info("凭证失效或不存在，即将唤起UI完成全套主流程认证。")
                success = await self.login()
                if not success:
                    logger.error("🛑 登录流产，主动终止后续源数据检索环节。")
                    return
            
            # --- Phase 10: 异常自愈自动重启 ---
            current_index = 0
            while True:
                try:
                    # 将游标输入，开始执行
                    current_index = await self.execute_search(start_index=current_index)
                    if current_index == -1: 
                        # -1 代表全量跑完，正常退出循环
                        break
                        
                    # 若没等于 -1 就跳出来了，说明一定是遇到 closed 或超时致命错误
                    logger.warning(f"⚠️ [进程自愈] 页面容器崩溃于第 {current_index + 1} 条，准备热重启恢复上下游环境...")
                    
                    # 首先进行强力收尾清场 (必须把整个 Playwright 驱动卸载，防止底层的 Connection Closed 死锁)
                    if hasattr(self, 'browser') and self.browser:
                        try: await self.browser.close()
                        except: pass
                    
                    if hasattr(self, 'playwright') and self.playwright:
                        try: await self.playwright.stop()
                        except: pass
                        self.playwright = None  # 必须置空，让 init_browser 重新拉起 Node 子进程
                    
                    # 稍微等待确保资源系统句柄释放
                    await asyncio.sleep(3)
                    
                    # 从缓存热重载浏览器 (连带底层 Playwright Socket 一起重建)
                    logger.info("🔄 重新初始化 Playwright 引擎与浏览器以恢复爬取...")
                    await self.init_browser(use_cache=True)
                    
                except Exception as e:
                    logger.error(f"❌ [自愈循环捕获到未处理崩溃]: {e}")
                    # 避免死循环狂抛
                    await asyncio.sleep(5)
                
            logger.info("👋 全量数据运行完毕，挂起10秒后退出...")
            await asyncio.sleep(10)
            
        except Exception as e:
            logger.error(f"❌ [致命崩塌] 主协程跑出了未拦截的错误: {e}")
        finally:
            logger.info("🧹 正在执行系统资源回收...")
            if hasattr(self, 'browser') and self.browser:
                try: await self.browser.close()
                except: pass
            if hasattr(self, 'playwright') and self.playwright:
                try: await self.playwright.stop()
                except: pass
            logger.info("✅ 退出销毁流程完毕。")

if __name__ == "__main__":
    bot = LiepinBot()
    asyncio.run(bot.run())
