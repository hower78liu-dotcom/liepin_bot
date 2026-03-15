# Antigravity 模块化开发标准规范 (AI v2.0)

> **致 AI 工程师**：你正在参与 Antigravity 项目的开发。本文档是**唯一的架构权威参考**。
> 在编写任何代码之前，必须完整阅读本文档。严禁任何形式的"自由发挥"。

---

## 〇、 如何使用本文档 (For AI Agents)

### 文档定位
本文件 `PROJECT_GUIDE.md` 位于项目根目录 `d:\ljg\Antigravity\liepin_bot\PROJECT_GUIDE.md`。
它是面向 AI 编程助手（如 Claude、Gemini、Cursor 等）的**强制阅读型开发规范**，旨在：
1. **防止架构漂移**：确保 AI 产出的新模块代码与既有系统 100% 兼容。
2. **统一接口契约**：所有插件必须暴露标准化的 `run()` 入口，才能被总控调度。
3. **消灭硬编码**：路径、配置、日志全部由基座层托管，模块不得自行解决。

### 标准调用方式
当用户要求 AI 开发新功能或新模块时，**第一步必须**引用本文件：

**推荐 Prompt 模板：**
```
请阅读 @[d:\ljg\Antigravity\liepin_bot\PROJECT_GUIDE.md]，
然后按照规范，为我开发一个新模块 [模块名]，功能是 [描述]。
```

AI 在接收到此 Prompt 后，应当：
1. ✅ 读取并确认理解本文档的全部规则
2. ✅ 在 `src/modules/<module_name>/` 下创建标准骨架
3. ✅ 使用本文档第三节的 `task.py` 模板作为入口
4. ✅ 完成后使用第六节的检查清单自验

### 相关文档导航
| 文档 | 受众 | 用途 |
| :--- | :--- | :--- |
| **PROJECT_GUIDE.md** (本文) | AI 开发者 | 架构约束与编码规范 |
| [README.md](README.md) | 所有人 | 项目概览、安装与启动 |
| [USER_MANUAL.md](USER_MANUAL.md) | 终端用户 | 配置操作与使用说明 |

---

## 一、 开发准则 (The Golden Rules)

1. **路径零硬编码**：严禁出现 `"C:/"`, `"D:/"`, `"./"`。所有路径必须引用 `paths.py`。
2. **配置零侵入**：模块内禁止直接读取 `.env` 或硬编码密码，必须通过 `config_loader.Config.get()` 获取。
3. **接口契约**：`src/modules/<name>/task.py` 是唯一对外接口，必须暴露 `run(params: dict = None) -> dict`。
4. **异常穿透**：严禁静默失败。捕获异常后必须 `logger.error()` 记录，关键错误需 `raise` 抛给总控。
5. **日志统一**：禁用 Python 原生 `print()`。全部使用 `LoggerFactory.get_logger()` 获取的日志器。
6. **类型约束**：优先使用 Type Hints，复杂结构建议使用 `TypedDict` 或 `dataclass` 约束。
7. **相对导入**：模块包内部文件之间**必须**使用 `from . import xxx` 或 `from .xxx import yyy` 形式。

---

## 二、 基座层 API 速查 (Infrastructure Quick Ref)

以下是团队已经开发完成的全局基建，新模块**必须直接复用**，严禁重复造轮子。

### 2.1 路径管理 — `paths.py`

```python
from paths import PROJECT_ROOT, SRC_DIR, MODULES_DIR, CORE_DIR, DATA_DIR, CONFIG_DIR, LOG_DIR, BACKUP_DIR

# 已暴露常量：
#   PROJECT_ROOT  → 项目根目录 (liepin_bot/)
#   SRC_DIR       → src/
#   MODULES_DIR   → src/modules/
#   CORE_DIR      → src/core/
#   DATA_DIR      → data/          ← 所有读写数据放这里
#   CONFIG_DIR    → config/        ← auth.json 等配置文件
#   LOG_DIR       → logs/          ← 日志、截图、崩溃现场
#   BACKUP_DIR    → data/backup/

# 使用示例：
input_file = DATA_DIR / "Input" / "MyModule" / "params.xlsx"
output_file = DATA_DIR / "Output" / "result.xlsx"
```

> ⚠️ `paths.py` 在被 import 时会**自动创建**所有缺失目录，无需手动 `mkdir`。

### 2.2 日志工厂 — `src/core/logger.py`

```python
from src.core.logger import LoggerFactory

# 获取模块专属日志器 (自动写入 logs/<module_name>_YYYY-MM-DD.log)
logger = LoggerFactory.get_logger("my_module")

logger.info("普通信息")
logger.warning("警告")
logger.error("错误")
logger.critical("致命崩溃")
```

> ⚠️ 注意：API 是 `LoggerFactory.get_logger()`，**不是** ~~`get_logger()`~~。

### 2.3 配置加载 — `config/config_loader.py`

```python
from config.config_loader import Config

username = Config.get("LIEPIN_USERNAME")
is_debug = Config.get_bool("DEBUG_MODE", default=False)
```

> 所有环境变量均从根目录 `.env` 文件读取。模块不得自行调用 `os.getenv()` 或 `load_dotenv()`。

---

## 三、 模块标准结构 (Standard Scaffolding)

所有新模块必须放置在 `src/modules/<module_name>/` 下并遵守以下目录树：

```text
src/modules/<module_name>/
├── __init__.py          # 空文件，标记为 Python 包
├── task.py              # 🔑 唯一入口：参数校验、资源调度、结果组装
├── processor.py         # 核心逻辑：业务算法、数据处理、页面交互
├── utils.py             # (可选) 模块内部辅助函数
└── schema.py            # (可选) TypedDict / dataclass 定义输入输出结构
```

### 现有模块参考实例

```text
src/modules/liepin_bot/          ← 第一个已上线的生产插件
├── __init__.py
├── task.py                      # run() 入口 + LiepinBot 类
├── LiepinSearch_Extractor.py    # DOM 解构与表单自动化 (相当于 processor)
├── slider_solver.py             # 滑块验证码 CV 破解
├── ai_normalizer.py             # AI 辅助字段标准化
├── condition_normalizer.py      # 搜索条件语义拆解
└── Clean_source/                # 数据清洗子包
    ├── __init__.py
    ├── cleaners.py
    ├── ai_engine.py
    └── utils.py
```

---

## 四、 接口协议规范 (task.py Template)

每个模块的 `task.py` 必须遵循以下模板：

```python
"""
模块名称: <module_name>
功能描述: <一句话说明>
"""
from src.core.logger import LoggerFactory
from config.config_loader import Config
from paths import DATA_DIR, CONFIG_DIR, LOG_DIR
from pathlib import Path
from typing import Dict, Any, Optional

logger = LoggerFactory.get_logger("<module_name>")

def run(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    标准插件入口 — 被 main.py Orchestrator 动态调用

    :param params: 可选参数字典，结构如下：
        {
            "task_id": str,       # (可选) 任务唯一标识
            "payload": dict,      # (可选) 业务参数
        }
    :return: {
        "status": "success" | "error",
        "data": Any,
        "message": str
    }
    """
    params = params or {}
    task_id = params.get("task_id", "default")
    logger.info(f"[{task_id}] 模块启动")

    try:
        # === 业务逻辑区 ===
        # 1. 从 processor.py 导入并调用核心处理函数
        # 2. 组装返回结果
        
        return {
            "status": "success",
            "data": {},
            "message": "执行完毕"
        }
    except Exception as e:
        logger.exception(f"[{task_id}] 执行崩溃: {e}")
        return {"status": "error", "data": None, "message": str(e)}
```

### 总控如何调用你的模块

`main.py` 通过以下方式动态装载：
```python
# main.py 内部核心逻辑 (无需修改)
plugin = importlib.import_module(f"src.modules.{module_name}.task")
result = plugin.run(params)  # 调用你的 run()
```

启动方式：
```bash
python main.py --module <module_name>
```

---

## 五、 AI 开发标准工作流 (Must Follow)

### Step 1: 上下文锁定
```
我需要开发新模块 [模块名]。
请阅读 @[PROJECT_GUIDE.md]，确认你已理解路径管理、task.py 契约和异常处理要求。
```

### Step 2: 骨架生成
```
请在 src/modules/[模块名]/ 下创建标准骨架文件。
先提供 task.py 的完整代码（含 run() 签名），processor.py 用 pass 占位。
确保接口符合 PROJECT_GUIDE 第四节的模板。
```

### Step 3: 逻辑实现
```
现在请实现 processor.py 的核心业务逻辑。
要求：
- 文件读写必须使用 paths.py 常量
- 日志必须使用 LoggerFactory.get_logger()
- 不得硬编码路径或敏感信息
- 包内引用使用 from . import xxx
```

### Step 4: 自检对齐 (推荐)
```
请对照 PROJECT_GUIDE.md 第六节的检查清单，逐项验证代码合规性。
如有违规请立即修复。
```

---

## 六、 防跑偏检查清单 (Anti-Drift Checklist)

| # | 检查项 | 判定标准 | 违规等级 |
| :---: | :--- | :--- | :---: |
| 1 | **路径硬编码** | 代码中出现 `"C:/"`, `"D:/"`, `"../"` 或 `os.path.abspath()` | 🔴 拦截 |
| 2 | **入口违规** | `task.py` 未定义 `run()` 函数 | 🔴 拦截 |
| 3 | **Logger 违规** | 使用 `print()` 或 `from loguru import logger` 直接使用 | 🟡 警告 |
| 4 | **Logger API 错误** | 使用 `get_logger()` 而非 `LoggerFactory.get_logger()` | 🔴 拦截 |
| 5 | **环境污染** | 模块内调用 `os.getenv()` / `load_dotenv()` / 硬编码密码 | 🔴 拦截 |
| 6 | **导入方式** | 包内文件使用 `import xxx` 而非 `from . import xxx` | 🟡 警告 |
| 7 | **`__init__.py` 缺失** | 新模块目录下没有 `__init__.py` | 🔴 拦截 |
| 8 | **返回值不合规** | `run()` 未返回 `{"status": ..., "message": ...}` 格式字典 | 🟡 警告 |
| 9 | **调试残留** | 提交代码中包含 `debug_*.png`, `tmp_*.py` 等临时文件 | 🟡 警告 |

---

## 七、 项目目录总览 (当前状态)

```text
liepin_bot/                         # 项目根目录
├── main.py                         # 🎯 Orchestrator 总控入口
├── paths.py                        # 📍 全局路径常量中心
├── verify_restructure.py           # ✅ 系统健康体检脚本
├── PROJECT_GUIDE.md                # 📘 本文档 (AI 开发规范)
├── README.md                       # 项目介绍
├── USER_MANUAL.md                  # 用户操作手册
├── .env                            # 🔐 环境变量 (不上传)
├── .gitignore
│
├── config/                         # 配置中心
│   ├── config_loader.py            #   环境变量加载器
│   └── auth.json                   #   浏览器凭证缓存 (自动生成)
│
├── data/                           # 读写隔离数据层
│   ├── Input/                      #   输入数据源
│   └── Output/                     #   输出结果
│
├── logs/                           # 运行日志 & 风控截图
│
└── src/
    ├── core/                       # 核心基座
    │   └── logger.py               #   单例日志工厂
    └── modules/                    # 🔌 插件模块区
        └── liepin_bot/             #   已上线：猎聘抓取插件
            ├── task.py
            ├── LiepinSearch_Extractor.py
            ├── slider_solver.py
            └── Clean_source/
```

---

> **最后提醒**：本文档随项目演进持续更新。如果新增了基座层能力（如数据库连接池、消息队列），请同步在第二节中补充 API 说明。
