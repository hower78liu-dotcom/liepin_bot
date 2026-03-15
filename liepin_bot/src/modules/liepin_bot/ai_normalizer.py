import json
import re
from loguru import logger

def call_llm_for_judgment(prompt):
    """
    调用 LLM 的占位函数。
    在实际部署时，应替换为真实的 LLM API 调用（如 OpenAI, Anthropic, 或内部接口）。
    返回格式应为 JSON 字符串。
    """
    # 这里我们通过 mock 返回来模拟 LLM 的决策
    # 实际开发中需集成具体 API
    mock_response = {
        "category": "互联网IT", 
        "confidence": 0.85,
        "experience_normalized": "5-10年",
        "reasoning": "职级为资深且职责包含独立主导架构"
    }
    return json.dumps(mock_response)

def ai_judge_category(job_desc, job_req, hard_req):
    """
    职位类别（Category）的递归判定
    “合并‘岗位职责’、‘岗位要求’及‘硬性条件’作为上下文，调用 LLM 进行行业分类预测。”
    """
    context = f"职责: {job_desc}\n要求: {job_req}\n硬性条件: {hard_req}"
    prompt = f"""
你是一名资深猎头专家。请根据以下职位描述、要求和硬性条件，判断该职位所属的最佳行业类别。
上下文内容如下：
{context}

请输出以下 JSON 格式：
{{
  "category": "类别名称",
  "confidence": 0.0到1.0之间的得分,
  "explanation": "简要判断理由"
}}

若无法判断，请在 category 中填入 "无法判断"。
"""
    try:
        response_raw = call_llm_for_judgment(prompt)
        res = json.loads(response_raw)
        
        confidence = res.get("confidence", 0)
        category = res.get("category", "")
        
        if confidence < 0.6 or category == "无法判断":
            return None
        return category
    except Exception as e:
        logger.error(f"AI 职位类别研判失败: {e}")
        return None

def ai_judge_experience(level, experience_desc, complexity_desc):
    """
    经验要求的深度研判
    “针对‘自定义’标签，程序需调用 AI 模型，结合岗位职级（Level）与职责复杂度进行行业基准对标。”
    """
    if not experience_desc and not complexity_desc:
        return None
        
    prompt = f"""
你是一名资深 HR 专家。请根据职级和职责复杂度，推断该岗位所需的典型工作经验年限。
职级：{level}
描述：{experience_desc}
职责复杂度：{complexity_desc}

请输出猎聘标准经验区间中的一个：
"经验不限", "应届生", "1年以下", "1-3年", "3-5年", "5-10年", "10年以上"

输出 JSON 格式：
{{
  "experience_normalized": "标准区间",
  "reasoning": "判断依据"
}}
"""
    try:
        response_raw = call_llm_for_judgment(prompt)
        res = json.loads(response_raw)
        return res.get("experience_normalized")
    except Exception as e:
        logger.error(f"AI 经验年限研判失败: {e}")
        return None
