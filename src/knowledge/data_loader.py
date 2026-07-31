"""
云观星传 - 数据加载模块
统一加载科学数据、媒体语料、受众画像等
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.settings import DATA_DIR, SCIENCE_DIR, MEDIA_DIR, AUDIENCE_DIR, KG_DIR

logger = logging.getLogger(__name__)


class DataLoader:
    """数据加载器：统一管理所有数据文件的读取"""

    def __init__(self):
        self.data_dir = DATA_DIR

    def load_science_facts(self, topic: Optional[str] = None) -> List[Dict]:
        """
        加载科学事实数据
    
        Args:
            topic: 议题名称（如“嫦娥七号”），为 None 则加载全部
    
        Returns:
            科学事实数据列表
        """
        facts = []
        for json_file in SCIENCE_DIR.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if topic is None or data.get("topic", "") == topic:
                    facts.append(data)
            except Exception as e:
                logger.warning(f"加载科学数据 {json_file} 失败: {e}")
    
        # 模糊匹配兜底：如果精确匹配无结果，尝试包含匹配
        if not facts and topic:
            for json_file in SCIENCE_DIR.glob("*.json"):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    file_topic = data.get("topic", "")
                    if topic in file_topic or file_topic in topic:
                        facts.append(data)
                except Exception:
                    pass
    
        logger.info(f"加载 {len(facts)} 个科学数据集")
        return facts

    def load_media_reports(self, country: Optional[str] = None) -> List[Dict]:
        """
        加载媒体报道数据

        Args:
            country: 国家名称（如 "us", "france", "brazil"），为 None 则加载全部

        Returns:
            媒体报道列表
        """
        reports = []

        if country:
            country_dir = MEDIA_DIR / country
            if country_dir.exists():
                for json_file in country_dir.glob("*.json"):
                    try:
                        with open(json_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if isinstance(data, list):
                            reports.extend(data)
                        else:
                            reports.append(data)
                    except Exception as e:
                        logger.warning(f"加载媒体数据 {json_file} 失败: {e}")
        else:
            for country_dir in MEDIA_DIR.iterdir():
                if country_dir.is_dir():
                    for json_file in country_dir.glob("*.json"):
                        try:
                            with open(json_file, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            if isinstance(data, list):
                                reports.extend(data)
                            else:
                                reports.append(data)
                        except Exception as e:
                            logger.warning(f"加载媒体数据 {json_file} 失败: {e}")

        logger.info(f"加载 {len(reports)} 篇媒体报道")
        return reports

    def load_audience_profiles(self) -> Dict[str, Dict]:
        """
        加载受众画像数据

        Returns:
            受众画像字典 {profile_id: profile_data}
        """
        profiles = {}
        for json_file in AUDIENCE_DIR.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                profile_id = json_file.stem
                profiles[profile_id] = data
            except Exception as e:
                logger.warning(f"加载受众画像 {json_file} 失败: {e}")

        logger.info(f"加载 {len(profiles)} 个受众画像")
        return profiles

    def load_kg_data(self) -> Dict:
        """
        加载知识图谱原始数据

        Returns:
            包含 entities 和 relations 的字典
        """
        kg_data = {"entities": [], "relations": []}

        entities_file = KG_DIR / "entities.json"
        if entities_file.exists():
            with open(entities_file, "r", encoding="utf-8") as f:
                kg_data["entities"] = json.load(f)

        relations_file = KG_DIR / "relations.json"
        if relations_file.exists():
            with open(relations_file, "r", encoding="utf-8") as f:
                kg_data["relations"] = json.load(f)

        logger.info(
            f"加载 KG 数据: {len(kg_data['entities'])} 个实体, "
            f"{len(kg_data['relations'])} 条关系"
        )
        return kg_data

    def get_media_summary(self) -> Dict:
        """
        获取媒体数据统计摘要

        Returns:
            按国家分组的统计信息
        """
        reports = self.load_media_reports()
        summary = {}

        for report in reports:
            country = report.get("country", "unknown")
            if country not in summary:
                summary[country] = {
                    "total": 0,
                    "frameworks": {},
                    "sentiments": {},
                    "sources": set(),
                }

            summary[country]["total"] += 1
            framework = report.get("framework", "unknown")
            sentiment = report.get("sentiment", "unknown")
            source = report.get("source", "unknown")

            summary[country]["frameworks"][framework] = \
                summary[country]["frameworks"].get(framework, 0) + 1
            summary[country]["sentiments"][sentiment] = \
                summary[country]["sentiments"].get(sentiment, 0) + 1
            summary[country]["sources"].add(source)

        # 转换 set 为 list（JSON 序列化）
        for country in summary:
            summary[country]["sources"] = list(summary[country]["sources"])

        return summary

    def get_all_data_for_topic(self, topic: str) -> Dict:
        """
        获取指定议题的所有相关数据

        Args:
            topic: 议题名称

        Returns:
            包含所有相关数据的字典
        """
        return {
            "topic": topic,
            "science_facts": self.load_science_facts(topic),
            "media_reports": self.load_media_reports(),
            "audience_profiles": self.load_audience_profiles(),
            "kg_data": self.load_kg_data(),
        }


# 全局单例
_data_loader: Optional[DataLoader] = None


def get_data_loader() -> DataLoader:
    """获取全局数据加载器单例"""
    global _data_loader
    if _data_loader is None:
        _data_loader = DataLoader()
    return _data_loader
