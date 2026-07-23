"""
云观星传 - 科学事实数据生成工具
用 LLM（联网搜索）为指定议题生成结构化科学事实，存入 data/science/

用法：
    python scripts/gen_science_data.py 神舟二十三号
    python scripts/gen_science_data.py 嫦娥七号 天问二号 商业航天
"""
import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm_client import LLMClient

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data" / "science"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = """你是一个航天科技领域的数据标注专家。请为给定议题生成结构化的科学事实数据。
要求：
1. 只输出可验证的客观事实
2. 每个事实尽量标注来源
3. 提取关键实体和关系
4. 输出严格 JSON 格式
5. 必须输出标准 JSON，字符串值内如有双引号请用反斜杠转义为 \""""

USER_PROMPT_TEMPLATE = """请为以下科技议题生成结构化科学事实数据：

## 议题：{topic}

## 输出格式（严格 JSON）：
{{
  "topic": "{topic}",
  "key_facts": [
    "事实1（来源：xxx）",
    "事实2（来源：xxx）",
    ...至少8条
  ],
  "entities": [
    {{"name": "实体名", "type": "mission/body/technology/organization/person/event", "attributes": {{}}, "description": "简短描述"}}
  ],
  "relations": [
    {{"subject": "主体", "predicate": "关系动词", "object": "客体", "confidence": 0.9, "source": "来源"}}
  ],
  "timeline": [
    {{"date": "YYYY-MM-DD", "event": "事件描述"}}
  ],
  "data_sources": ["来源1", "来源2"]
}}

请确保：
- key_facts 至少 8 条，涵盖时间、地点、技术参数、意义等
- entities 至少 5 个关键实体
- relations 至少 4 条关系
- timeline 按时间排序"""


def generate_facts(topic: str) -> dict:
    """调用 LLM 生成科学事实"""
    client = LLMClient()
    logger.info(f"  正在生成「{topic}」的科学事实（联网搜索中）...")

    result = client.chat_json(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=USER_PROMPT_TEMPLATE.format(topic=topic),
        temperature=0.2,
        enable_search=True,
    )
    return result


def save_facts(topic: str, data: dict):
    """保存到 data/science/ 目录"""
    # 生成文件名
    safe_name = topic.replace(" ", "_").replace("/", "_")[:20]
    file_path = DATA_DIR / f"{safe_name}_facts.json"

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"  ✓ 已保存: {file_path}")
    logger.info(f"    - {len(data.get('key_facts', []))} 条事实")
    logger.info(f"    - {len(data.get('entities', []))} 个实体")
    logger.info(f"    - {len(data.get('relations', []))} 条关系")
    return file_path


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/gen_science_data.py <议题1> [议题2] [议题3] ...")
        print("示例: python scripts/gen_science_data.py 神舟二十三号 嫦娥七号 天问二号")
        sys.exit(1)

    topics = sys.argv[1:]
    print("=" * 60)
    print("  云观星传 - 科学事实数据生成工具")
    print("=" * 60)
    print(f"\n  待生成议题: {', '.join(topics)}\n")

    success = 0
    for i, topic in enumerate(topics, 1):
        print(f"\n[{i}/{len(topics)}] 处理: {topic}")
        try:
            data = generate_facts(topic)
            save_facts(topic, data)
            success += 1
        except Exception as e:
            logger.error(f"  ✗ 生成失败: {e}")

    print(f"\n{'=' * 60}")
    print(f"  完成！成功 {success}/{len(topics)} 个议题")
    if success > 0:
        print(f"\n  下一步：重建向量索引")
        print(f"    python scripts/build_index.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
