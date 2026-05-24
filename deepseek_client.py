"""
DeepSeek 统一客户端
"""
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


class DeepSeek:

    def __init__(self):
        self._c = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

    def chat(self, system: str, user: str, history: list = None,
             temperature: float = 0.3, max_tokens: int = 300) -> str | None:
        messages = [{"role": "system", "content": system}]
        if history:
            for h in history[-10:]:
                messages.append({"role": h["role"], "content": h["content"][:200]})
        messages.append({"role": "user", "content": user})
        try:
            r = self._c.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return r.choices[0].message.content.strip()
        except Exception:
            return None


deepseek = DeepSeek() if DEEPSEEK_API_KEY else None
