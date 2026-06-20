"""最小可运行示例：验证百炼 (DashScope) key 与连通性。
通过 OpenAI 兼容端点调用一次 chat completion。
"""
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

# 1) 加载 .env 里的非敏感配置（base_url / 模型名）。
#    注意：系统环境变量优先级高于 .env，所以你已设到系统环境变量里的
#    DASHSCOPE_API_KEY 会被直接读到，不会被 .env 覆盖。
load_dotenv()

# 2) 从环境变量读取 key（你已放进 Windows 用户环境变量）。
api_key = os.getenv("DASHSCOPE_API_KEY")
if not api_key:
    sys.exit("❌ 没读到 DASHSCOPE_API_KEY，请确认已设置到环境变量并重开终端。")

# 3) 读取百炼兼容端点与模型名（给了默认值，没 .env 也能跑）。
base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
model = os.getenv("CHAT_MODEL", "qwen-plus")

# 4) 用 OpenAI SDK，但把地址指向百炼。这就是"统一适配层"最朴素的样子。
client = OpenAI(api_key=api_key, base_url=base_url)

# 5) 发一次最小请求。
resp = client.chat.completions.create(
    model=model,
    messages=[
        {"role": "system", "content": "你是一个简洁的助手。"},
        {"role": "user", "content": "用一句话证明你能正常工作。"},
    ],
)

# 6) 打印结果与 token 用量（用量信息以后做成本统计会用到）。
print("✅ 调用成功！模型回复：")
print(resp.choices[0].message.content)
print(f"\n(model={model}, tokens={resp.usage.total_tokens})")