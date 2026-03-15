from pathlib import Path

# 获取项目根目录 (liepin_bot 的顶层绝对路径)
PROJECT_ROOT = Path(__file__).resolve().parent

# 定义全局架构目录字典
SRC_DIR = PROJECT_ROOT / "src"
MODULES_DIR = SRC_DIR / "modules"
CORE_DIR = SRC_DIR / "core"

DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = PROJECT_ROOT / "config"
LOG_DIR = PROJECT_ROOT / "logs"
BACKUP_DIR = DATA_DIR / "backup"

# 暴露的统一常量引用，保障工程各处在运行前能够确保这些基础目录实体存在
def ensure_directories():
    for d in [SRC_DIR, MODULES_DIR, CORE_DIR, DATA_DIR, CONFIG_DIR, LOG_DIR, BACKUP_DIR]:
        d.mkdir(parents=True, exist_ok=True)

# 装载时立即校验创建
ensure_directories()
