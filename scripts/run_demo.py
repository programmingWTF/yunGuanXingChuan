"""
云观星传 - Demo 运行脚本
输入议题名即可一键跑完整流程

用法：
    python scripts/run_demo.py --topic "嫦娥六号"
    python scripts/run_demo.py --topic "天宫空间站"
"""
import argparse
import json
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import Pipeline
from src.knowledge.kg_builder import get_knowledge_graph
from src.knowledge.vector_store import get_vector_store


def setup_logging(verbose: bool = False):
    """配置日志"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def print_banner():
    """打印启动横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   云观星传 — 基于通义大模型的科技议题传播分析与表达系统        ║
║                                                              ║
║   AI Scientist 范式：假设生成 - 验证 - 迭代                   ║
║   RAG + 知识图谱双校验 | 五维评分 + 自迭代闭环                ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_result_summary(result):
    """打印结果摘要"""
    print("\n" + "=" * 60)
    print("📊 Pipeline 执行结果摘要")
    print("=" * 60)

    print(f"\n🔬 议题: {result.topic}")
    print(f"⏰ 时间: {result.timestamp}")
    print(f"🔄 迭代轮数: {result.iteration_count}")
    print(f"✅ 最终状态: {result.final_status}")

    # 科学事实
    facts = result.science_facts
    print(f"\n📚 科学事实: {len(facts.get('key_facts', []))} 条")
    for i, fact in enumerate(facts.get("key_facts", [])[:3], 1):
        print(f"   {i}. {fact}")
    if len(facts.get("key_facts", [])) > 3:
        print(f"   ... 还有 {len(facts.get('key_facts', [])) - 3} 条")

    # 假设
    print(f"\n💡 传播假设: {len(result.hypotheses)} 条")
    for hyp in result.hypotheses[:2]:
        print(f"   - [{hyp.hypothesis_id}] {hyp.statement[:60]}...")
        print(f"     置信度: {hyp.confidence:.0%} | 框架: {hyp.framework.value}")

    # 校验
    print(f"\n🔍 校验结果: {len(result.verification_report)} 条断言")
    verified = sum(1 for r in result.verification_report if r.status.value == "verified")
    partial = sum(1 for r in result.verification_report if r.status.value == "partial")
    print(f"   已验证: {verified} | 部分验证: {partial} | 其他: {len(result.verification_report) - verified - partial}")

    # 策略
    print(f"\n📋 传播策略: {len(result.strategies)} 条")
    for strategy in result.strategies:
        print(f"   - [{strategy.strategy_id}] 受众: {strategy.target_audience}")
        print(f"     人设: {strategy.narrative_persona.value} | 渠道: {', '.join(strategy.channel_recommendation[:2])}")

    # 评分
    scores = result.evaluation
    print(f"\n📈 五维评分:")
    print(f"   事实准确度:     {scores.factual_accuracy:.0f}/100 (权重30%)")
    print(f"   策略可操作性:   {scores.strategic_actionability:.0f}/100 (权重25%)")
    print(f"   受众适配度:     {scores.audience_fit:.0f}/100 (权重20%)")
    print(f"   文化敏感性:     {scores.cultural_sensitivity:.0f}/100 (权重15%)")
    print(f"   叙事流畅度:     {scores.narrative_fluency:.0f}/100 (权重10%)")
    print(f"   ─────────────────────────────────")
    print(f"   加权总分:       {scores.weighted_total:.1f}/100")

    print("\n" + "=" * 60)


def save_result(result, output_dir: Path):
    """保存结果到文件"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存完整结果
    output_file = output_dir / f"pipeline_result_{result.topic}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)

    print(f"\n💾 结果已保存到: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="云观星传 - Demo 运行脚本")
    parser.add_argument(
        "--topic", "-t",
        type=str,
        default="嫦娥六号",
        help="科技议题名称（默认：嫦娥六号）"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细日志"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="输出目录（默认：data/output/）"
    )
    parser.add_argument(
        "--skip-init",
        action="store_true",
        help="跳过知识图谱和向量库初始化"
    )

    args = parser.parse_args()

    # 配置日志
    setup_logging(args.verbose)

    # 打印横幅
    print_banner()

    print(f"🚀 开始分析议题: {args.topic}")
    print("-" * 60)

    # 初始化知识图谱和向量库
    if not args.skip_init:
        print("\n📦 初始化知识图谱...")
        try:
            kg = get_knowledge_graph()
            stats = kg.get_stats()
            print(f"   实体: {stats['total_entities']} | 关系: {stats['total_relations']}")
        except Exception as e:
            print(f"   ⚠️ 知识图谱初始化失败: {e}")

        print("\n📦 初始化向量库...")
        try:
            vs = get_vector_store()
            if vs.index is None or vs.index.ntotal == 0:
                print("   构建向量索引...")
                vs.build_index()
            print(f"   向量数: {vs.index.ntotal if vs.index else 0}")
        except Exception as e:
            print(f"   ⚠️ 向量库初始化失败: {e}")

    # 运行 Pipeline
    print("\n" + "=" * 60)
    print("🔄 开始运行 Pipeline...")
    print("=" * 60)

    pipeline = Pipeline()
    result = pipeline.run(args.topic)

    # 打印结果
    print_result_summary(result)

    # 保存结果
    output_dir = Path(args.output) if args.output else PROJECT_ROOT / "data" / "output"
    save_result(result, output_dir)

    # 打印迭代总结
    iteration_summary = pipeline.get_iteration_summary()
    if iteration_summary.get("total_rounds", 0) > 1:
        print(f"\n📊 迭代总结:")
        print(f"   初始分数: {iteration_summary.get('initial_score', 0):.1f}")
        print(f"   最终分数: {iteration_summary.get('final_score', 0):.1f}")
        print(f"   提升: +{iteration_summary.get('improvement', 0):.1f}")

    print("\n✨ Demo 运行完成！")


if __name__ == "__main__":
    main()
