"""
云观星传 - 向量存储模块
基于 FAISS + 百炼 text-embedding-v3 实现本地向量检索
"""
import json
import logging
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import faiss

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import DATA_DIR, SCIENCE_DIR, MEDIA_DIR
from src.llm_client import get_llm_client

logger = logging.getLogger(__name__)


class VectorStore:
    """FAISS 向量存储，支持文档分块、索引构建和语义检索"""

    def __init__(self, dimension: int = 1024, index_path: Optional[Path] = None):
        """
        Args:
            dimension: 向量维度（默认 1024，构建索引时会自动检测）
            index_path: 索引文件保存路径
        """
        self.dimension = dimension
        self.index_path = index_path or (DATA_DIR / "kg" / "vectors.faiss")
        self.index: Optional[faiss.IndexFlatIP] = None
        self.documents: List[Dict] = []  # 存储文档块及其元数据
        self.llm_client = get_llm_client()
        self._dimension_detected = False

    def _init_index(self):
        """初始化 FAISS 索引（内积相似度）"""
        self.index = faiss.IndexFlatIP(self.dimension)

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 400,
        overlap: int = 50,
        metadata: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        将文本分块

        Args:
            text: 原始文本
            chunk_size: 每块大小（字符数）
            overlap: 重叠字符数
            metadata: 附加元数据

        Returns:
            文档块列表，每块包含 text 和 metadata
        """
        chunks = []
        start = 0
        chunk_id = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end]

            if chunk_text.strip():
                chunks.append({
                    "chunk_id": chunk_id,
                    "text": chunk_text.strip(),
                    "metadata": metadata or {},
                })
                chunk_id += 1

            start = end - overlap if end < len(text) else end

        return chunks

    def build_index(self, documents: Optional[List[Dict]] = None):
        """
        构建向量索引

        Args:
            documents: 文档列表，每个文档包含 text 和 metadata
                      如果为 None，则自动加载 data/ 目录下的数据
        """
        if documents is None:
            documents = self._load_all_documents()

        if not documents:
            logger.warning("没有文档可供索引")
            return

        # 分块
        all_chunks = []
        for doc in documents:
            chunks = self.chunk_text(
                text=doc.get("text", doc.get("content", "")),
                metadata={
                    "source": doc.get("source", doc.get("id", "unknown")),
                    "title": doc.get("title", ""),
                    "date": doc.get("date", ""),
                    "type": doc.get("type", "unknown"),
                }
            )
            all_chunks.extend(chunks)

        if not all_chunks:
            logger.warning("分块后没有有效文档")
            return

        logger.info(f"共 {len(all_chunks)} 个文档块，开始向量化...")

        # 批量获取 embedding
        texts = [chunk["text"] for chunk in all_chunks]
        embeddings = self._get_embeddings_batch(texts)

        if not embeddings:
            logger.error("向量化失败")
            return

        # 自动检测维度（以第一条 embedding 为准）
        actual_dim = len(embeddings[0])
        if actual_dim != self.dimension:
            logger.info(f"检测到实际维度 {actual_dim}，更新索引维度（原设置 {self.dimension}）")
            self.dimension = actual_dim

        # 构建 FAISS 索引
        self._init_index()
        vectors = np.array(embeddings, dtype=np.float32)
        # L2 归一化（使内积等价于余弦相似度）
        faiss.normalize_L2(vectors)
        self.index.add(vectors)
        self.documents = all_chunks

        logger.info(f"索引构建完成，共 {self.index.ntotal} 个向量")

        # 保存索引
        self._save_index()

    def _get_embeddings_batch(self, texts: List[str], batch_size: int = 20) -> List[List[float]]:
        """批量获取 embedding（分批处理避免超限）"""
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                embeddings = self.llm_client.get_embeddings_batch(batch)
                all_embeddings.extend(embeddings)
            except Exception as e:
                logger.error(f"批次 {i//batch_size} 向量化失败: {e}")
                # 逐条重试
                for text in batch:
                    try:
                        emb = self.llm_client.get_embedding(text)
                        all_embeddings.append(emb)
                    except Exception:
                        all_embeddings.append([0.0] * self.dimension)
        return all_embeddings

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        语义检索

        Args:
            query: 查询文本
            top_k: 返回最相关的 k 个文档块

        Returns:
            检索结果列表，每项包含 text、score、metadata
        """
        if self.index is None or self.index.ntotal == 0:
            logger.warning("索引为空，尝试加载已有索引")
            if not self._load_index():
                return []

        # 获取查询向量
        query_embedding = self.llm_client.get_embedding(query)
        if not query_embedding:
            return []

        query_vector = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query_vector)

        # 检索
        scores, indices = self.index.search(query_vector, min(top_k, self.index.ntotal))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.documents):
                continue
            doc = self.documents[idx]
            results.append({
                "text": doc["text"],
                "score": float(score),
                "metadata": doc["metadata"],
            })

        return results

    def verify_claim(self, claim: str, threshold: float = 0.6) -> Dict:
        """
        校验事实断言

        Args:
            claim: 待校验的事实断言
            threshold: 相似度阈值

        Returns:
            校验结果字典
        """
        results = self.search(claim, top_k=5)

        if not results:
            return {
                "status": "unverified",
                "confidence": 0.0,
                "evidence": None,
                "message": "未找到相关文档",
            }

        top_result = results[0]
        if top_result["score"] >= threshold:
            return {
                "status": "supported",
                "confidence": top_result["score"],
                "evidence": top_result["text"],
                "source": top_result["metadata"].get("source", ""),
                "message": "找到支持性证据",
            }
        elif top_result["score"] >= threshold * 0.7:
            return {
                "status": "partial",
                "confidence": top_result["score"],
                "evidence": top_result["text"],
                "source": top_result["metadata"].get("source", ""),
                "message": "找到部分相关证据",
            }
        else:
            return {
                "status": "unverified",
                "confidence": top_result["score"],
                "evidence": top_result["text"],
                "source": top_result["metadata"].get("source", ""),
                "message": "相关度不足，无法验证",
            }

    def _load_all_documents(self) -> List[Dict]:
        """加载 data/ 目录下的所有文档"""
        documents = []

        # 加载科学数据
        for json_file in SCIENCE_DIR.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 将 key_facts 转为文档
                if "key_facts" in data:
                    for fact in data["key_facts"]:
                        documents.append({
                            "text": fact,
                            "source": json_file.stem,
                            "type": "science_fact",
                            "title": data.get("topic", ""),
                        })
                # 将实体描述转为文档
                if "entities" in data:
                    for entity in data["entities"]:
                        desc = f"{entity['name']} ({entity['type']}): {json.dumps(entity.get('attributes', {}), ensure_ascii=False)}"
                        documents.append({
                            "text": desc,
                            "source": json_file.stem,
                            "type": "entity",
                            "title": entity["name"],
                        })
            except Exception as e:
                logger.warning(f"加载 {json_file} 失败: {e}")

        # 加载媒体数据
        for country_dir in MEDIA_DIR.iterdir():
            if country_dir.is_dir():
                for json_file in country_dir.glob("*.json"):
                    try:
                        with open(json_file, "r", encoding="utf-8") as f:
                            reports = json.load(f)
                        for report in reports:
                            documents.append({
                                "text": report.get("content", ""),
                                "source": report.get("source", ""),
                                "type": "media_report",
                                "title": report.get("title", ""),
                                "date": report.get("date", ""),
                                "id": report.get("id", ""),
                            })
                    except Exception as e:
                        logger.warning(f"加载 {json_file} 失败: {e}")

        logger.info(f"共加载 {len(documents)} 个文档")
        return documents

    def _save_index(self):
        """保存索引和文档到磁盘"""
        if self.index is None:
            return

        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存 FAISS 索引
        faiss.write_index(self.index, str(self.index_path))

        # 保存文档元数据
        meta_path = self.index_path.with_suffix(".meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(self.documents, f, ensure_ascii=False, indent=2)

        logger.info(f"索引已保存到 {self.index_path}")

    def _load_index(self) -> bool:
        """从磁盘加载索引"""
        if not self.index_path.exists():
            return False

        try:
            self.index = faiss.read_index(str(self.index_path))
            meta_path = self.index_path.with_suffix(".meta.json")
            with open(meta_path, "r", encoding="utf-8") as f:
                self.documents = json.load(f)
            logger.info(f"索引已加载，共 {self.index.ntotal} 个向量")
            return True
        except Exception as e:
            logger.error(f"加载索引失败: {e}")
            return False


# 全局单例
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """获取全局向量存储单例"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
