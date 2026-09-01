# AGENTS.md — AI 编程代理工作指南（云观星传）

> 给在仓库里工作的 AI 编程代理（Claude Code / Cursor / Copilot / OpenClaw 等）的根级规则。
> 电报风格，只写硬规则。开工前先读：`README.md`、`CONTRIBUTING.md`、`LABELS.md`。

## 项目一句话

云观星传 = AI Scientist 科技议题研究与国际传播辅助平台（挑战杯揭榜挂帅擂台赛 XH-202619）。
七阶段科研工作台：选题孵化 → 文献综述 → 研究设计 → 方法推荐 → 数据分析 → 学术写作 → 同行评审。
后端 Python 3.11 + FastAPI + pydantic v2，前端 React（`frontend/`，含 admin 版），Docker 多阶段构建。

## 常用命令

```bash
pip install -r requirements.txt        # 后端依赖
python -m pytest tests/ -q             # 全量测试（573+ 用例，自包含，不依赖外部 API）
python -m pytest tests/ --cov=src --cov=api --cov-fail-under=55   # 含覆盖率门槛
cd frontend && npm install && npm run build   # 前端构建（涉及前端改动时必须验证）
docker compose up --build              # 本地起全栈（镜像内自动构建前端）
```

## 硬规则

1. **中文优先**：代码注释、提交信息、Issue/PR 一律中文；标识符用英文。
2. **提交格式**：Conventional Commits，scope 必填 —— `fix(schema): 描述`。示例见 CONTRIBUTING.md。
3. **绝不 push main**：只能开 PR 合并（main 有分支保护，要求 1 个 review）。
4. **密钥零容忍**：`.env`、API Key 绝不入库、绝不打进日志/评论；用环境变量注入。
5. **标签体系**：Issue/PR 打标签先看 `LABELS.md`（优先级 P0-P3 / 规模 / 模块 / 影响 等维度）。
6. **数据勿扰**：`data/` 下用户项目库、知识库为运行时数据，`data/projects`、`data/experience.db` 等已 gitignore，不要提交。

## 修复准则（Bug 修复时）

- **根因修复优先**：读完整受影响模块（及其调用方、测试、文档）再动手，禁止只贴症状。
- **先复现后修复**：确认 bug 先用测试复现（新测试必须在修复前的代码上失败），修完跑同一用例，必须转绿。
- **不硬编码样例**：不要把报告里的示例文本/错误信息硬编码进生产代码。
- **容错边界**：本仓库大量 `LLM 格式漂移容错`（见 schemas.py 的 field/model validators）——新增校验前先确认不会误伤容错路径。

## 文件地图

| 路径 | 内容 |
|---|---|
| `src/agents/` | 七个阶段智能体（选题/综述/设计/方法/分析/写手/评审），继承 `BaseAgent` |
| `src/parliament/` | 议会辩论引擎（多学者模拟讨论） |
| `src/pipeline.py`、`src/workflow/` | 流程编排与工作流引擎（含自动迭代闭环） |
| `src/verification/` | 校验层（RAG + 知识图谱双校验，外部三路交叉验证） |
| `src/knowledge/` | 知识图谱 / 向量库 / 语料加载（faiss + networkx） |
| `src/search/` | 联网搜索（Qwen WebSearch / Tashan / Tavily 统一入口） |
| `src/schemas.py` | 全链路 pydantic 模型 + LLM 格式漂移容错（改这里务必跑 `tests/test_workflow.py`） |
| `api/` | FastAPI 后端接口 |
| `frontend/` | React 前端（普通版 + admin 版） |
| `tests/` | pytest 全量测试（自包含 fixture，不调 LLM/网络） |

## 已知坑

- `PaperDraft` 等 schema 有「完整性 + 容错」双层校验：缺「摘要/结论」会抛 `ValidationError` 触发重试（论文截断防线），这是**有意设计**，别放宽。
- CI（`.github/workflows/test.yml`）跑全量 573+ 用例 + 覆盖率门槛 55%，push 前本地先过一遍。
- tests 里 PDF/Word 导出用例依赖中文字体，容器/CI 已装 `fonts-noto-cjk`。