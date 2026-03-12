# 猎聘自动化抓取任务列表

此任务列表是对本次自动化脚本需求的具象化排期，所有开发步骤需勾选确认。

## 前期准备与规划 (Planning)
- [x] 读取分析 `AutoLogin_Ref.md`。
- [x] 读取分析 `liepin_crawler_task_plan.md`。
- [x] 生成 `implementation_plan.md` 供用户审核与修正实现细节。

## 阶段一：基础架构与反检测配置 (Infrastructure & Anti-Bot)
- [ ] 初始化 Playwright 环境配置（包含 `headless=False` 与拦截 WebDriver 特征的 `playwright-stealth` 配置）。
- [ ] 设置持久化 Browser Context (用于复用登录 Session `auth.json`)。
- [ ] 封装真实 User-Agent 与全局统一的随机事件延迟机制。

## 阶段二：自动化登录与验证码突破 (Auth & Captcha)
- [ ] 导航至猎聘密码登录页并填写账户密码 (`type()` 模拟逐字节敲击输入)。
- [ ] 配置页面检测与等待 iframe 的弹窗（若出现）。
- [ ] 编写 OpenCV 验证码背景 / 滑块截图缺口计算函数。
- [ ] 编写基于物理拟真的三段式（加速-匀速-回弹抖动）位移轨迹算法。
- [ ] 完成自动化滑动事件派发并验证登录是否成功。

## 阶段三：源数据加载与表单驱动 (Source Load & Form Navigation)
- [ ] 加载 `D:\ljg\leipin\test_search.xlsx` 的条件集合。
- [ ] 遍历检索行：完成字段至猎聘页面找人筛选项的自动化点击与输入映射（涵盖城市、年龄边界、经验等下拉联动处理）。
- [ ] 实现针对“学历要求”字段的向下兼容扩展逻辑（专科及以上包含专、本、硕、博下拉勾选实现）。
- [ ] 加入页面搜索结果空集检测。若为空，安全跳转至下条检索语句。

## 阶段四：名片级详情抓取与拼装 (Extraction & Structuring)
- [ ] 编写循环切入逻辑：每组检索限制最大采集 20 个 C 端用户条目。
- [ ] 针对弹窗名片或新标签页的数据实施爬虫规则映射：定位抽取姓名、求职意向以及核心履历块（工作、项目、教育等）。
- [ ] 将本次结果与母表中的关键词组合并压入输出缓冲队列。

## 阶段五：数据沉淀与交付 (Data Persistence)
- [ ] 构建严格对齐目标要求的输出 Pandas Dataframe / OpenPyXL Row 对象。
- [ ] 建立每条目落地写入 `D:\ljg\leipin\Get_result\Get_result_leipin.xlsx` 的保存触发逻辑（边拿边存或单组批量写入）。
- [ ] 清理、销毁浏览器上下文释放资源。
