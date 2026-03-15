# 猎聘自动化抓取机器人 (Liepin Bot)

## 📖 项目简介
本项目是一个基于 Playwright 与 Orchestrator-Plugin (总控-插件化) 架构设计的自动化招聘数据抓取引擎。
主要解决企业或用人单位在猎聘网进行大批量候选人结构化简历精确匹配与抓取的效率要求。程序内置了全自动登录状态轮换、滑块验证码绕过（本地自研模式/云打码API双保险）以及对抗高级防爬机制（Anti-Bot）的拟人化轨迹仿真等自愈能力。

## ✨ 核心特性

- **🛡️ 守护者机制 (Guardian Mode)**: 遇到高级别滑块验证码阻击时，自动进入挂起状态并发出蜂鸣警报，提供 60 秒人工接管窗口，完成后自动同步 Session。
- **🩹 自动化自愈系统 (Self-Healing)**: 
    - **Session 预检**: 启动时静默模拟请求，检测 Cookie 是否过期，24 小时陈旧凭证强制重拉。
    - **进程热重启**: 监测到底层 Playwright Socket 崩溃或页面 Closed 时，自动重装驱动并从断点位置续爬。
    - **迭代复位**: 每条任务完成后强制回归锚点 URL，清理残留浮层。
- **💾 原子化数据保障 (Atomic Persistence)**:
    - **原子写盘**: 采用“副本编辑-整体替换”策略，彻底解决 Excel 被占用时导致的写盘崩溃问题。
    - **熔断备份**: 连续 3 次写文件锁定失败后，自动启动极速 CSV 紧急落盘，确保采集数据零丢失。
- **🧠 智能降级策略**:
    - **语义清洗**: 自动提取职位名称核心词进行第一波搜索，命中为 0 时自动回退至长关键词全文搜索。
    - **详情容灾**: 侧边栏/新页详情加载超时后，自动采用卡片表面数据（First Pass）降级落盘。
- **🤖 AI 深度简历评估 (CV Matcher)**:
    - **LLM 并发推理**: 内置多线程请求引擎，自动获取回填的“岗位预算薪资”，结合候选人全量经历与目标职位 JD 进行多维评分。
    - **MD5 极速缓存**: 采用本地 Cache 阻挡重复运算，大幅降低 Token 消耗并加速重复职位检验。
- **🔌 核心 AI 基座 (AIService)**:
    - **持久化配额管理**: 自动追踪已用 Token，基于 JSON 同步额度水位，防止费用超支。
    - **弹性重试机制**: 针对 SiliconFlow 等平台 503/Rate Limit 错误内置 3 次自动重试逻辑。
    - **精准 Token 预估**: 集成 `tiktoken` 编码器，在请求发送前校准输入长度。
- **🔄 全双工数据管道 (Pipeline Synchronization)**:
    - 具备完整的双向数据同步生态，实现从《项目清单》清洗、自动生成《投递指令表》，直至最终抓取结果回填（Left Join 架构）的无缝自动化流转。

#### **AI 模块概览表**

| 模块名 | AI 核心功能 | 核心逻辑位置 | 提升说明 |
| --- | --- | --- | --- |
| DataCleaner | 职位/行业自动归类 | `src/modules/data_cleaner/ai_engine.py` | 提高清洗准确度，支持模糊与语义匹配 |
| CV Matcher | 简历-JD 深度匹配 | `src/modules/cv_matcher/processor.py` | 实现 4 维度专家级打分，特别引入**岗位预算参考**，使匹配度结果更具参考价值 |

## 🏗️ 架构设计图
项目的代码遵循总调度路由与底层实施插件相隔离的现代化微内核设计原则：

```mermaid
graph TD
    A[main.py (Orchestrator 总控)] -->|挂载 --module liepin_bot| B(src/modules/liepin_bot/task.py)
    
    subgraph Core Infrastructure [全局基建层]
        C[paths.py (全局路径与约束)] -.注入.-> A
        D[src/core/logger.py (分级日志设施)] -.注入.-> A
        E[config/config_loader.py (密钥桥接)] -.注入.-> A
    end

    subgraph Plugin Business [猎聘垂直业务层]
        B -.-> F(LiepinBot 引擎)
        F --> G(LiepinSearch_Extractor.py: DOM 解构)
        F --> H(slider_solver.py: 过验证与 CV 计算)
        F --> I(Clean_source: 数据管道与清洗)
    end
    
    subgraph Data Space [读写隔离区]
        J[(data/Input/.../test_search.xlsx)] -->|消费| B
        B -->|原子覆写| K[(data/Output/Get_result_leipin.xlsx)]
        L[(Data_Cleaned.xlsx)] -.同步.-> J
        K -.回填与AI评分.-> K
    end
```

## 📁 核心目录结构
经过 Orchestrator 重构后，项目完全与无状态执行对齐：
```text
liepin_bot/
├── main.py                     # 全局入口调度器
├── paths.py                    # 跨平台相对路径定义中心
├── verify_restructure.py       # 系统健康/结构一致性体检脚本
├── config/                     # 配置中心 (含 auth.json)
├── data/                       # 读写隔离数据层 (Input / Output)
├── logs/                       # 所有执行追踪日志与风控截图快照
└── src/
    ├── core/                   # 核心基座 (如单例 logger, AIService)
    │   ├── logger.py
    │   └── ai_client.py        # 封装 Token 统计、限额与重试逻辑
    └── modules/
        └── liepin_bot/         # 猎聘专用执行插件
            ├── Clean_source/   # 专属简历与数据字段清洗打平包
            ├── task.py         # 插件入口
            ├── LiepinSearch_Extractor.py
            └── slider_solver.py
        ├── data_cleaner/           # 项目初期数据清洗与城市爆破拆分
        ├── liepin_search_preparer/ # 搜刮前指令同步模块
        ├── result_data_enricher/   # 结果拉链/多主键回填映射模块
        └── cv_matcher/             # AI 大模型自动简历评审模块
```

## 🛠️ 安装步骤

1. **底层引擎要求**:
   确保您的电脑上已安装 Python 3.9 或更高版本。

2. **三方依赖绑定**:
   在项目根目录下打开终端，执行以下命令安装核心依赖栈，并下载专用的无头 Chromium 浏览器内核：
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **配置下发**:
   您需要在系统根目录提供 `.env` 配置文件以承载敏感数据（避免将账号直接写在代码里上传），详情可参见 [用户手册 (USER_MANUAL.md)](USER_MANUAL.md)。

## 🚀 启动与运行

通过统一管理核心 `main.py` 调用您的插件以启动程序调度。指定要执行的组件代号：

**模块流转生命周期**：
1. **数据清洗**: `python main.py --module data_cleaner`
2. **指令下发**: `python main.py --module liepin_search_preparer`
3. **爬虫作业**: `python main.py --module liepin_bot`
4. **数据回灌**: `python main.py --module result_data_enricher`
5. **AI 评审**: `python main.py --module cv_matcher`

> **💡 贴士:** 运行期间产生的所有追踪数据（包含 401/403 的拦截 DOM 快照、CV 框图抓拍、运行 Info 轨迹）均会被自动分类下沉到 `logs/` 文件夹，您可以借此进行崩溃复盘。

## 📐 开发者专区

如果您计划为本项目开发新的插件模块（例如新增其他招聘平台或数据清洗功能），请务必先阅读：

📚 **[PROJECT_GUIDE.md](PROJECT_GUIDE.md)** — AI 开发规范与架构约束文档

该文档包含：
- 基座层 API 速查表（路径、日志、配置）
- 模块标准骨架与 `task.py` 接口契约模板
- AI 开发三步工作流
- 防跑偏检查清单

## 📚 文档导航

| 文档 | 受众 | 用途 |
| :--- | :--- | :--- |
| [README.md](README.md) | 所有人 | 项目简介、安装与启动 |
| [USER_MANUAL.md](USER_MANUAL.md) | 终端用户 | 配置操作与使用说明 |
| [PROJECT_GUIDE.md](PROJECT_GUIDE.md) | AI 开发者 | 架构约束与编码规范 |
