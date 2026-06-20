"""LLM 客户端工厂：统一构造指向百炼的 OpenAI 客户端。

以后模型路由、多 provider 适配都长在这里——现在先把"创建客户端"收口到一处。
"""

from openai import OpenAI

from insight.config import Settings


def get_chat_client(settings: Settings) -> OpenAI:
    return OpenAI(
        api_key=settings.dashscope_api_key.get_secret_value(),
        base_url=settings.dashscope_base_url,
    )
