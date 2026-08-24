"""
云观星传 - RAG 校验模块
基于百炼 text-embedding-v3 + FAISS 实现事实检索校验
"""
import logging
from typing import List, Dict, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.knowledge.vector_store import get_vector_store
from src.llm_client import get_llm_client
from src.schemas import VerificationResult, VerificationStatus

logger = logging.getLogger(__name__)


class RAGChecker:
    """RAG 校验器：通过向量检索验证事实断言"""

    def __init__(self, similarity_threshold: float = 0.45, llm_client=None):
        """
        Args:
            similarity_threshold: 相似度阈值，高于此值认为找到支持证据（默认 0.45，中文短文本检索适配）
            llm_client: 多租户模式下当前用户的 LLM 客户端（None 用全局默认）
        """
        self.similarity_threshold = similarity_threshold
        self.vector_store = get_vector_store()
        self.llm_client = llm_client

    def verify_claim(self, claim: str) -> Dict:
        """
        校验单条事实断言（优先语义校验，回退相似度匹配）
        """
        try:
            # 优先尝试 LLM 语义校验
            try:
                return self.verify_claim_semantic(claim)
            except Exception:
                pass
            # 回退到向量相似度校验
            result = self.vector_store.verify_claim(
                claim, threshold=self.similarity_threshold
            )
            return {
                "claim": claim,
                "status": result["status"],
                "confidence": result["confidence"],
                "evidence": result.get("evidence", ""),
                "source": result.get("source", ""),
                "message": result.get("message", ""),
            }
        except Exception as e:
            logger.error(f"RAG 校验失败: {e}")
            return {
                "claim": claim,
                "status": "unverified",
                "confidence": 0.0,
                "evidence": None,
                "source": "",
                "message": f"校验异常: {str(e)}",
            }

    def verify_claim_semantic(self, claim: str, top_k: int = 5) -> Dict:
        """
        使用 LLM 进行语义级事实校验（替代纯相似度匹配）
        """
        search_results = self.vector_store.search(claim, top_k=top_k)
        if not search_results:
            return {
                "claim": claim, "status": "unverified", "confidence": 0.0,
                "evidence": None, "source": "",
                "message": "未找到相关文档用于语义校验",
            }

        parts = []
        for i, r in enumerate(search_results):
            src = r["metadata"].get("source", "?")
            parts.append(f"[{i+1}] {src}: {r['text'][:200]}")
        evidence_text = "\n".join(parts)

        prompt_text = (
            "请校验以下断言是否与参考文本一致：\n\n"
            f"断言：{claim}\n\n参考文本：\n{evidence_text}\n\n"
            '请输出 JSON：{{"consistent": true/false, "confidence": 0.0-1.0, '
            '"evidence_summary": "证据摘要", "key_sources": ["来源"], "notes": "说明"}}'
        )

        llm = self.llm_client or get_llm_client()
        result = llm.chat_json(
            system_prompt="你是事实校验专家。请判断给定断言是否与参考文本一致。输出 JSON。",
            user_prompt=prompt_text,
            temperature=0.1,
            json_mode=True,
        )

        consistent = result.get("consistent", False)
        confidence = result.get("confidence", 0.5)

        if consistent and confidence >= 0.7:
            s = "supported"
        elif consistent:
            s = "partial"
        else:
            s = "unverified"

        return {
            "claim": claim,
            "status": s,
            "confidence": confidence,
            "evidence": result.get("evidence_summary", ""),
            "source": result.get("key_sources", [search_results[0]["metadata"].get("source", "") if search_results else ""]),
            "message": result.get("notes", "LLM semantic verification"),
            "semantic_check": True,
        }

    def verify_claims_batch(self, claims: List[str]) -> List[Dict]:
        """
        批量校验事实断言

        Args:
            claims: 待校验的事实断言列表

        Returns:
            校验结果列表
        """
        results = []
        for claim in claims:
            result = self.verify_claim(claim)
            results.append(result)
        return results

    def verify_science_facts(self, science_facts: Dict) -> List[Dict]:
        """
        校验科学事实数据中的所有 key_facts

        Args:
            science_facts: 科学事实数据（包含 key_facts 字段）

        Returns:
            校验结果列表
        """
        key_facts = science_facts.get("key_facts", [])
        if not key_facts:
            logger.warning("没有需要校验的事实")
            return []

        logger.info(f"开始 RAG 校验 {len(key_facts)} 条事实...")
        results = self.verify_claims_batch(key_facts)

        # 统计
        verified = sum(1 for r in results if r["status"] == "supported")
        partial = sum(1 for r in results if r["status"] == "partial")
        unverified = sum(1 for r in results if r["status"] == "unverified")

        logger.info(
            f"RAG 校验完成: {verified} 条已验证, {partial} 条部分验证, {unverified} 条未验证"
        )

        return results

    def get_verification_summary(self, results: List[Dict]) -> Dict:
        """
        获取校验结果摘要

        Args:
            results: 校验结果列表

        Returns:
            摘要字典
        """
        if not results:
            return {"total": 0, "verified": 0, "partial": 0, "unverified": 0}

        verified = sum(1 for r in results if r["status"] == "supported")
        partial = sum(1 for r in results if r["status"] == "partial")
        unverified = sum(1 for r in results if r["status"] == "unverified")

        return {
            "total": len(results),
            "verified": verified,
            "partial": partial,
            "unverified": unverified,
            "verification_rate": verified / len(results) if results else 0,
            "avg_confidence": sum(r["confidence"] for r in results) / len(results),
        }