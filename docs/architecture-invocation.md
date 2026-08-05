# 云观星传 — 智能体调用关系与完整流程

> 本文档描述系统当前的**智能体调用链路**。当前架构下存在两条调用链：
>
> - **主链路（前端主入口）**：科研工作台 → 7 阶段工作流（`WorkflowEngine`）
> - **后端保留能力**：认知议会（Parliament）+ Pipeline + 成果中心（Output Center），通过 API 直接调用

---

## 一、架构总览

```
                    ┌──────────────────────────────────────────────┐
                    │              前端（React SPA）                │
                    │  Workspace（科研工作台） + 7 个科研子页        │
                    └──────────────┬───────────────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
┌───────────────┐        ┌─────────────────┐        ┌─────────────────┐
│ /api/workflow │        │ /api/parliament │        │ /api/outputs    │
│ 7 阶段工作流   │        │ 认知议会（保留）  │        │ 成果中心（保留）  │
└───────┬───────┘        └────────┬────────┘        └────────┬────────┘
        │                         │                          │
        ▼                         ▼                          │
┌────────────────────────────────────────────────────┐       │
│               WorkflowEngine（src/workflow/）        │       │
│  7 阶段 Agent + RAG/KG 双校验 + 确认推进             │       │
└────────────────────────────────────────────────────┘       │
        │                                                     │
        └────────── 复用相同 Agent / 校验层 / 搜索 ─────────────┘
```

> 历史上前端主入口是 TaskCenter → Parliament（V2），**V3 起前端统一到 7 阶段科研工作台**。Parliament / Pipeline / 成果中心仍作为后端能力保留，`POST /api/parliament/convene`、`POST /api/analyze/run`、`POST /api/outputs/generate` 均可独立调用。

---

## 二、主链路：7 阶段科研工作流

### 2.1 前端入口

**文件**：`frontend/src/pages/Workspace.tsx`（工作台）、`frontend/src/components/ResearchPipeline.tsx`（阶段进度）

```
用户输入研究兴趣 → 新建项目（POST /api/workflow/projects）
  → 「一键生成全部」（POST /api/workflow/projects/{id}/run-all，后台串行 7 阶段）
  → 或逐阶段操作（run / approve / rerun / polish）
  → 前端轮询项目状态，展示各阶段产出物
```

工作台支持：项目列表/详情/删除（`DELETE /api/workflow/projects/{id}`，二次确认）、阶段产出物查看、重新生成（二次确认弹窗防误触覆盖）、导出（`GET /projects/{id}/export?fmt=md|json|word|pdf`）。

### 2.2 后端 Workflow 路由

**文件**：`api/routes/workflow.py`

| 端点 | 说明 |
|------|------|
| `GET /api/workflow/stages` | 阶段元数据（前端 Research Pipeline 渲染） |
| `POST /api/workflow/projects` | 创建研究项目 |
| `GET /api/workflow/projects` | 项目列表（按创建时间倒序） |
| `GET /api/workflow/projects/{id}` | 项目详情（阶段进度/产出物摘要） |
| `DELETE /api/workflow/projects/{id}` | 删除项目（物理移除项目文件与产出物） |
| `POST /api/workflow/projects/{id}/stages/{s}/run` | 执行阶段 s（同步，产出物落盘 awaiting_review） |
| `GET /api/workflow/projects/{id}/stages/{s}/result` | 获取阶段产出物 |
| `POST /api/workflow/projects/{id}/stages/{s}/approve` | 研究者确认，推进到下一阶段 |
| `POST /api/workflow/projects/{id}/run-all` | 一键全流程（后台串行 7 阶段） |
| `GET /api/workflow/projects/{id}/export?fmt=...` | 项目导出（md/json/word/pdf） |
| `POST /api/workflow/projects/{id}/stages/{s}/polish` | 章节 AI 润色（仅学术写作阶段） |
| `GET /api/workflow/hot-topics` | 今日科技热点（工作台驾驶舱） |

### 2.3 WorkflowEngine 内部执行顺序

**文件**：`src/workflow/engine.py`

```
WorkflowEngine.run_stage(project_id, stage, inputs)
  │
  ├─ 1. 注入该阶段知识库检索上下文（engine.py:293-389）
  │     按 stages.py 的 STAGE_META[stage]["library"] 检索四库：
  │     文献库 / 理论库 / 顶刊论文库 / 方法库
  ├─ 2. 调对应 Agent 生成（阶段 → Agent 映射见 stages.py）
  ├─ 3. RAG + KG 双校验产出物（engine.py:467-538）
  │     RAG 向量校验 + 知识图谱校验，校验异常自动容错重试
  ├─ 4. 产出物落盘为 awaiting_review，写运行历史
  └─ 5. 研究者 approve 后解锁下一阶段（engine.py:167）

WorkflowEngine.run_all(project_id)（engine.py:193-271）
  └─ 后台任务串行执行 1→7 阶段，跳过已 confirmed 的阶段
```

### 2.4 七阶段与 Agent 映射

**文件**：`src/workflow/stages.py`

| 阶段 | key | Agent | 注入知识库 | 产出 Schema |
|------|-----|-------|-----------|-------------|
| ① 选题孵化 | `inspiration` | `research_inspiration_agent` | 文献库、理论库 | `InspirationResult` |
| ② 文献综述 | `literature` | `literature_review_agent` | 文献库、理论库 | `LiteratureReview` |
| ③ 研究设计 | `design` | `research_question_agent` | 顶刊论文库 | `ResearchDesignResult` |
| ④ 方法推荐 | `method` | `method_advisor_agent` | 方法库、顶刊论文库 | `MethodRecommendationResult` |
| ⑤ 数据分析 | `data-analysis` | `data_analysis_agent` | 方法库 | `AnalysisResult` |
| ⑥ 学术写作 | `writing` | `paper_writer_agent` | 顶刊论文库 | `PaperDraft` |
| ⑦ 同行评审 | `review` | `reviewer_simulator_agent` | 顶刊论文库 | `ReviewerFeedback` |

> 各阶段执行统一走 `base_agent`（LLM 调用 / JSON 修复 / 重试 / Tool Use），产出物 LLM 格式漂移均有归一化容错（如评审 `suggestions`、方法推荐 `representative_papers` 对象列表归一化）。

---

## 三、后端能力一：认知议会（Parliament）包裹 Pipeline

> 以下链路仍然可用（`POST /api/parliament/convene`），但**不再是前端主入口**。

```
用户输入议题
      │
      ▼
┌─────────────────────────────────────┐
│  CognitiveParliament.convene()      │
│                                     │
│  ① 开幕（Scientist + Humanist）      │
│  ② 多轮辩论 + 加权投票               │
│  ③ 调用 Pipeline.run_with_motions() │
│  ④ 策略整合                          │
│  ⑤ 闭幕总结 + 最终报告                │
└─────────────────────────────────────┘
```

### 3.1 调用链速查

```
POST /api/parliament/convene                    [api/routes/parliament.py:283]
  └─ run_parliament_task()                      [api/routes/parliament.py:232]
     └─ CognitiveParliament.convene(topic)      [src/pipeline.py:760]
        ├─ debate_engine.open_parliament()      [src/parliament/debate_engine.py:77]
        │   ├─ ScienceAgent.run(task_type="opening_report")
        │   └─ HumanistAgent.run(task_type="opening_report")
        ├─ while not should_close():            [src/parliament/debate_engine.py:508]
        │   └─ debate_engine.debate_round()     [src/parliament/debate_engine.py:188]
        │       ├─ SpeakerAgent.plan_round()
        │       ├─ 联网搜索（统一搜索：Tavily + 百炼 WebSearch + 他山）
        │       ├─ for speaker in next_speakers:
        │       │   └─ agent.run(task_type="debate_speech")
        │       └─ vote_on_motion() → 僵持由 Speaker 裁定
        ├─ Pipeline.run_with_motions()          [src/pipeline.py:298]
        │   ├─ 联网搜索
        │   ├─ CrossValidator 四路校验（RAG + KG + Wikidata + Wikipedia）
        │   └─ for round in range(max_pipeline_rounds):
        │       ├─ StrategyAgent.run()  → 生成策略
        │       └─ EvaluatorAgent.run() → 五维评分（≥75 通过，否则迭代）
        ├─ StrategyAgent.run() → 最终策略整合
        ├─ SpeakerAgent.close_parliament()      [src/parliament/debate_engine.py:468]
        └─ LLM → 结构化最终报告
```

### 3.2 辩论循环详解（`debate_round()`, debate_engine.py:188）

```
┌────────────────────────────────────────────┐
│ Speaker.plan_round()                       │
│ → 决定本轮讨论主题 / 发言者(2-4人) / 投票权重 │
│ → 决定表决哪个动议                          │
├────────────────────────────────────────────┤
│ 联网搜索（统一搜索：Tavily + 百炼 + 他山）     │
├────────────────────────────────────────────┤
│ 顺序发言（for speaker_name in next_speakers）│
│   agent.run({ task_type: "debate_speech", … })│
│   → 返回 { stance, content, references }    │
│   → 相似度检查（bigram 重叠>0.8 标记"重述"）  │
├────────────────────────────────────────────┤
│ 投票表决 vote_on_motion()                   │
│   每个 Agent 独立投票 → 加权计算 → 判定结果    │
│   → 僵持 → Speaker 裁定 → 记录少数派意见      │
└────────────────────────────────────────────┘
```

### 3.3 Agent 辩论中的角色转换

| Agent 类 | Pipeline 角色 | 辩论角色 | 发言风格 |
|----------|-------------|---------|---------|
| ScienceAgent | 科学事实提取者 | **Scientist** 科学专家 | 从证据角度评价动议 |
| HypothesisAgent | 假设生成者 | **Skeptic** 质疑者 | 强制找漏洞（至少1个），温度 0.5 |
| HumanistAgent | （不参与 Pipeline） | **Humanist** 人文学者 | 文化风险审查，温度 0.5 |
| StrategyAgent | 策略转译师 | **Strategist** 策略师 | 可操作性评估 |
| EvaluatorAgent | 评测员 | **Evaluator** 评估者 | 五维标准独立评估 |
| ContextAgent | 语境分析师 | **不参与辩论** | — |

### 3.4 动态投票权重（speaker.py）

| 讨论类型 | Scientist | Skeptic | Humanist | Strategist | Evaluator |
|---------|-----------|---------|----------|------------|-----------|
| 事实讨论 | **0.40** | 0.25 | 0.10 | 0.10 | 0.15 |
| 文化适配 | 0.10 | 0.15 | **0.40** | 0.20 | 0.15 |
| 策略可行性 | 0.10 | 0.15 | 0.15 | **0.35** | 0.25 |
| 方法论 | 0.25 | **0.35** | 0.10 | 0.10 | 0.20 |

### 3.5 run_with_motions() 与 run() 的对比

| 对比维度 | `Pipeline.run()` | `Pipeline.run_with_motions()` |
|---------|------------------|------------------------------|
| 谁来调用 | API `/analyze/run`（独立使用） | `CognitiveParliament.convene()` |
| Step 0: 搜索 | ✅ | ✅ |
| Step 1: 科学理解 | ✅ | ❌ **跳过**（动议已替代假设） |
| Step 2: 语境分析 | ✅ | ❌ **跳过** |
| Step 3: 假设生成 | ✅ | ❌ **跳过**（动议 = 假设） |
| Step 4: 校验 | ✅ | ✅ |
| Step 5-7: 策略+评测+迭代 | ✅ | ✅ |
| 少数派意见注入 | 无 | ✅ |
| 辩论摘要注入 | 无 | ✅ |

---

## 四、后端能力二：成果中心（Output Center）

Parliament / Pipeline / Workflow 运行完成后，原始结果可通过**统一的成果接口**加工为标准化的「科研成果 + 传播成果」：

```
研究中间结果（科学事实、校验报告、策略集、工作台产出物）
                │
                ▼
     成果中心（Output Center）
       POST /api/outputs/generate
       ├── research_plan   研究计划（助研）
       ├── strategy_report 策略报告（助传）
       ├── paper_outline   论文大纲（助研）
       ├── press_release   新闻建议稿
       ├── science_script  科普脚本
       └── ...（按议题逐步填充）
                │
                ▼
    标准化成果文件（JSON 落盘 + 多格式导出 JSON/MD/HTML/PDF/Word/KG-PNG）
```

**关键点**：成果中心复用研究中间结果作为生成素材（`_load_source_material`），**不重复跑研究过程**，而是做面向交付的表达加工。这正是『助研 + 助传』双主线的落地。

---

## 五、统一搜索层

**文件**：`src/search/`（`unified_search.py` 为默认入口，`get_unified_search_service`）

```
统一搜索 UnifiedSearchService
  ├─ qwen_websearch.py   百炼 WebSearch MCP（需 DASHSCOPE_API_KEY）
  ├─ tavily_search.py    Tavily REST（需 TAVILY_API_KEY，可选 TAVILY_PROXY）
  └─ tashan_search.py    他山世界 TopicLab（需 TASHAN_TOKEN，可选）
      → 三引擎并行调用 → 结果合并去重 → 返回结构化引用
```

Pipeline、议会辩论、工作流阶段（engine.py:308-313, 580-586）全部走统一搜索。

---

## 六、一次完整运行的 LLM 调用次数估算（议会模式）

以默认参数（5 轮辩论 + 3 轮 Pipeline 评测）为例：

| 阶段 | 调用次数 | 明细 |
|------|---------|------|
| 开幕 | 2 | Scientist + Humanist 各 1 次 |
| 辩论（每轮） | 7-9 | Speaker 1 次 + 2-4 个发言者 + 5 个投票 |
| 辩论总计（按 5 轮） | 35-45 | |
| Pipeline 校验 | 4-6 | 取决于断言数量 |
| Pipeline 策略+评测（每轮） | 2 | StrategyAgent + EvaluatorAgent |
| Pipeline 总计（按 2 轮通过） | 6-10 | |
| 策略整合 | 1 | |
| 闭幕+最终报告 | 2 | Speaker 总结 + LLM 结构化报告 |
| **总计** | **约 46-64 次 LLM 调用** | |

> 对比：7 阶段工作台模式每次只调 1 个阶段 Agent（+双校验），成本远低于议会全流程，这也是前端主入口迁移到工作台的原因之一。

---

## 七、经验池的当前覆盖范围

```
Pipeline 评测每轮完成后:
  EvaluationEngine.log_experience()
    ├─ 写入内存 pool（会话级）
    └─ 写入 SQLite experience_store
         ├─ experiences 表：五维评分 + 低分维度 + 反馈
         └─ topic_embeddings 表：议题 embedding（相似议题检索）

下次处理相似议题时:
  EvaluationEngine.load_past_experience(topic)
    ├─ 相似议题检索（embedding 余弦相似度）
    ├─ 常见弱点统计
    └─ 全局改进趋势
```

**当前局限性**：经验池只记录 Pipeline 评测层的经验（评分数据），**不记录辩论层的经验**。

---

## 八、关键文件索引

| 模块 | 文件 |
|------|------|
| 工作流引擎 | `src/workflow/engine.py`、`src/workflow/stages.py`、`src/workflow/project.py` |
| 工作流 API | `api/routes/workflow.py` |
| 议会引擎 | `src/parliament/debate_engine.py`、`src/parliament/speaker.py` |
| 编排器 | `src/pipeline.py`（`run()` / `run_with_motions()` / `CognitiveParliament.convene()`） |
| 校验层 | `src/verification/`（rag_checker / kg_checker / cross_validator / external_validator / report_generator） |
| 知识层 | `src/knowledge/`（libraries / vector_store / kg_builder / wikidata_enricher / preprocessor / experience_store） |
| 搜索层 | `src/search/`（unified_search / qwen_websearch / tavily_search / tashan_search） |
| 成果中心 | `api/routes/outputs.py`、`src/export_service.py` |
| Agent 基类 | `src/agents/base_agent.py`（LLM 调用 / JSON 修复 / 重试 / Tool Use） |

---

*最后更新：2026-08-05*
