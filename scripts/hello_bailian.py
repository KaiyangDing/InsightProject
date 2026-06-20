"""最小可运行示例：验证百炼连通性。现在统一从 insight.config 读配置。"""

from openai import OpenAI

from insight.config import get_settings

settings = get_settings()

client = OpenAI(
    api_key=settings.dashscope_api_key.get_secret_value(),
    base_url=settings.dashscope_base_url,
)

resp = client.chat.completions.create(
    model=settings.chat_model,
    messages=[
        {"role": "system", "content": "你是一个简洁的助手。"},
        {"role": "user", "content": "用一句话证明你能正常工作。"},
    ],
)

print("✅ 调用成功！模型回复：")
print(resp.choices[0].message.content)
print(f"\n(model={settings.chat_model}, tokens={resp.usage.total_tokens})")
