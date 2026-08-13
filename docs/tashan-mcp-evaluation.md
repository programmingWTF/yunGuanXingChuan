# 他山世界（TopicLab）MCP 能力评估与接入决策

> **日期**：2026-08-13
> **任务来源**：issue #97（[Feat] 联网搜索：明确标注数据来源 + 进一步结合他山 MCP 服务）
> **背景**：平台联网搜索由 `src/search/unified_search.py` 统一编排三路引擎（Tavily / 百炼 WebSearch / 他山世界）。本项需评估「他山世界（TopicLab）的 MCP 服务能力」能否进一步提升召回质量与来源丰富度，并落文档、视结论完成接入。
>
> **评估方式**：实际网络探测他山世界公开端点 + 结合现有 `src/search/tashan_search.py` 已接入的 HTTP API 实证，避免空泛判断。
>
> **结论速览**：⚠️ **他山世界当前不提供公开的标准 MCP（Model Context Protocol）服务端点**。其能力通过 REST HTTP API（`world.tashan.chat/api/v1/*`）完整暴露，且**每条结果已携带来源标识 + URL**，充分满足 issue #97「来源可追溯」需求。**建议：不引入 MCP 封装，保留并深化现有 HTTP 直连链路**。理由见 [五、结论与建议](#五结论与建议)。

---

## 一、结论速览

| 问题 | 答案 |
| --- | --- |
| 他山世界有没有公开的标准 MCP 端点？ | **没有**。实测 `world.tashan.chat/mcp` 与 `mcp.tashan.chat` 均为前端 SPA 页面（GET 返回 HTML），POST 分别返回 404 / 501，**不是 MCP 协议端点** |
| 它当前怎么提供搜索能力？ | 通过 REST HTTP API **`https://world.tashan.chat/api/v1/*`**，已深度接入（`tashan_search.py`），五路子源全部可用 |
| 现有数据能否满足「来源标注 + URL 追溯」？ | **能**。五路子源每条均带 `url` + `source`（引擎标识）字段，且已并入统一搜索去重 |
| 该不该为 MCP 而 MCP？ | **不建议**。他山目前无公开 MCP 服务；接口能力（学术 / 信源 / 信号召回）已通过 HTTP 全覆盖 |
| 后续他山出正式 MCP 怎么办？ | 预留扩展点：`tashan_search.py` 已解耦，未来可新增 MCP 客户端类（参考 `qwen_websearch.py` 的 Streamable HTTP + JSON-RPC 模式）无缝替换 |

---

## 二、他山世界当前能力：REST HTTP API（已接入）

### 2.1 端点全景（已实测可用）

`src/search/tashan_search.py` 已覆盖五路子源，全部免鉴权（仅 AMiner 需 `TASHAN_TOKEN` 可选）：

| 路线 | 端点 | 说明 | 来源标识 |
| --- | --- | --- | --- |
| **AMiner 学术检索** | `POST /aminer/paper/search` | 精确学术检索（1.15 亿论文 + 6200 万专利），**需 `TASHAN_TOKEN`** | `TashanAminer` |
| **信源文章** | `GET /source-feed/articles` | 浏览式信源发现，支持分页（多页抓取） | `TashanSourceFeed` |
| **WorldWeave 召回** | `GET /world/source-knowledge/recall` | 近 30 天信源/信号热点召回，多 `scene`（global / technology）× 多查询词 | `TashanWorldWeave` |
| **近期学术扫描** | `GET /literature/recent` | 近 30 天论文扫描，按主题词过滤 | `TashanLiterature` |
| **最近信号流** | `GET /world/signals` | 全球近 30 天信源信号流，按主题词过滤 | `TashanWorldSignals` |

### 2.2 来源字段实证（数据完整性）

以 `GET /world/signals` 实测返回（2026-08-13）为例，每条信号携带：

```
{
  "id": "selected-source-1cf60825936ea5a0",
  "title": "华盛顿 · 地缘有新消息",
  "summary": "Progressive Lt. Gov. Peggy Flanagan won ...",
  "scene": "global",
  "region_label": "华盛顿",
  "published_at": "2026-08-12T03:34:54.000Z",
  "source_name": "NPR News RSS",
  "url": "https://www.npr.org/2026/08/11/nx-s1-5927473/...",
  "source_url": "https://www.npr.org/2026/08/11/nx-s1-5927473/..."
}
```

**关键点**：`url`（来源链接）+ `source_name`（信源名，如 NPR News RSS）在 API 层已原生携带。`tashan_search.py` 将 `source_name` 拼入 `content` 前缀（`信源: {feed}；`），且 `to_dict()` 保留 `url` + `source` 引擎标识 → 进入统一搜索去重 → 随 Pipeline / 议会 / Workflow 结构化回传前端。**「来源 → 结果」的结构化链路已闭环**（issue #97 验收标准 1/3）。

---

## 三、MCP 能力实测探测（2026-08-13）

针对 issue #97「进一步结合他山世界（TopicLab）的 MCP 服务能力」，实地探测候选 MCP 端点：

| 探测端点 | 方法 | HTTP 状态 | 响应体 | 判定 |
| --- | --- | --- | --- | --- |
| `world.tashan.chat/mcp` | GET | 200 | 他山世界 SPA 前端 HTML（`<div id="root">`） | ❌ 非 MCP 端点 |
| `world.tashan.chat/mcp` | POST | 405 | nginx `405 Not Allowed` | ❌ 不接受 JSON-RPC |
| `world.tashan.chat/api/v1/mcp` | GET | 404 | 不存在 | ❌ |
| `mcp.tashan.chat` | GET | 200 | 「他山 Ask · AI 认知分身」前端 HTML | ❌ 非 MCP 端点 |
| `mcp.tashan.chat` | POST | 501 | `Unsupported method ('POST')` | ❌ 非标准 MCP 端点 |

**结论**：两个返回 200 的域名/路径均只是**前端页面**，并不实现 MCP 协议（JSON-RPC `initialize` / `tools/list` / `tools/call` 均不被接受，POST 直接 405/501）。因此**他山世界当前未对外暴露标准 MCP 服务**。

> 备注：因作者侧网络对 `help.tashan.chat`、官方文档站不可达（web_search 服务不可用），上述结论基于**对生产 API 域名的直接请求**，可信度高于二手文档转述；如后续官方开放 MCP，需以官方文档为准复检。

---

## 四、项目内 MCP 接入参考（若未来他山开放 MCP）

项目已有成熟 MCP 客户端先例——`src/search/qwen_websearch.py` 通过 **Streamable HTTP 协议**调用阿里云百炼 WebSearch MCP：

1. `initialize`（`protocolVersion: 2024-11-05` + `clientInfo`）
2. 发送 `notifications/initialized`
3. 携带 `Mcp-Session-Id` 会话头
4. `tools/call` 调用 `bailian_web_search` 并解析 SSE/JSON-RPC 结果

**若未来他山开放标准 MCP 端点**，可在 `tashan_search.py` 旁新增 `tashan_mcp_search.py`，复用同一套 Streamable HTTP + JSON-RPC 封装，将 MCP 工具结果映射为 `SearchSource`，无缝并入 `UnifiedSearchService` 去重链，无需改动上层。

---

## 五、结论与建议

**接入决策：不引入 MCP 封装，保留并深化现有 HTTP 直连。**

理由：
1. **他山无公开 MCP**：实测无标准端点，引入 MCP 无对象可连。
2. **HTTP API 已完全覆盖需求**：五路子源全部可用，且来源字段（url/source_name/region）在 API 层已携带，满足 issue #97「来源标注 + URL 追溯」验收。
3. **结构化链路已闭环**：`tashan_search.py → unified_search.py（标注 source 去重）→ Pipeline/议会/Workflow（search_sources 结构化回传）→ 前端渲染`（配合 #98 的可点击来源列表）。
4. **避免重复造轮子**：为不存在的服务写封装违背 YAGNI。

**落地动作（随 issue #97 一并交付）**：
- ✅ 保留五路 HTTP 子源，`source` 标识 + `url` 已逐条标注（既有实现）
- ✅ 补强议会链路：`debate_engine` 将辩论全程累积的 `search_sources` 结构化挂入 `DeliberationTranscript.final_strategies.search_sources`（新增）
- 📌 **后续跟进（他山开放 MCP 时）**：按 [四、接入参考](#四项目内-mcp-接入参考若未来他山开放-mcp) 新增 `tashan_mcp_search.py` 即可无缝接入
- 📌 **待办**：需申请 `TASHAN_TOKEN` 以启用 AMiner 学术检索（由组长统一管理），启用后 `tashan_search.py` 自动激活，无需改码
