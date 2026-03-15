import json
import time
import tiktoken
from openai import OpenAI
from src.core.logger import LoggerFactory
from config.config_loader import Config
from paths import DATA_DIR

logger = LoggerFactory.get_logger("AI_Client")

class AIService:
    def __init__(self):
        # 1. 从统一配置中心读取，严禁硬编码
        self.api_key = Config.get("API_KEY") or Config.get("LLM_API_KEY")
        self.base_url = Config.get("BASE_URL") or Config.get("LLM_BASE_URL", "https://api.openai.com/v1")
        self.model = Config.get("TARGET_MODEL") or Config.get("LLM_MODEL", "deepseek-ai/DeepSeek-V3.2")
        self.quota_file = DATA_DIR / "config" / "ai_usage.json"
        
        # 确保配置目录存在
        self.quota_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化客户端
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _get_used_quota(self):
        """持久化读取已用额度"""
        if not self.quota_file.exists():
            return 0
        try:
            with open(self.quota_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("used_tokens", 0)
        except Exception as e:
            logger.error(f"读取额度文件失败: {e}")
            return 0

    def _update_quota(self, tokens):
        """持久化更新已用额度"""
        current = self._get_used_quota()
        try:
            with open(self.quota_file, 'w', encoding='utf-8') as f:
                json.dump({"used_tokens": current + tokens}, f, indent=4)
        except Exception as e:
            logger.error(f"更新额度文件失败: {e}")

    def count_tokens(self, text):
        """精确计算 Token"""
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            # 兼容性兜底：中文字符粗略估计
            return len(str(text)) // 2

    def call_llm(self, prompt, system_prompt=None, max_tokens=2000, retry_count=3):
        """核心调用：带限额检查、异常处理与针对 503 的重试机制"""
        if not self.api_key:
            logger.error("❌ 未配置 API_KEY，无法调用 AI 服务")
            return None

        # 2. 预估成本检查
        input_tokens = self.count_tokens(prompt)
        if system_prompt:
            input_tokens += self.count_tokens(system_prompt)
            
        used = self._get_used_quota()
        limit = int(Config.get("FREE_QUOTA_TOTAL", 20000000))
        
        if (used + input_tokens + max_tokens) > limit:
            logger.error(f"❌ 额度超限！当前上限: {limit} | 已用: {used} | 剩余: {limit - used}")
            return None

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        last_error = None
        for attempt in range(retry_count):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.3, # 降低随机性，提高匹配准确率
                    max_tokens=max_tokens,
                    timeout=60
                )
                
                # 3. 更新实际消耗
                actual_usage = response.usage.total_tokens
                self._update_quota(actual_usage)
                
                logger.info(f"✅ LLM调用成功 | 消耗: {actual_usage} | 余额: {limit - (used + actual_usage)}")
                return response.choices[0].message.content

            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                # 针对 503 服务器繁忙、速率限制或超时进行重试
                if any(k in error_str for k in ["503", "rate_limit", "rate limit", "timeout", "connection"]):
                    logger.warning(f"⚠️ AI 调用遭遇暂时性错误 (第{attempt+1}次重试): {e}. 2秒后重试...")
                    time.sleep(2)
                    continue
                else:
                    # 授权错误等致命错误直接中断
                    logger.error(f"❌ AI 调用致命错误: {e}")
                    break

        if last_error:
            logger.error(f"❌ AI 调用在 {retry_count} 次重试后失败: {last_error}")
        return None
