"""
云观星传 - 核心数据 Schema（Pydantic）
所有 Agent 间通信必须使用这些结构化 Schema
"""
from pydantic import BaseModel, Field, field_validator, model_validator, BeforeValidator
from typing import Dict, List, Optional, Annotated
from enum import Enum
import json
import re


def _normalize_str_list(v):
    """LLM 格式漂移容错：字符串数组中出现对象时，提取最可读的文本键归一为字符串。

    实测高发场景（均为对象列表而非字符串列表）：
    - 评审 suggestions: {"problem": "..."} → 提取 problem
    - 方法推荐 representative_papers: {"title": "..."} → 提取 title
    - 选题 reasons/keywords、Gap missing_perspectives 等同理
    """
    if not isinstance(v, list):
        return []
    out = []
    for item in v:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = (
                item.get("title") or item.get("text") or item.get("name")
                or item.get("suggestion") or item.get("problem") or item.get("content")
                or item.get("reason") or item.get("keyword") or item.get("step")
                or item.get("issue") or item.get("paper") or ""
            )
            if not text and item:
                text = json.dumps(item, ensure_ascii=False)
            text = str(text).strip()
        else:
            text = str(item).strip()
        if text:
            out.append(text)
    return out


# 通用字符串列表类型：由 LLM 直接产出的 List[str] 字段统一用它，防格式漂移
StrList = Annotated[List[str], BeforeValidator(_normalize_str_list)]


def _wrap_list_root(data, field: str):
    """LLM 格式漂移容错：结果对象被直接输出为数组（未包成 {field: [...]} 对象）时，
    自动包装进指定列表字段。实测高发：方法推荐/文献综述等 Agent 把整个结果写成数组"""
    if isinstance(data, list):
        return {field: data}
    return data


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


# ==========================================================================
# 认知议会 (Cognitive Parliament) 相关 Schema
# ==========================================================================


class MotionType(str, Enum):
    """议案类型"""
    FACT_CLAIM = "fact_claim"         # 事实性断言
    HYPOTHESIS = "hypothesis"         # 传播假设
    STRATEGY_PROPOSAL = "strategy"    # 策略建议
    METHODOLOGY = "methodology"       # 方法论问题


class Motion(BaseModel):
    """议会动议/提案"""
    motion_id: str                    # M001, M002...
    motion_type: MotionType
    proposer: str                     # 提案 Agent 名: "scientist"/"context"等
    content: str                      # 提案全文
    supporting_evidence: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class Speech(BaseModel):
    """一次发言"""
    speaker: str                      # "scientist"/"humanist"/"strategist"...
    round_num: int
    content: str
    stance: str                       # "support"/"oppose"/"amend"/"question"/"clarify"
    references: List[str] = Field(default_factory=list)


class DebateRound(BaseModel):
    """一轮辩论"""
    round_id: int
    topic: str                        # 当前轮核心议题
    speeches: List[Speech] = Field(default_factory=list)
    speaker_weights: Dict[str, float] = Field(default_factory=dict)
    speaker_rationale: str = ""       # Speaker为什么这样分配权重


class VoteResult(BaseModel):
    """投票结果"""
    motion_id: str
    votes: Dict[str, str] = Field(default_factory=dict)  # {agent_name: "yes"/"no"/"abstain"}
    weighted_yes: float = 0.0         # 加权赞成票总和（0-1）
    weighted_no: float = 0.0          # 加权反对票总和（0-1）
    result: str = "pending"           # "passed"/"rejected"/"amended"/"deadlocked"
    minority_opinions: List[str] = Field(default_factory=list)
    speaker_ruling: str = ""          # 议长裁决（僵持时）


class MinorityOpinion(BaseModel):
    """少数派意见"""
    agent: str
    motion_id: str
    objection: str                    # 反对理由
    alternative_proposal: str = ""    # 替代方案
    why_overruled: str = ""           # 为什么多数派仍否决（由Speaker记录）


class DeliberationTranscript(BaseModel):
    """完整辩论记录"""
    topic: str
    total_rounds: int = 0
    rounds: List[DebateRound] = Field(default_factory=list)
    motions: List[Motion] = Field(default_factory=list)
    votes: List[VoteResult] = Field(default_factory=list)
    minority_opinions: List[MinorityOpinion] = Field(default_factory=list)
    final_strategies: dict = Field(default_factory=dict)
    final_report: dict = Field(default_factory=dict)  # 结构化最终总结报告（核心结论/TOP3策略/风险/受众建议）
    started_at: str = ""              # ISO时间
    completed_at: str = ""            # ISO时间


# ==========================================================================
# 成果生成 (Research Output) 相关 Schema
# ==========================================================================


class ResearchPlan(BaseModel):
    """科学假设与研究计划生成器输出（AI Scientist 核心，助研而非代写）"""
    topic: str                                # 研究主题
    research_background: str                  # 研究背景
    existing_research: List[str] = Field(default_factory=list)   # 已有研究
    research_gap: str                         # 研究空白
    scientific_hypotheses: List[str] = Field(default_factory=list)  # AI提出的科学假设
    suggested_methods: List[str] = Field(default_factory=list)     # 建议研究方法
    suggested_data_sources: List[str] = Field(default_factory=list)  # 建议数据来源
    experiment_steps: List[str] = Field(default_factory=list)       # 建议实验步骤
    feasibility_analysis: str                 # 可行性分析
    evidence_sources: List[str] = Field(default_factory=list)  # 引用校验来源（三库证据）
    note: str = ""                            # 助研说明（非代写声明）


class SceneShot(BaseModel):
    """科普视频脚本中的单个镜头"""
    scene_no: int = 0                    # 第几镜头
    scene_description: str               # 画面/镜头描述
    duration_seconds: int = 0            # 建议时长（秒）
    caption: str = ""                   # 字幕（屏幕文字）
    narration: str = ""                 # 旁白（口播文案）
    visual_suggestion: str = ""         # 配图/画面建议


class ScienceScript(BaseModel):
    """科普视频脚本生成器输出（多平台）"""
    topic: str                                # 科普主题
    platform: str                             # 目标平台（短视频/公众号/微博/B站/小红书）
    title: str                                # 建议标题
    opening_hook: str = ""                    # 开场钩子（前3秒抓住注意力）
    shots: List[SceneShot] = Field(default_factory=list)   # 分镜列表（第一镜头、第二镜头...）
    bgm_suggestion: str = ""                  # BGM 建议
    hashtags: List[str] = Field(default_factory=list)      # 话题标签
    author_notes: str = ""                    # 发布/运营提示（贴合平台风格）
    evidence_sources: List[str] = Field(default_factory=list)  # 依据的科学事实来源


class TermPair(BaseModel):
    """中英对照术语对"""
    chinese: str                              # 中文术语
    english: str                              # 英文对应
    context: str = ""                         # 适用语境/媒体说明


class MetaphorPair(BaseModel):
    """中英对照隐喻/表达对"""
    chinese: str                              # 中文表达/隐喻
    english: str                              # 英文对应表达
    note: str = ""                            # 使用建议/注意事项


class ExpressionSuggestion(BaseModel):
    """表达适配建议（场景化）"""
    scenario: str                             # 场景/媒体类型（如“欧美媒体”“国际期刊”）
    recommended: str                          # 推荐表达
    avoid: str = ""                           # 不建议使用的表达
    reason: str = ""                          # 原因说明


class ExpressionAdaptation(BaseModel):
    """表达适配建议生成器输出（中英对照术语/隐喻/表达建议）"""
    topic: str                                # 议题
    terms: List[TermPair] = Field(default_factory=list)            # 术语对照
    metaphors: List[MetaphorPair] = Field(default_factory=list)    # 隐喻/表达对照
    suggestions: List[ExpressionSuggestion] = Field(default_factory=list)  # 场景化表达建议
    evidence_sources: List[str] = Field(default_factory=list)      # 引用来源
    note: str = ""                            # 说明（传播学视角）


class MediaRecommendation(BaseModel):
    """推荐的媒体与标题建议"""
    media: str
    reason: str = ""


class CommunicationStrategyReport(BaseModel):
    """国际传播策略报告生成器输出"""
    topic: str                                # 议题
    target_countries: List[str] = Field(default_factory=list)       # 目标国家
    target_audiences: List[str] = Field(default_factory=list)       # 目标受众
    communication_goals: List[str] = Field(default_factory=list)    # 传播目标
    narrative_frameworks: List[str] = Field(default_factory=list)   # 叙事框架
    recommended_media: List[MediaRecommendation] = Field(default_factory=list)  # 推荐媒体
    recommended_titles: List[str] = Field(default_factory=list)     # 推荐标题
    keywords: List[str] = Field(default_factory=list)               # 关键词
    risk_warnings: List[str] = Field(default_factory=list)          # 风险提醒
    china_media_differences: List[str] = Field(default_factory=list)  # 中外媒体差异（结合 Context Agent 框架分析）
    evidence_sources: List[str] = Field(default_factory=list)       # 引用来源


class PressReleaseDraft(BaseModel):
    """新闻传播建议稿生成器输出（助传定位：建议稿，非 AI 代写新闻）"""
    topic: str                                # 议题
    communication_goals: List[str] = Field(default_factory=list)    # 传播目标
    recommended_titles: List[str] = Field(default_factory=list)     # 推荐标题
    lead_suggestions: List[str] = Field(default_factory=list)       # 导语建议
    body_framework: List[str] = Field(default_factory=list)         # 正文框架
    interview_subjects: List[str] = Field(default_factory=list)     # 推荐采访对象
    image_suggestions: List[str] = Field(default_factory=list)      # 配图建议
    platform_suggestions: List[str] = Field(default_factory=list)   # 传播平台建议
    evidence_sources: List[str] = Field(default_factory=list)       # 引用来源
    note: str = ""                            # 助传说明


class PaperOutline(BaseModel):
    """论文大纲生成器输出（助研定位：仅框架与要点提示，不含正文）"""
    topic: str                                # 研究主题
    paper_title: str = ""                     # Title（用 paper_title 避免与前端 title 过滤冲突）
    abstract_framework: str = ""              # Abstract 框架+要点
    introduction_framework: str = ""          # Introduction 框架+要点
    literature_review_framework: str = ""     # Literature Review 框架+要点
    method_framework: str = ""                # Method 框架+要点
    result_framework: str = ""                # Result 框架+要点
    discussion_framework: str = ""            # Discussion 框架+要点
    future_work_framework: str = ""           # Future Work 框架+要点
    research_questions: List[str] = Field(default_factory=list)     # 研究问题/创新点
    evidence_sources: List[str] = Field(default_factory=list)       # 引用来源
    note: str = ""                            # 助研说明


class KGNodeStat(BaseModel):
    """图谱节点统计（热点节点/关键人物/机构共用）"""
    name: str
    type: str = ""
    degree: int = 0
    top_relation: str = ""


class KGRelation(BaseModel):
    """图谱关系三元组（含证据来源）"""
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0
    source: str = ""


class KGReport(BaseModel):
    """知识图谱报告生成器输出（数据驱动：从知识图谱统计组装）"""
    topic: str                                # 主题
    kg_summary: str = ""                      # 知识图谱总览（一段话）
    hot_nodes: List[KGNodeStat] = Field(default_factory=list)       # 热点节点
    key_persons: List[KGNodeStat] = Field(default_factory=list)     # 关键人物
    organizations: List[KGNodeStat] = Field(default_factory=list)   # 机构
    relations: List[KGRelation] = Field(default_factory=list)       # 关系（围绕 topic）
    evidence_sources: List[str] = Field(default_factory=list)       # 证据来源（可追溯）
    note: str = ""                            # 说明


# ============================================================================
# 科研流程工作流（AI Scientist Workflow）—— 7 智能体体系
# 对应《智能体.docx》：①选题孵化 → ②文献综述 → ③研究设计 → ④方法推荐
#               → ⑤数据分析 → ⑥论文写作 → ⑦评审修改
# ============================================================================


class TopicDirection(BaseModel):
    """选题方向建议（①选题孵化器输出项）"""
    title: str                                # 方向标题
    summary: str = ""                         # 方向简介
    research_value: int = Field(ge=0, le=100, default=0)        # 研究价值评分
    existing_coverage: int = Field(ge=0, le=100, default=0)     # 既有研究覆盖度
    innovation_potential: int = Field(ge=0, le=100, default=0)  # 创新潜力评分
    reasons: StrList = Field(default_factory=list)            # 推荐理由
    keywords: StrList = Field(default_factory=list)           # 关键词


class InspirationResult(BaseModel):
    """①选题孵化器输出"""
    topic: str = ""  # 允许 LLM 漏填，由 WorkflowEngine 兜底补全
    directions: List[TopicDirection] = Field(default_factory=list)
    selected_direction: str = ""              # 用户选定方向（默认推荐第 1 个）
    discussion_summary: str = ""              # 多学者讨论纪要


    @model_validator(mode="before")
    @classmethod
    def _coerce_list_root(cls, data):
        """LLM 格式漂移容错：结果直接输出为数组时自动包装"""
        return _wrap_list_root(data, "directions")
class LiteratureSection(BaseModel):
    """文献综述章节（②文献综述助手输出项）"""
    theme: str                                # 主题（按主题/时间/方法论维度归类）
    content: str = ""


class ResearchGap(BaseModel):
    """研究空白（Gap）"""
    description: str = ""
    missing_perspectives: StrList = Field(default_factory=list)  # 未覆盖的视角/方法/对象
    suggestion: str = ""                      # 深入研究建议


class LiteratureReference(BaseModel):
    """文献引用条目"""
    title: str
    source: str = ""                          # 期刊/机构
    year: str = ""

    @field_validator("title", "source", "year", mode="before")
    @classmethod
    def _coerce_str(cls, v):
        """LLM 可能输出 int/float（如 year=2026），统一转字符串避免 schema 校验失败"""
        if v is None:
            return ""
        if isinstance(v, (int, float)):
            return str(v)
        return v

    @model_validator(mode="before")
    @classmethod
    def _coerce_plain_reference(cls, data):
        """LLM 格式漂移容错：整条引用输出为字符串 '《标题》/ 来源 / 年份' 时，
        自动拆解为结构化对象（实测高发：模型把 references 写成一串字符串而非 dict）"""
        if not isinstance(data, str):
            return data
        text = data.strip()
        if not text:
            return {}
        m = re.match(r'^《([^》]+)》\s*[/／]?\s*(.*)$', text, re.S)
        if m:
            title, rest = m.group(1).strip(), m.group(2).strip()
        else:
            title, rest = text, ""
        # 剩余部分拆「来源 / 年份」（来源可能含斜杠），年份优先识别 4 位数字
        parts = [x.strip() for x in re.split(r'[/／]', rest) if x.strip()]
        year = next((x for x in parts if re.fullmatch(r'\d{4}', x)), "")
        parts = [x for x in parts if x != year]
        source = parts[0] if parts else ""
        out = {"title": title}
        if source:
            out["source"] = source
        if year:
            out["year"] = year
        return out


class TheoryRelation(BaseModel):
    """理论关系（②文献综述输出项：理论关系图节点与连线，前端渲染）"""
    source: str = ""   # 理论 A
    relation: str = "" # 关系描述（如：承继自 / 互补 / 对比）
    target: str = ""   # 理论 B

    @model_validator(mode="before")
    @classmethod
    def _coerce_plain_relation(cls, data):
        """LLM 格式漂移容错：输出 'A 承继自 B' / 'A→B' / 'A：承继自 B' 等字符串时拆解"""
        if not isinstance(data, str):
            return data
        text = data.strip()
        if not text:
            return {}
        m = re.match(r'^(.+?)\s*(?:承继自|互补|对比|应用|关联|→|->|：|:)\s*(.+)$', text)
        if m:
            return {"source": m.group(1).strip(), "relation": re.search(r'承继自|互补|对比|应用|关联|→|->', text).group(0).replace('->', '→'), "target": m.group(2).strip()}
        return {"source": text}


class LiteratureReview(BaseModel):
    """②文献综述助手输出"""
    topic: str = ""  # 允许 LLM 漏填，由 WorkflowEngine 兜底补全
    sections: List[LiteratureSection] = Field(default_factory=list)
    research_gap: ResearchGap = Field(default_factory=ResearchGap)
    references: List[LiteratureReference] = Field(default_factory=list)
    theory_relations: List[TheoryRelation] = Field(default_factory=list)  # 理论关系图


    @model_validator(mode="before")
    @classmethod
    def _coerce_list_root(cls, data):
        """LLM 格式漂移容错：结果直接输出为数组时自动包装"""
        return _wrap_list_root(data, "sections")
class ResearchQuestion(BaseModel):
    """研究问题（RQ）"""
    id: str                                   # RQ1
    text: str


class ResearchHypothesis(BaseModel):
    """研究假设（H）"""
    id: str                                   # H1
    statement: str
    hypothesis_type: str = "quantitative"     # quantitative/qualitative


class QuestionQualityReport(BaseModel):
    """问题质量检验（对比顶刊论文范式）"""
    clarity: int = Field(ge=0, le=100, default=0)        # 清晰度
    innovativeness: int = Field(ge=0, le=100, default=0) # 创新性
    operability: int = Field(ge=0, le=100, default=0)    # 可操作性
    comments: List[str] = Field(default_factory=list)


class ResearchDesignResult(BaseModel):
    """③研究问题设计师输出"""
    topic: str = ""  # 允许 LLM 漏填，由 WorkflowEngine 兜底补全
    research_questions: List[ResearchQuestion] = Field(default_factory=list)
    hypotheses: List[ResearchHypothesis] = Field(default_factory=list)
    quality_report: QuestionQualityReport = Field(default_factory=QuestionQualityReport)


    @model_validator(mode="before")
    @classmethod
    def _coerce_list_root(cls, data):
        """LLM 格式漂移容错：结果直接输出为数组时自动包装"""
        return _wrap_list_root(data, "research_questions")
class MethodRecommendation(BaseModel):
    """研究方法推荐（④方法顾问输出项）"""
    name: str                                 # 方法名，如"内容分析"
    method_type: str = "quantitative"         # quantitative/qualitative/mixed
    fit_score: int = Field(ge=0, le=100, default=0)       # 方法适配度评分
    representative_papers: StrList = Field(default_factory=list)  # 范文/代表论文
    operation_steps: StrList = Field(default_factory=list)        # 操作步骤
    rationale: str = ""                       # 推荐理由


class MethodRecommendationResult(BaseModel):
    """④方法顾问输出"""
    topic: str = ""  # 允许 LLM 漏填，由 WorkflowEngine 兜底补全
    methods: List[MethodRecommendation] = Field(default_factory=list)


    @model_validator(mode="before")
    @classmethod
    def _coerce_list_root(cls, data):
        """LLM 格式漂移容错：结果直接输出为数组时自动包装"""
        return _wrap_list_root(data, "methods")
class AnalysisCodingCategory(BaseModel):
    """分析编码类目统计（⑤数据分析助手输出项）"""
    category: str
    count: int = 0


class AnalysisFinding(BaseModel):
    """分析发现"""
    finding: str
    evidence: str = ""
    confidence: float = Field(ge=0, le=1, default=0.5)


class SentimentDistribution(BaseModel):
    """情绪分布（⑤数据分析输出项：词云/情绪/框架/传播路径四图中的情绪分析）"""
    positive: float = Field(ge=0, le=100, default=0.0)
    neutral: float = Field(ge=0, le=100, default=0.0)
    negative: float = Field(ge=0, le=100, default=0.0)
    summary: str = ""  # 一句话情绪解读


class AnalysisResult(BaseModel):
    """⑤数据分析助手输出"""
    topic: str = ""  # 允许 LLM 漏填，由 WorkflowEngine 兜底补全
    analysis_type: str = "content_analysis"   # content_analysis/text_analysis/framework_analysis
    coding_table: List[AnalysisCodingCategory] = Field(default_factory=list)
    findings: List[AnalysisFinding] = Field(default_factory=list)
    sentiment: SentimentDistribution = Field(default_factory=SentimentDistribution)  # 情绪分析（四图之一）
    interpretation: str = ""                  # 初步解读


    @model_validator(mode="before")
    @classmethod
    def _coerce_list_root(cls, data):
        """LLM 格式漂移容错：结果直接输出为数组时自动包装"""
        return _wrap_list_root(data, "findings")
class PaperSection(BaseModel):
    """论文章节（⑥论文写手输出项）"""
    section: str                              # 摘要/引言/文献综述/方法/发现/讨论/结论
    content: str


class PaperDraft(BaseModel):
    """⑥论文写手输出"""
    topic: str = ""  # 允许 LLM 漏填，由 WorkflowEngine 兜底补全
    title: str = ""
    sections: List[PaperSection] = Field(default_factory=list)
    style_notes: List[str] = Field(default_factory=list)      # 风格蒸馏说明


    @field_validator("style_notes", mode="before")
    @classmethod
    def _coerce_style_notes(cls, v):
        """LLM 偶发把 style_notes 写成整段字符串（如 "1. ... 2. ..."）而非数组，
        按行拆分并去掉序号前缀，避免 schema 校验失败（实测 2026-08-26 paper_writer_agent）"""
        if isinstance(v, str):
            notes = [re.sub(r'^\s*\d+\s*[\.、．]\s*', '', ln.strip()) for ln in v.splitlines()]
            return [n for n in notes if n]
        return v

    @model_validator(mode="before")
    @classmethod
    def _coerce_list_root(cls, data):
        """LLM 格式漂移容错：结果直接输出为数组时自动包装"""
        return _wrap_list_root(data, "sections")
class ReviewerScores(BaseModel):
    """审稿人评分（⑦评审模拟器输出项）"""
    innovation: int = Field(ge=0, le=100, default=0)      # 创新性
    methodology: int = Field(ge=0, le=100, default=0)     # 方法规范性
    argumentation: int = Field(ge=0, le=100, default=0)   # 论证逻辑
    literature: int = Field(ge=0, le=100, default=0)      # 文献覆盖度
    language: int = Field(ge=0, le=100, default=0)        # 学术语言

    @field_validator("innovation", "methodology", "argumentation", "literature", "language", mode="before")
    @classmethod
    def _coerce_numeric(cls, v):
        """LLM 偶发输出浮点/字符串数值时归一为整数（防 Schema 校验失败）"""
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, (int, float)):
            return int(round(v))
        if isinstance(v, str):
            try:
                return int(round(float(v.strip())))
            except (TypeError, ValueError):
                return 0
        return v


class ReviewerOpinion(BaseModel):
    """单个审稿人意见"""
    reviewer_id: str                          # Reviewer 1
    perspective: str = ""                     # 方法专家/理论专家/实践专家
    scores: ReviewerScores = Field(default_factory=ReviewerScores)
    suggestions: List[str] = Field(default_factory=list)

    @field_validator("suggestions", mode="before")
    @classmethod
    def _normalize_suggestions(cls, v):
        """LLM 输出格式漂移容错：suggestions 应为字符串列表，
        若模型输出为对象列表（如 {"problem": "..."}）则提取文本键归一化，
        避免整阶段 Schema 校验失败。"""
        if not isinstance(v, list):
            return []
        out = []
        for item in v:
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = (
                    item.get("suggestion") or item.get("suggest") or item.get("text")
                    or item.get("issue") or item.get("problem") or item.get("content")
                    or ""
                )
                if not text and item:
                    text = json.dumps(item, ensure_ascii=False)
                text = str(text).strip()
            else:
                text = str(item).strip()
            if text:
                out.append(text)
        return out


class ReviewerFeedback(BaseModel):
    """⑦评审模拟器输出"""
    topic: str = ""  # 允许 LLM 漏填，由 WorkflowEngine 兜底补全
    reviewers: List[ReviewerOpinion] = Field(default_factory=list)
    revision_notes: str = ""                  # 一键修改说明

    @field_validator("revision_notes", mode="before")
    @classmethod
    def _normalize_revision_notes(cls, v):
        """revision_notes 偶发输出为对象时提取文本，防 Schema 校验失败"""
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            text = v.get("notes") or v.get("content") or v.get("text") or ""
            return str(text).strip() if text else json.dumps(v, ensure_ascii=False)
        if v is None:
            return ""
        return str(v)


class StageStatus(str, Enum):
    """工作流阶段状态"""
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"       # 产出物待研究者确认
    COMPLETED = "completed"
    FAILED = "failed"


class StageRecord(BaseModel):
    """单阶段记录"""
    stage: int
    status: StageStatus = StageStatus.PENDING
    output: Optional[Dict] = None             # 阶段产出物（对应阶段 Agent 输出 schema）
    error: Optional[str] = None
    run_count: int = 0
    updated_at: str = ""


class ResearchProject(BaseModel):
    """科研项目（工作流状态机持久化模型）"""
    id: str
    owner_id: Optional[str] = None             # 归属用户（None = 旧版无主项目，仅 admin 可见）
    title: str = ""
    interest: str = ""                        # 初始研究兴趣/议题
    current_stage: int = 1
    status: str = "active"                    # active/completed
    created_at: str = ""
    updated_at: str = ""
    stages: Dict[str, StageRecord] = Field(default_factory=dict)
    history: List[Dict] = Field(default_factory=list)  # [{stage, action, timestamp, summary}]
