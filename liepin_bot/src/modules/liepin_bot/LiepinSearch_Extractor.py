import asyncio
import random
import pandas as pd
import os
import json
import re
from dateutil.relativedelta import relativedelta
from datetime import datetime
from loguru import logger
import time
from pathlib import Path

class LiepinResumeExtractor:
    # --- 架构约束: 提取文件表头结构化字段作为类常量解耦 ---
    EXCEL_COLUMNS = [
        "职位名称", "公司名称", "工作城市", "经验要求", "学历要求", 
        "年龄要求", "候选人名称", "求职意向", "期望薪资",
        "工作经历(全量)", "项目经历(全量)", "教育经历(全量)"
    ]
    # --- 这里修改每条搜索记录需要获取的匹配候选人条数 ---
    def __init__(self, page, output_excel, max_records=20):
        self.page = page
        self.output_excel = str(Path(output_excel).resolve())
        self.max_records = max_records
        self.results = []
        
        # 确保目录存在
        try:
            Path(self.output_excel).parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"目录创建失败或非法路径（仅在特殊预检中抛出）: {e}")
        self.init_excel()

    def init_excel(self):
        """初始化输出 Excel 表头并确保所有的父级结构正确挂载"""
        out_path = Path(self.output_excel)
        # --- 架构约束: 目标明确要求递归检查并创建所有不存在的父级目录 ---
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"目录安全兜底捕获异常 (非法路径或被独占): {e}")

        # --- 架构约束: 文件初始化协议 ---
        if not out_path.exists():
            try:
                # 严禁因文件缺失导致进程中断，初始化预设表头的空 Excel 模板
                df = pd.DataFrame(columns=self.EXCEL_COLUMNS)
                df.to_excel(self.output_excel, index=False)
                logger.info(f"✨ 检测到目标结果本不存在已为其自动初始化模板结构：{self.output_excel}")
            except Exception as e:
                logger.warning(f"初始化空 Excel 文件结构时发生异常: {e}")

    async def _safe_click(self, locator, timeout=5000):
        """带有随机延迟的安全点击，附带透传降级策略防止阻挡"""
        await asyncio.sleep(random.uniform(0.5, 1.5))
        try:
            await locator.click(timeout=timeout)
        except Exception as e:
            logger.debug(f"常规点击被阻塞 ({str(e).split('==')[0][:40]}...), 尝试强制穿透点击")
            await locator.click(force=True, timeout=3000)

    async def _smart_click(self, locator, label="element", timeout=5000):
        """
        智能点击：先检查 is_visible + is_enabled，再执行带拟人延迟的安全点击。
        若元素不可见或被禁用，记录日志并跳过。
        """
        try:
            if not await locator.is_visible(timeout=timeout):
                logger.warning(f"[smart_click] {label} not visible, skip")
                return False
            if not await locator.is_enabled(timeout=2000):
                logger.warning(f"[smart_click] {label} disabled, force enable")
                await locator.evaluate("node => node.removeAttribute('disabled')")
            await self._safe_click(locator, timeout=timeout)
            return True
        except Exception as e:
            logger.warning(f"[smart_click] {label} click failed: {e}")
            return False

    async def _screenshot_on_error(self, context_name):
        """Timeout or error auto-screenshot to LOG_DIR"""
        try:
            from paths import LOG_DIR
            snap_path = LOG_DIR / f"error_{context_name}_{int(time.time())}.png"
            await self.page.screenshot(path=str(snap_path), full_page=True)
            logger.info(f"[Screenshot] saved: {snap_path}")
        except Exception as e:
            logger.debug(f"Screenshot save failed: {e}")

    async def _safe_type(self, locator, text):
        """带有随机延迟的安全逐字输入"""
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await locator.type(text, delay=random.randint(50, 150))

    async def expand_education_levels(self, base_edu):
        """只针对最底层核心学历提取单点Tag特征，防止多选演变为交集"""
        base_edu = str(base_edu)
        if "博士" in base_edu:
            return ["博士/博士后"]
        elif "硕士" in base_edu:
            return ["硕士"] # 不再自动勾选博士，猎聘单选“硕士”往往本身就涵盖向上要求，甚至只需要匹配字面
        elif "本科" in base_edu:
            return ["本科"]
        elif "大专" in base_edu or "专科" in base_edu:
            return ["大专"]
        return [base_edu.replace('及以上', '').replace('统招', '').strip()]

    async def fill_search_condition(self, condition):
        """
        填充搜索表单 (不再处理活跃度等极易触发风控的弱相关特征)
        """
        logger.info(f"🔍 准备施加搜索条件: {condition.get('职位名称', '空')}")
        
        # [Phase 10] 拟人: 随机沉思沉浸式浏览
        logger.debug("🤔 [拟人] 执行页面随机沉思沉浸浏览...")
        await self.page.mouse.wheel(0, random.randint(100, 500))
        await asyncio.sleep(random.uniform(1.0, 3.0))
        await self.page.mouse.wheel(0, random.randint(-500, -100))
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        # 调试截屏，确保此时页面处于正常搜索态而非别处
        await self.page.screenshot(path="debug_before_search_input.png", full_page=True)
        logger.debug("📸 截取了开始定位输入框前的界面: debug_before_search_input.png")
        
        # --- 重构1: 职位名称 (带联想触发的输入) ---
        search_input = self.page.locator('input[placeholder*="职位/公司/行业"]').first
        if not await search_input.is_visible(timeout=5000):
            # 兜底旧版或者A/B Test方案
            search_input = self.page.locator('.search-item input').first
        logger.info("🛠️ [Phase 7] 启动稳态预检与交互式表单重构流程...")
        # ==========================================
        # 1. 稳态守护：必须确保核心 DOM 承载节点就位！
        # ==========================================
        try:
            # 等待搜索区域整体可视，兼容新老版本的顶层容器类名
            await self.page.wait_for_selector('.search-condition-wrap, .search-resume-wrap-v3', state='visible', timeout=20000)
            logger.debug("✅ [稳态预检] 检测到条件搜索基础面板渲染完毕。")
        except Exception as e:
            logger.error(f"❌ [稳态崩塌] 严重超时：搜索面板未能在规定时间生成，可能触发验证码重定向！{e}")
            # [致命转储] WAF 黑箱探测保护现场
            from paths import LOG_DIR
            dump_filename = LOG_DIR / f"waf_crash_dump_{int(time.time())}.html"
            with open(dump_filename, "w", encoding="utf-8") as f:
                f.write(page_content)
            await self.page.screenshot(path=str(LOG_DIR / "waf_crash_screenshot.png"), full_page=True)
            logger.error(f"📸 崩溃现场 DOM 拓扑已强制倾泻至 {dump_filename}，快照已封存！")
            raise e # 向外层主动抛出，交接给 runtime healer

        # --- 重构1: 职位名称 (带人体工学抖动与指纹隐匿) ---
        target_text = str(condition.get("职位名称", "")).strip()
        if target_text:
            # 增强定位：寻找带有该占位符的 input
            search_input = self.page.locator('input[placeholder*="搜职位"], input[placeholder*="职位/公司/行业"], .search-item input').first
            
            if await search_input.is_visible():
                # [Phase 10] 拟人：输入框防激惹聚焦
                # 几何中心悬停并点击
                box = await search_input.bounding_box()
                if box:
                    center_x = box['x'] + box['width'] / 2
                    center_y = box['y'] + box['height'] / 2
                    await self.page.mouse.move(center_x + random.randint(-10, 10), center_y + random.randint(-5, 5))
                    await asyncio.sleep(0.2)
                    await self.page.mouse.down()
                    await asyncio.sleep(0.1)
                    await self.page.mouse.up()
                else:
                    await search_input.click(position={'x': random.randint(2, 8), 'y': random.randint(2, 8)})
                
                await asyncio.sleep(0.5) # 给下拉联想列表弹出的渲染时间
                
                # 拟人清除：点击 -> 全选 -> 物理删除 -> 回调缓冲双重清理防污染
                await self.page.keyboard.press("Control+A")
                await self.page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(0.1, 0.4))
        # --- 重构1: 职位名称与公司注入 (带异常捕获防挂起) ---
        target_text = ""
        is_job_title = False
        if pd.notna(condition.get("职位名称")):
             target_text = str(condition["职位名称"]).strip()
             is_job_title = True
        elif pd.notna(condition.get("搜索关键词/摘要")):
             target_text = str(condition["搜索关键词/摘要"]).strip()

        if target_text:
             logger.info(f"🔍 准备施加搜索条件: {target_text}")
             await self.page.mouse.move(100, 200)
             await asyncio.sleep(random.uniform(1.0, 2.0))
             
             # 截图定位前状态用于 debug
             from paths import LOG_DIR
             temp_snap = LOG_DIR / "debug_before_search_input.png"
             await self.page.screenshot(path=str(temp_snap))
             logger.debug(f"📸 截取了开始定位输入框前的界面: {temp_snap}")
             
             logger.info("🛠️ [Phase 7] 启动稳态预检与交互式表单重构流程...")
             
             # 动态确定输入框
             if is_job_title:
                 main_input = self.page.locator('span:has-text("职位名称：")').locator("..").locator('input[type="search"]').first
             else:
                 main_input = self.page.locator('input[placeholder*="职位/公司/行业"]').first

             # 稳态预检：等待条件面板渲染
             try:
                 await main_input.wait_for(state="visible", timeout=10000)
                 logger.debug("✅ [稳态预检] 检测到条件搜索基础面板渲染完毕。")
             except Exception as e:
                 logger.warning(f"⚠️ 稳态预检未找到主输入框 ({e})，尝试继续。")
                 
             if await main_input.count() > 0:
                 await main_input.fill("")
                 await asyncio.sleep(0.5)
                 logger.debug(f"⌨️ [隐匿模式] 按序缓注 '{target_text}'...")
                 await main_input.press_sequentially(target_text, delay=random.randint(50, 250))
                 await asyncio.sleep(0.5)
                 
                 # 猎聘要求按回车或者等下拉联想框消失
                 await self.page.keyboard.press("Enter")
                 # ... 其他延迟
                 await asyncio.sleep(2.0)
                 
                 logger.info(f"✅ 核心搜索参数精准拟人注入完成: '{target_text}' (类别: {'职位名称' if is_job_title else '全局关键词'})")
             else:
                 logger.error("❌ [Locator Error] 未能找到目标核心输入框")
                 page_content = await self.page.content()
                 from paths import LOG_DIR
                 with open(LOG_DIR / "debug_input_error.html", "w", encoding="utf-8") as f:
                     f.write(page_content)
                 raise Exception("CaptchaHijack (猎聘风控阻击): 无法定位职位输入框。DOM 结构异常！")
            
        # --- 重构2: 工作城市 (相对锚点查找 + 弹窗搜索兜底) ---
        if pd.notna(condition.get("工作城市")):
            city_name = str(condition["工作城市"]).strip()
            city_selected = False

            # 锚定"期望城市"文本的父级块
            city_block = self.page.locator('span:has-text("期望城市")').locator("..").first
            # 在父级块内精确寻找 tag
            city_label = city_block.locator(f'label:has-text("{city_name}"), .tag-label-group label:has-text("{city_name}")').first
            if await city_label.is_visible():
                await self._safe_click(city_label)
                await asyncio.sleep(0.5)
                classes = await city_label.evaluate("el => el.className")
                if 'active' in classes or 'selected' in classes or 'checked' in classes:
                    logger.info(f"[City] Tag hit: {city_name}")
                    city_selected = True
                else:
                    logger.warning(f"[City] Tag clicked but no active class for {city_name}")

            # 兜底：点击"其他"打开城市弹窗 -> 搜索框输入 -> 选中 -> 确认
            if not city_selected:
                other_btn = city_block.locator('label:has-text("其他"), .btn-choose:has-text("其他"), button:has-text("其他")').first
                if await other_btn.is_visible():
                    await self._smart_click(other_btn, label="city-other-btn")
                    await asyncio.sleep(1.5)

                    # 等待城市选择弹窗出现
                    city_modal = self.page.locator('.ant-modal-content, .ant-drawer-content, [class*="city-modal"], [class*="city-select"]').first
                    try:
                        await city_modal.wait_for(state='visible', timeout=5000)
                    except Exception:
                        logger.warning("[City] Modal did not appear, trying to continue")

                    # 在弹窗中查找搜索输入框
                    search_input = self.page.locator(
                        'input[placeholder*="搜索城市"], '
                        'input[placeholder*="搜索"], '
                        '.ant-modal-content input[type="text"], '
                        '.ant-modal input'
                    ).first

                    if await search_input.is_visible(timeout=3000):
                        await search_input.click()
                        await asyncio.sleep(0.3)
                        await search_input.fill("")
                        await asyncio.sleep(0.2)
                        await search_input.press_sequentially(city_name, delay=random.randint(80, 200))
                        await asyncio.sleep(1.5)
                        logger.debug(f"[City] Typed in modal search: {city_name}")

                        # 点击搜索结果中匹配的城市
                        city_result = self.page.locator(
                            f'.ant-modal-content span:has-text("{city_name}"), '
                            f'.ant-modal-content label:has-text("{city_name}"), '
                            f'.ant-modal-content div:text-is("{city_name}")'
                        ).first
                        if await city_result.is_visible(timeout=3000):
                            await self._smart_click(city_result, label=f"search-result-{city_name}")
                            await asyncio.sleep(0.5)
                            logger.info(f"[City] Selected in modal: {city_name}")

                            # 点击确认按钮
                            confirm_btn = self.page.locator(
                                '.ant-modal-content button:has-text("确认"), '
                                '.ant-modal-content button:has-text("确定"), '
                                '.ant-modal-footer button.ant-btn-primary'
                            ).first
                            if await confirm_btn.is_visible(timeout=3000):
                                await confirm_btn.click(force=True)
                                await asyncio.sleep(0.5)
                                logger.info(f"[City] Modal confirmed")
                                city_selected = True
                            else:
                                logger.warning("[City] Confirm button not found")
                                await self._screenshot_on_error("city_confirm")
                        else:
                            logger.warning(f"[City] No search result for '{city_name}'")
                            await self._screenshot_on_error("city_search")
                    else:
                        # 没有搜索框，尝试直接在弹窗内点击
                        direct_city = self.page.locator(f'.ant-modal-content :text-is("{city_name}")').first
                        if await direct_city.is_visible(timeout=3000):
                            await self._smart_click(direct_city, label=f"direct-{city_name}")
                            await asyncio.sleep(0.5)
                            confirm_btn = self.page.locator(
                                '.ant-modal-content button:has-text("确认"), '
                                '.ant-modal-content button:has-text("确定")'
                            ).first
                            if await confirm_btn.is_visible(timeout=3000):
                                await confirm_btn.click(force=True)
                                city_selected = True
                                logger.info(f"[City] Direct click in modal: {city_name}")
                        else:
                            logger.warning("[City] No search input and no direct match in modal")
                            await self._screenshot_on_error("city_modal_empty")

            if not city_selected:
                logger.warning(f"[City] FAILED to select: {city_name}")

        # --- 重构3: 经验要求 (防挂起弹性寻址 + AntD容忍) ---
        if pd.notna(condition.get("经验要求")):
             exp_val = str(condition["经验要求"]).strip()
             exp_block = self.page.locator('span:has-text("工作年限：")').locator("..").first
             
             # 【新增 Phase 7】使用包含文本的模糊容错查找。不要使用 class 等硬条件捆绑
             # 注意：对于 '8-99年' 这样的输入可能在页面渲染成了 '8年以上'，此时使用 textMatches
             if '-' in exp_val and exp_val.split('-')[1] == '99年':
                 fuzzy_base = exp_val.split('-')[0]  # 提取 '8'
                 exp_label = exp_block.locator(f'label:text-matches("{fuzzy_base}年以上", "g")').first
             else:
                 exp_label = exp_block.locator(f'label:text-is("{exp_val}"), label:has-text("{exp_val}")').first
             
             if await exp_label.is_visible():
                  await self._safe_click(exp_label)
                  await asyncio.sleep(0.5)
                  logger.info(f"✅ 成功勾选工作年限: {exp_val}")
             else:
                  # 尝试自定义按钮
                  custom_label = exp_block.locator('label:has-text("自定义")').first
                  if await custom_label.is_visible():
                      await self._safe_click(custom_label)
                      await asyncio.sleep(0.5)
                      
                      low = exp_val.split('-')[0] if '-' in exp_val else exp_val.replace('年', '').replace('以上', '')
                      high = exp_val.split('-')[1].replace('年', '') if '-' in exp_val else ''
                      
                      inputs = exp_block.locator('input.interval-input')
                      if await inputs.count() >= 2:
                          if low:
                              await inputs.nth(0).evaluate("node => node.removeAttribute('disabled')")
                              await inputs.nth(0).press_sequentially(low, delay=random.randint(50, 100))
                          if high:
                              await inputs.nth(1).evaluate("node => node.removeAttribute('disabled')")
                              await inputs.nth(1).press_sequentially(high, delay=random.randint(50, 100))
                              
                          submit_btn = exp_block.locator('button.shadow-box-submit-btn').first
                          if await submit_btn.is_visible(): 
                              await self._safe_click(submit_btn)
                              logger.info(f"✅ 成功填入自定义工作年限: {low}-{high}")
                  else:
                      logger.warning(f"⚠️ 工作年限自定义按钮未找到，跳过经验要求注入")

        # --- 学历要求 (AntD 下拉框向下兼容多选) ---
        if pd.notna(condition.get("学历要求")):
             edu_val = str(condition["学历要求"]).strip()
             target_levels = await self.expand_education_levels(edu_val)
             # 使用文本容错匹配
             edu_title = self.page.locator('span:has-text("学历要求"), span:has-text("教育经历")').first
             if await edu_title.is_visible():
                 edu_block = edu_title.locator("..").first
                 
                 # 场景 A: 存在直接露出的 Tag 标签池（旧式）
                 if await edu_block.locator('.tag-item').count() > 0:
                     actual_selected = []
                     for level in target_levels:
                         edu_checkbox = edu_block.locator(f'.tag-item:has-text("{level}")').first
                         if await edu_checkbox.is_visible():
                             await self._safe_click(edu_checkbox)
                             actual_selected.append(level)
                     if actual_selected:
                         logger.info(f"🎓 [INFO] 成功点选学历 Tag: {', '.join(actual_selected)}")
                 
                 # 场景 B: Ant Design Select (点击展开 -> 等待浮层 -> 文本匹配点击)
                 else:
                     selector_box = edu_block.locator('.ant-select-selector').first
                     if await selector_box.is_visible():
                         try:
                             # 增加缓冲降温期防止连击焦点吞没
                             await asyncio.sleep(1.0)
                             # force防劫持
                             await selector_box.click(force=True)
                             await self.page.wait_for_selector('.ant-select-dropdown:visible', timeout=3000)
                             
                             actual_selected = []
                             for level in target_levels:
                                 # 严格依据用户提供的类名与文本定位器
                                 edu_option = self.page.locator(f'.ant-select-dropdown:visible .ant-select-item-option-content:has-text("{level}")').first
                                 if await edu_option.is_visible():
                                     await edu_option.scroll_into_view_if_needed()
                                     await edu_option.click(force=True)
                                     actual_selected.append(level)
                                     await asyncio.sleep(0.3)
                                     
                             logger.info(f"🎓 [INFO] 条件：{edu_val} | 实际尝试勾选: {', '.join(actual_selected)}")
                         except Exception as e:
                             logger.error(f"❌ [ERROR] 点击“学历要求”下拉框失败，当前页面未发现正确的选项组: {e}")
                         
        # --- 重构4: 年龄要求 (带特殊实体字符的容错与相对锚点自定义赋值) ---
        if pd.notna(condition.get("年龄要求")):
            age_str = str(condition["年龄要求"]).strip()
            # 通过匹配核心汉字“龄”规避全半角空格陷阱
            age_block = self.page.locator('span:text-matches("龄", "g")').locator("..").first
            if await age_block.is_visible():
                low, high = "", ""
                if '-' in age_str:
                    low, high = age_str.split('-')
                else:
                    low = age_str.replace('岁', '').replace('以上', '')
                    
                low, high = low.replace('岁', ''), high.replace('岁', '')
                
                # 同样的需要激活自定义输入框面版
                custom_btn = age_block.locator('.interval-input-box').first
                if await custom_btn.count() > 0: 
                    await custom_btn.evaluate("node => node.click()")
                    await asyncio.sleep(0.5)
                
                # 【防黑盒 Phase 7】使用相对 placeholder 重构，替代 #ageLow 绝对挂靠锁死
                input_low = age_block.locator('input[placeholder="最低"]').first
                input_high = age_block.locator('input[placeholder="最高"]').first
                
                if low and await input_low.is_visible(): 
                    await input_low.evaluate("node => node.removeAttribute('disabled')")
                    await input_low.press_sequentially(low, delay=random.randint(60, 110))
                if high and await input_high.is_visible(): 
                    await input_high.evaluate("node => node.removeAttribute('disabled')")
                    await input_high.press_sequentially(high, delay=random.randint(60, 110))
                
                submit_btn = age_block.locator('.shadow-box-submit-btn').first
                if await submit_btn.is_visible():
                    await self._safe_click(submit_btn)
        
        # --- 重构5: 活跃度处理 (AntD body Portal 脱离流挂载与二次检索) ---
        if pd.notna(condition.get("活跃度")):
            act_str = str(condition["活跃度"]).strip()
            
            # 精确查找容器，增加稳定度
            act_block = self.page.locator('.search-condition-item:has-text("活跃度")').first
            if not await act_block.is_visible():
                # 兼容猎聘老旧DOM或者渲染延迟的情况
                act_title = self.page.locator('span:has-text("活跃度"), span:has-text("活跃度：")').first
                if await act_title.is_visible():
                    act_block = act_title.locator("..").first
                    
            if await act_block.is_visible():
                selector_box = act_block.locator('.ant-select-selector').first
                if await selector_box.is_visible():
                    max_retries = 2
                    for attempt in range(max_retries):
                        try:
                            # 先关闭可能残留的其他 AntD 浮层
                            await self.page.keyboard.press("Escape")
                            await asyncio.sleep(0.8)
                            
                            await selector_box.click(force=True)
                            await asyncio.sleep(1.5)  # 给 AntD Portal 动画渲染更多时间
                            
                            # 等待浮层面板生成，过滤隐藏的旧DOM
                            dropdown_selector = '.ant-select-dropdown:not(.ant-select-dropdown-hidden):visible'
                            await self.page.wait_for_selector(dropdown_selector, state='visible', timeout=8000)
                            
                            act_option = self.page.locator(dropdown_selector).locator(f'.ant-select-item-option-content:has-text("{act_str}")').first
                            if await act_option.is_visible():
                                await act_option.scroll_into_view_if_needed()
                                await act_option.click(force=True)
                                await asyncio.sleep(0.5)
                                logger.info(f"✅ 成功勾选活跃度: {act_str}")
                            else:
                                logger.warning(f"⚠️ 活跃度浮层已展开但未找到选项 '{act_str}'")
                            break  # 成功则退出重试
                        except Exception as e:
                            if attempt < max_retries - 1:
                                logger.warning(f"⚠️ 活跃度下拉框第 {attempt+1} 次尝试失败，重试中... ({e})")
                                await asyncio.sleep(1.0)
                            else:
                                logger.error(f"❌ [ERROR] 点击“活跃度”下拉框交互失败或超时 (已重试 {max_retries} 次): {e}")
                        
        # --- 显式提交搜索表单 (防呆保障) ---
        search_btn_final = self.page.locator('.search-btn:has-text("搜 索"), button:has-text("搜索")').first
        if await search_btn_final.is_visible():
            await self._safe_click(search_btn_final)
            logger.debug("🖱️ [拟人] 已显式点击全局搜索按钮确认执行联动。")
            
        # --- 前置联动预检记录 (检查搜错项有没有被挂在全局 Tag 上) ---
        await asyncio.sleep(2.0)
        try:
            # 猎聘的选区实际上在 `.search-suck-quick-filter` 或 `.search-tags-box` 里的文本
            tags_box = self.page.locator('.search-suck-quick-filter, .search-tags-box').first
            if await tags_box.is_visible():
                combined_tag_str = await tags_box.inner_text()
                logger.debug(f"🔍 [DEBUG] 提交前页面显示的全局活动 Tag 区: {combined_tag_str}")
                
                # 严格拦截规则
                if not combined_tag_str.strip():
                    logger.error("❌ [风控/拦截] 全局活动 Tag 在提交前为空，视为表单未能成功激活任何条件！")
                    from paths import LOG_DIR
                    dump_path = LOG_DIR / f"failed_tags_{int(time.time())}.png"
                    await self.page.screenshot(path=str(dump_path), full_page=True)
                    logger.error(f"📸 丢失 Tags 的 DOM 快照已保存: {dump_path}")
                    raise Exception("TagNotAppliedError: 猎聘UI未响应，搜索参数被丢弃！")
                    
                if target_text and target_text not in combined_tag_str:
                    logger.warning(f"⚠️ 核心词 [{target_text}] 没有出现在底部活动 Tags 中")
            else:
                logger.debug("⚠️ 未找到 .search-suck-quick-filter 元素进行预检验证。")
                
        except Exception as e:
            if "TagNotAppliedError" in str(e):
                raise e # 抛给外层引发 try except 重试
            logger.debug(f"Tag 预检过程本身异常（可能定位符变更）: {e}")

        # --- 最终: 触发搜索并等待网络歇息 ---
        search_submit = self.page.locator('button.ant-btn-primary.search-btn, button:has-text("搜索")').first
        if await search_submit.is_visible():
            await self._safe_click(search_submit)
        
        await self.page.wait_for_timeout(2000)
        # 兼容处理: 复杂的 B 端如果存在长轮询可能无法达到严格 idle，兜底退化等待加载遮罩消散
        try:
            await self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            logger.debug("等待 networkidle 超时，使用兜底延时等待页帧解冻。")

    async def extract_resume_detail(self, detail_page):
        """抓取名片/新页面的简历结构数据 (Phase 8: 基于 ant-drawer-body 深度建模)"""
        data = {
            "候选人名称": "",
            "求职意向": "",
            "工作经历": "[]",
            "项目经历": "[]",
            "教育经历": "[]"
        }
        
        # --- 候选人名称 ---
        try:
            name_selectors = [
                '.ant-drawer-body .name',
                '.resume-name',
                '.name-text',
                '.ant-drawer-header .ant-drawer-title',
                '.new-resume-personal .name'
            ]
            for sel in name_selectors:
                name_el = detail_page.locator(sel).first
                if await name_el.count() > 0 and await name_el.is_visible(timeout=1000):
                    data["候选人名称"] = (await name_el.inner_text()).strip()
                    break
        except Exception as e:
            logger.debug(f"候选人名称提取异常(非致命): {e}")
        
        # --- 求职意向 ---
        try:
            intent_selectors = [
                'div.job-intention',
                '.ant-drawer-body section:has-text("求职意向")',
                'div:has-text("求职意向") >> .detail-content',
            ]
            for sel in intent_selectors:
                intent_el = detail_page.locator(sel).first
                if await intent_el.count() > 0 and await intent_el.is_visible(timeout=1000):
                    data["求职意向"] = (await intent_el.inner_text()).strip()
                    break
        except Exception as e:
            logger.debug(f"求职意向提取异常(非致命): {e}")

        # --- 通用经历结构化提取 ---
        async def parse_experience_list(selectors_list):
            """尝试多组选择器，提取经历列表为 JSON"""
            arr = []
            for selector in selectors_list:
                els = await detail_page.locator(selector).all()
                if els:
                    for el in els:
                        try:
                            raw = await el.inner_text()
                            if raw and raw.strip():
                                arr.append({"raw_text": raw.strip()})
                        except Exception:
                            pass
                    if arr:
                        break  # 找到了就不再尝试后续选择器
            return json.dumps(arr, ensure_ascii=False)

        # --- 工作经历 ---
        try:
            data["工作经历"] = await parse_experience_list([
                'div.work-experience-item',
                '.ant-drawer-body section:has-text("工作经历") .experience-item',
                '.ant-drawer-body .work-list .item',
            ])
        except Exception as e:
            logger.debug(f"工作经历提取异常(非致命): {e}")
            
        # --- 项目经历 ---
        try:
            data["项目经历"] = await parse_experience_list([
                'div.project-experience-item',
                '.ant-drawer-body section:has-text("项目经历") .experience-item',
                '.ant-drawer-body .project-list .item',
            ])
        except Exception as e:
            logger.debug(f"项目经历提取异常(非致命): {e}")
            
        # --- 教育经历 ---
        try:
            data["教育经历"] = await parse_experience_list([
                'div.edu-experience-item',
                '.ant-drawer-body section:has-text("教育经历") .experience-item',
                '.ant-drawer-body .edu-list .item',
            ])
        except Exception as e:
            logger.debug(f"教育经历提取异常(非致命): {e}")
            
        return data

    async def process_list_and_save(self, condition):
        """处理列表并写入Excel (Phase 10: 列表预解析与详情容灾降级机制)"""
        # 检查是否为空结果
        empty_tip = self.page.locator('text="抱歉，没有找到符合条件的候选人"').first
        if await empty_tip.is_visible(timeout=2000):
            logger.info("🈳 该条件无搜索结果，跳过")
            return 0

        # 获取列表卡片
        cards = await self.page.locator('.candidate-card, .user-card, .tlog-common-resume-card').all()
        fetch_len = min(len(cards), self.max_records)
        
        if len(cards) == 0:
            logger.warning("⚠️ 未提取到任何卡片，如果你在页面上看到了结果，说明猎聘再次更改了 DOM 类名！")
            
        logger.info(f"📊 当前条件下命中 {len(cards)} 条，计划抽取前 {fetch_len} 条")
        
        # 初始化缓冲池
        data_buffer = []
        
        for i in range(fetch_len):
            card = cards[i]
            
            # === Phase 10: 第一遍提取 (First Pass Summary) 预组装底表数据 ===
            card_name = ""
            card_intent = ""
            try:
                name_el_card = card.locator('.new-resume-personal-name em').first
                if await name_el_card.count() > 0:
                    card_name = (await name_el_card.inner_text()).strip()
                intent_el_card = card.locator('.personal-expect-content, .new-resume-personal-expect').first
                if await intent_el_card.count() > 0:
                    card_intent = (await intent_el_card.inner_text()).strip()
            except Exception:
                pass
                
            # 基础预案数据，若详情页加载失败，则用此数据落盘
            row_data = {
                "职位名称": condition.get("职位名称", ""),
                "公司名称": condition.get("公司名称", ""),
                "工作城市": condition.get("工作城市", ""),
                "经验要求": condition.get("经验要求", ""),
                "学历要求": condition.get("学历要求", ""),
                "年龄要求": condition.get("年龄要求", ""),
                "候选人名称": card_name,
                "求职意向": card_intent,
                "期望薪资": "缺失(降级)",
                "工作经历(全量)": "采集超时，请手动查看",
                "项目经历(全量)": "采集超时，请手动查看",
                "教育经历(全量)": "采集超时，请手动查看"
            }

            # --- 穿透式点击唤起策略 ---
            click_target = None
            name_el = card.locator('.new-resume-personal-name, .new-resume-personal-name em, .user-info .name').first
            if await name_el.count() > 0:
                click_target = name_el
            else:
                avatar_el = card.locator('img.new-resume-logo, .user-avatar img').first
                if await avatar_el.count() > 0:
                    click_target = avatar_el
                else:
                    click_target = card.locator('div.new-resume-personal').first
            
            try:
                box = await click_target.bounding_box()
                if box:
                    cx = box['x'] + box['width'] / 2 + random.randint(-3, 3)
                    cy = box['y'] + box['height'] / 2 + random.randint(-3, 3)
                    await self.page.mouse.move(cx, cy, steps=random.randint(5, 15))
                    await asyncio.sleep(random.uniform(0.1, 0.3))
            except Exception:
                pass
            
            detail_target = None
            is_new_page = False
            detail_success = False
            
            try:
                async with self.page.context.expect_page(timeout=3000) as new_page_info:
                    await self._safe_click(click_target)
                detail_target = await new_page_info.value
                is_new_page = True
                logger.debug(f"↗️ 第 {i+1} 条触发了新标签页详情")
            except Exception:
                logger.debug(f"第 {i+1} 条未触发新页面，检测侧边栏...")
                detail_target = self.page
                drawer_locator = self.page.locator('.ant-drawer, .resume-detail, .resume-drawer, [class*="drawer"], [class*="detail-content"], [class*="resume-side"], .ant-drawer-content').first
                try:
                    await drawer_locator.wait_for(state='visible', timeout=15000)
                    detail_success = True
                except Exception:
                    # 二次兜底：尝试更宽泛的选择器
                    try:
                        fallback_drawer = self.page.locator('.ant-drawer-body, [class*="resume"][class*="detail"]').first
                        await fallback_drawer.wait_for(state='visible', timeout=5000)
                        detail_success = True
                        logger.debug(f"第 {i+1} 条通过兜底选择器检测到侧边栏")
                    except Exception:
                        logger.warning(f"⚠️ 第 {i+1} 条侧边栏无法界定或渲染超时，将采用卡片表面数据降级存储。")
            
            # 详情提取挂载与解析块
            if detail_success or is_new_page:
                if is_new_page:
                    try:
                        await detail_target.wait_for_load_state("networkidle", timeout=10000)
                    except:
                        pass
                else:
                    try:
                        await self.page.locator('text="求职意向", text="工作经历", .ant-drawer-body').first.wait_for(state="visible", timeout=6000)
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                    except:
                        pass
                        
                # === Phase 10: 第二遍深层提取 ===
                try:
                    deep_data = await self.extract_deep_resume_detail(detail_target, card_name)
                    # 全量覆盖更新 row_data
                    row_data["候选人名称"] = deep_data.get("候选人名称", card_name)
                    row_data["求职意向"] = deep_data.get("求职意向", card_intent) or card_intent
                    row_data["期望薪资"] = deep_data.get("期望薪资", "")
                    row_data["工作经历(全量)"] = deep_data.get("工作经历", "[]")
                    row_data["项目经历(全量)"] = deep_data.get("项目经历", "[]")
                    row_data["教育经历(全量)"] = deep_data.get("教育经历", "[]")
                except Exception as e:
                    logger.error(f"❌ 详情页核心解析抛错: {e}，将使用局部降级数据。")
            
            # --- 缓冲组装 ---
            data_buffer.append(row_data)
            
            # --- 触发批量写盘 (缓冲达 10 条 或 最后一条) ---
            if len(data_buffer) >= 10 or i == fetch_len - 1:
                await self._atomic_save_batch(data_buffer)
                # 清空缓冲池，准备装载下一批
                data_buffer.clear()
                
            # --- 防阻塞闭环：抹平状态 ---
            if is_new_page:
                try:
                    await detail_target.close()
                except:
                    pass
            else:
                try:
                    await self.page.keyboard.press("Escape")
                    await asyncio.sleep(0.5)
                    close_btn = self.page.locator('button.ant-drawer-close, .close-btn, [class*="close-icon"]').first
                    if await close_btn.is_visible():
                        await close_btn.click(timeout=2000)
                    # Mask 兜底
                    mask = self.page.locator('.ant-drawer-mask').first
                    if await mask.is_visible():
                        await mask.click(position={"x": 5, "y": 5}, timeout=2000)
                except:
                    pass

            await asyncio.sleep(random.uniform(0.8, 1.5))
            
        return len(cards)

    async def extract_deep_resume_detail(self, detail_target, card_name=""):
        """穿透式核心：深层提取整份简历的各个板块 (应对侧边栏DOM)"""
        data = {
            "候选人名称": card_name,
            "求职意向": "",
            "期望薪资": "",
            "工作经历": "[]",
            "项目经历": "[]",
            "教育经历": "[]"
        }
        
        try:
            # --- 解析姓名 ---
            name_el = detail_target.locator('.resume-name, h2.name, h1.name, .user-name').first
            if await name_el.count() > 0:
                extracted_name = (await name_el.inner_text()).strip()
                if extracted_name:
                    data["候选人名称"] = extracted_name
            
            # 如果上一步没拿到，再尝试详情页em
            if not data["候选人名称"]:
                em_name = detail_target.locator('.new-resume-personal-name em').first
                if await em_name.count() > 0:
                    data["候选人名称"] = (await em_name.inner_text()).strip()

            # --- 求职意向 与 薪水期望 ---
            intent_block = detail_target.locator('div:has-text("求职意向")').last
            if await intent_block.count() > 0:
                txt = await intent_block.inner_text()
                data["求职意向"] = txt.replace('\n', ' | ')
                
                salary_match = re.search(r'(\d+[-]\d+[kKwW].*?薪|\d+[万wW])', txt)
                if salary_match:
                    data["期望薪资"] = salary_match.group(1).strip()
                else:
                    pay_el = detail_target.locator('.salary, .pay, [class*="pay-text"]').first
                    if await pay_el.count() > 0:
                        data["期望薪资"] = (await pay_el.inner_text()).strip()

            # --- 工作经历 (全量) ---
            work_items = []
            work_blocks = await detail_target.locator('div:has-text("工作经历")').last.locator('ul > li, div.work-exp-item, .exp-item').all()
            if len(work_blocks) == 0:
                work_blocks = await detail_target.locator('h3:has-text("工作经历") ~ div').all()

            for wk in work_blocks:
                try:
                    work_text = await wk.inner_text()
                    if work_text and len(work_text.strip()) > 5:
                        work_items.append({"工作明细": work_text.replace('\n', ' | ')})
                except:
                    pass
            data["工作经历"] = json.dumps(work_items, ensure_ascii=False) if work_items else "[]"

            # --- 项目经历 (全量) ---
            proj_items = []
            proj_blocks = await detail_target.locator('div:has-text("项目经历")').last.locator('ul > li, div.project-exp-item').all()
            for pk in proj_blocks:
                try:
                    proj_text = await pk.inner_text()
                    if proj_text and len(proj_text.strip()) > 5:
                        proj_items.append({"项目明细": proj_text.replace('\n', ' | ')})
                except:
                    pass
            data["项目经历"] = json.dumps(proj_items, ensure_ascii=False) if proj_items else "[]"

            # --- 教育经历 (全量) ---
            edu_items = []
            edu_blocks = await detail_target.locator('div:has-text("教育经历")').last.locator('ul > li, div.edu-exp-item').all()
            for ek in edu_blocks:
                try:
                    edu_text = await ek.inner_text()
                    if edu_text and len(edu_text.strip()) > 3:
                        edu_items.append({"教育明细": edu_text.replace('\n', ' | ')})
                except:
                    pass
            data["教育经历"] = json.dumps(edu_items, ensure_ascii=False) if edu_items else "[]"
            
        except Exception as e:
            logger.error(f"❌ 详情页全量抽取时发生硬错: {e}")
            
        return data

    async def _atomic_save_batch(self, data_buffer: list) -> bool:
        """
        核心解耦方法: 带有 3 次锁定重试的原子化写入
        确保数据在内存安全转移至临时文件，无误后在宿主系统替换原始文件
        """
        if not data_buffer:
            return True
        import shutil
        
        df = pd.DataFrame(data_buffer)
        out_path = Path(self.output_excel)
        tmp_path = out_path.with_name(f"{out_path.name}.tmp.xlsx")
        
        write_success = False
        # 强制防备底层目录不存在
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
             pass
             
        for attempt in range(1, 4):  # 1, 2, 3 次重试
            try:
                # 原子前置处理：如果源文件存在且有内容，复制一份当做垫底的切片用于续写
                if out_path.exists():
                    shutil.copy2(out_path, tmp_path)
                else:
                    # 如果不存在，临时造一个表头骨架
                    pd.DataFrame(columns=self.EXCEL_COLUMNS).to_excel(tmp_path, index=False)
                
                # 开始针对副本切片执行危险的 IO（append 写）
                with pd.ExcelWriter(tmp_path, mode='a', if_sheet_exists='overlay', engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, header=False, startrow=writer.sheets['Sheet1'].max_row)
                    
                # 【原子替换核爆点】：若前置 append 无任何异常，说明临时切片组装成功，开始致命的原子替代
                # Path.replace 在 Windows/POSIX 下均为强原子语义，若原文件被软占用则会触发 PermissionError
                tmp_path.replace(out_path)
                
                logger.info(f"💾 [Atomic Write] 第 {attempt} 轮尝试：成功原子批量落盘 {len(data_buffer)} 条数据！")
                write_success = True
                break
                
            except PermissionError as e:
                logger.warning(f"⚠️ [锁定警告] 写盘遇阻！目标文件 {out_path.name} 极可能正被 Excel 或系统独占！")
                logger.warning(f"👉 请立即手动关闭该文件。程序将在 5 秒后执行第 {attempt}/3 次自动重试... ({e})")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"❌ [IO 异常] 原子写盘期间遇到未预期的底层异常：{e} (第 {attempt}/3 轮)")
                await asyncio.sleep(3)
            finally:
                # [清洁机制] 如果副本没能成功替换，证明这一轮脏了或者没走完，把垃圾切片删掉释放句柄
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except:
                        pass
        
        # --- 如果三次耗尽还是没有突破封锁，触发终极熔断底线防丢 ---
        if not write_success:
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            local_backup_dir = Path(__file__).parent.resolve() / "backup"
            local_backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = local_backup_dir / f"backup_failed_records_{timestamp}.csv"
            try:
                df.to_csv(backup_path, index=False, encoding='utf-8-sig')
                logger.critical(f"🚨 [灾难恢复] 连续 3 次 Excel 写锁重试耗尽！已将 {len(data_buffer)} 条抓取数据转储强制保存为 CSV 至: {backup_path}")
                # 向外部返回失败状态
                return False
            except Exception as fatal_e:
                logger.critical(f"💀 [完全失联] CSV 紧急备份抢救失败！这批数据彻底丢失在内存！原因: {fatal_e}")
                return False
                
        return True

