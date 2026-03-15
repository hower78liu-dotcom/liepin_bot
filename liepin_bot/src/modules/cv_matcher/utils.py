"""
模块名称: cv_matcher/utils.py
功能描述: 封装用于简历匹配的 MD5 哈希生成器、安全存取本地缓存文件的方法及针对 LLM 返回的 JSON 清洗处理工具。
"""

import os
import json
import hashlib
import re
from pathlib import Path
from src.core.logger import LoggerFactory
from typing import Dict, Any

logger = LoggerFactory.get_logger("cv_matcher_utils")

def calculate_md5(text1: str, text2: str) -> str:
    """
    接收 JD 和 Resume，并构建唯一 MD5 判断值
    """
    raw = f"{str(text1).strip()}|||{str(text2).strip()}"
    return hashlib.md5(raw.encode('utf-8')).hexdigest()

def clean_json_response(raw_text: str) -> dict:
    """
    过滤 LLM 掺杂的 markdown 或外部废话，安全地转换为词典
    """
    text = raw_text.strip()
    
    # 去除首尾的 markdown 代码块包裹 (如 ```json ... ```)
    text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```$", "", text)
    text = text.strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"无法解析 LLM 响应内容为 JSON: {str(e)}\n\n由于格式错误引发崩溃，响应原文:\n{raw_text}")
        return {
            "matching_percent": "解析错误",
            "matching_structure": {},
            "summary": "AI 返回格式异常"
        }

class JSONCache:
    """锁隔离的安全本地字典缓存"""
    def __init__(self, cache_file: Path):
        self.cache_file = cache_file
        self.data: Dict[str, Any] = self._load()
        
    def _load(self) -> dict:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"不能正确挂载 cv_match_cache.json, 原因为 [{e}]。将从空集开始覆盖建立...")
        return {}
        
    def get(self, key: str) -> Any:
        return self.data.get(key)
        
    def set(self, key: str, value: Any):
        self.data[key] = value
        self.save()
        
    def save(self):
        # 原生写库（如果是密集写入最好搭配 Lock()，由于 ThreadPool 并发一般不大，此处为精简可以直接 dump）
        # 如果追求更极端的并发写入安全，这里可以引入 threading.Lock()
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
