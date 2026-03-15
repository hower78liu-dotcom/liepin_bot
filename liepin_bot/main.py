import argparse
import importlib
import sys
from loguru import logger
from paths import ensure_directories, PROJECT_ROOT
from src.core.logger import LoggerFactory

def main():
    # 1. 确保全局目录结构就位
    ensure_directories()
    
    # 2. 挂载主控日志
    LoggerFactory.setup_global_logger()
    logger = LoggerFactory.get_logger("orchestrator")
    logger.info(f"🚀 [Orchestrator] 系统启动. PROJECT_ROOT: {PROJECT_ROOT}")
    
    # 3. 解析命令行参数
    parser = argparse.ArgumentParser(description="Antigravity 自动化编排总控 (Orchestrator)")
    parser.add_argument(
        "--module", 
        type=str, 
        required=True, 
        help="指定要运行的插件模块名称，例如 'liepin_bot'"
    )
    # 不解析会导致如果 --module 在中间出问题，将所有参数传递过去
    args, unknown = parser.parse_known_args()
    
    target_module = args.module
    logger.info(f"🔌 [Orchestrator] 准备挂载并执行模块: {target_module}")
    
    # 4. 动态载入模块并执行契约方法 (run)
    try:
        # 因为我们已经把执行逻辑放到了 src.modules.<module>.task
        module_path = f"src.modules.{target_module}.task"
        
        # 动态导入
        plugin = importlib.import_module(module_path)
        
        # 校验接口契约：必须暴露一个 run(params: dict=None) 函数
        if not hasattr(plugin, 'run') or not callable(plugin.run):
            logger.error(f"❌ [Orchestrator] 插件契约不合规：模块 {module_path} 缺失可调用的 run() 入口函数。")
            sys.exit(1)
            
        logger.info(f"✅ [Orchestrator] 模块 {target_module} 挂载成功，即将移交控制权...")
        
        # 移交执行
        result = plugin.run()
        logger.info(f"🏁 [Orchestrator] 模块 {target_module} 执行完毕。返回结果: {result}")
        
    except ModuleNotFoundError as e:
        logger.error(f"❌ [Orchestrator] 无法找到指定的插件模块 '{target_module}': {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"🛑 [Orchestrator] 插件级致命崩溃，总控已捕获异常栈防止进程静默退出: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
