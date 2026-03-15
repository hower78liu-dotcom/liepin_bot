"""
AI 引擎 — LLM 调用封装
- 统一接口，强制 JSON 输出
- LRU 缓存 + 相似度复用（>95% 直接复用）
- Mock 模式（无 API Key 时自动降级）
"""
import json
import hashlib
import difflib
from typing import Dict, Any, Optional, List
from functools import lru_cache

from src.core.logger import LoggerFactory
from config.config_loader import Config

logger = LoggerFactory.get_logger("data_cleaner")

# 历史调用缓存 (text_hash -> result)
_SIMILARITY_CACHE: Dict[str, Dict] = {}


def _text_hash(text: str) -> str:
    """计算文本 MD5 哈希"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _find_similar_cached(text: str, threshold: float = 0.95) -> Optional[Dict]:
    """
    在缓存中查找相似度 > threshold 的历史结果
    """
    for cached_text_hash, entry in _SIMILARITY_CACHE.items():
        cached_text = entry.get("_original_text", "")
        ratio = difflib.SequenceMatcher(None, text, cached_text).ratio()
        if ratio >= threshold:
            logger.info(f"🎯 AI 缓存命中 (相似度 {ratio:.2%})")
            return entry.get("result")
    return None


# ============================================================
# 职位分类 — 内置规则引擎
# ============================================================
_CATEGORY_RULES: List[tuple] = [
    # (关键词列表, 分类)
    (["算法", "AI", "机器学习", "深度学习", "NLP", "CV", "视觉", "具身", "VLA", "大模型", "LLM"], "人工智能"),
    (["前端", "后端", "全栈", "Java", "Python", "Go", "C++", "C#", "Node", "Web", "微服务", "架构师"], "计算机/互联网"),
    (["嵌入式", "单片机", "RTOS", "Linux驱动", "BSP", "固件"], "嵌入式/硬件"),
    (["硬件", "PCB", "电路", "射频", "信号", "EMC", "电源", "BMS", "PCS", "储能", "逆变"], "电子/电器/半导体"),
    (["FPGA", "DSP", "ASIC", "芯片", "IC", "半导体", "光刻"], "电子/电器/半导体"),
    (["结构", "机械", "CAD", "CAE", "SolidWorks", "模具", "工装", "夹具"], "机械/制造"),
    (["质量", "QA", "QC", "QE", "SQE", "IATF", "体系", "审核", "检验"], "质量管理"),
    (["项目经理", "PMO", "项目管理", "PMP"], "项目管理"),
    (["销售", "BD", "商务", "客户"], "销售/商务"),
    (["采购", "供应链", "供应商"], "采购/供应链"),
    (["化工", "工艺", "化学", "制药", "天然气", "液化", "氢", "氨", "醇"], "化工/制药"),
    (["电气", "PLC", "自动化", "控制", "DCS", "SIS"], "自动化/电气"),
    (["测试", "QA", "Test", "自动化测试", "性能测试"], "测试"),
    (["运维", "DevOps", "SRE", "部署", "监控"], "运维"),
    (["产品经理", "产品设计", "需求分析"], "产品"),
    (["人力", "HR", "招聘", "HRBP", "薪酬", "绩效"], "人力资源"),
    (["财务", "会计", "审计", "税务", "出纳"], "财务/审计"),
    (["法务", "合规", "法律"], "法务"),
]


def classify_job_category(job_title: str, responsibilities: str = "", requirements: str = "") -> Optional[str]:
    """
    职位分类 — 规则引擎优先，LLM 兜底

    :return: 行业分类字符串 或 None
    """
    # 合并所有文本用于匹配
    combined = f"{job_title} {responsibilities} {requirements}"

    # 1. 规则引擎匹配
    for keywords, category in _CATEGORY_RULES:
        for kw in keywords:
            if kw.lower() in combined.lower():
                return category

    # 2. 尝试 LLM（如有 API Key）
    api_key = Config.get("LLM_API_KEY")
    if api_key:
        result = _call_llm_classify(combined, api_key)
        if result:
            return result

    # 3. 无法判定
    return None


@lru_cache(maxsize=512)
def _call_llm_classify(text: str, api_key: str) -> Optional[str]:
    """
    LLM 分类调用（带 LRU 缓存）
    预留接口 — 配置 LLM_API_KEY 后启用
    """
    # TODO: 替换为真实 LLM API 调用
    logger.info("🤖 LLM 分类调用 (Mock 模式)")
    return None


def ai_judge_experience(level: str, raw_exp: str, responsibilities: str) -> Optional[str]:
    """
    AI 研判经验要求 — 结合职级与职责复杂度

    :param level: 职级 (如 "资深", "高级")
    :param raw_exp: 原始经验描述
    :param responsibilities: 岗位职责文本
    :return: 标准区间 或 None
    """
    # 先检查缓存
    cache_key = f"{level}|{raw_exp}|{responsibilities}"
    cached = _find_similar_cached(cache_key)
    if cached:
        return cached.get("experience")

    # 规则研判
    result = None
    combined = f"{level} {raw_exp} {responsibilities}"

    if any(kw in combined for kw in ["架构", "专家", "总监", "首席", "CTO"]):
        result = "10年以上"
    elif any(kw in combined for kw in ["资深", "高级", "独立主导", "负责人", "团队管理"]):
        result = "5-10年"
    elif any(kw in combined for kw in ["中级", "骨干"]):
        result = "3-5年"
    elif any(kw in combined for kw in ["初级", "助理", "实习"]):
        result = "1-3年"

    # 存入缓存
    if result:
        text_hash = _text_hash(cache_key)
        _SIMILARITY_CACHE[text_hash] = {
            "_original_text": cache_key,
            "result": {"experience": result},
        }

    return result
