"""
云观星传 - 知识图谱校验模块
基于 NetworkX 知识图谱验证实体关系
"""
import logging
from typing import List, Dict, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.knowledge.kg_builder import get_knowledge_graph

logger = logging.getLogger(__name__)


class KGChecker:
    """知识图谱校验器：通过图谱匹配验证实体关系"""

    def __init__(self):
        self.kg = get_knowledge_graph()

    def verify_triple(self, subject: str, predicate: str, obj: str) -> Dict:
        """
        校验三元组

        Args:
            subject: 主体
            predicate: 谓词
            obj: 客体

        Returns:
            校验结果
        """
        try:
            result = self.kg.verify_triple(subject, predicate, obj)
            return {
                "subject": subject,
                "predicate": predicate,
                "object": obj,
                "status": result["status"],
                "confidence": result["confidence"],
                "source": result.get("source", ""),
                "message": result.get("message", ""),
            }
        except Exception as e:
            logger.error(f"KG 校验失败: {e}")
            return {
                "subject": subject,
                "predicate": predicate,
                "object": obj,
                "status": "unverified",
                "confidence": 0.0,
                "source": "",
                "message": f"校验异常: {str(e)}",
            }

    def verify_relations(self, relations: List[Dict]) -> List[Dict]:
        """
        批量校验关系列表

        Args:
            relations: 关系列表，每项包含 subject/predicate/object

        Returns:
            校验结果列表
        """
        results = []
        for rel in relations:
            result = self.verify_triple(
                subject=rel.get("subject", ""),
                predicate=rel.get("predicate", ""),
                obj=rel.get("object", ""),
            )
            results.append(result)
        return results

    def verify_entities_exist(self, entities: List[str]) -> Dict:
        """
        检查实体是否存在于知识图谱中

        Args:
            entities: 实体名称列表

        Returns:
            存在性检查结果
        """
        existing = []
        missing = []

        for entity in entities:
            if entity in self.kg.G:
                existing.append(entity)
            else:
                missing.append(entity)

        return {
            "total": len(entities),
            "existing": existing,
            "missing": missing,
            "coverage_rate": len(existing) / len(entities) if entities else 0,
        }

    def verify_science_facts(self, science_facts: Dict) -> Dict:
        """
        校验科学事实数据中的实体和关系

        Args:
            science_facts: 科学事实数据

        Returns:
            校验结果
        """
        # 校验实体
        entities = [e.get("name", "") for e in science_facts.get("entities", [])]
        entity_check = self.verify_entities_exist(entities)

        # 校验关系
        relations = science_facts.get("relations", [])
        relation_results = self.verify_relations(relations)

        # 统计
        verified_relations = sum(1 for r in relation_results if r["status"] == "verified")
        partial_relations = sum(1 for r in relation_results if r["status"] == "partial")

        return {
            "entity_check": entity_check,
            "relation_results": relation_results,
            "summary": {
                "total_relations": len(relations),
                "verified": verified_relations,
                "partial": partial_relations,
                "unverified": len(relations) - verified_relations - partial_relations,
                "entity_coverage": entity_check["coverage_rate"],
            }
        }

    def get_related_context(self, entity: str, depth: int = 2) -> List[Dict]:
        """
        获取实体的相关上下文（用于辅助校验）

        Args:
            entity: 实体名称
            depth: 搜索深度

        Returns:
            相关实体列表
        """
        return self.kg.find_related_entities(entity, depth=depth)

    def check_for_conflicts(self, claim_subject: str, claim_object: str) -> Dict:
        """
        检查是否存在矛盾关系

        Args:
            claim_subject: 断言主体
            claim_object: 断言客体

        Returns:
            冲突检查结果
        """
        # 检查是否有竞争关系
        try:
            if self.kg.G.has_edge(claim_subject, claim_object):
                edge_data = self.kg.G[claim_subject][claim_object]
                predicate = edge_data.get("predicate", "")
                if predicate in ["competes_with", "conflicts_with"]:
                    return {
                        "has_conflict": True,
                        "conflict_type": predicate,
                        "message": f"知识图谱中存在竞争/冲突关系: {claim_subject} -{predicate}-> {claim_object}",
                    }
            return {"has_conflict": False, "message": "未发现矛盾关系"}
        except Exception as e:
            return {"has_conflict": False, "message": f"检查异常: {str(e)}"}
