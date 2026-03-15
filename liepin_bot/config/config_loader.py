import os
from dotenv import load_dotenv
from paths import CONFIG_DIR, PROJECT_ROOT

# 我们默认寻找项目根目录的 .env 文件
ENV_PATH = PROJECT_ROOT / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)

class Config:
    @staticmethod
    def get(key: str, default=None):
        return os.getenv(key, default)

    @classmethod
    def get_bool(cls, key: str, default: bool = False) -> bool:
        val = cls.get(key)
        if val is None:
            return default
        return str(val).lower() in ("true", "1", "yes")

config = Config()
