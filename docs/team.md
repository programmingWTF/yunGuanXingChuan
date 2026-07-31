# 团队分工与职责

> 记录项目三个方向的职责边界与交接关系。成员名单由各组自行维护，不在本文件中固定。

---

## 三个方向总览

| 方向 | 负责什么 | 主要在哪些目录产出 |
|------|---------|-------------------|
| 📰 新闻传播 | 议题内容、媒体语料、受众画像、提示词 | `data/`、`config/prompts/` |
| 💻 计算机 / AI | 系统架构、多智能体、校验层、前后端、部署 | `src/`、`api/`、`frontend/`、`scripts/`、`tests/` |
| 🎨 美术设计 | 前端视觉、数据可视化、交互设计 | `frontend/src/` |

---

## 📰 新闻传播方向

**定位**：内容的生产者与质检员。判断"这个议题在国际上该怎么讲、对谁讲、用什么框架讲"。

**职责**：
- **科学知识库**（`data/science/`）：整理议题背景、关键事实、时间线、参与方，供 Agent 提取与校验
- **媒体语料**（`data/media/<国家>/reports.json`）：收集多语种报道（法国、巴西等），标注报道倾向
- **受众画像**（`data/audience_profiles/`）：为不同受众（美国政策精英 / 全球南方公众 / 国内青年）建立认知与媒介画像
- **提示词**（`config/prompts/*.txt`）：用自然语言调整各 Agent 的角色、任务、输出要求

**交接给**：💻 方向读取 `data/` 与 `config/prompts/`；🎨 方向根据传播策略设计可视化。

**不需要**：写 Python / TypeScript 代码。编辑 JSON 和 txt 用记事本或 VS Code 即可。

---

## 💻 计算机 / AI 方向

**定位**：系统的建设者与维护者。把新闻传播的洞察变成可运行的智能体系统。

**职责**：
- **多智能体系统**（`src/agents/`）：Science / Context / Hypothesis / Strategy / Evaluator / Humanist 六个 Agent
- **议会辩论引擎**（`src/parliament/`）：多轮辩论、加权投票、Speaker 主持
- **编排器**（`src/pipeline.py`）：完整流程控制（搜索 → 提取 → 分析 → 校验 → 策略 → 评测迭代）
- **校验层**（`src/verification/`）：RAG + 知识图谱 + Wikidata + Wikipedia 四路交叉验证
- **接口**（`api/routes/`）：FastAPI 后端，供前端调用
- **前端**（`frontend/`）：React 界面（Dashboard / TaskCenter / Parliament / KnowledgeGraph 等）
- **部署与脚本**（`scripts/`、`docker-compose.yml`）：本地 / NAS 部署

**质量红线**：合并进 `main` 的改动必须能跑——`python -m pytest tests/` 通过、前端 `npm run build` 通过。

**交接给**：🎨 方向实现视觉细节；📰 方向校验输出内容是否专业。

---

## 🎨 美术设计方向

**定位**：系统的门面。把分析结果变成好看、好懂、有科技感又贴近"星空叙事"的界面。

**职责**：
- **页面布局**（`frontend/src/pages/`）：驾驶舱、任务中心、议会页、知识图谱页
- **组件与动效**（`frontend/src/components/`）：星空背景、图表配色、过渡动画
- **可视化优化**：ECharts 图表的美观与可读性（知识图谱力导向布局等）

**注意**：与 💻 方向在 `frontend/src/` 下有重叠，改动前先看对应组件归谁负责，避免冲突。

---

## 沟通与协作约定

| 事项 | 约定 |
|------|------|
| 任务登记 | 先开 **Issue**，用模板填写，动手前 **Assign** 给自己 |
| 代码提交 | 分支 + PR，至少一人 Review 后合并（见 [CONTRIBUTING.md](../CONTRIBUTING.md)） |
| 跨方向交接 | 在 PR 描述里说明"我交付了什么、你需要用什么" |
| 数据格式 | JSON / txt，编码 UTF-8，遵循已有文件的结构 |
| 大模型 API Key | 各自申请自己的，放 `.env`（已 gitignore），**严禁提交 / 外传** |
| 日常沟通 | 微信群（团队自定），问题先查文档再问人 |

---

## 新人入门路径

1. 读 [README.md](../README.md) — 了解项目是什么
2. 读 [SETUP_GUIDE.md](../SETUP_GUIDE.md) — 配置环境、跑起来
3. 读 [github-guide.md](github-guide.md) — 学会 Git/GitHub 协作
4. 读 [CONTRIBUTING.md](../CONTRIBUTING.md) — 了解分支与提交规范
5. 找一个带 `good first issue` 标签的 Issue 练手

---

*最后更新：2026-07-31*
