"""
DeepSeek 统一客户端 — 所有 handler 共用，配置精简
"""
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


class DeepSeekClient:
    """统一 DeepSeek 调用客户端"""

    def __init__(self):
        self._client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 300,
    ) -> str | None:
        """简单对话 — 单轮、低延迟"""
        try:
            resp = self._client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return None

    def chat_with_history(
        self,
        system_prompt: str,
        user_message: str,
        history: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 300,
    ) -> str | None:
        """带历史的多轮对话"""
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for h in history[-6:]:  # 限制6条历史
                role = h.get("role", "user")
                content = h.get("content", "")[:200]  # 每条截断200字
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_message})
        try:
            resp = self._client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return None


# 全局单例
deepseek = DeepSeekClient() if DEEPSEEK_API_KEY else None
