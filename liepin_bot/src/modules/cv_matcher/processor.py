"""
模块名称: cv_matcher/processor.py
功能描述: 单条记录的验证逻辑引擎。负责计算 MD5、读写缓存、构建 Prompt 交由 LLM 并解析结果。
"""

from typing import Dict, Any
from src.core.logger import LoggerFactory
from src.core.ai_client import AIService
from src.modules.cv_matcher.utils import calculate_md5, clean_json_response, JSONCache

logger = LoggerFactory.get_logger("cv_matcher_processor")

# 初始化 AI 服务单例
ai_service = AIService()

def call_llm(jd_text: str, resume_text: str) -> str:
    """
    通过 AIService 调用标准 OpenAI 兼容的 Chat Completions 接口
    """
    system_prompt = (
        "你是资深技术猎头。对比【职位描述】与【候选人经历】。\n"
        "**评分维度**：核心硬技能 (40%)、行业背景 (20%)、职责契合度 (30%)、职级契合度 (10%)。\n"
        "**输出要求 (必须 JSON，禁止返回任何多余的 Markdown 标记)**：\n"
        "{\n"
        '  "matching_percent": "XX%",\n'
        '  "matching_structure": {"skills": "...", "industry": "...", "duty": "...", "rank": "..."},\n'
        '  "summary": "最终评价"\n'
        "}"
    )

    user_prompt = f"**输入数据**：\n* JD: {jd_text}\n* Resume: {resume_text}"

    # 使用封装好的 AIService，内含重试与额度管理逻辑
    response = ai_service.call_llm(prompt=user_prompt, system_prompt=system_prompt)
    
    if response:
        return response
    else:
        # 如果保存返回 None (调用失败/额度耗尽)，返回容错 JSON
        return '{"matching_percent": "请求失败", "matching_structure": {}, "summary": "接口调用出错或额度耗尽"}'

def evaluate_candidate(jd: str, resume: str, cache_mgr: JSONCache) -> Dict[str, Any]:
    """
    接收 JD 和 Resume，比对 MD5 缓存。如果不存在缓存则发送到 LLM 并存入。
    
    :param jd: 提取至"简历描述对比"的岗位描述要求
    :param resume: 提取至"工作经历(全量)"的简历经历
    :param cache_mgr: 全局挂载的 JSONCache 对象
    :return: 字段字典 dict
    """
    # 判空
    if not jd or not resume or len(str(jd).strip()) < 5 or len(str(resume).strip()) < 5:
        return {
            "matching_percent": "条件不足",
            "matching_structure": {},
            "summary": "简历或职位描述字数太少，无法执行 AI 匹配"
        }

    # 1. 计算哈希指纹
    md5_hash = calculate_md5(jd, resume)

    # 2. 探针缓存查表
    cached_val = cache_mgr.get(md5_hash)
    if cached_val:
        # logger.debug(f"缓存命中 MD5: {md5_hash[:8]}...")
        return cached_val

    # 3. 缓存穿透，请求外部 LLM (此处会阻塞当前线程)
    raw_llm_response = call_llm(jd, resume)

    # 4. JSON 文本清洗提取
    parsed_json = clean_json_response(raw_llm_response)

    # 5. 写入本地穿透缓存
    cache_mgr.set(md5_hash, parsed_json)

    return parsed_json
