"""
模块名称: data_cleaner
功能描述: 从 Project_list.xlsx 中读取招聘原始数据，按 9 大维度清洗后输出至 Data_Cleaned.xlsx
"""
import shutil
import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import pandas as pd

from src.core.logger import LoggerFactory
from config.config_loader import Config
from paths import DATA_DIR

from .schema import (
    SRC_SHEET_NAME, KEY_FIELD, OUTPUT_COLUMNS, SRC_JOB_TITLE,
)
from . import processor

logger = LoggerFactory.get_logger("data_cleaner")

# ============================================================
# 路径定义（基于 paths.py 常量，零硬编码）
# ============================================================
INPUT_DIR = DATA_DIR / "Input" / "DataCleaner"
OUTPUT_DIR = DATA_DIR / "Output" / "DataCleaner"
HIS_DIR = DATA_DIR / "Output" / "HIS" / "Data_Cleaner"

SOURCE_FILE = INPUT_DIR / "Project_list.xlsx"
OUTPUT_FILE = OUTPUT_DIR / "Data_Cleaned.xlsx"


def _ensure_dirs():
    """自动创建所有依赖目录"""
    for d in [INPUT_DIR, OUTPUT_DIR, HIS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def _check_file_accessible(filepath: Path) -> bool:
    """
    检测文件是否可读（未被 Excel 等进程占用）。
    返回 True 表示可读，False 表示被占用。
    """
    if not filepath.exists():
        return True  # 文件不存在不算占用
    try:
        with open(filepath, "rb"):
            pass
        return True
    except PermissionError:
        return False


def _archive_existing_output():
    """
    若 Output 目录下已有 Data_Cleaned.xlsx，
    附加时间戳后迁移到 HIS/Data_Cleaner/ 目录。
    """
    if not OUTPUT_FILE.exists():
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    archived_name = f"Data_Cleaned_{timestamp}.xlsx"
    archived_path = HIS_DIR / archived_name

    try:
        shutil.move(str(OUTPUT_FILE), str(archived_path))
        logger.info(f"📦 已将旧文件归档至: {archived_path}")
    except PermissionError:
        logger.error(f"❌ 归档失败：输出文件 {OUTPUT_FILE} 被占用，请关闭后重试。")
        raise


def run(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    标准插件入口 — 被 main.py Orchestrator 动态调用

    :param params: 可选参数字典
    :return: {"status": "success" | "error", "data": Any, "message": str}
    """
    params = params or {}
    task_id = params.get("task_id", "data_cleaner")
    logger.info(f"[{task_id}] 🚀 Data_Cleaner 模块启动")

    try:
        # === 1. 环境预检 ===
        _ensure_dirs()

        # 1a. Source 文件存在性检查
        if not SOURCE_FILE.exists():
            msg = f"❌ Source 文件不存在: {SOURCE_FILE}"
            logger.error(msg)
            return {"status": "error", "data": None, "message": msg}

        # 1b. Source 文件占用检查
        if not _check_file_accessible(SOURCE_FILE):
            msg = f"❌ Source 文件被占用（请关闭 Excel）: {SOURCE_FILE}"
            logger.error(msg)
            return {"status": "error", "data": None, "message": msg}

        # === 2. 读取 Source 数据 ===
        logger.info(f"📂 读取 Source 文件: {SOURCE_FILE}")
        df = pd.read_excel(str(SOURCE_FILE), sheet_name=SRC_SHEET_NAME)
        total_rows = len(df)
        logger.info(f"📊 读取完毕，共 {total_rows} 行原始数据")

        # 2a. 跳过关键字段为空的行
        valid_mask = df[KEY_FIELD].apply(
            lambda x: bool(str(x).strip()) if pd.notna(x) and str(x).lower() != "nan" else False
        )
        skipped = (~valid_mask).sum()
        if skipped > 0:
            logger.warning(f"⚠️ 跳过 {skipped} 行（{KEY_FIELD} 为空）")
        df_valid = df[valid_mask].reset_index(drop=True)

        # === 3. 核心清洗 ===
        logger.info("🧹 开始执行数据清洗...")
        df_cleaned = processor.process(df_valid)

        # 确保输出列完整且有序
        for col in OUTPUT_COLUMNS:
            if col not in df_cleaned.columns:
                df_cleaned[col] = None
        df_output = df_cleaned[OUTPUT_COLUMNS]

        # === 4. 归档旧文件 ===
        _archive_existing_output()

        # === 5. 写入 Output ===
        df_output.to_excel(str(OUTPUT_FILE), index=False, engine="openpyxl")
        logger.info(f"✅ 清洗完成！输出文件: {OUTPUT_FILE} ({len(df_output)} 行)")

        return {
            "status": "success",
            "data": {
                "output_path": str(OUTPUT_FILE),
                "total_input": total_rows,
                "total_output": len(df_output),
                "skipped": skipped,
            },
            "message": f"清洗完成，{len(df_output)} 条记录已导出。",
        }

    except Exception as e:
        logger.exception(f"[{task_id}] 执行崩溃: {e}")
        return {"status": "error", "data": None, "message": str(e)}
