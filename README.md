# 云观星传 — 基于通义大模型的科技议题传播分析与表达系统

> 🌟 **AI Scientist 范式**：假设生成 → 验证 → 迭代
> 🔍 **RAG + 知识图谱双校验**：确保科学事实准确性
> 📊 **五维评分 + 自迭代闭环**：自动评估与改进
> 🤖 **多智能体协作**：六个专职 Agent + 议会辩论引擎（Parliament）互相校验

---

## 📖 项目简介（给所有人看）

"云观星传"是一个**帮助新闻传播研究者分析科技议题国际传播效果**的智能工具。

### 它做什么？

简单来说，你输入一个科技议题（比如"嫦娥六号月球背面采样返回"），系统会自动：

1. **搜集信息** — 从互联网搜索相关的中文、英文、法文报道
2. **提取事实** — 用 AI 提取关键科学事实（时间线、参与方、技术参数等）
3. **分析语境** — 分析不同国家媒体是如何报道这个议题的（用了什么框架、什么情感倾向）
4. **生成假设** — 自动提出可验证的传播学假设（比如"美国精英媒体倾向于用安全化框架报道中国航天"）
5. **事实校验** — 用知识图谱 + 文档检索双重验证每个科学事实的准确性
6. **策略建议** — 输出面向不同受众（美国政策精英 / 全球南方公众 / 国内青年）的传播策略
7. **自动评分** — 用五维评分矩阵自动评估输出质量，不够好的会自动迭代改进

### 为什么叫"云观星传"？

- **云** = 阿里云 / 云计算
- **观星** = 观测星空（航天、天文议题）
- **传** = 传播

---

## 📚 文档导航（新手按这个顺序读）

> 不用一次读完，**按顺序读到"能跑起来、能提交代码"** 就够了，等熟悉了再回头细看。

| 顺序 | 文档 | 看完能做什么 |
|------|------|-------------|
| ① | **[README.md](README.md)**（本文档） | 知道项目是什么、能做什么 |
| ② | **[SETUP_GUIDE.md](SETUP_GUIDE.md)** | 配好环境、拿到 API Key、把项目跑起来 |
| ③ | **[docs/github-guide.md](docs/github-guide.md)** ⭐ | 学会 Git/GitHub：建分支、提交、PR、Review |
| ④ | **[CONTRIBUTING.md](CONTRIBUTING.md)** | 掌握团队规范：分支命名、提交格式、PR 要求 |
| ⑤ | **[docs/team.md](docs/team.md)** | 了解三个方向的职责边界与交接 |
| ⑥ | **[docs/labels.md](docs/labels.md)** | 了解 Issue / PR 标签体系（组长会用 AI 统一添加） |
| ⑦ | **[docs/architecture-invocation.md](docs/architecture-invocation.md)** | （技术同学）理解多智能体完整调用链路 |

> ⭐ = **不会用 Git 的成员必读**。会用的也建议扫一遍——里面有针对本项目私有仓库的注意事项。
>
> 还没拿到仓库协作者权限？找组长把你的 GitHub 账号添加进去。

---

## 👥 团队成员角色指引

| 角色 | 需要关注的部分 | 需要做什么 |
|------|---------------|-----------|
| **新闻传播方向** | 数据文件、Prompt 模板 | 编辑 `data/` 下的语料和受众画像，微调 `config/prompts/` 中的提示词 |
| **计算机/AI 方向** | 全部代码 | 系统架构、API 集成、Agent 编排、前端开发 |
| **美术设计方向** | 前端样式、可视化 | 修改 `frontend/src/` 下的组件样式、图表配色、星空背景 |

---

## 🚀 快速开始（零基础也能看懂）

> ⚠️ **第一步最重要**：你需要先获取 API Key，具体方法看 → **[📘 环境配置与 API Key 获取指南 (SETUP_GUIDE.md)](SETUP_GUIDE.md)**

### 你需要安装的软件

在开始之前，你的电脑上需要安装两个东西：

#### 1. Python（运行后端 AI 程序）
- **是什么**：一种编程语言，我们的 AI 分析系统用它写的
- **去哪下载**：[https://www.python.org/downloads/](https://www.python.org/downloads/)
- **装哪个版本**：3.10 或更高版本
- **安装时注意**：勾选 ☑️ "Add Python to PATH"（把 Python 加到系统路径）

<details>
<summary>📸 点击展开：安装 Python 的详细步骤</summary>

1. 打开 [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. 点击黄色的 "Download Python 3.x.x" 按钮
3. 运行下载的安装程序
4. **重要**：在安装界面的底部，勾选 **"Add Python to PATH"**
5. 点击 "Install Now"
6. 等待安装完成

**验证安装成功**：
- Windows：按 `Win + R`，输入 `cmd`，回车，在黑色窗口中输入 `python --version`
- 如果显示 `Python 3.x.x` 就说明安装成功了
</details>

#### 2. Node.js（运行前端网页界面）
- **是什么**：用来运行项目的前端网页界面
- **去哪下载**：[https://nodejs.org/](https://nodejs.org/)
- **装哪个版本**：18 或更高版本（推荐下载左边的 **LTS** 版本，最稳定）

<details>
<summary>📸 点击展开：安装 Node.js 的详细步骤</summary>

1. 打开 [https://nodejs.org/](https://nodejs.org/)
2. 点击左边的 "LTS" 版本下载
3. 运行安装程序，一路点 "Next" 即可
4. 等待安装完成

**验证安装成功**：
- Windows：按 `Win + R`，输入 `cmd`，回车，输入 `node --version`
- 如果显示版本号就说明安装成功了
</details>

---

### 第一步：下载项目代码

> 如果你是第一次使用 Git，可以直接在网页上下载 ZIP。

**方法 A：用 Git 克隆（推荐）**
```bash
git clone https://github.com/programmingWTF/yunGuanXingChuan.git
cd yunGuanXingChuan
```
> 这是**私有仓库**，首次 clone 需要登录你的 GitHub 账号；还没有权限？先让组长把账号加进协作者列表。

**方法 B：下载 ZIP**
1. 在 GitHub 仓库页面点击绿色的 "Code" 按钮
2. 选择 "Download ZIP"
3. 解压到你喜欢的文件夹

---

### 第二步：配置 API Key（关键步骤！）

> 📘 **详细教程请阅读：[SETUP_GUIDE.md](SETUP_GUIDE.md)** ← 里面有截图指引和每个 Key 的具体获取网址

1. 复制配置模板：
   ```bash
   cp .env.example .env
   ```
   > Windows 用户也可以直接在文件管理器中复制 `.env.example`，然后重命名为 `.env`

2. 用记事本（或任何文本编辑器）打开 `.env` 文件

3. 把里面的 `your_xxx_key_here` 替换成你自己的 API Key

   你最少需要一个 Key：

   | Key 名称 | 作用 | 获取网站 |
   |----------|------|---------|
   | `QWEN_API_KEY` | 调用通义千问大模型 | [百炼控制台](https://bailian.console.aliyun.com/) |
   | `DASHSCOPE_API_KEY` | 联网搜索能力 | 同上（可与 QWEN_API_KEY 共用一个） |
   | `TAVILY_API_KEY` | 搜索国际新闻 | [Tavily 官网](https://app.tavily.com/) |

   > 💡 **最小启动配置**：只填 `QWEN_API_KEY` 和 `DASHSCOPE_API_KEY`（可以是同一个 Key），项目就能跑起来。Tavily 是可选的。

---

### 第三步：安装项目依赖

打开终端（命令行），进入项目文件夹，依次执行：

```bash
# 1. 安装 Python 依赖（AI 相关库）
pip install -r requirements.txt

# 2. 进入前端目录
cd frontend

# 3. 安装前端依赖（网页界面相关库）
npm install

# 4. 回到项目根目录
cd ..
```

<details>
<summary>📸 什么是"终端"？怎么打开？</summary>

**终端**（也叫"命令行"）是一个黑色的文字窗口，你可以在里面输入命令来控制电脑。

**打开方法（Windows）**：
- 按 `Win + R`，输入 `cmd`，回车
- 或者在项目文件夹里，按住 `Shift` 键，右键点击空白处，选择"在此处打开 PowerShell 窗口"

**导航到项目文件夹**：
- 假如你解压到 `D:\Code\yunGuanXingChuan`
- 在终端输入：`cd D:\Code\yunGuanXingChuan`
- 然后就可以执行上面的命令了
</details>

---

### 第四步：运行项目

有三种运行方式，按需选择：

#### 方式 1：命令行 Demo（⭐ 推荐先试这个）

最简单的方式，一行命令体验完整流程：

```bash
python scripts/run_demo.py --topic "嫦娥六号"
```

你会看到系统一步步执行：搜集信息 → 提取事实 → 分析语境 → 生成假设 → 校验 → 策略建议 → 评分。整个过程大约需要 2-5 分钟。

#### 方式 2：启动后端 API + Swagger 文档

```bash
uvicorn api.main:app --reload --port 8000
```

然后打开浏览器访问：
- **API 文档（Swagger）**：[http://localhost:8000/docs](http://localhost:8000/docs) ← 在这里可以直接测试所有 API 接口
- **系统信息**：[http://localhost:8000/api/info](http://localhost:8000/api/info)

#### 方式 3：完整前后端（有可视化界面）

需要两个终端窗口：

**终端 1 — 启动后端：**
```bash
uvicorn api.main:app --reload --port 8000
```

**终端 2 — 构建并启动前端：**
```bash
cd frontend
npm run build
cd ..
uvicorn api.main:app --port 8000
```

然后在浏览器打开 [http://localhost:8000](http://localhost:8000) 就能看到完整界面。

---

## 🤝 团队协作（标准流程）

不会用 GitHub 也没关系，跟着这套标准流程走，**每一步都在仓库里留痕，队友能看见你在做什么**：

```
① 提 Issue → ② 认领 → ③ 开分支 → ④ 改代码 → ⑤ 提交 → ⑥ 推送 → ⑦ 开 PR → ⑧ Review → ⑨ 合并
```

| 步骤 | 做什么 | 在哪操作 |
|------|--------|---------|
| ① 提 Issue | 把要做的事写成任务单（用模板） | GitHub → **Issues** → New issue |
| ② 认领 | 把自己设成 Assignee，说"我来做" | Issue 右侧 **Assignees** |
| ③ 开分支 | `git checkout -b feat/xxx` | 本地终端 |
| ④ 改代码 | 编辑文件 | VS Code |
| ⑤ 提交 | `git add .` → `git commit -m "<type>(<scope>): <描述>"` | 本地终端 |
| ⑥ 推送 | `git push origin feat/xxx` | 本地终端 |
| ⑦ 开 PR | 申请合并，描述里写 `Closes #编号` | GitHub → **Pull requests** |
| ⑧ Review | 等至少一位队友 Approve | GitHub PR 页面 |
| ⑨ 合并 | Merge 进 `main` | GitHub PR 页面 |

**三个最重要的规矩**：

1. **永远不要在 `main` 上直接改代码** — 先开自己的分支，做完 PR 合并
2. **开工前先 `git pull origin main`** — 拉最新代码，别在旧代码上改（会把队友的工作覆盖掉）
3. **提交信息用 `<type>(<scope>): <描述>`** — 例如 `fix(parliament): 修复辩论显示`；类型：`feat`（新功能）/ `fix`（修bug）/ `docs`（文档）/ `data`（数据）/ `style`（样式）...

> 📖 每一步具体怎么操作、遇到报错怎么办，看 **[docs/github-guide.md](docs/github-guide.md)**；完整规范见 **[CONTRIBUTING.md](CONTRIBUTING.md)**。

---

## 📁 项目结构（给技术同学看）

```
yunGuanXingChuan/
├── README.md                   # 项目说明（你正在看）
├── CONTRIBUTING.md             # 团队协作规范（分支/提交/PR）
├── SETUP_GUIDE.md              # API Key 获取详细指南
├── .github/                    # GitHub 模板（Issue / PR）
├── .env.example                # 配置模板（复制为 .env 后填写）
├── requirements.txt            # Python 依赖列表
│
├── docs/                       # 📚 文档
│   ├── github-guide.md         # GitHub 协作入门（新手必读）
│   ├── team.md                 # 团队分工与职责
│   ├── labels.md               # Issue/PR 标签规范
│   └── architecture-invocation.md  # 多智能体调用链路（技术）
│
├── config/                     # 配置文件
│   ├── settings.py             # 全局配置（读取 .env）
│   └── prompts/                # 各 Agent 的 System Prompt
│       ├── science_agent.txt   # 科学理解 Agent 提示词
│       ├── context_agent.txt   # 语境分析 Agent 提示词
│       ├── hypothesis_agent.txt
│       ├── strategy_agent.txt
│       └── evaluator_agent.txt
│
├── data/                       # 数据（新闻传播同学主要编辑这里）
│   ├── science/                # 科学知识库（嫦娥六号、天宫等）
│   ├── media/                  # 多语种媒体语料
│   │   ├── france/reports.json # 法国媒体报道
│   │   └── brazil/reports.json # 巴西媒体报道
│   ├── audience_profiles/      # 受众画像
│   │   ├── us_policy_elite.json
│   │   ├── global_south_public.json
│   │   └── domestic_youth.json
│   └── kg/                     # 知识图谱数据
│
├── src/                        # 核心代码
│   ├── agents/                 # 6 个 AI Agent
│   │   ├── base_agent.py       # Agent 基类
│   │   ├── science_agent.py    # 科学理解
│   │   ├── context_agent.py    # 语境分析
│   │   ├── hypothesis_agent.py # 假设生成
│   │   ├── strategy_agent.py   # 策略转译
│   │   ├── evaluator_agent.py  # 评测迭代
│   │   └── humanist_agent.py   # 人文审查（文化/伦理）
│   ├── parliament/             # 议会辩论引擎（Speaker + 辩论循环）
│   ├── verification/           # 校验层
│   │   ├── rag_checker.py      # RAG 向量检索校验
│   │   ├── kg_checker.py       # 知识图谱校验
│   │   ├── cross_validator.py  # 交叉验证
│   │   └── report_generator.py # 校验报告生成
│   ├── knowledge/              # 知识层
│   │   ├── data_loader.py      # 数据加载
│   │   ├── vector_store.py     # FAISS 向量存储
│   │   └── kg_builder.py       # 知识图谱构建
│   ├── search/                 # 搜索引擎
│   │   ├── unified_search.py   # 统一搜索接口
│   │   ├── qwen_websearch.py   # 百炼 WebSearch
│   │   └── tavily_search.py    # Tavily 搜索
│   ├── pipeline.py             # 编排器（核心流程控制）
│   ├── evaluation.py           # 评测引擎
│   ├── schemas.py              # 数据模型定义
│   └── llm_client.py           # LLM 客户端封装
│
├── api/                        # FastAPI 后端接口
│   ├── main.py                 # 入口
│   └── routes/                 # 各模块 API 路由
│
├── frontend/                   # React 前端
│   ├── src/pages/
│   │   ├── Dashboard.tsx       # 数据驾驶舱
│   │   ├── TaskCenter.tsx      # 任务中心（启动议会）
│   │   ├── Parliament.tsx      # 议会辩论结果页
│   │   ├── Hypotheses.tsx      # 假设浏览
│   │   ├── Strategy.tsx        # 策略推演
│   │   ├── KnowledgeGraph.tsx  # 知识图谱可视化
│   │   └── VerifyReport.tsx    # 校验报告
│   └── src/components/
│       └── StarfieldBackground.tsx  # 星空背景动画
│
└── scripts/                    # 工具脚本
    ├── run_demo.py             # 命令行 Demo
    ├── build_index.py          # 构建向量索引
    └── gen_science_data.py     # 生成科学数据
```

---

## 🤖 多智能体系统详解

| Agent | 中文名 | 做什么 | 输出 |
|-------|--------|--------|------|
| Science Agent | 科学理解 | 从多语种报道中提取结构化科学事实、实体、关系、时间线 | `ScienceFacts`（JSON） |
| Context Agent | 语境分析 | 分析各国媒体报道的框架（framing）、情感倾向、叙事差异 | `ContextAnalysis`（JSON） |
| Hypothesis Agent | 假设生成 | 基于科学事实 + 语境分析，生成可验证的传播学假设 | `HypothesisSet`（JSON） |
| Strategy Agent | 策略转译 | 针对不同受众生成具体传播策略（渠道、人设、文案） | `StrategySet`（JSON） |
| Evaluator Agent | 评测迭代 | 五维评分 + 迭代反馈，驱动自改进闭环 | `EvaluationResult`（JSON） |
| Humanist Agent | 人文审查 | 审查文化敏感性与伦理风险，在议会中担任人文守护者 | `CulturalReview`（JSON） |

> 除上述六位 Agent 外，系统还有 **议会辩论引擎（Parliament）**：由 Speaker 主持多轮辩论与加权投票，先通过辩论筛出有价值的动议，再交给 Pipeline 做四路事实校验与策略评测。完整的调用链路见 **[docs/architecture-invocation.md](docs/architecture-invocation.md)**。

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

## 🎯 当前聚焦议题

| 维度 | 内容 |
|------|------|
| **科学议题** | 嫦娥六号（月球背面采样返回）、天宫空间站 |
| **目标国家** | 美国、法国、巴西 |
| **分析语言** | 中文 + 英文 + 法文 |
| **时间窗口** | 2024 — 2026 |

---

## 🔧 常见问题（FAQ）

### Q：运行时提示 "ModuleNotFoundError: No module named 'xxx'"
**A**：说明缺少 Python 依赖，运行 `pip install -r requirements.txt` 即可。

### Q：运行时提示 "QWEN_API_KEY 未设置"
**A**：`.env` 文件没有配置好，请确认：
1. 是否把 `.env.example` 复制为 `.env`？
2. `.env` 文件里的 `QWEN_API_KEY` 是否填了真实的 Key？（不是 `your_bailian_api_key_here`）

### Q：npm install 报错
**A**：确认已安装 Node.js 18+。在终端运行 `node --version` 检查。如果没装，去 [https://nodejs.org/](https://nodejs.org/) 下载。

### Q：前端页面打不开 / 白屏
**A**：确保后端已启动（`uvicorn api.main:app --port 8000`），然后访问 [http://localhost:8000](http://localhost:8000)

### Q：运行 Demo 一直卡住不动
**A**：首次运行需要下载模型和构建索引，可能需要几分钟。如果超过 10 分钟还没反应，检查网络连接和 API Key 是否正确。

### Q：我想分析其他议题（不是嫦娥六号/天宫），可以吗？
**A**：可以！系统支持任意议题。运行：
```bash
python scripts/run_demo.py --topic "你想分析的议题"
```
系统会自动联网搜索并生成结构化数据。

### Q：文科同学需要学编程吗？
**A**：不需要！如果你只使用命令行 Demo（方式 1），只需要会打开终端、复制粘贴命令即可。如果你想编辑数据（媒体语料、受众画像等），只需编辑 JSON 或文本文件，用记事本就能打开。

---

## 🛠 技术栈

| 层级 | 技术 |
|------|------|
| 大模型 | 通义千问 Qwen（阿里云百炼平台） |
| 向量检索 | FAISS + text-embedding-v3 |
| 知识图谱 | NetworkX + JSON |
| 后端 | FastAPI + Pydantic + uvicorn |
| 前端 | React 18 + TypeScript + Vite + ECharts + Tailwind CSS |
| 搜索引擎 | Tavily Search API + 百炼 WebSearch MCP |
| 视觉风格 | 星空主题（深蓝 #0A1628 + 青蓝 #00D4FF） |

---

## 📋 赛事信息

- **赛事**：2026 挑战杯"揭榜挂帅"擂台赛
- **榜题**：阿里云榜题（编号 XH-202619）
- **题目**：基于国产开源大模型的 AI Scientist 的研发与应用
- **作品提交截止**：2026 年 9 月 5 日

---

## 📄 License

MIT License — 详见 [LICENSE](LICENSE) 文件。
