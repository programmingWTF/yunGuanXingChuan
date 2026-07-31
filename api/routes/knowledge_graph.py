"""
知识图谱路由 - 获取图谱数据
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, Query
from typing import Optional

from src.knowledge.kg_builder import get_knowledge_graph

router = APIRouter()


@router.get("/")
async def get_graph():
    """获取完整知识图谱数据"""
    kg = get_knowledge_graph()
    return kg.get_all_graph_data()


@router.get("/stats")
async def get_stats():
    """获取图谱统计信息"""
    kg = get_knowledge_graph()
    return kg.get_stats()


@router.get("/entity/{entity_name}")
async def get_entity(entity_name: str):
    """获取实体详情"""
    kg = get_knowledge_graph()
    info = kg.get_entity_info(entity_name)
    if info is None:
        return {"error": f"实体 '{entity_name}' 不存在"}
    return info


@router.get("/related/{entity_name}")
async def get_related(
    entity_name: str,
    depth: int = Query(2, ge=1, le=3, description="搜索深度"),
):
    """获取相关实体"""
    kg = get_knowledge_graph()
    related = kg.find_related_entities(entity_name, depth=depth)
    return {"entity": entity_name, "related": related}


@router.get("/subgraph/{topic}")
async def get_subgraph(topic: str):
    """获取议题相关子图"""
    kg = get_knowledge_graph()
    return kg.get_subgraph_for_topic(topic)


@router.get("/search")
async def search_entities(
    q: str = Query(..., description="搜索关键词"),
    entity_type: Optional[str] = Query(None, description="实体类型筛选"),
):
    """搜索实体"""
    kg = get_knowledge_graph()
    results = []
    for node in kg.G.nodes():
        if q.lower() in node.lower():
            node_data = kg.G.nodes[node]
            if entity_type is None or node_data.get("entity_type") == entity_type:
                results.append({
                    "name": node,
                    "type": node_data.get("entity_type", "unknown"),
                    "attributes": node_data.get("attributes", {}),
                })
    return {"query": q, "count": len(results), "results": results}


@router.get("/components")
async def get_components():
    """获取所有连通分量（分区浏览用）"""
    kg = get_knowledge_graph()
    components = kg.get_connected_components()
    # 返回时不包含 nodes 列表（太大），只返回摘要
    return {
        "total_components": len(components),
        "components": [
            {
                "id": c["id"],
                "label": c["label"],
                "hub_type": c["hub_type"],
                "node_count": c["node_count"],
                "edge_count": c["edge_count"],
            }
            for c in components
        ],
    }


@router.get("/component/{component_id}")
async def get_component_graph(component_id: int):
    """获取指定连通分量的图谱数据"""
    kg = get_knowledge_graph()
    return kg.get_component_graph_data(component_id)
