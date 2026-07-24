"""
云观星传 - 认知议会 Demo 入口
一键运行：python scripts/run_parliament_demo.py --topic "嫦娥六号"
"""
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# 确保项目根目录在 path 中
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("parliament_demo")


def progress_callback(step: str, status: str, message: str, *args):
    """进度回调：打印到控制台"""
    icon = {"running": "⏳", "completed": "✅", "error": "❌"}.get(status, "•")
    print(f"  {icon} [{step}] {message}")


def main():
    parser = argparse.ArgumentParser(description="认知议会 Demo")
    parser.add_argument("--topic", type=str, default="嫦娥六号",
                        help="分析议题（默认：嫦娥六号）")
    parser.add_argument("--max-rounds", type=int, default=None,
                        help="最大辩论轮次（默认从配置读取）")
    parser.add_argument("--output", type=str, default=None,
                        help="输出文件路径（默认 data/results/parliament_<topic>.json）")
    args = parser.parse_args()

    topic = args.topic
    print(f"\n{'='*60}")
    print(f"  认知议会 (Cognitive Parliament) Demo")
    print(f"  议题: {topic}")
    print(f"{'='*60}\n")

    # 初始化议会
    from src.pipeline import CognitiveParliament

    parliament = CognitiveParliament(
        max_rounds=args.max_rounds,
        progress_callback=progress_callback,
    )

    # 加载本地科学数据（如果有）
    science_facts = None
    context_analysis = None
    try:
        from src.knowledge.data_loader import get_data_loader
        data_loader = get_data_loader()
        science_facts = data_loader.load_science_facts(topic)
        if science_facts:
            print(f"  📚 已加载本地科学数据: {topic}")
    except Exception as e:
        logger.debug(f"加载本地数据失败（不影响运行）: {e}")

    # 召集议会
    start_time = datetime.now()
    transcript = parliament.convene(
        topic=topic,
        science_facts=science_facts,
        context_analysis=context_analysis,
    )
    elapsed = (datetime.now() - start_time).total_seconds()

    # 输出结果
    print(f"\n{'='*60}")
    print(f"  议会闭幕")
    print(f"{'='*60}")
    print(f"  总轮次: {transcript.total_rounds}")
    print(f"  动议数: {len(transcript.motions)}")
    print(f"  表决数: {len(transcript.votes)}")
    print(f"  少数派意见: {len(transcript.minority_opinions)}")
    print(f"  耗时: {elapsed:.1f}s")

    # 打印表决结果
    print(f"\n  📊 表决结果:")
    for vote in transcript.votes:
        icon = {"passed": "✅", "rejected": "❌", "amended": "⚠️", "deadlocked": "🔶"}.get(
            vote.result, "•")
        print(f"    {icon} {vote.motion_id}: {vote.result} "
              f"(yes={vote.weighted_yes:.2f}, no={vote.weighted_no:.2f})")

    # 打印少数派意见
    if transcript.minority_opinions:
        print(f"\n  🔶 少数派意见:")
        for mo in transcript.minority_opinions:
            print(f"    - [{mo.agent}] {mo.motion_id}: {mo.objection[:80]}")

    # 保存结果
    output_path = args.output
    if not output_path:
        results_dir = PROJECT_ROOT / "data" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        safe_name = topic.replace(" ", "_").replace("/", "_")[:20]
        output_path = str(results_dir / f"parliament_{safe_name}.json")

    transcript_dict = transcript.model_dump()
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(transcript_dict, f, ensure_ascii=False, indent=2)
    print(f"\n  💾 完整辩论记录已保存: {output_path}")

    # 验证验收标准
    print(f"\n  📋 验收自查:")
    checks = [
        (transcript.total_rounds >= 3, f"辩论 ≥3 轮 (实际 {transcript.total_rounds})"),
        (len(transcript.votes) >= 1, f"至少1次投票 (实际 {len(transcript.votes)})"),
        (all(v.votes for v in transcript.votes), "每条动议有 VoteResult"),
        (len(transcript.minority_opinions) >= 1,
         f"至少1条少数派意见 (实际 {len(transcript.minority_opinions)})"),
        (all(r.speaker_rationale for r in transcript.rounds),
         "Speaker 权重调整有 rationale"),
    ]
    for passed, desc in checks:
        icon = "✅" if passed else "❌"
        print(f"    {icon} {desc}")

    return transcript


if __name__ == "__main__":
    main()
