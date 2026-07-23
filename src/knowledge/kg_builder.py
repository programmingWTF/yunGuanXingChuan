"""
云观星传 - 知识图谱构建与查询模块
基于 NetworkX + JSON 实现轻量级知识图谱
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import networkx as nx

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import KG_DIR, SCIENCE_DIR

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """知识图谱：基于 NetworkX 的实体-关系图"""

    def __init__(self, graph_path: Optional[Path] = None):
        """
        Args:
            graph_path: 图谱 JSON 文件路径
        """
        self.graph_path = graph_path or (KG_DIR / "graph.json")
        self.G = nx.DiGraph()  # 有向图
        self.entities: Dict[str, Dict] = {}  # 实体字典
        self.relations: List[Dict] = []  # 关系列表

    def build_from_data(self):
        """从 data/kg/ 和 data/science/ 构建知识图谱"""
        self._load_entities()
        self._load_relations()
        self._load_science_data()
        self._save_graph()
        logger.info(
            f"知识图谱构建完成: {self.G.number_of_nodes()} 个实体, "
            f"{self.G.number_of_edges()} 条关系"
        )

    def _load_entities(self):
        """加载实体数据"""
        entities_file = KG_DIR / "entities.json"
        if not entities_file.exists():
            logger.warning(f"实体文件不存在: {entities_file}")
            return

        with open(entities_file, "r", encoding="utf-8") as f:
            entities = json.load(f)

        for entity in entities:
            name = entity["name"]
            self.entities[name] = entity
            self.G.add_node(
                name,
                entity_type=entity.get("type", "unknown"),
                attributes=entity.get("attributes", {}),
                id=entity.get("id", ""),
            )

        logger.info(f"加载 {len(entities)} 个实体")

    def _load_relations(self):
        """加载关系数据"""
        relations_file = KG_DIR / "relations.json"
        if not relations_file.exists():
            logger.warning(f"关系文件不存在: {relations_file}")
            return

        with open(relations_file, "r", encoding="utf-8") as f:
            relations = json.load(f)

        for rel in relations:
            subject = rel["subject"]
            obj = rel["object"]
            predicate = rel["predicate"]

            # 确保节点存在
            if subject not in self.G:
                self.G.add_node(subject, entity_type="unknown", attributes={})
            if obj not in self.G:
                self.G.add_node(obj, entity_type="unknown", attributes={})

            self.G.add_edge(
                subject, obj,
                predicate=predicate,
                confidence=rel.get("confidence", 1.0),
                source=rel.get("source", ""),
            )
            self.relations.append(rel)

        logger.info(f"加载 {len(relations)} 条关系")

    def _load_science_data(self):
        """从科学数据文件补充实体和关系（去重）"""
        existing_nodes = set(self.G.nodes())
        for json_file in SCIENCE_DIR.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for entity in data.get("entities", []):
                    name = entity["name"]
                    if name not in existing_nodes:
                        self.G.add_node(name, entity_type=entity.get("type", "unknown"), attributes=entity.get("attributes", {}))
                        self.entities[name] = entity
                        existing_nodes.add(name)
                for rel in data.get("relations", []):
                    s, o, p = rel["subject"], rel["object"], rel["predicate"]
                    if s not in existing_nodes:
                        self.G.add_node(s, entity_type="unknown", attributes={}); existing_nodes.add(s)
                    if o not in existing_nodes:
                        self.G.add_node(o, entity_type="unknown", attributes={}); existing_nodes.add(o)
                    if not self.G.has_edge(s, o):
                        self.G.add_edge(s, o, predicate=p, confidence=rel.get("confidence", 1.0), source=rel.get("source", json_file.stem))
                        self.relations.append(rel)
            except Exception as e:
                logger.warning(f"加载科学数据 {json_file} 失败: {e}")

    def verify_triple(self, subject: str, predicate: str, obj: str) -> Dict:
        """
        校验三元组是否存在于知识图谱中

        Args:
            subject: 主体
            predicate: 谓词
            obj: 客体

        Returns:
            校验结果
        """
        # 精确匹配
        if self.G.has_edge(subject, obj):
            edge_data = self.G[subject][obj]
            if edge_data.get("predicate") == predicate:
                return {
                    "status": "verified",
                    "confidence": edge_data.get("confidence", 1.0),
                    "source": edge_data.get("source", ""),
                    "message": f"三元组 ({subject}, {predicate}, {obj}) 在知识图谱中存在",
                }
            else:
                return {
                    "status": "partial",
                    "confidence": 0.5,
                    "source": edge_data.get("source", ""),
                    "message": f"实体间存在关系但谓词不同: 实际为 {edge_data.get('predicate')}",
                }

        # 模糊匹配：检查实体是否存在
        subject_exists = subject in self.G
        obj_exists = obj in self.G

        if subject_exists and obj_exists:
            # 检查是否有路径连接
            try:
                path = nx.shortest_path(self.G, subject, obj)
                return {
                    "status": "partial",
                    "confidence": 0.4,
                    "source": "",
                    "message": f"实体存在但无直接关系，最短路径: {' -> '.join(path)}",
                }
            except nx.NetworkXNoPath:
                return {
                    "status": "unverified",
                    "confidence": 0.2,
                    "source": "",
                    "message": "实体存在但无路径连接",
                }

        if subject_exists or obj_exists:
            return {
                "status": "unverified",
                "confidence": 0.1,
                "source": "",
                "message": f"部分实体不存在: {'客体' if subject_exists else '主体'} '{obj if subject_exists else subject}' 未在图谱中",
            }

        return {
            "status": "unverified",
            "confidence": 0.0,
            "source": "",
            "message": "主体和客体均不在知识图谱中",
        }

    def find_related_entities(self, entity_name: str, depth: int = 2) -> List[Dict]:
        """
        查找与指定实体相关的实体

        Args:
            entity_name: 实体名称
            depth: 搜索深度

        Returns:
            相关实体列表
        """
        if entity_name not in self.G:
            return []

        related = []
        # BFS 搜索
        visited = {entity_name}
        current_level = [entity_name]

        for d in range(depth):
            next_level = []
            for node in current_level:
                # 出边
                for successor in self.G.successors(node):
                    if successor not in visited:
                        visited.add(successor)
                        next_level.append(successor)
                        edge_data = self.G[node][successor]
                        related.append({
                            "entity": successor,
                            "relation": edge_data.get("predicate", ""),
                            "direction": "outgoing",
                            "depth": d + 1,
                            "confidence": edge_data.get("confidence", 1.0),
                        })
                # 入边
                for predecessor in self.G.predecessors(node):
                    if predecessor not in visited:
                        visited.add(predecessor)
                        next_level.append(predecessor)
                        edge_data = self.G[predecessor][node]
                        related.append({
                            "entity": predecessor,
                            "relation": edge_data.get("predicate", ""),
                            "direction": "incoming",
                            "depth": d + 1,
                            "confidence": edge_data.get("confidence", 1.0),
                        })
            current_level = next_level

        return related

    def get_entity_info(self, entity_name: str) -> Optional[Dict]:
        """获取实体详细信息"""
        if entity_name not in self.G:
            return None

        node_data = self.G.nodes[entity_name]
        return {
            "name": entity_name,
            "type": node_data.get("entity_type", "unknown"),
            "attributes": node_data.get("attributes", {}),
            "outgoing_relations": [
                {"target": s, "predicate": self.G[entity_name][s].get("predicate", "")}
                for s in self.G.successors(entity_name)
            ],
            "incoming_relations": [
                {"source": p, "predicate": self.G[p][entity_name].get("predicate", "")}
                for p in self.G.predecessors(entity_name)
            ],
        }

    def get_subgraph_for_topic(self, topic: str) -> Dict:
        """
        获取与指定议题相关的子图（用于前端可视化）

        Args:
            topic: 议题名称

        Returns:
            子图数据（nodes + edges）
        """
        # 找到与 topic 相关的所有实体
        related = self.find_related_entities(topic, depth=2)
        entity_names = {topic} | {r["entity"] for r in related}

        # 构建子图
        subgraph = self.G.subgraph(entity_names)

        nodes = []
        for node in subgraph.nodes():
            node_data = subgraph.nodes[node]
            nodes.append({
                "name": node,
                "type": node_data.get("entity_type", "unknown"),
                "attributes": node_data.get("attributes", {}),
            })

        edges = []
        for u, v, data in subgraph.edges(data=True):
            edges.append({
                "source": u,
                "target": v,
                "predicate": data.get("predicate", ""),
                "confidence": data.get("confidence", 1.0),
            })

        return {"nodes": nodes, "edges": edges}

    def get_all_graph_data(self) -> Dict:
        """获取完整图谱数据（用于前端可视化）"""
        nodes = []
        for node in self.G.nodes():
            node_data = self.G.nodes[node]
            nodes.append({
                "name": node,
                "type": node_data.get("entity_type", "unknown"),
                "attributes": node_data.get("attributes", {}),
            })

        edges = []
        for u, v, data in self.G.edges(data=True):
            edges.append({
                "source": u,
                "target": v,
                "predicate": data.get("predicate", ""),
                "confidence": data.get("confidence", 1.0),
            })

        return {"nodes": nodes, "edges": edges}

    def _save_graph(self):
        """保存图谱到 JSON 文件"""
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)

        graph_data = {
            "nodes": [],
            "edges": [],
            "stats": {
                "node_count": self.G.number_of_nodes(),
                "edge_count": self.G.number_of_edges(),
            }
        }

        for node in self.G.nodes():
            node_data = self.G.nodes[node]
            graph_data["nodes"].append({
                "name": node,
                "type": node_data.get("entity_type", "unknown"),
                "attributes": node_data.get("attributes", {}),
            })

        for u, v, data in self.G.edges(data=True):
            graph_data["edges"].append({
                "source": u,
                "target": v,
                "predicate": data.get("predicate", ""),
                "confidence": data.get("confidence", 1.0),
                "source_doc": data.get("source", ""),
            })

        with open(self.graph_path, "w", encoding="utf-8") as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)

        logger.info(f"图谱已保存到 {self.graph_path}")

    def load_graph(self) -> bool:
        """从 JSON 文件加载图谱"""
        if not self.graph_path.exists():
            return False

        try:
            with open(self.graph_path, "r", encoding="utf-8") as f:
                graph_data = json.load(f)

            self.G = nx.DiGraph()

            for node in graph_data.get("nodes", []):
                self.G.add_node(
                    node["name"],
                    entity_type=node.get("type", "unknown"),
                    attributes=node.get("attributes", {}),
                )

            for edge in graph_data.get("edges", []):
                self.G.add_edge(
                    edge["source"],
                    edge["target"],
                    predicate=edge.get("predicate", ""),
                    confidence=edge.get("confidence", 1.0),
                    source=edge.get("source_doc", ""),
                )

            logger.info(
                f"图谱已加载: {self.G.number_of_nodes()} 个实体, "
                f"{self.G.number_of_edges()} 条关系"
            )
            return True
        except Exception as e:
            logger.error(f"加载图谱失败: {e}")
            return False

    def get_stats(self) -> Dict:
        """获取图谱统计信息"""
        entity_types = {}
        for node in self.G.nodes():
            etype = self.G.nodes[node].get("entity_type", "unknown")
            entity_types[etype] = entity_types.get(etype, 0) + 1

        relation_types = {}
        for _, _, data in self.G.edges(data=True):
            rtype = data.get("predicate", "unknown")
            relation_types[rtype] = relation_types.get(rtype, 0) + 1

        return {
            "total_entities": self.G.number_of_nodes(),
            "total_relations": self.G.number_of_edges(),
            "entity_types": entity_types,
            "relation_types": relation_types,
        }


# 全局单例
_kg: Optional[KnowledgeGraph] = None


def get_knowledge_graph() -> KnowledgeGraph:
    """获取全局知识图谱单例"""
    global _kg
    if _kg is None:
        _kg = KnowledgeGraph()
        # 尝试加载已有图谱，否则构建
        if not _kg.load_graph():
            _kg.build_from_data()
    return _kg
