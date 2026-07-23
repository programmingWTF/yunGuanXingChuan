"""快速验证 API Key + base_url 组合是否可用"""
from openai import OpenAI

API_KEY = "sk-sp-H.EMRPD.qdIs.MEYCIQCILl9qVOzC0qrhbR9dx4o-BsKyoV_D6729MOK1vc0OtQIhANJds6u7OxzW1CDhqX0xx2aj6uYGyLKIyUwgb29mm83c"

# 尝试不同的 base_url
endpoints = [
    ("Token Plan OpenAI兼容", "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"),
    ("标准百炼 OpenAI兼容", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
]

for name, base_url in endpoints:
    print(f"\n--- 测试: {name} ---")
    print(f"    URL: {base_url}")
    try:
        client = OpenAI(api_key=API_KEY, base_url=base_url)
        resp = client.chat.completions.create(
            model="qwen3.8-max-preview",
            messages=[{"role": "user", "content": "reply with exactly: OK"}],
        )
        print(f"    ✓ 成功! 回复: {resp.choices[0].message.content}")
    except Exception as e:
        print(f"    ✗ 失败: {e}")
