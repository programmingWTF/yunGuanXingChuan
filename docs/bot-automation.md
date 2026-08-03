# Bot 自动化系统

云观星传项目使用 GitHub Actions 和自定义 Bot 脚本实现 Issue/PR 的自动化管理，减少人工维护成本。

## 系统组成

| 组件 | 位置 | 功能 |
|------|------|------|
| **自动打标签** | `.github/workflows/bot-labels.yml` | 根据 PR 修改的文件路径自动添加中文标签 |
| **过时管理** | `.github/workflows/bot-stale.yml` | 自动标记和关闭长期不活跃的 Issue |
| **AI 维护 Bot** | `scripts/bot/sweep.mjs` | 使用 AI 对 Issue/PR 进行智能分类、评估和标签管理 |

---

## 1. 自动打标签（bot-labels.yml）

### 触发条件

- PR 创建时（`opened`）
- PR 更新时（`synchronize`）

### 工作原理

使用 GitHub 官方的 `actions/labeler@v5`，根据 PR 修改的文件路径自动添加对应的中文标签（如 `模块：智能体`、`模块：前端` 等）。

**纯确定性规则，无需 AI 调用。**

### 配置

标签规则定义在仓库根目录的 `.github/labeler.yml`。路径规则与模块对应关系：

| 模块标签 | 匹配路径 |
|---------|---------|
| `模块：智能体` | `src/agents/**` |
| `模块：议会辩论` | `src/parliament/**` |
| `模块：流程编排` | `src/pipeline.py` |
| `模块：校验层` | `src/verification/**` |
| `模块：知识图谱` | `src/knowledge/**`、`src/search/**`、`data/**` |
| `模块：后端API` | `api/**` |
| `模块：前端` | `frontend/src/**` |
| `模块：部署` | `.github/**`、`scripts/**`、`Dockerfile`、`docker-compose*.yml` |
| `类型：文档` | `**/*.md`、`docs/**` |

---

## 2. 过时管理（bot-stale.yml）

### 触发条件

- 定时任务：每天凌晨 3:30（UTC）
- 手动触发：`workflow_dispatch`

### 工作流程

```
Issue 30 天无活动 → 标记「状态：已过时」+ 发送提醒
    ↓
再过 7 天无活动 → 自动关闭 Issue
```

### 豁免规则

带有以下标签的 Issue 不会被标记为过时：
- `优先级：P0`
- `优先级：P1`
- `状态：进行中`

### 配置参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `days-before-stale` | 30 | 多少天无活动后标记为过时 |
| `days-before-close` | 7 | 标记过时后多少天自动关闭 |
| `days-before-pr-stale` | -1 | 不对 PR 应用过时规则（-1 = 禁用） |
| `operations-per-run` | 30 | 每次运行最多处理 30 个 Issue |

---

## 3. AI 维护 Bot（sweep.mjs）

### 功能

模仿 [OpenClaw ClawSweeper](https://github.com/openclaw/openclaw) 风格，使用 AI 对 Issue 和 PR 进行：
- **智能分类**：自动识别类型（Bug / 功能请求 / 文档 / 数据 / 问题咨询 / 重构）
- **规模评估**：XS / S / M / L / XL
- **优先级评估**：P0（紧急）/ P1（高）/ P2（中）/ P3（低）
- **质量评级**：使用**王者荣耀段位**系统（倔强青铜 → 秩序白银 → 荣耀黄金 → 永恒钻石 → 至尊星耀 → 最强王者）
- **模块识别**：判断改动涉及哪个模块（智能体 / 议会辩论 / 流程编排 / 校验层 / 知识图谱 / 前端 / 后端API / 部署）
- **自动回复**：根据评估结果生成中文评论

### 部署位置

**NAS 服务器**（内网 `192.168.0.150`），通过阿里云百炼千问 API（公网，无需 VPN）。

### 运行方式

```bash
# 日常维护（处理最近的 Issue/PR）
GH_TOKEN=ghp_xxx DEEPSEEK_KEY=sk-xxx node scripts/bot/sweep.mjs daily

# 回填历史数据（处理所有未分类的 Issue/PR）
GH_TOKEN=ghp_xxx DEEPSEEK_KEY=sk-xxx node scripts/bot/sweep.mjs backfill
```

### 环境变量

| 变量 | 说明 |
|------|------|
| `GH_TOKEN` | GitHub Personal Access Token（需要 `repo` 权限） |
| `DEEPSEEK_KEY` | 阿里云百炼 API Key（从 `bailian.console.aliyun.com` 获取） |

### AI 模型

- **API 端点**：`https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions`（OpenAI 兼容接口）
- **模型**：`qwen3.8-max-preview`

### 状态管理

Bot 使用 `scripts/bot/state.json` 记录已处理的 Issue/PR，避免重复处理。

---

## 标签体系

详见 [docs/labels.md](labels.md)。

标签体系模仿 ClawSweeper，包括：
- **规模**：XS / S / M / L / XL
- **优先级**：P0 / P1 / P2 / P3
- **段位**：王者荣耀 7 级（未定级 / 倔强青铜 / 秩序白银 / 荣耀黄金 / 永恒钻石 / 至尊星耀 / 最强王者）
- **类型**：Bug / 功能请求 / 文档 / 数据 / 问题咨询 / 重构
- **模块**：智能体 / 议会辩论 / 流程编排 / 校验层 / 知识图谱 / 前端 / 后端API / 部署
- **状态**：需要更多信息 / 等待确认 / 已确认 / 进行中 / 等待审核 / 准备合并 / 已过时

---

## 开发背景

### 为什么需要 Bot？

项目由计算机 / 新闻传播 / 美术设计三个方向协作，Issue 和 PR 数量多，人工分类和标签管理成本高。Bot 自动化可以：
- 减少重复性人工操作
- 保证标签一致性
- 及时清理过期 Issue
- 提供质量反馈（段位评级）

### 技术选型

- **GitHub Actions**：用于简单的确定性规则（自动打标签、过时管理）
- **自定义 Node.js 脚本**：用于需要 AI 判断的复杂任务（智能分类、质量评估）
- **阿里云百炼千问**：通义大模型，支持 reasoning_content

---

## 相关文档

- [标签体系说明](labels.md)
- [GitHub 协作入门指南](github-guide.md)
- [团队协作规范](../CONTRIBUTING.md)

---

<sub>🦞 Bot 由 @LiGuiyu-AI 运营 · 有问题请联系李桂聿</sub>
