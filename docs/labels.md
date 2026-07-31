# Issue / PR 标签规范

> 标签用来快速给 Issue 和 PR 分类：一眼看出"这是什么事、属于哪个模块、优先级多高"。
> 提 Issue、开 PR 时，勾上合适的标签，能帮队友快速分流。

---

## 一、类型标签（这个任务属于什么性质）

| 标签 | 颜色建议 | 什么时候用 |
|------|---------|-----------|
| `bug` | 🟥 `d73a4a` | 程序行为不对，需要修复 |
| `enhancement` | 🟩 `a2eeef` | 新功能、新能力 |
| `docs` | 🟦 `0075ca` | 文档相关 |
| `data` | 🟨 `e4e669` | 数据、语料、受众画像相关 |
| `question` | 🟪 `d876e3` | 疑问、求助，不是任务 |
| `refactor` | 🟫 `7057ff` | 重构，不改行为 |
| `chore` | ⬜ `c5def5` | 杂项（构建、依赖、CI） |
| `good first issue` | 🟩 `7057ff` | 适合新手练手的任务 |

## 二、模块标签（涉及项目的哪部分）

| 标签 | 说明 |
|------|------|
| `module: agents` | 智能体 Agent 相关（`src/agents/`） |
| `module: parliament` | 议会辩论引擎（`src/parliament/`） |
| `module: pipeline` | 流程编排（`src/pipeline.py`） |
| `module: verification` | 校验层（RAG / KG / Wikidata） |
| `module: api` | 后端接口（`api/`） |
| `module: frontend` | 前端界面（`frontend/`） |
| `module: knowledge` | 知识图谱 / 向量库 / 数据加载（`src/knowledge/`） |
| `module: deploy` | 部署、Docker、NAS（`docker-compose.yml` / `scripts/`） |

## 三、优先级标签

| 标签 | 含义 | 建议处理时限 |
|------|------|-------------|
| `priority: high` | 阻塞开发 / 影响演示 | 尽快（当天） |
| `priority: medium` | 正常任务 | 本周内 |
| `priority: low` | 不紧急、可后置 | 有时间再做 |

> ⚠️ `priority: high` 别滥用——每件事都是"紧急"就等于没有紧急。

---

## 使用建议

1. **每个 Issue / PR 至少一个类型标签 + 一个模块标签**，如 `bug` + `module: frontend`
2. 新手任务打 `good first issue`，方便新人快速上手
3. 标签不够用 → 开一个 Issue 建议新标签，由维护者统一添加
4. 状态（谁在做、做完了）用 **Assignees** 和 **PR 关联**表达，不靠标签

---

## 需要先在 GitHub 上创建的标签

首次使用请管理员（有仓库权限的人）在 GitHub 仓库 **Settings → Labels** 里按上表创建（大部分常见标签 GitHub 已内置，比如 `bug`、`enhancement`、`question`、`good first issue`，只需补 `data`、`refactor`、`chore` 和 `module:*`、`priority:*` 系列）。

---

*最后更新：2026-07-31*
