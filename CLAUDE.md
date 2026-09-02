# CLAUDE.md — Claude Code 工作指南（云观星传）

> Claude Code 专用速查。通用规则见 [AGENTS.md](./AGENTS.md)（两者保持一致，改一处同步另一处）。

## 项目

云观星传：AI Scientist 科技议题研究与国际传播辅助平台（挑战杯 XH-202619）。
后端 Python 3.11 + FastAPI + pydantic v2，前端 React，Docker 部署。

## 开工前

1. 读 `README.md`、`CONTRIBUTING.md`、`LABELS.md`
2. 熟悉仓库文档结构与约定后再动手

## 常用命令

```bash
python -m pytest tests/ -q                                # 全量测试（自包含，不调外部 API）
python -m pytest tests/test_workflow.py -k PaperWriter   # 改 schema 后的针对性验证
cd frontend && npm run build                              # 前端改动必验证
docker compose up --build                                 # 本地起全栈
```

## 硬规则

- **中文**：注释、提交信息、文档全中文；提交格式 `type(scope): 描述`（scope 必填）。
- **绝不 push main**：开 PR 合并，main 有分支保护（需 1 review）。
- **密钥零容忍**：`.env` / API Key 不入库、不进日志；环境变量注入。
- **schema 改动的伴生检查**：`src/schemas.py` 的模型常带「完整性强校验 + LLM 容错」双层逻辑（如 `PaperDraft` 缺摘要/结论会抛 `ValidationError`——这是论文截断防线，勿放宽）。改完跑 `tests/test_workflow.py` 全类。
- **修复流程**：先复现（新测试在旧代码上失败）→ 根因修复 → 回归转绿 → 全量 `pytest tests/ -q`。

## 文件地图速查

`src/agents/`（七阶段智能体）· `src/parliament/`（辩论引擎）· `src/workflow/`（流程编排）·
`src/verification/`（知识图谱+RAG 双校验）· `src/knowledge/`（图谱/向量库）· `src/search/`（联网搜索）·
`api/`（FastAPI）· `frontend/`（React）· `tests/`（自包含测试）

## 红线提醒

- `data/` 运行时数据不入库；`data/projects`、`data/experience.db` 已 gitignore。
- CI 要求覆盖率 ≥ 55%，push 前本地过一遍 `--cov-fail-under=55`。
- 比赛仓库规范：README 已重构为「项目讲解为主」，改动文档注意保持同一语气结构。