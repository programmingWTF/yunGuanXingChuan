"""快速验证 API Key + base_url 组合是否可用"""
import os
import sys

# Windows 控制台默认 GBK，无法输出 ✓/✗，统一转 UTF-8 避免崩溃
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from openai import OpenAI

# 从 .env 读取 API Key（密钥不入库，配置参考 .env.example）
load_dotenv()
API_KEY = os.getenv("QWEN_API_KEY", "")

if not API_KEY:
    raise SystemExit("未设置 QWEN_API_KEY，请先在 .env 中配置（参考 .env.example）")

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
