# 云观星传 — AI Scientist 科技议题研究与国际传播辅助平台

> ✨ **让 AI 帮助科研，而不是替代科研；让知识不仅能被发现，更能被理解、验证与传播。**

> 🌟 **AI Scientist 范式**：假设生成 → 验证 → 迭代
> 🔍 **RAG + 知识图谱双校验**：确保科学事实准确性
> 📊 **方法学评审 + 自动迭代闭环**：数据分析后自动诊断、修订、重跑
> 🧩 **七阶段科研工作台**：选题孵化 → 文献综述 → 研究设计 → 方法推荐 → 数据分析 → 学术写作 → 同行评审
> 📦 **成果中心**：研究计划 / 策略报告 / 新闻建议稿 / 论文大纲 / 科普脚本 / KG 报告 / 表达适配，多格式导出（JSON/MD/HTML/PDF/Word/KG-PNG）

---

## 🌐 成品网站

> **👉 直接访问：https://yunguanxingchuan.xyz**（无需安装任何环境，打开即用）
>
> - **科研工作台**：输入一个科技议题，自动跑完 7 阶段科研流程
> - 支持任意议题（航天、科技、国际传播等），实时联网检索 + AI 全流程辅助
> - 管理后台：https://admin.yunguanxingchuan.xyz

---

## 📖 项目简介（给所有人看）

“云观星传”是一个 **AI Scientist 科技议题研究与国际传播辅助平台**，围绕 **『助研（Research Assistant）＋助传（Communication Assistant）』** 双主线：既帮助研究者完成科研（选题、文献、研究设计、方法推荐、数据分析、写作、评审），也服务传播工作（国际传播策略、新闻建议稿、科普脚本）。

### 它做什么？（一句话版）

**你输入一个科技议题（比如"中国空间站的海外多语种媒体报道与形象建构研究"），系统自动完成整个科研流程：**

1. **选题孵化** 💡 — 结合文献库与理论库，推荐 3-5 个研究方向（研究价值/覆盖度/创新潜力评分），模拟多学者讨论后选定方向
2. **文献综述** 📚 — 检索相关文献与理论，产出综述章节、研究空白（Gap）与理论关系图
3. **研究设计** 🎯 — 拆解研究问题（RQ）与假设（H），输出问题质量检验报告
4. **方法推荐** 🧪 — 匹配顶刊论文库中的研究方法，给出适配度评估与操作步骤
5. **数据分析** 📊 — 上传素材（报道文本/访谈/表格），执行内容/文本/框架分析，输出编码表、研究发现与情绪分布
6. **学术写作** ✍️ — 按顶刊风格生成论文草稿（摘要/引言/文献/方法/发现/讨论/结论），支持分章节 AI 润色
7. **同行评审** 🧑‍⚖️ — 模拟三位专家（方法/理论/实践）五维打分，输出修改建议与修订说明

**每个阶段产出物都经过 RAG + 知识图谱双校验**，并支持一键生成全部、任意阶段重新生成（二次确认防误触）、项目删除、多格式导出（MD/JSON/Word/PDF）。

### 为什么叫"云观星传"？

- **云** = 阿里云 / 云计算
- **观星** = 观测星空（航天、天文议题）
- **传** = 传播

---

## 🚀 核心亮点（为什么它不一样）

### 1. 不是"一次性生成"，而是「AI Scientist 自迭代闭环」

普通 AI 工具生成一次就完事；云观星传在**数据分析之后强制做一次方法学评审**：

```
数据分析 → LLM 方法论诊断（可信度 0~1 + 问题清单 + 定向路由）
   → 自动修订 研究设计 / 文献综述 / 方法 / 写作
   → 重跑数据分析 → 直到可信度达标 或 最多 3 轮
   → 收尾自动重新同行评审并确认
```

- 评审会指出「编码类目与 RQ 脱节」「结论无实证支撑属过度推断」「样本外推断」等真实的方法论缺陷
- 每轮修订持久化为**设计版本 V1→V2→V3…**，前端可展开迭代计数器回看每轮指标变化
- 实测案例：某案例经迭代后证据覆盖率 0.333 → 1.000，平均置信度 0.233 → 0.717

### 2. RAG + 知识图谱双校验，杜绝「编造」

每个阶段的每一条关键断言，都会检索本地知识库（RAG）与知识图谱（KG）逐条核对，输出 `verified / partial / unverified / conflicting` 四档状态与置信度；冲突断言提示人工审查，无法验证的断言明确标注。

### 3. 三引擎联网搜索，证据可点击溯源

阿里云百炼 WebSearch MCP + Tavily + 他山世界 TopicLab 三引擎并行检索、去重合并；每个阶段的检索来源随产出物返回前端，**可点击查看原文链接**（哪个阶段搜了什么一目了然）。

### 4. 多租户「自带钥匙」，安全可审计

平台不持有推理 Key：用户注册后在「⚙ 模型设置」填入自己的 Qwen 模型配置（API Key / BaseURL / 模型 ID），保存时自动验证连通性。开发全程使用 **Qwen3.8-Max Preview / Qwen3.8-Max**，平台兼容 Qwen 全系模型，支持用户自定义任意模型（qwen-plus / qwen-long 等）。

### 5. 简易部署：一个 Docker 命令上线

```bash
docker compose up -d --build
# 科研工作台 :8123 · 管理后台 :8124
```

---

## 🛠 技术栈

| 层级 | 技术 |
|------|------|
| 大模型 | 通义千问 Qwen（阿里云百炼 DashScope，开发全程 Qwen3.8-Max Preview / Qwen3.8-Max，兼容 Qwen 全系） |
| 向量检索 | FAISS + Qwen text-embedding 系列 |
| 知识图谱 | NetworkX + JSON（Wikidata 自动扩充） |
| 后端 | FastAPI + Pydantic + uvicorn |
| 前端 | React 18 + TypeScript + Vite + ECharts + Tailwind CSS |
| 搜索引擎 | 百炼 WebSearch MCP + Tavily + 他山世界 TopicLab（三引擎统一） |
| 部署 | Docker（docker-compose）+ Nginx |
| 视觉风格 | 他山世界学术风（衬线字体 + 低饱和青蓝 + 大留白 + 微动效） |

---

## 🧩 七阶段科研工作流详解

| 阶段 | Agent | 注入知识库 | 产出物 |
|------|-------|-----------|--------|
| ① 选题孵化 | `research_inspiration_agent` | 文献库、理论库 | 研究方向候选（含价值/覆盖/创新评分） |
| ② 文献综述 | `literature_review_agent` | 文献库、理论库 | 综述章节 + 研究 Gap + 理论关系图 |
| ③ 研究设计 | `research_question_agent` | 顶刊论文库 | 研究问题 RQ + 假设 H + 质量报告 |
| ④ 方法推荐 | `method_advisor_agent` | 方法库、顶刊论文库 | 方法推荐（适配度/理由/代表论文） |
| ⑤ 数据分析 | `data_analysis_agent` | 方法库 | 编码表 + 发现 + 情绪分布（词云/条形图/情绪环） |
| ⑥ 学术写作 | `paper_writer_agent` | 顶刊论文库 | 论文草稿（分章节，支持润色） |
| ⑦ 同行评审 | `reviewer_simulator_agent` | 顶刊论文库 | 三位审稿人意见 + 修订说明 |

> 阶段产出物统一落盘为 `awaiting_review`，研究者确认（approve）后解锁下一阶段；每个阶段执行前后做 RAG + KG 双校验。数据分析（S5）产出后自动追加**迭代记录**（指标 + AI 诊断建议），研究设计（S3）重新生成时**设计版本 +1**。

---

## 🦞 多智能体系统

### 科研工作流 Agent（7 阶段，前端主链路）

见上表，7 个 Agent 一一对应 7 个科研阶段，统一继承 `BaseAgent`（LLM 调用 / JSON Schema 校验 / 自动重试 / Tool Use）。

### 迭代方法学评审（闭环核心）

数据分析后由 Qwen 以「严格社会科学研究方法评审专家」身份，从 ①方法适配性 ②抽样与编码类目设计 ③结论-证据匹配度 ④论文呈现质量 四维评审，输出综合可信度（0~1）与问题清单（每条标注应去哪个页面修复），驱动自动迭代闭环。

### 核心分析 Agent（Pipeline / 议会，后端保留能力）

| Agent | 中文名 | 做什么 | 输出 |
|-------|--------|--------|------|
| Science Agent | 科学理解 | 从多语种报道中提取结构化科学事实、实体、关系、时间线 | `ScienceFacts` |
| Context Agent | 语境分析 | 分析各国媒体报道的框架（framing）、情感倾向、叙事差异 | `ContextAnalysis` |
| Hypothesis Agent | 假设生成 | 基于科学事实 + 语境分析，生成可验证的传播学假设 | `HypothesisSet` |
| Strategy Agent | 策略转译 | 针对不同受众生成具体传播策略 | `StrategySet` |
| Evaluator Agent | 评测迭代 | 五维评分 + 迭代反馈，驱动自改进闭环 | `EvaluationResult` |
| Humanist Agent | 人文审查 | 审查文化敏感性与伦理风险 | `CulturalReview` |

> 上述 Agent 供**认知议会（Parliament）**与 **Pipeline** 使用（`/api/parliament/*`、`/api/analyze/*`）；前端主流程已统一到 7 阶段科研工作台。完整调用链路见 **[docs/architecture-invocation.md](docs/architecture-invocation.md)**。

---

## 📊 五维评分矩阵

| 维度 | 权重 | 打分标准 |
|------|------|---------|
| **事实准确度** | 30% | 科学事实是否与 RAG/KG 校验结果一致 |
| **策略可操作性** | 25% | 建议是否具体可执行，含渠道、时间、人设 |
| **受众适配度** | 20% | 语调、渠道是否匹配目标受众 |
| **文化敏感性** | 15% | 是否避开文化禁忌、尊重当地价值观 |
| **叙事流畅度** | 10% | 文案是否自然、有感染力 |

---

## 🧑‍💻 本地开发运行（可选）

> 🌐 **想直接体验产品，不用装任何东西**——访问成品站 https://yunguanxingchuan.xyz 即可。
> 以下为**开发者**在本地跑代码的完整流程；详细指南见 **[SETUP_GUIDE.md](SETUP_GUIDE.md)**。

### 环境要求

| 软件 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | 运行后端 AI 程序 |
| Node.js | 18+（推荐 LTS） | 构建前端网页 |
| Docker（可选） | 最新 | 一键容器化部署 |

### 第一步：克隆代码

```bash
git clone https://github.com/programmingWTF/yunGuanXingChuan.git
cd yunGuanXingChuan
```

### 第二步：配置 API Key（关键）

```bash
cp .env.example .env
```

然后编辑 `.env`，填入你的 Key（**最少需要 QWEN_API_KEY**，与 DASHSCOPE_API_KEY 可用同一个）：

| Key | 作用 | 获取网站 |
|-----|------|---------|
| `QWEN_API_KEY` | 调用通义千问大模型 | [百炼控制台](https://bailian.console.aliyun.com/) |
| `DASHSCOPE_API_KEY` | 联网搜索能力 | 同上（可与 QWEN_API_KEY 共用） |
| `TAVILY_API_KEY` | 搜索国际新闻（可选） | [Tavily](https://app.tavily.com/) |
| `TASHAN_TOKEN` | 他山 TopicLab 搜索（可选） | 组长处获取 |
| `RESEND_API_KEY` | 邮箱验证码（用户系统，可选） | [Resend](https://resend.com/api-keys) |

> 🔑 **多租户「自带钥匙」**：平台也支持用户登录后在「模型设置」页自行填写 Key，不强制在 `.env` 全局配置。

### 第三步：安装依赖 + 启动

```bash
# 方式 A：Docker（推荐，一条命令）
docker compose up -d --build
# → 科研工作台 http://localhost:8123

# 方式 B：本地直跑
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
uvicorn api.main:app --reload --port 8000
# → 科研工作台 http://localhost:8000 · Swagger 文档 /docs
```

---

## 📁 项目结构（给技术同学看）

```
yunGuanXingChuan/
├── README.md                   # 项目说明（你正在看）
├── CONTRIBUTING.md             # 团队协作规范（分支/提交/PR）
├── SETUP_GUIDE.md              # API Key 获取详细指南
├── docker-compose.yml          # 一键容器化（app:8123 / admin:8124）
├── .env.example                # 配置模板（复制为 .env 后填写）
│
├── docs/                       # 📚 文档
│   ├── github-guide.md         # GitHub 协作入门（新手必读）
│   ├── team.md                 # 团队分工与职责
│   ├── labels.md               # Issue/PR 标签规范
│   ├── architecture-invocation.md  # 智能体调用链路（技术）
│   └── bot-automation.md       # Bot 自动化系统
│
├── config/                     # 配置文件
│   ├── settings.py             # 全局配置（读取 .env）
│   └── prompts/                # 各 Agent 的 System Prompt（19 个）
│
├── data/                       # 数据（新闻传播同学主要编辑这里）
│   ├── science/                # 科学知识库（中国空间站、嫦娥、天问、朱雀等）
│   ├── media/                  # 多语种媒体语料（11 国）
│   ├── audience_profiles/      # 受众画像
│   ├── kg/                     # 知识图谱数据
│   └── libraries/              # 四库：文献库 / 理论库 / 顶刊论文库 / 方法库
│
├── src/                        # 核心代码
│   ├── agents/                 # AI Agent（7 阶段 + 核心分析 + 成果生成）
│   ├── workflow/               # 7 阶段科研工作流引擎
│   │   ├── engine.py           # WorkflowEngine（阶段执行/确认/run-all/迭代/导出）
│   │   ├── project.py          # ProjectStore（项目文件读写/删除，带锁）
│   │   └── stages.py           # 7 阶段元数据与 Agent 绑定
│   ├── verification/           # 校验层（RAG / KG / 外部 / 报告）
│   ├── knowledge/              # 知识层（四库 / 向量 / KG / 经验池）
│   ├── search/                 # 统一搜索（百炼 WebSearch + Tavily + 他山）
│   ├── pipeline.py             # 编排器（议会/Pipeline 保留能力）
│   ├── evaluation.py           # 评测引擎
│   ├── export_service.py       # 成果多格式导出
│   ├── schemas.py              # 数据模型定义（Pydantic）
│   └── llm_client.py           # LLM 客户端封装（OpenAI 兼容）
│
├── api/                        # FastAPI 后端接口
│   ├── main.py                 # 入口（含 SPA 静态托管）
│   └── routes/                 # analyze / workflow / parliament / outputs / verify …
│
├── frontend/                   # React 前端（他山世界学术风）
│   └── src/pages/
│       ├── Workspace.tsx       # 科研工作台（项目列表/新建/一键生成/导出）
│       ├── Inspiration.tsx     # ① 选题孵化
│       ├── Literature.tsx      # ② 文献综述
│       ├── Design.tsx          # ③ 研究设计（迭代提示条 + 按建议保存修改）
│       ├── Method.tsx          # ④ 方法推荐
│       ├── DataAnalysis.tsx    # ⑤ 数据分析（迭代计数器 + AI 诊断 + 自动迭代触发）
│       ├── Writing.tsx         # ⑥ 学术写作（分栏 + 章节润色）
│       ├── Review.tsx          # ⑦ 同行评审
│       ├── Settings.tsx        # 模型设置（自带钥匙）
│       └── …
│
├── scripts/                    # 工具脚本（向量索引 / 数据注入 / 部署 / 测试）
└── tests/                      # pytest 测试（30 个文件，覆盖工作流/校验/API 全链路）
```

---

## 🤝 团队协作（标准流程）

不会用 GitHub 也没关系，跟着这套标准流程走，**每一步都在仓库里留痕**：

```
① 提 Issue → ② 认领 → ③ 开分支 → ④ 改代码 → ⑤ 提交 → ⑥ 推送 → ⑦ 开 PR → ⑧ Review → ⑨ 合并
```

**三个最重要的规矩**：

1. **永远不要在 `main` 上直接改代码** — 先开自己的分支，做完 PR 合并（`main` 已开启分支保护）
2. **开工前先 `git pull origin main`** — 拉最新代码，别在旧代码上改
3. **提交信息用 `<type>(<scope>): <描述>`** — 如 `fix(workflow): 修复阶段重跑确认`

> 📖 每一步具体怎么操作看 **[docs/github-guide.md](docs/github-guide.md)**；完整规范见 **[CONTRIBUTING.md](CONTRIBUTING.md)**。

---

## 🔧 常见问题（FAQ）

**Q：我只想用产品，不想装环境？**
**A**：直接访问 https://yunguanxingchuan.xyz 即可，注册后填写自己的 Qwen Key 就能开始研究。

**Q：文科同学需要学编程吗？**
**A**：不需要！你只需要会用浏览器打开成品网站、输入议题、看结果。想编辑数据（媒体语料、受众画像）也只需用记事本改 JSON/文本文件。

**Q：提示 "QWEN_API_KEY 未设置"？**
**A**：`.env` 没配好——确认已把 `.env.example` 复制为 `.env`，且 `QWEN_API_KEY` 填了真实 Key（不是占位符）。

**Q：我可以分析其他议题吗？**
**A**：可以！系统支持任意议题，工作日台上输入兴趣（如"天问三号"）即可，系统会自动联网搜索并跑完 7 阶段。

**Q：npm install 报错？**
**A**：确认 Node.js ≥ 18（`node --version` 检查），去 [https://nodejs.org/](https://nodejs.org/) 下载。

---

## 📋 赛事信息

- **赛事**：2026 挑战杯"揭榜挂帅"擂台赛 · 阿里云榜题（编号 XH-202619）
- **题目**：基于国产开源大模型的 AI Scientist 的研发与应用

---

## 📄 License

MIT License — 详见 [LICENSE](LICENSE) 文件。