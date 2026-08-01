"""
云观星传 - 知识图谱报告生成器（数据驱动，不调用 LLM）
从知识图谱（get_knowledge_graph）组装统计报告：#8 议题
报告结构：主题 → 知识图谱 → 热点节点 → 关键人物 → 机构 → 关系 → 证据来源
"""
from typing import Dict, List, Any, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.knowledge.kg_builder import get_knowledge_graph
from src.schemas import KGReport, KGNodeStat, KGRelation

# Wikidata 来源标记（报告中需要排除的噪声来源）
WIKIDATA_SOURCE = "wikidata"

# 有效的实体类型白名单（排除 unknown 与 Wikidata 噪声）
MEANINGFUL_TYPES = {"mission", "body", "organization", "person", "technology", "event"}

# Wikidata 扩充的典型噪声关键词（基因名等科研术语，非航天议题相关）
_NOISE_KEYWORDS = ("SH3GL", "COPD", "gene", "protein", "chromosome", "Homo sapiens")


def _is_noise_node(name: str, node_type: str) -> bool:
    """判断是否为 Wikidata 噪声节点（基因名等科研术语）"""
    if any(k.lower() in name.lower() for k in _NOISE_KEYWORDS):
        return True
    # TODO: 尚未实现"technology 类型但仅通过 wikidata 边连接、且不在原始 entities.json 中"
    #       的更严格过滤规则，目前仅按关键词匹配（见 _NOISE_KEYWORDS）
    return False


def _hot_nodes(kg, top_n: int = 10) -> List[Dict[str, Any]]:
    """按度数 Top N 计算热点节点，过滤 unknown 与 Wikidata 噪声"""
    scored = []
    for name, deg in kg.G.degree():
        node_type = kg.G.nodes[name].get("entity_type", "unknown")
        if node_type == "unknown" or node_type not in MEANINGFUL_TYPES:
            continue
        if _is_noise_node(name, node_type):
            continue
        # 取该节点出入边中置信度最高的关系作为 top_relation
        top_rel = ""
        best_conf = -1.0
        for _, _, data in kg.G.edges(name, data=True):
            conf = data.get("confidence", 0.0)
            if conf > best_conf:
                best_conf = conf
                top_rel = f"{data.get('predicate', '')}→{data.get('source', '')}"
        for pred, _, data in kg.G.in_edges(name, data=True):
            conf = data.get("confidence", 0.0)
            if conf > best_conf:
                best_conf = conf
                top_rel = f"{data.get('predicate', '')}←{data.get('source', '')}"
        scored.append({"name": name, "type": node_type, "degree": int(deg), "top_relation": top_rel})

    scored.sort(key=lambda x: x["degree"], reverse=True)
    return scored[:top_n]


def _nodes_by_type(kg, entity_type: str) -> List[Dict[str, Any]]:
    """按类型取节点（关键人物/机构）"""
    nodes = []
    for name in kg.G.nodes():
        node_type = kg.G.nodes[name].get("entity_type", "unknown")
        if node_type != entity_type:
            continue
        if _is_noise_node(name, node_type):
            continue
        deg = kg.G.degree(name)
        nodes.append({"name": name, "type": entity_type, "degree": int(deg), "top_relation": ""})
    nodes.sort(key=lambda x: x["degree"], reverse=True)
    return nodes


def _topic_triples(kg, topic: str, limit: int = 15) -> List[Dict[str, Any]]:
    """围绕 topic 的关系三元组（含证据来源），直接读边数据避免 source 丢失"""
    triples = []
    seen = set()

    def _add(subject, pred, obj, data):
        key = (subject, pred, obj)
        if key in seen:
            return
        seen.add(key)
        triples.append({
            "subject": subject,
            "predicate": pred,
            "object": obj,
            "confidence": float(data.get("confidence", 1.0)),
            "source": data.get("source", ""),
        })

    if topic not in kg.G:
        return triples

    for succ in kg.G.successors(topic):
        data = kg.G[topic][succ]
        _add(topic, data.get("predicate", ""), succ, data)
    for pred in kg.G.predecessors(topic):
        data = kg.G[pred][topic]
        _add(pred, data.get("predicate", ""), topic, data)

    # 非 wikidata 来源优先，再按 confidence 降序
    triples.sort(key=lambda t: (t["source"] != WIKIDATA_SOURCE, t["confidence"]), reverse=True)
    return triples[:limit]


def _evidence_sources(kg, topic: Optional[str] = None, limit: int = 12) -> List[str]:
    """去重的证据来源（排除 wikidata）；topic 存在时优先收集其出入边来源，否则收集全图来源"""
    sources = set()

    def _collect_node_edges(node: str):
        """收集指定节点出入边上的非 wikidata 来源"""
        for _, _, data in list(kg.G.edges(node, data=True)) + list(kg.G.in_edges(node, data=True)):
            src = data.get("source", "")
            if src and src != WIKIDATA_SOURCE:
                sources.add(src)

    if topic and topic in kg.G:
        _collect_node_edges(topic)
    else:
        # 全图收集非 wikidata 来源
        for _, _, data in kg.G.edges(data=True):
            src = data.get("source", "")
            if src and src != WIKIDATA_SOURCE:
                sources.add(src)

    return sorted(sources)[:limit]


def generate_kg_report(input_data: Dict[str, Any], top_n: int = 10) -> Dict[str, Any]:
    """知识图谱报告生成入口（纯函数，不调用 LLM）
    输入：input_data 含 topic（可选）
    输出：KGReport 结构的 dict
    """
    topic = input_data.get("topic", "")
    kg = get_knowledge_graph()
    stats = kg.get_stats()

    # 图谱总览段落
    total_entities = stats.get("total_entities", kg.G.number_of_nodes())
    total_relations = stats.get("total_relations", kg.G.number_of_edges())
    et = stats.get("entity_types", {})
    kg_summary = (
        f"知识图谱共 {total_entities} 个实体、{total_relations} 条关系。"
        f"实体类型分布：任务 {et.get('mission', 0)}、天体 {et.get('body', 0)}、"
        f"技术 {et.get('technology', 0)}、机构 {et.get('organization', 0)}、人物 {et.get('person', 0)}。"
    )
    if topic and topic in kg.G:
        related = kg.find_related_entities(topic, depth=2)
        kg_summary += f"该议题「{topic}」关联 {len(related)} 个实体。"
    else:
        kg_summary += f"当前未在图中找到议题「{topic}」，展示全图统计。"

    report = KGReport(
        topic=topic,
        kg_summary=kg_summary,
        hot_nodes=[KGNodeStat(**x) for x in _hot_nodes(kg, top_n)],
        key_persons=[KGNodeStat(**x) for x in _nodes_by_type(kg, "person")],
        organizations=[KGNodeStat(**x) for x in _nodes_by_type(kg, "organization")],
        relations=[KGRelation(**x) for x in _topic_triples(kg, topic)],
        evidence_sources=_evidence_sources(kg, topic),
        note="本报告由知识图谱数据自动生成，仅作为分析参考，可追溯至下方证据来源。",
    )
    return report.model_dump()
