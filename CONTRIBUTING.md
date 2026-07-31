# 团队协作规范（云观星传）

> 🆕 还不会用 Git/GitHub？先看 [GitHub 协作入门指南](docs/github-guide.md)，从零开始手把手教学。
>
> 本规范面向所有在仓库里提交代码的成员。**改代码之前，请先读完这一页。**

---

## Git 工作流

### 分支策略

```
main  ← 主分支（所有代码最终合并到这里）
  ├─ feat/xxx      ← 新功能
  ├─ fix/xxx       ← 修复 bug
  ├─ docs/xxx      ← 文档
  ├─ data/xxx      ← 数据 / 语料 / 受众画像
  ├─ style/xxx     ← 前端样式、视觉
  └─ refactor/xxx  ← 重构
```

> **规则**：永远从 `main` 拉最新 → 创建自己的功能分支 → 完成后通过 Pull Request 合并回 `main`。
> **红线**：任何人都不直接 push 到 `main`（虽然目前没开保护，但这是团队纪律）。

### 提交信息规范

采用 Conventional Commits 格式：

```
<type>(<scope>): <description>
```

**type（必填）**：

| type | 含义 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修 bug |
| `docs` | 文档 |
| `data` | 数据、语料、受众画像 |
| `style` | 样式、UI、视觉 |
| `refactor` | 重构（行为不变） |
| `chore` | 杂项（构建、依赖、CI） |
| `test` | 测试 |

**scope（可选）**：`agents` / `pipeline` / `parliament` / `api` / `frontend` / `kg` / `data` / `docs` / `scripts`

**示例**：
```
feat(kg): 知识图谱增加连通分量分区浏览
fix(parliament): 修复辩论发言全文换行显示
data: 添加法国媒体嫦娥六号报道语料
docs: 更新项目文档导航
style(frontend): 调整星空背景动画
refactor(pipeline): 抽取验证层公共逻辑
```

> 描述用**中文**，一句话说清"做了什么"。历史提交没有 scope 是可以的，scope 只是锦上添花。

---

## 协作流程

### 日常开发（五步）

1. `git checkout main` → `git pull origin main`（拉最新）
2. `git checkout -b feat/xxx`（开功能分支）
3. 开发 + 提交（`git add` → `git commit`）
4. `git push origin feat/xxx` → 创建 Pull Request
5. **至少一人 Approve 后**合并回 `main`

### Pull Request 要求

- **标题**遵循提交信息规范：`<type>: <描述>`
- **描述**说清楚：做了什么、为什么这么做、怎么测试的
- **关联 Issue**：在描述第一行写 `Closes #编号`（如 `Closes #58`），合并后自动关闭 Issue
- **涉及 UI 改动**：附截图（贴进 PR 描述即可）
- **涉及数据改动**：说明数据来源
- **涉及 API Key / 敏感信息**：一律不提交，用 `.env`（已被 gitignore）
- **至少一人 Approve 后方可合并**

### Issue 规范

- 所有功能 / bug / 任务**先开 Issue** 登记，再动手
- 提 Issue 用仓库配好的模板（Bug 报告 / 功能请求），按字段填
- **动手前先 Assign 给自己**，避免两人重复做一件事
- 做完后 PR 里写 `Closes #xxx` 自动关闭

---

## 角色分工与交接约定

项目有三个方向，不同角色的产出物和交接接口如下：

### 📰 新闻传播方向（内容生产者）

**产出**（主要是数据，不需要写代码）：

| 产出 | 位置 | 说明 |
|------|------|------|
| 科学知识库 | `data/science/` | 议题背景、事实要点，JSON 文件 |
| 媒体语料 | `data/media/<国家>/reports.json` | 多语种报道原文/摘要（法、巴西等） |
| 受众画像 | `data/audience_profiles/` | 不同受众的认知背景、媒介习惯 |
| 提示词 | `config/prompts/*.txt` | 各 Agent 的 System Prompt，用自然语言调整 |

> 编辑 JSON / txt 用记事本或 VS Code 即可，**不需要学编程**。

### 💻 计算机 / AI 方向（代码与系统）

**产出**：`src/`（Agent、Pipeline、校验层）、`api/`（接口）、`frontend/`（界面）、`scripts/`（脚本）、`tests/`（测试）。

**职责**：
- 系统架构、多智能体协作、RAG + KG 校验
- API 集成、前端开发、部署
- 保证每个合并进 `main` 的改动**能跑**（`pytest` 通过、前端构建通过）

### 🎨 美术设计方向（视觉）

**产出**：`frontend/src/components/`、`frontend/src/pages/` 中的样式与可视化（星空背景、图表配色、页面布局）。

> 改动前端时尽量复用 `config/` 里的设计令牌，保持视觉一致性。

### 三方交接的通用规则

1. 每个方向的产出都在仓库里，**用 PR 合并**，不留私活
2. 交接时在 PR 描述里说明"我给了什么、你需要用什么"
3. 有疑问直接开 Issue 提，标注涉及模块
4. **不要改动不属于自己方向的文件**，除非已在 Issue 里说明并 Assign

---

## 本地开发

```bash
# 后端（Python + FastAPI）
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

# 前端（React + TypeScript + Vite）
cd frontend
npm install
npm run build
```

> 环境配置和 API Key 获取详见 [SETUP_GUIDE.md](SETUP_GUIDE.md)。

---

## 目录结构

```
yunGuanXingChuan/
├── README.md                   # 项目总览 + 文档导航（从这里开始读）
├── CONTRIBUTING.md             # 团队协作规范（本文件）
├── SETUP_GUIDE.md              # 环境配置与 API Key 获取
├── .github/                    # GitHub 模板与工作流
│   ├── ISSUE_TEMPLATE/         # Issue 模板（bug / 功能请求）
│   └── pull_request_template.md # PR 模板
│
├── src/                        # 💻 核心代码（计算机/AI 方向）
│   ├── agents/                 # 智能体（Science/Context/Hypothesis/Strategy/Evaluator/Humanist）
│   ├── parliament/             # 议会辩论引擎（debate_engine + speaker）
│   ├── pipeline.py             # 编排器
│   ├── verification/           # 校验层（RAG + KG + Wikidata + Wikipedia）
│   ├── knowledge/              # 知识层（向量库 / 知识图谱 / 经验池）
│   ├── search/                 # 搜索引擎（Tavily + 百炼 WebSearch）
│   └── evaluation.py           # 评测引擎
│
├── api/                        # 💻 FastAPI 后端接口
│   └── routes/                 # analyze / parliament / hypotheses / strategies / verify / knowledge_graph
│
├── frontend/                   # 💻🎨 React 前端
│   └── src/
│       ├── pages/              # Dashboard / TaskCenter / Parliament / KnowledgeGraph / ...
│       └── components/         # 星空背景等组件
│
├── config/                     # 📰 配置与提示词
│   ├── settings.py             # 全局配置（读 .env）
│   └── prompts/                # 各 Agent 的 System Prompt（文科同学主要编辑这里）
│
├── data/                       # 📰 数据（新闻传播方向主要编辑这里）
│   ├── science/                # 科学知识库
│   ├── media/                  # 多语种媒体语料
│   ├── audience_profiles/      # 受众画像
│   └── kg/                     # 知识图谱数据（运行时生成）
│
├── scripts/                    # 💻 工具脚本（demo / 构建索引 / 部署）
├── tests/                      # 💻 pytest 测试
└── docs/                       # 📚 文档（本目录）
```

> 💻 = 计算机/AI 方向 | 📰 = 新闻传播方向 | 🎨 = 美术设计方向 | 📚 = 所有人

---

## 检查清单（提交 PR 前）

- [ ] 已从 `main` 拉取最新代码
- [ ] 分支命名符合 `<type>/<描述>` 规范
- [ ] 提交信息符合 `<type>: <描述>` 规范
- [ ] `git status` 确认**没有** `.env`、`node_modules`、临时文件
- [ ] 改动能在本地跑起来（后端 `uvicorn` 能起、前端 `npm run build` 能过）
- [ ] 相关测试通过（`python -m pytest tests/`）
- [ ] PR 描述写明"做了什么 / 为什么 / 怎么测"
- [ ] 有对应 Issue 的话，PR 描述第一行写了 `Closes #编号`
- [ ] UI 改动已附截图
