import time
import json
import logging

# 配置日志（单独记录 AI 消耗）
ai_logger = logging.getLogger("AI_Engine")

def call_llm_mock(prompt):
    """
    LLM 调用模拟接口。
    实际使用时需替换为真正的 API Call。
    """
    start_time = time.time()
    # 模拟耗时
    time.sleep(0.5) 
    
    # 模拟返回
    response = {
        "result": "研判结果",
        "confidence": 0.8,
        "token_usage": 150
    }
    
    duration = time.time() - start_time
    ai_logger.info(f"AI Reasoning: duration={duration:.2f}s, tokens={response['token_usage']}")
    
    return response

def ai_judge_category(responsibilities, requirements, hard_conditions):
    """职位类别二次研判"""
    context = f"职责: {responsibilities}\n要求: {requirements}\n硬性条件: {hard_conditions}"
    # 模拟 prompt
    # res = call_llm_mock(f"请对以下职位进行行业分类预测: {context}")
    # 这里保持与之前 placeholder 一致，但增加日志
    return "其他" # 默认占位

def ai_judge_experience(level, raw_exp, responsibilities):
    """经验要求深度研判"""
    # 模拟对标逻辑
    if "架构师" in str(responsibilities) or "专家" in str(level):
        return "5-10年"
    return None
