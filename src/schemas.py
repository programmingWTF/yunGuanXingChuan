"""
云观星传 - 核心数据 Schema（Pydantic）
所有 Agent 间通信必须使用这些结构化 Schema
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class FrameworkType(str, Enum):
    """传播框架类型"""
    COMPETITION = "competition"   # 竞争框架
    COOPERATION = "cooperation"   # 合作框架
    PROGRESS = "progress"         # 进步框架
    THREAT = "threat"             # 威胁框架
    DEVELOPMENT = "development"   # 发展框架


class SentimentPolarity(str, Enum):
    """情感极性"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class VerificationStatus(str, Enum):
    """校验状态"""
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partial"
    CONFLICTING = "conflicting"
    UNVERIFIED = "unverified"


class NarrativePersona(str, Enum):
    """四种叙事人设"""
    SCIENTIST = "scientist"       # 科学家：Nature风格，数据驱动
    COLLABORATOR = "collaborator" # 合作者：共赢叙事
    STORYTELLER = "storyteller"   # 讲述者：故事化，国家地理风格
    COMMUNICATOR = "communicator" # 沟通者：理性平衡，政策分析风格


class ScientificEntity(BaseModel):
    """科学实体"""
    name: str
    entity_type: str  # mission/body/technology/organization/person/event
    attributes: dict = Field(default_factory=dict)
    description: str = ""


class ScientificRelation(BaseModel):
    """科学关系三元组"""
    subject: str
    predicate: str  # belongs_to/launched_at/discovered/part_of/collaborates_with/competes_with
    object: str
    confidence: float = Field(ge=0, le=1)
    source: str = ""


class Evidence(BaseModel):
    """证据"""
    source: str
    quote: str
    relevance: float = Field(ge=0, le=1)
    evidence_type: str  # media_report/scientific_data/policy_document


class Hypothesis(BaseModel):
    """传播假设"""
    hypothesis_id: str
    statement: str
    framework: FrameworkType
    target_countries: List[str]
    evidence_chain: List[Evidence]
    verification_path: str
    confidence: float = Field(ge=0, le=1)
    kg_entities_involved: List[str]
    falsification_criteria: str


class Strategy(BaseModel):
    """传播策略"""
    strategy_id: str
    target_audience: str
    narrative_persona: NarrativePersona
    narrative_angle: str
    key_messages: List[str]
    channel_recommendation: List[str]
    cultural_adaptations: List[str]
    sample_text: str  # 100-200字示例文本
    expected_effect: str
    risks: List[str]


class EvaluationScores(BaseModel):
    """五维评分"""
    factual_accuracy: float = Field(ge=0, le=100)       # 权重 30%
    strategic_actionability: float = Field(ge=0, le=100) # 权重 25%
    audience_fit: float = Field(ge=0, le=100)            # 权重 20%
    cultural_sensitivity: float = Field(ge=0, le=100)    # 权重 15%
    narrative_fluency: float = Field(ge=0, le=100)       # 权重 10%

    @property
    def weighted_total(self) -> float:
        """Use centralized weights from config/settings.py"""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from config.settings import EVALUATION_WEIGHTS  # noqa
        return (self.factual_accuracy * EVALUATION_WEIGHTS["factual_accuracy"]
              + self.strategic_actionability * EVALUATION_WEIGHTS["strategic_actionability"]
              + self.audience_fit * EVALUATION_WEIGHTS["audience_fit"]
              + self.cultural_sensitivity * EVALUATION_WEIGHTS["cultural_sensitivity"]
              + self.narrative_fluency * EVALUATION_WEIGHTS["narrative_fluency"])


class IterationFeedback(BaseModel):
    """迭代反馈"""
    dimension: str
    current_score: float
    issue: str
    suggestion: str
    target_agent: str  # 应该由哪个 Agent 改进


class VerificationResult(BaseModel):
    """校验结果"""
    claim: str
    status: VerificationStatus
    rag_evidence: Optional[str] = None
    kg_match: Optional[str] = None
    cross_source_agreement: Optional[bool] = None
    confidence: float
    notes: str = ""


class ScienceFacts(BaseModel):
    """科学理解 Agent 输出"""
    topic: str
    key_facts: List[str]
    entities: List[ScientificEntity]
    relations: List[ScientificRelation]
    timeline: List[dict] = Field(default_factory=list)
    data_sources: List[str] = Field(default_factory=list)


class ContextAnalysis(BaseModel):
    """语境分析 Agent 输出"""
    topic: str
    country_analysis: List[dict]  # 按国家分组的框架分析
    framework_distribution: dict  # 框架分布百分比
    sentiment_summary: dict  # 情感分析汇总
    key_narratives: List[str]  # 关键叙事点
    cross_cultural_differences: List[str]  # 跨文化差异


class HypothesisSet(BaseModel):
    """假设生成 Agent 输出"""
    topic: str
    hypotheses: List[Hypothesis]
    reasoning_chain: str  # Chain-of-Thought 推理过程
    hypothesis_count: int


class StrategySet(BaseModel):
    """策略转译 Agent 输出"""
    topic: str
    strategies: List[Strategy]
    audience_coverage: List[str]  # 覆盖的受众群体
    cultural_notes: List[str]  # 文化适配说明


class EvaluationResult(BaseModel):
    """评测迭代 Agent 输出"""
    scores: EvaluationScores
    weighted_total: float
    passed: bool
    feedback: List[IterationFeedback]
    experience_log: str  # 经验池记录
    audience_simulation: List[dict] = Field(default_factory=list)


class PipelineResult(BaseModel):
    """完整 Pipeline 输出"""
    topic: str
    timestamp: str
    science_facts: dict
    context_analysis: dict
    hypotheses: List[Hypothesis]
    verification_report: List[VerificationResult]
    strategies: List[Strategy]
    evaluation: EvaluationScores
    iteration_feedback: List[IterationFeedback]
    iteration_count: int
    final_status: str  # completed / max_iterations_reached / error
    search_sources: List[dict] = Field(default_factory=list)  # Tavily 搜索来源（含 URL）
