import os
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

def print_result(msg: str, success: bool):
    prefix = "✅" if success else "❌"
    print(f"{prefix} {msg}")

def verify_structure():
    print("=== 开始自动化重构环境验证 (Verification) ===")
    
    project_root = Path(__file__).parent.resolve()
    
    # 核心目录预期表
    expected_dirs = [
        project_root / "src" / "core",
        project_root / "src" / "modules" / "liepin_bot",
        project_root / "config",
        project_root / "logs",
        project_root / "data" / "Input" / "Liepin",
        project_root / "data" / "Output"
    ]
    
    for d in expected_dirs:
        print_result(f"目录探测: {d.relative_to(project_root)}", d.exists() and d.is_dir())
        
    expected_files = [
        project_root / "paths.py",
        project_root / "main.py",
        project_root / "src" / "modules" / "liepin_bot" / "task.py",
        project_root / "src" / "core" / "logger.py",
        project_root / "config" / "config_loader.py",
        project_root / "data" / "Input" / "Liepin" / "test_search.xlsx"
    ]
    
    for f in expected_files:
        print_result(f"文件探测: {f.relative_to(project_root)}", f.exists() and f.is_file())
        
    # 测试主干连通性
    try:
        from paths import PROJECT_ROOT
        print_result("引用探测: paths.py 能够正常导入", True)
    except Exception as e:
        print_result(f"引用探测: paths.py 导入受阻 ({e})", False)

    try:
        from src.core.logger import LoggerFactory
        print_result("引用探测: src.core.logger.LoggerFactory 能够正常导入", True)
    except ImportError as e:
        print_result(f"引用探测: src.core.logger.LoggerFactory 导入受阻 ({e})", False)
        
    print("\n=== 验证阶段结束 ===")
    
if __name__ == "__main__":
    verify_structure()
