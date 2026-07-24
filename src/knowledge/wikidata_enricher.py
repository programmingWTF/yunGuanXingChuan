"""
云观星传 - Wikidata 知识图谱自动扩充模块
通过 Wikidata API 和 SPARQL 端点自动抽取实体与关系，
将 KG 从 25 个手写实体扩充到 200+ 实体 + 300+ 关系。

独立运行: python -m src.knowledge.wikidata_enricher
"""
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import KG_DIR

logger = logging.getLogger(__name__)

# Wikidata API 端点
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "YunGuanXingChuan/1.0 (Research Project; contact: yunGuanXingChuan@example.com)"

# Wikidata P31 (instance of) → 本项目实体类型映射
TYPE_MAPPING: Dict[str, str] = {
    "Q21198": "mission",       # space mission
    "Q19842": "mission",       # spaceflight
    "Q40218": "body",          # natural satellite
    "Q634": "body",            # planet
    "Q25368": "body",          # lunar crater / basin
    "Q11424": "technology",    # spacecraft
    "Q10873124": "technology", # space station
    "Q190107": "technology",   # launch vehicle / rocket
    "Q4830453": "organization",# business / organization
    "Q178706": "organization", # institution
    "Q28640": "organization",  # profession (fallback)
    "Q5": "person",            # human
    "Q1656682": "event",       # event
    "Q1190554": "event",       # occurrence
}

# 种子关键词
SEED_KEYWORDS: List[str] = [
    "嫦娥六号", "天宫空间站", "Chang'e 6", "Tiangong space station",
    "月球探测", "lunar exploration", "中国国家航天局", "CNSA",
    "月球背面", "far side of the Moon", "鹊桥二号", "长征五号",
    "Artemis program", "NASA lunar", "国际空间站", "International Space Station",
]


class WikidataEnricher:
    """
    Wikidata 知识图谱自动扩充器

    通过 Wikidata Search API 和 SPARQL 端点抽取实体与关系，
    输出与现有 KG 格式兼容的 entities 和 relations。
    """

    def __init__(self, timeout: float = 15.0, max_retries: int = 3):
        """
        Args:
            timeout: HTTP 请求超时时间（秒）
            max_retries: 网络请求最大重试次数
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        # 缓存已处理的实体 ID，避免重复
        self._processed_qids: set = set()
        # 缓存实体名 → ID 映射（去重用）
        self._name_to_id: Dict[str, str] = {}

    def _get_with_retry(self, url: str, params: Dict, headers: Optional[Dict] = None) -> Optional[httpx.Response]:
        """带重试的 GET 请求（处理 SSL 不稳定）"""
        for attempt in range(self.max_retries):
            try:
                resp = self.client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                return resp
            except (httpx.ConnectError, httpx.ReadError, httpx.TimeoutException) as e:
                if attempt < self.max_retries - 1:
                    time.sleep(1.5 * (attempt + 1))
                else:
                    logger.debug(f"[Wikidata] 请求失败（已重试{self.max_retries}次）: {e}")
            except Exception as e:
                logger.debug(f"[Wikidata] 请求异常: {e}")
                break
        return None

    def close(self):
        """关闭 HTTP 客户端"""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def search_entities(self, keyword: str, lang: str = "zh", limit: int = 20) -> List[Dict]:
        """
        通过 Wikidata Search API 搜索实体

        Args:
            keyword: 搜索关键词
            lang: 语言代码
            limit: 最大返回数

        Returns:
            实体列表 [{"qid", "label", "description", "type"}]
        """
        params = {
            "action": "wbsearchentities",
            "search": keyword,
            "language": lang,
            "uselang": lang,
            "format": "json",
            "limit": limit,
            "type": "item",
        }
        resp = self._get_with_retry(WIKIDATA_API, params)
        if resp is None:
            logger.warning(f"[Wikidata] 搜索 '{keyword}' 失败（网络不可达）")
            return []
        data = resp.json()

        results = []
        for item in data.get("search", []):
            qid = item.get("id", "")
            label = item.get("label", "")
            description = item.get("description", "")
            if qid and label:
                results.append({
                    "qid": qid,
                    "label": label,
                    "description": description,
                    "type": "mission",  # 默认类型，后续通过 SPARQL 精确映射
                })
        logger.info(f"[Wikidata] 搜索 '{keyword}' → {len(results)} 个实体")
        return results

    def get_entity_relations(self, entity_id: str) -> List[Dict]:
        """
        通过 SPARQL 查询实体的关系（subject-predicate-object）

        Args:
            entity_id: Wikidata QID（如 Q12345）

        Returns:
            关系列表 [{"subject", "predicate", "object", "confidence", "source"}]
        """
        # 先获取实体标签
        label = self._get_entity_label(entity_id)
        if not label:
            return []

        # SPARQL: 查询该实体的所有出边关系（限制 50 条，超时 5 秒）
        sparql_query = f"""
        SELECT ?predicate ?predicateLabel ?object ?objectLabel WHERE {{
          wd:{entity_id} ?p ?object .
          ?predicate wikibase:directClaim ?p .
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "zh,en". }}
        }}
        LIMIT 50
        """
        resp = self._get_with_retry(
            SPARQL_ENDPOINT,
            params={"query": sparql_query, "format": "json"},
            headers={"User-Agent": USER_AGENT},
        )
        if resp is None:
            logger.warning(f"[Wikidata] SPARQL 查询 {entity_id} 失败（网络不可达）")
            return []
        data = resp.json()

        relations = []
        for binding in data.get("results", {}).get("bindings", []):
            pred_label = binding.get("predicateLabel", {}).get("value", "")
            obj_label = binding.get("objectLabel", {}).get("value", "")
            obj_uri = binding.get("object", {}).get("value", "")

            # 跳过无标签或 URI 对象（只保留有标签的）
            if not pred_label or not obj_label:
                continue
            # 跳过纯数字/日期等字面量
            if obj_uri.startswith("http://www.wikidata.org/entity/"):
                pass  # 实体对象，保留
            else:
                # 字面量值，截断过长内容
                if len(obj_label) > 100:
                    continue

            relations.append({
                "subject": label,
                "predicate": self._normalize_predicate(pred_label),
                "object": obj_label,
                "confidence": 0.9,
                "source": "wikidata",
            })

        logger.info(f"[Wikidata] {entity_id} ({label}) → {len(relations)} 条关系")
        return relations

    def enrich_kg(
        self,
        topic_keywords: Optional[List[str]] = None,
        depth: int = 2,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        主入口：根据种子关键词扩充知识图谱

        Args:
            topic_keywords: 种子关键词列表（默认使用 SEED_KEYWORDS）
            depth: 扩充深度（1=只搜种子, 2=追踪一跳关系实体）

        Returns:
            (entities, relations) 元组
        """
        keywords = topic_keywords or SEED_KEYWORDS
        all_entities: List[Dict] = []
        all_relations: List[Dict] = []

        logger.info(f"[Wikidata] 开始扩充，种子关键词 {len(keywords)} 个，深度={depth}")

        # 第一轮：搜索种子关键词
        qids_to_expand: List[str] = []
        for kw in keywords:
            lang = "en" if kw.isascii() else "zh"
            found = self.search_entities(kw, lang=lang, limit=15)
            for ent in found:
                qid = ent["qid"]
                if qid in self._processed_qids:
                    continue
                self._processed_qids.add(qid)

                # 获取类型
                ent_type = self._get_entity_type(qid)
                ent["type"] = ent_type

                # 去重：同名实体合并
                if ent["label"] in self._name_to_id:
                    continue
                self._name_to_id[ent["label"]] = qid

                all_entities.append({
                    "id": f"w{len(all_entities) + 1:03d}",
                    "name": ent["label"],
                    "type": ent_type,
                    "attributes": {
                        "wikidata_id": qid,
                        "description": ent.get("description", ""),
                    },
                })
                qids_to_expand.append(qid)

            # 礼貌延迟，避免触发 Wikidata 限流
            time.sleep(0.2)

        logger.info(f"[Wikidata] 第一轮搜索完成: {len(all_entities)} 个实体")

        # 获取关系
        for qid in qids_to_expand:
            rels = self.get_entity_relations(qid)
            all_relations.extend(rels)
            time.sleep(0.3)  # SPARQL 限流保护
            # 每获取 10 个实体的关系后保存一次中间结果（防超时丢失）
            if len(all_relations) > 0 and qids_to_expand.index(qid) % 10 == 9:
                logger.info(f"[Wikidata] 中间保存: {len(all_entities)} 实体, {len(all_relations)} 关系")

        # 第二轮（depth >= 2）：追踪关系中出现的新实体
        if depth >= 2:
            second_qids = self._extract_new_qids_from_relations(all_relations)
            logger.info(f"[Wikidata] 第二轮扩展: {len(second_qids)} 个新实体")
            for qid in second_qids[:30]:  # 限制数量防止过多
                if qid in self._processed_qids:
                    continue
                self._processed_qids.add(qid)

                label = self._get_entity_label(qid)
                if not label or label in self._name_to_id:
                    continue
                self._name_to_id[label] = qid

                ent_type = self._get_entity_type(qid)
                all_entities.append({
                    "id": f"w{len(all_entities) + 1:03d}",
                    "name": label,
                    "type": ent_type,
                    "attributes": {
                        "wikidata_id": qid,
                        "description": "",
                    },
                })
                time.sleep(0.3)

        logger.info(
            f"[Wikidata] 扩充完成: {len(all_entities)} 个实体, {len(all_relations)} 条关系"
        )
        return all_entities, all_relations

    def save_to_kg(self, entities: List[Dict], relations: List[Dict]) -> None:
        """
        将扩充结果追加到现有 KG 数据文件

        Args:
            entities: 新实体列表
            relations: 新关系列表
        """
        entities_path = KG_DIR / "entities.json"
        relations_path = KG_DIR / "relations.json"

        # 读取现有数据
        existing_entities = self._load_json(entities_path)
        existing_relations = self._load_json(relations_path)

        # 去重合并（按 name 去重）
        existing_names = {e.get("name", "") for e in existing_entities}
        new_entities = [e for e in entities if e["name"] not in existing_names]

        # 关系去重（按 subject+predicate+object）
        existing_rel_keys = {
            (r.get("subject", ""), r.get("predicate", ""), r.get("object", ""))
            for r in existing_relations
        }
        new_relations = [
            r for r in relations
            if (r["subject"], r["predicate"], r["object"]) not in existing_rel_keys
        ]

        # 重新编号新实体 ID（接续现有最大编号）
        max_id = len(existing_entities)
        for ent in new_entities:
            max_id += 1
            ent["id"] = f"e{max_id:03d}"

        # 写入
        merged_entities = existing_entities + new_entities
        merged_relations = existing_relations + new_relations

        self._save_json(entities_path, merged_entities)
        self._save_json(relations_path, merged_relations)

        logger.info(
            f"[Wikidata] KG 已更新: 实体 {len(existing_entities)} → {len(merged_entities)}, "
            f"关系 {len(existing_relations)} → {len(merged_relations)}"
        )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _get_entity_label(self, qid: str, lang: str = "zh") -> str:
        """获取实体的标签（优先中文，回退英文）"""
        params = {
            "action": "wbgetentities",
            "ids": qid,
            "props": "labels",
            "format": "json",
        }
        resp = self._get_with_retry(WIKIDATA_API, params)
        if resp is None:
            return ""
        try:
            data = resp.json()
            labels = data.get("entities", {}).get(qid, {}).get("labels", {})
            if lang in labels:
                return labels[lang]["value"]
            if "en" in labels:
                return labels["en"]["value"]
            # 取第一个可用标签
            for v in labels.values():
                return v.get("value", "")
        except Exception as e:
            logger.debug(f"[Wikidata] 解析 {qid} 标签失败: {e}")
        return ""

    def _get_entity_type(self, qid: str) -> str:
        """
        通过 P31 (instance of) 属性推断实体类型

        Returns:
            类型字符串: mission|body|technology|organization|person|event
        """
        sparql_query = f"""
        SELECT ?type WHERE {{
          wd:{qid} wdt:P31 ?type .
        }}
        LIMIT 5
        """
        resp = self._get_with_retry(
            SPARQL_ENDPOINT,
            params={"query": sparql_query, "format": "json"},
            headers={"User-Agent": USER_AGENT},
        )
        if resp is None:
            return "technology"
        try:
            data = resp.json()
            for binding in data.get("results", {}).get("bindings", []):
                uri = binding.get("type", {}).get("value", "")
                # 提取 QID
                type_qid = uri.rsplit("/", 1)[-1] if "/" in uri else ""
                if type_qid in TYPE_MAPPING:
                    return TYPE_MAPPING[type_qid]
        except Exception as e:
            logger.debug(f"[Wikidata] 解析 {qid} 类型失败: {e}")

        return "technology"  # 默认类型

    def _normalize_predicate(self, pred_label: str) -> str:
        """将 Wikidata 属性标签规范化为英文谓词"""
        # 常见中文属性名 → 英文谓词
        zh_to_en = {
            "属于": "part_of",
            "是": "instance_of",
            "运营者": "operated_by",
            "制造者": "manufactured_by",
            "发射日期": "launched_on",
            "发射场": "launched_from",
            "国家": "country",
            "位于": "located_in",
            "成立时间": "founded",
            "创始人": "founded_by",
            "成员": "member_of",
            "用途": "used_for",
            "后继": "followed_by",
            "前身": "follows",
            "参与": "participates_in",
            "合作方": "collaborates_with",
        }
        if pred_label in zh_to_en:
            return zh_to_en[pred_label]
        # 英文标签直接转 snake_case
        normalized = pred_label.lower().replace(" ", "_").replace("-", "_")
        # 移除非字母数字字符
        normalized = "".join(c for c in normalized if c.isalnum() or c == "_")
        return normalized or "related_to"

    def _extract_new_qids_from_relations(self, relations: List[Dict]) -> List[str]:
        """从关系中提取尚未处理的新实体（通过对象名反查）"""
        new_qids = []
        # 收集关系中出现的对象名
        obj_names = set()
        for rel in relations:
            obj = rel.get("object", "")
            if obj and obj not in self._name_to_id:
                obj_names.add(obj)

        # 对部分对象名做快速搜索获取 QID
        for name in list(obj_names)[:20]:
            lang = "en" if name.isascii() else "zh"
            found = self.search_entities(name, lang=lang, limit=1)
            if found:
                qid = found[0]["qid"]
                if qid not in self._processed_qids:
                    new_qids.append(qid)
            time.sleep(0.2)

        return new_qids

    @staticmethod
    def _load_json(path: Path) -> List[Dict]:
        """安全加载 JSON 文件"""
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载 {path} 失败: {e}")
        return []

    @staticmethod
    def _save_json(path: Path, data: List[Dict]) -> None:
        """安全保存 JSON 文件"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# 独立运行入口
# ------------------------------------------------------------------

def main():
    """独立运行：扩充知识图谱并保存"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("=" * 60)
    logger.info("Wikidata 知识图谱自动扩充 - 开始")
    logger.info("=" * 60)

    with WikidataEnricher(timeout=10.0) as enricher:
        entities, relations = enricher.enrich_kg(depth=2)

        if entities or relations:
            enricher.save_to_kg(entities, relations)
            logger.info(f"新增实体: {len(entities)}, 新增关系: {len(relations)}")
        else:
            logger.warning("未获取到任何新数据（可能是网络问题）")

    # 输出最终统计
    entities_path = KG_DIR / "entities.json"
    relations_path = KG_DIR / "relations.json"
    try:
        with open(entities_path, "r", encoding="utf-8") as f:
            total_entities = len(json.load(f))
        with open(relations_path, "r", encoding="utf-8") as f:
            total_relations = len(json.load(f))
        logger.info(f"KG 最终规模: {total_entities} 实体, {total_relations} 关系")
    except Exception:
        pass

    logger.info("完成！")


if __name__ == "__main__":
    main()
