"""
云观星传 - 经验池 SQLite 持久化存储
支持：评测结果持久化、历史议题经验检索、相似议题匹配、全局统计
"""
import json
import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import DATA_DIR

logger = logging.getLogger(__name__)

# 数据库默认路径
DEFAULT_DB_PATH = str(DATA_DIR / "experience.db")


class ExperienceStore:
    """SQLite 持久化的经验池"""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        """
        Args:
            db_path: SQLite 数据库文件路径
        """
        self.db_path = db_path
        # 确保目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """创建表结构"""
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS experiences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    round_num INTEGER NOT NULL,
                    weighted_total REAL NOT NULL,
                    passed INTEGER NOT NULL DEFAULT 0,
                    scores_json TEXT NOT NULL,
                    weak_dims_json TEXT NOT NULL DEFAULT '[]',
                    feedback_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_experiences_topic
                    ON experiences(topic);
                CREATE INDEX IF NOT EXISTS idx_experiences_created
                    ON experiences(created_at);

                CREATE TABLE IF NOT EXISTS topic_embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL UNIQUE,
                    embedding_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)
            conn.commit()
            logger.info(f"经验池数据库初始化完成: {self.db_path}")
        except Exception as e:
            logger.error(f"经验池数据库初始化失败: {e}")
        finally:
            conn.close()

    def log_experience(
        self,
        topic: str,
        round_num: int,
        scores: Dict[str, float],
        feedback: List[Dict],
        passed: bool,
        weak_dims: Optional[List[str]] = None,
    ) -> int:
        """
        记录一次评测经验

        Args:
            topic: 议题名称
            round_num: 迭代轮次
            scores: 五维评分字典
            feedback: 迭代反馈列表
            passed: 是否通过
            weak_dims: 低分维度列表

        Returns:
            记录 ID
        """
        # 计算加权总分
        from config.settings import EVALUATION_WEIGHTS
        weighted_total = sum(
            scores.get(dim, 0) * weight
            for dim, weight in EVALUATION_WEIGHTS.items()
        )

        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """INSERT INTO experiences
                   (topic, round_num, weighted_total, passed, scores_json, weak_dims_json, feedback_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    topic,
                    round_num,
                    weighted_total,
                    1 if passed else 0,
                    json.dumps(scores, ensure_ascii=False),
                    json.dumps(weak_dims or [], ensure_ascii=False),
                    json.dumps(feedback, ensure_ascii=False),
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
            record_id = cursor.lastrowid
            logger.info(f"[经验池] 记录经验: topic={topic}, round={round_num}, total={weighted_total:.1f}")
            return record_id
        except Exception as e:
            logger.error(f"[经验池] 记录失败: {e}")
            return -1
        finally:
            conn.close()

    def get_topic_history(self, topic: str) -> List[Dict]:
        """
        获取某个议题的所有历史经验

        Args:
            topic: 议题名称

        Returns:
            经验记录列表（按时间排序）
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM experiences WHERE topic = ? ORDER BY created_at",
                (topic,),
            ).fetchall()
            return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            logger.error(f"[经验池] 查询失败: {e}")
            return []
        finally:
            conn.close()

    def find_similar_topics(self, topic: str, top_k: int = 3) -> List[Dict]:
        """
        查找与给定议题最相似的历史议题

        使用 embedding 余弦相似度匹配。如果 embedding 不可用，
        回退到简单的字符串包含匹配。

        Args:
            topic: 查询议题
            top_k: 返回最相似的前 k 个

        Returns:
            相似议题列表 [{topic, similarity, best_score, times_run}]
        """
        conn = self._get_conn()
        try:
            # 获取所有已存储的议题及其 embedding
            rows = conn.execute(
                "SELECT topic, embedding_json FROM topic_embeddings"
            ).fetchall()

            if not rows:
                # 没有 embedding 数据，回退到字符串匹配
                return self._fallback_similarity(topic, top_k, conn)

            # 尝试获取查询议题的 embedding
            query_embedding = self._get_or_compute_embedding(topic)
            if not query_embedding:
                return self._fallback_similarity(topic, top_k, conn)

            # 计算余弦相似度
            import math
            results = []
            for row in rows:
                stored_topic = row["topic"]
                if stored_topic == topic:
                    continue
                try:
                    stored_embedding = json.loads(row["embedding_json"])
                    sim = self._cosine_similarity(query_embedding, stored_embedding)
                    results.append({"topic": stored_topic, "similarity": sim})
                except (json.JSONDecodeError, TypeError):
                    continue

            # 按相似度排序
            results.sort(key=lambda x: x["similarity"], reverse=True)
            top_results = results[:top_k]

            # 补充每个议题的统计信息
            for item in top_results:
                stats = conn.execute(
                    """SELECT MAX(weighted_total) as best_score, COUNT(DISTINCT created_at) as times_run
                       FROM experiences WHERE topic = ?""",
                    (item["topic"],),
                ).fetchone()
                item["best_score"] = stats["best_score"] if stats else 0
                item["times_run"] = stats["times_run"] if stats else 0

            return top_results

        except Exception as e:
            logger.error(f"[经验池] 相似议题查询失败: {e}")
            return []
        finally:
            conn.close()

    def _fallback_similarity(self, topic: str, top_k: int, conn: sqlite3.Connection) -> List[Dict]:
        """回退的字符串匹配相似度"""
        rows = conn.execute(
            "SELECT DISTINCT topic FROM experiences"
        ).fetchall()

        results = []
        for row in rows:
            stored_topic = row["topic"]
            if stored_topic == topic:
                continue
            # 简单的字符重叠度
            common = len(set(topic) & set(stored_topic))
            total = max(len(set(topic)), len(set(stored_topic)), 1)
            sim = common / total
            results.append({"topic": stored_topic, "similarity": sim})

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def _get_or_compute_embedding(self, topic: str) -> Optional[List[float]]:
        """获取或计算议题的 embedding"""
        conn = self._get_conn()
        try:
            # 先查缓存
            row = conn.execute(
                "SELECT embedding_json FROM topic_embeddings WHERE topic = ?",
                (topic,),
            ).fetchone()
            if row:
                return json.loads(row["embedding_json"])

            # 计算新 embedding
            try:
                from src.llm_client import get_llm_client
                client = get_llm_client()
                embedding = client.get_embedding(topic)
                if embedding:
                    # 存入缓存
                    conn.execute(
                        """INSERT OR REPLACE INTO topic_embeddings (topic, embedding_json, created_at)
                           VALUES (?, ?, ?)""",
                        (topic, json.dumps(embedding), datetime.now().isoformat()),
                    )
                    conn.commit()
                    return embedding
            except Exception as e:
                logger.warning(f"[经验池] 计算 embedding 失败: {e}")

            return None
        except Exception as e:
            logger.error(f"[经验池] embedding 查询失败: {e}")
            return None
        finally:
            conn.close()

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        if len(a) != len(b) or not a:
            return 0.0
        import math
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def get_improvement_trend(self) -> Dict:
        """
        获取全局改进趋势统计

        Returns:
            {total_runs, avg_first_score, avg_final_score, avg_improvement, pass_rate, topics_count}
        """
        conn = self._get_conn()
        try:
            # 总运行次数（按 topic+created_at 分组近似）
            total = conn.execute("SELECT COUNT(*) as cnt FROM experiences").fetchone()["cnt"]
            topics_count = conn.execute("SELECT COUNT(DISTINCT topic) as cnt FROM experiences").fetchone()["cnt"]

            if total == 0:
                return {
                    "total_runs": 0, "avg_first_score": 0, "avg_final_score": 0,
                    "avg_improvement": 0, "pass_rate": 0, "topics_count": 0,
                }

            # 通过率
            passed_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM experiences WHERE passed = 1"
            ).fetchone()["cnt"]

            # 每个议题的首轮和末轮分数
            topic_scores = conn.execute("""
                SELECT topic,
                       MIN(CASE WHEN round_num = 1 THEN weighted_total END) as first_score,
                       MAX(weighted_total) as best_score
                FROM experiences
                GROUP BY topic
            """).fetchall()

            first_scores = [r["first_score"] for r in topic_scores if r["first_score"] is not None]
            best_scores = [r["best_score"] for r in topic_scores if r["best_score"] is not None]

            avg_first = sum(first_scores) / len(first_scores) if first_scores else 0
            avg_best = sum(best_scores) / len(best_scores) if best_scores else 0

            return {
                "total_runs": total,
                "avg_first_score": round(avg_first, 1),
                "avg_final_score": round(avg_best, 1),
                "avg_improvement": round(avg_best - avg_first, 1),
                "pass_rate": round(passed_count / total, 3) if total > 0 else 0,
                "topics_count": topics_count,
            }
        except Exception as e:
            logger.error(f"[经验池] 统计查询失败: {e}")
            return {"total_runs": 0, "avg_first_score": 0, "avg_final_score": 0,
                    "avg_improvement": 0, "pass_rate": 0, "topics_count": 0}
        finally:
            conn.close()

    def get_common_weaknesses(self, limit: int = 5) -> List[Dict]:
        """
        获取最常见的低分维度

        Args:
            limit: 返回前 N 个

        Returns:
            [{dimension, count, avg_score}]
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT weak_dims_json, scores_json FROM experiences WHERE weak_dims_json != '[]'"
            ).fetchall()

            dim_stats: Dict[str, Dict] = {}  # dim -> {count, total_score}
            for row in rows:
                try:
                    weak_dims = json.loads(row["weak_dims_json"])
                    scores = json.loads(row["scores_json"])
                    for dim in weak_dims:
                        if dim not in dim_stats:
                            dim_stats[dim] = {"count": 0, "total_score": 0}
                        dim_stats[dim]["count"] += 1
                        dim_stats[dim]["total_score"] += scores.get(dim, 0)
                except (json.JSONDecodeError, TypeError):
                    continue

            results = []
            for dim, stats in dim_stats.items():
                results.append({
                    "dimension": dim,
                    "count": stats["count"],
                    "avg_score": round(stats["total_score"] / stats["count"], 1) if stats["count"] > 0 else 0,
                })

            results.sort(key=lambda x: x["count"], reverse=True)
            return results[:limit]
        except Exception as e:
            logger.error(f"[经验池] 弱点统计失败: {e}")
            return []
        finally:
            conn.close()

    def store_topic_embedding(self, topic: str, embedding: List[float]):
        """
        存储议题 embedding（供相似议题匹配使用）

        Args:
            topic: 议题名称
            embedding: 向量
        """
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO topic_embeddings (topic, embedding_json, created_at)
                   VALUES (?, ?, ?)""",
                (topic, json.dumps(embedding), datetime.now().isoformat()),
            )
            conn.commit()
        except Exception as e:
            logger.warning(f"[经验池] 存储 embedding 失败: {e}")
        finally:
            conn.close()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict:
        """将数据库行转为字典"""
        d = dict(row)
        # 解析 JSON 字段
        for key in ("scores_json", "weak_dims_json", "feedback_json"):
            if key in d and d[key]:
                try:
                    d[key.replace("_json", "")] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    d[key.replace("_json", "")] = {}
        d["passed"] = bool(d.get("passed", 0))
        return d


# 全局单例
_store: Optional[ExperienceStore] = None


def get_experience_store() -> ExperienceStore:
    """获取全局经验池单例"""
    global _store
    if _store is None:
        _store = ExperienceStore()
    return _store
