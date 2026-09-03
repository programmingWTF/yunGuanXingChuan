"""
云观星传 - 测试 Fixtures
提供不依赖 LLM 的预定义示例数据
"""
import sys
from pathlib import Path

# 确保项目根目录在 path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

# 关键：先真实导入 httpx / openai，防止部分测试文件的
# `sys.modules['httpx'] = MagicMock()` 兼容 hack 在 openai>=1.66
# （httpx2 兼容层）下全量运行崩溃（isinstance 拿到 MagicMock 非 type）。
# conftest 最先加载，真实模块先入 sys.modules 后，后续 hack 不再覆盖。
import httpx  # noqa: F401
import openai  # noqa: F401

# 同理锁定 faiss：vector_store 等模块依赖真实 FAISS 行为
# （IndexFlatIP/normalize_L2），若任一测试文件的条件 mock 先行注册
# `sys.modules['faiss'] = MagicMock()`，后续导入会拿到假模块。
# CI 与本地均安装 faiss-cpu，导入失败时静默回退由各测试自行 mock。
try:
    import faiss  # noqa: F401
except ImportError:  # pragma: no cover - 环境无 faiss 时由测试文件自行 mock
    pass

import pytest


@pytest.fixture
def sample_science_facts():
    """返回一组预定义的示例科学事实，不依赖 LLM"""
    return {
        "topic": "嫦娥六号",
        "key_facts": [
            "嫦娥六号于2024年5月3日发射，6月25日返回地球（中国国家航天局）",
            "嫦娥六号实现了人类首次月球背面采样返回（CNSA官方公告）",
            "嫦娥六号携带月背样品1935.3克返回（新华社报道）",
            "嫦娥六号着陆于月球背面南极-艾特肯盆地（NASA月球勘测轨道飞行器确认）",
            "鹊桥二号中继卫星为嫦娥六号提供通信支持（中国航天科技集团）",
            "嫦娥六号搭载了法国、巴基斯坦等国的国际合作载荷（ESA/CNSA联合声明）",
            "长征五号遥八运载火箭执行了嫦娥六号发射任务（文昌航天发射场）",
            "嫦娥六号任务历时53天（从发射到返回器着陆）",
        ],
        "entities": [
            {"name": "嫦娥六号", "entity_type": "mission", "attributes": {"launch_date": "2024-05-03"}, "description": "中国月球背面采样返回任务"},
            {"name": "月球背面", "entity_type": "body", "attributes": {}, "description": "月球永远背对地球的一面"},
            {"name": "中国国家航天局", "entity_type": "organization", "attributes": {"abbr": "CNSA"}, "description": "中国航天主管部门"},
            {"name": "鹊桥二号", "entity_type": "technology", "attributes": {}, "description": "中继通信卫星"},
            {"name": "长征五号", "entity_type": "technology", "attributes": {}, "description": "大型运载火箭"},
        ],
        "relations": [
            {"subject": "嫦娥六号", "predicate": "launched_by", "object": "长征五号", "confidence": 0.95, "source": "CNSA"},
            {"subject": "嫦娥六号", "predicate": "landed_on", "object": "月球背面", "confidence": 0.99, "source": "CNSA"},
            {"subject": "嫦娥六号", "predicate": "managed_by", "object": "中国国家航天局", "confidence": 0.99, "source": "官方"},
            {"subject": "鹊桥二号", "predicate": "supports", "object": "嫦娥六号", "confidence": 0.95, "source": "CNSA"},
        ],
        "timeline": [
            {"date": "2024-05-03", "event": "嫦娥六号发射"},
            {"date": "2024-06-02", "event": "着陆月球背面"},
            {"date": "2024-06-25", "event": "返回器着陆地球"},
        ],
        "data_sources": ["中国国家航天局", "新华社", "NASA"],
    }


@pytest.fixture
def sample_hypotheses():
    """返回一组预定义的示例假设"""
    return [
        {
            "hypothesis_id": "H001",
            "statement": "国际媒体倾向于使用'太空竞赛'框架报道嫦娥六号任务",
            "framework": "competition",
            "target_countries": ["美国", "法国"],
            "evidence_chain": [
                {"source": "Reuters", "quote": "China's space race ambitions", "relevance": 0.8, "evidence_type": "media_report"}
            ],
            "verification_path": "对比美法媒体报道中competition框架占比",
            "confidence": 0.75,
            "kg_entities_involved": ["嫦娥六号", "NASA"],
            "falsification_criteria": "若competition框架占比低于30%则假设不成立",
        },
        {
            "hypothesis_id": "H002",
            "statement": "发展中国家媒体更多采用'合作发展'框架",
            "framework": "cooperation",
            "target_countries": ["巴西", "巴基斯坦"],
            "evidence_chain": [
                {"source": "Pakistan Observer", "quote": "joint space exploration", "relevance": 0.7, "evidence_type": "media_report"}
            ],
            "verification_path": "统计发展中国家媒体cooperation框架占比",
            "confidence": 0.65,
            "kg_entities_involved": ["嫦娥六号", "国际合作"],
            "falsification_criteria": "若cooperation框架占比低于40%则假设不成立",
        },
    ]


@pytest.fixture
def sample_evaluation_scores():
    """返回一组示例五维评分"""
    from src.schemas import EvaluationScores
    return EvaluationScores(
        factual_accuracy=85,
        strategic_actionability=72,
        audience_fit=78,
        cultural_sensitivity=80,
        narrative_fluency=75,
    )


@pytest.fixture
def sample_low_scores():
    """返回一组低分五维评分（用于测试迭代触发）"""
    from src.schemas import EvaluationScores
    return EvaluationScores(
        factual_accuracy=55,
        strategic_actionability=60,
        audience_fit=65,
        cultural_sensitivity=70,
        narrative_fluency=68,
    )
