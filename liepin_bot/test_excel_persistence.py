import os
import sys
import asyncio
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
from loguru import logger
from pathlib import Path
import shutil
import time

# 设置基础路径以导入
BASE_PATH = r"D:\ljg\Antigravity"
BOT_PATH = r"D:\ljg\Antigravity\liepin_bot"
if BASE_PATH not in sys.path:
    sys.path.append(BASE_PATH)
if BOT_PATH not in sys.path:
    sys.path.append(BOT_PATH)

from LiepinSearch_Extractor import LiepinResumeExtractor

async def setup_test_environment(tmp_path: Path):
    """清理并准备测试环境"""
    if tmp_path.exists():
        shutil.rmtree(tmp_path)
    tmp_path.mkdir(parents=True)

async def test_auto_create_dir_and_init(tmp_path: Path):
    print("\n--- Testing: 目录不存在与自动初始化 ---")
    deep_path = tmp_path / "deep" / "nested" / "output.xlsx"
    
    # 初始化 extractor，期望其自动创建 deep/nested 并在其中生成带着明细表头的 output.xlsx
    extractor = LiepinResumeExtractor(page=None, output_excel=str(deep_path))
    
    assert deep_path.parent.exists(), "父目录未被成功创建"
    assert deep_path.exists(), "Excel 文件未被自动初始化"
    
    # 验证是否写入了表头
    df = pd.read_excel(deep_path)
    assert "职位名称" in df.columns, "Excel 初始化缺失预期表头"
    print("✅ 目录穿透与文件初始化测试通过")

async def test_atomic_write_and_permission_error(tmp_path: Path):
    print("\n--- Testing: 原子化写入与占用重试/逃生机制 ---")
    target_excel = tmp_path / "locked_output.xlsx"
    
    # 提前造一个文件
    extractor = LiepinResumeExtractor(page=None, output_excel=str(target_excel))
    
    # 模拟锁定目标文件（在 Windows 下独占打开）
    try:
        locked_f = open(target_excel, 'a')
        
        # 伪造抓取到的数据
        test_condition = {"职位名称": "测试原子写入"}
        test_data = [{"候选人名称": "张三", "职位名称": "测试原子写入"}]
        
        # 将假数据塞入缓冲池开始写盘
        extractor.results = [] # clear any existing
        
        # 因为真实调用在 process_list 中，我们直接调用一个专门暴露的写盘或者重构后的写盘逻辑。
        # 这里为了测试尚未写的逻辑，我们假设我们在测试其 _atomic_save_batch(data_buffer) [这是接下来的重构点]
        
        # 预期的行为：_atomic_save_batch 应该在重试 3 次后抛出警告，并把数据降级到 CSV
        result = await extractor._atomic_save_batch(test_data)
        
        assert not result, "应该返回 False 标志批量写盘最终失败"
        
        # 检查有没有生成 csv 备份
        backup_dir = Path(extractor.__module_path__).parent if hasattr(extractor, '__module_path__') else Path(__file__).parent
        backup_dir = backup_dir / "backup"
        
        csv_files = list(backup_dir.glob("backup_failed_records_*.csv"))
        # 请注意：我们在单测中需要确认是不是新生成的
        assert len(csv_files) >= 1, "未在 PermissionError 后生成 csv"
        
        print("✅ PermissionError 拦截与降级备份测试通过")
    except Exception as e:
        print(f"❌ 锁定测试失败: {e}")
    finally:
        try:
            locked_f.close()
        except:
            pass

    # 接着测试释放后的原子化写入（应该把 temp 完美替换掉）
    print("\n--- Testing: 正常释放后的原子写入 ---")
    test_data = [{"候选人名称": "李四", "职位名称": "成功写入"}]
    result = await extractor._atomic_save_batch(test_data)
    assert result, "释放锁定后，原子写入理应成功"
    
    # 验证原文件已被更新
    df = pd.read_excel(target_excel)
    assert len(df) >= 1
    assert "李四" in df["候选人名称"].values
    
    # 验证 temp 文件是否被清空/重命名走了
    tmp_files = list(tmp_path.glob("*.tmp.xlsx"))
    assert len(tmp_files) == 0, "原子写入后残留了 tmp 切片文件！"
    
    print("✅ 正常原子写入与无残痕替换测试通过")

if __name__ == "__main__":
    tmp_path = Path("D:/ljg/Antigravity/Files/Output/TDD_Test")
    asyncio.run(setup_test_environment(tmp_path))
    
    # 注意，我们暂时只是搭好架子，Extractor 里还没有 _atomic_save_batch。我们下一步去实现。
    try:
        asyncio.run(test_auto_create_dir_and_init(tmp_path))
        asyncio.run(test_atomic_write_and_permission_error(tmp_path))
    except AttributeError as e:
         print(f"预期中的 Attribute 错误（新方法尚未实现）: {e}\n接下来将去修改 Extractor 填充逻辑！")
    except Exception as e:
         print(f"未处理的错误: {e}")
