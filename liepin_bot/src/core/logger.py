import sys
import os
from loguru import logger
from paths import LOG_DIR
import time

class LoggerFactory:
    """全局单例 Logger 工厂，支持按模块名动态分发日志文件"""
    _initialized = False

    @classmethod
    def setup_global_logger(cls):
        if cls._initialized:
            return
            
        logger.remove()
        
        # 为了兼容 Windows 终端的中文字符打印报错，设定 utf-8 控制台
        # 但在通用封装库中，防止多次强刷，尽量使用 try except 捕捉或依赖上游
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

        # 终端全局输出 INFO 及以上级别
        logger.add(
            sys.stdout, 
            level="INFO", 
            format="[{time:YYYY-MM-DD HH:mm:ss}] [{level}] [{module}/{function}] - {message}"
        )
        
        # 全局异常捕获底垫 (统一记录所有的 WARNING 及以上到总控 master 日志)
        master_log_path = LOG_DIR / "master.log"
        logger.add(
            str(master_log_path), 
            level="WARNING", 
            format="[{time:YYYY-MM-DD HH:mm:ss}] [{level}] [{module}/{function}] - {message}", 
            rotation="10 MB"
        )
        
        cls._initialized = True

    @classmethod
    def get_logger(cls, module_name: str):
        """
        根据模块名称派生一个独立的 file handler。
        例如传入 'liepin', 将单独录入 logs/liepin.log
        """
        cls.setup_global_logger()
        
        file_path = LOG_DIR / f"{module_name}_{time.strftime('%Y-%m-%d')}.log"
        
        # 增加一个 filter 过滤器，利用 bind 的 context 限定特定文件写入
        logger.add(
            str(file_path),
            level="DEBUG",
            format="[{time:YYYY-MM-DD HH:mm:ss}] [{level}] [{module}/{function}] - {message}",
            rotation="00:00",
            filter=lambda record: record["extra"].get("module_name") == module_name
        )
        
        return logger.bind(module_name=module_name)

# 暴露一个默认总控日志器备用
global_logger = LoggerFactory.get_logger("orchestrator")
