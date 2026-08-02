// 云观星传 AI 维护 Bot — LiGuiyu-AI
// 部署在 NAS，调用阿里云百炼千问 API（公网，无需 VPN）
// 运行方式: GH_TOKEN=ghp_xxx DEEPSEEK_KEY=sk-xxx node sweep.mjs [daily|backfill]

import { readFileSync, writeFileSync, existsSync, mkdirSync, unlinkSync } from "node:fs";
import { execSync } from "node:child_process";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

// ============================================================
// 配置
// ============================================================

const CONFIG = {
  GH_TOKEN: process.env.GH_TOKEN || "",
  REPO: "programmingWTF/yunGuanXingChuan",
  REPO_API: "https://api.github.com/repos/programmingWTF/yunGuanXingChuan",
  BOT_LOGIN: "LiGuiyu-AI",

  DEEPSEEK_API: "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions",
  DEEPSEEK_MODEL: "qwen3.8-max-preview",
  DEEPSEEK_KEY: process.env.DEEPSEEK_KEY || "",

  STATE_FILE: join(__dirname, "state.json"),
  LOCK_FILE: join(__dirname, "sweep.lock"),
  MAX_ITEMS_PER_RUN: 10,
};

// ============================================================
// 标签体系 — 模仿 ClawSweeper，段位用王者荣耀
// ============================================================

const LABELS = {
  // 规模 — 继承 ClawSweeper Size: XS/S/M/L/XL（字母保留英文）
  size: [
    { name: "规模：XS", color: "8C959F", desc: "极简改动，预计几分钟" },
    { name: "规模：S", color: "8C959F", desc: "小改动，预计半天内" },
    { name: "规模：M", color: "8C959F", desc: "中等改动，预计 1-3 天" },
    { name: "规模：L", color: "8C959F", desc: "大改动，预计 3-7 天" },
    { name: "规模：XL", color: "8C959F", desc: "超大改动，预计超过 1 周" },
  ],
  // 优先级 — P0-P3
  priority: [
    { name: "优先级：P0", color: "B60205", desc: "紧急：安全漏洞、崩溃、核心功能不可用" },
    { name: "优先级：P1", color: "D93F0B", desc: "高：用户可见 Bug、功能回归" },
    { name: "优先级：P2", color: "FBCA04", desc: "中：常规任务" },
    { name: "优先级：P3", color: "8C959F", desc: "低：优化、文档、锦上添花" },
  ],
  // 段位 — 王者荣耀 7 级
  rank: [
    { name: "段位：未定级", color: "8C2F39", desc: "信息不足，尚无法评估质量" },
    { name: "段位：倔强青铜", color: "8B5A2B", desc: "初具雏形，仍需补充大量信息" },
    { name: "段位：秩序白银", color: "A0A4A8", desc: "基本清晰，可以正常处理" },
    { name: "段位：荣耀黄金", color: "D4A017", desc: "描述完整，质量不错" },
    { name: "段位：永恒钻石", color: "00BCD4", desc: "高质量，细节到位" },
    { name: "段位：至尊星耀", color: "7B1FA2", desc: "非常出色，堪称范例" },
    { name: "段位：最强王者", color: "E65100", desc: "顶级质量，完美无瑕" },
  ],
  // 类型
  type: [
    { name: "类型：Bug", color: "D73A4A", desc: "功能异常，需要修复" },
    { name: "类型：功能请求", color: "A2EEEF", desc: "新功能或改进建议" },
    { name: "类型：文档", color: "0075CA", desc: "文档改进或补充" },
    { name: "类型：数据", color: "84B6EB", desc: "数据、语料、受众画像相关" },
    { name: "类型：问题咨询", color: "D876E3", desc: "需要讨论或答疑" },
    { name: "类型：重构", color: "7057FF", desc: "重构代码，行为不变" },
  ],
  // 模块（改动范围，替代 NUAAMap 的小组）
  module: [
    { name: "模块：智能体", color: "5319E7", desc: "智能体 Agent（src/agents/）" },
    { name: "模块：议会辩论", color: "B60205", desc: "议会辩论引擎（src/parliament/）" },
    { name: "模块：流程编排", color: "1D76DB", desc: "流程编排（src/pipeline.py）" },
    { name: "模块：校验层", color: "E99695", desc: "校验层（src/verification/）" },
    { name: "模块：知识图谱", color: "FBCA04", desc: "知识图谱 / 向量库 / 数据（src/knowledge/、data/）" },
    { name: "模块：前端", color: "006B75", desc: "前端界面（frontend/）" },
    { name: "模块：后端API", color: "0E8A16", desc: "后端接口（api/）" },
    { name: "模块：部署", color: "0052CC", desc: "部署、Docker、脚本（scripts/、docker-compose.yml）" },
  ],
  // 状态
  status: [
    { name: "状态：需要更多信息", color: "6E7781", desc: "等待作者补充信息" },
    { name: "状态：等待确认", color: "D4C5F9", desc: "等待维护者确认" },
    { name: "状态：已确认", color: "A2EEEF", desc: "问题已被确认存在" },
    { name: "状态：进行中", color: "FBCA04", desc: "正在处理中" },
    { name: "状态：等待审核", color: "F9D0C4", desc: "PR 等待审核" },
    { name: "状态：准备合并", color: "0E8A16", desc: "PR 可以合并" },
    { name: "状态：已过时", color: "6E7781", desc: "过时管理自动标记，7 天后关闭" },
  ],
  // 杂项（含 GitHub 内置标签，防止 ensureLabelsExist 误删）
  misc: [
    { name: "重复", color: "6F42C1", desc: "此 Issue 或 PR 已存在" },
    { name: "good first issue", color: "7057FF", desc: "适合新手练手（GitHub 内置）" },
    { name: "help wanted", color: "008672", desc: "需要额外帮助（GitHub 内置）" },
    { name: "invalid", color: "E4E669", desc: "不符合要求（GitHub 内置）" },
    { name: "wontfix", color: "FFFFFF", desc: "不会处理（GitHub 内置）" },
  ],
};

// 扁平化为数组
const VALID_LABELS = [
  ...LABELS.size,
  ...LABELS.priority,
  ...LABELS.rank,
  ...LABELS.type,
  ...LABELS.module,
  ...LABELS.status,
  ...LABELS.misc,
].map((l) => l.name);

// ============================================================
// 工具函数
// ============================================================

function log(...args) {
  const ts = new Date().toISOString().slice(0, 19).replace("T", " ");
  console.log(`[${ts}]`, ...args);
}

/** 简单字符串哈希（djb2），用于内容指纹比较 */
function hashString(str) {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) + hash) + str.charCodeAt(i);
    hash = hash & hash; // 保持 32 位整数
  }
  return hash.toString(36);
}

/**
 * 计算 Issue/PR 的内容指纹
 * - Issue: title + body — 标签、指派人、评论等元数据不参与
 * - PR: title + body + head.sha — push 新 commit 也会触发重新审查
 */
function getContentFingerprint(item) {
  const title = item.title || "";
  const body = (item.body || "").slice(0, 5000);
  // PR 纳入最新 commit SHA，push 新代码后自动触发重新审查
  const sha = item.head?.sha || "";
  return hashString(title + "\n" + body + "\n" + sha);
}

function loadState() {
  const defaults = { reviewed: {}, lastDailySweep: null };
  if (!existsSync(CONFIG.STATE_FILE)) return defaults;
  try {
    const raw = JSON.parse(readFileSync(CONFIG.STATE_FILE, "utf-8"));
    return { ...defaults, ...raw, reviewed: { ...defaults.reviewed, ...(raw.reviewed || {}) } };
  }
  catch { return defaults; }
}

function saveState(state) {
  mkdirSync(dirname(CONFIG.STATE_FILE), { recursive: true });
  writeFileSync(CONFIG.STATE_FILE, JSON.stringify(state, null, 2));
}

async function ghAPI(path, opts = {}) {
  const url = path.startsWith("http") ? path : `${CONFIG.REPO_API}${path}`;
  const headers = {
    Authorization: `Bearer ${CONFIG.GH_TOKEN}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    ...opts.headers,
  };
  if (opts.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  // fetch 在 NAS 网络上偶发失败，最多重试 3 次
  let lastErr;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const res = await fetch(url, { headers, ...opts });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(`GitHub API ${res.status}: ${body.slice(0, 200)}`);
      }
      return res.json();
    } catch (e) {
      lastErr = e;
      if (attempt < 3) await new Promise(r => setTimeout(r, 2000));
    }
  }
  throw lastErr;
}

function extractIssueNumber(issueUrl) {
  const m = issueUrl?.match(/\/(\d+)$/);
  return m ? parseInt(m[1], 10) : null;
}

// ============================================================
// 标签管理
// ============================================================

async function ensureLabelsExist() {
  try {
    const existing = await ghAPI("/labels?per_page=100");
    const existingNames = new Set(existing.map((l) => l.name));

    const allLabels = [
      ...LABELS.size, ...LABELS.priority, ...LABELS.rank,
      ...LABELS.type, ...LABELS.module, ...LABELS.status, ...LABELS.misc,
    ];

    // 创建缺失的新标签
    let created = 0;
    for (const { name, color, desc } of allLabels) {
      if (existingNames.has(name)) continue;
      await ghAPI("/labels", {
        method: "POST",
        body: JSON.stringify({ name, color, description: desc }),
      });
      log(`  🏷️ 创建标签: ${name}`);
      created++;
    }

    // 删除不在新体系中的旧标签
    let deleted = 0;
    for (const label of existing) {
      if (!VALID_LABELS.includes(label.name)) {
        await ghAPI(`/labels/${encodeURIComponent(label.name)}`, { method: "DELETE" });
        log(`  🗑️ 删除旧标签: ${label.name}`);
        deleted++;
      }
    }

    if (created === 0 && deleted === 0) log("  ✅ 所有标签已就绪");
    else log(`  ✅ 创建 ${created} 个，清理 ${deleted} 个旧标签`);
  } catch (e) {
    log(`  ⚠️ 标签管理失败: ${e.message}`);
  }
}

async function setLabels(issueNumber, labels) {
  if (!labels || labels.length === 0) return;
  const valid = labels.filter((l) => VALID_LABELS.includes(l));
  if (valid.length === 0) return;
  try {
    // Node.js undici 对 PUT 请求偶发 fetch failed，改用 curl 保底
    const url = `https://api.github.com/repos/${CONFIG.REPO}/issues/${issueNumber}/labels`;
    const cmd = `curl -s --connect-timeout 10 --max-time 15 -X PUT -H "Authorization: Bearer ${CONFIG.GH_TOKEN}" -H "Accept: application/vnd.github+json" -H "Content-Type: application/json" -d ${JSON.stringify(JSON.stringify({ labels: valid }))} ${url}`;
    execSync(cmd, { encoding: "utf-8", timeout: 20000, stdio: ["pipe", "pipe", "pipe"] });
  } catch (e) {
    log(`  ⚠️ 设置标签失败: ${e.message}`);
  }
}

/** 把单个标签值归一化并匹配到合法标签名（兼容全/半角冒号、漏前缀、多余空格） */
function canonLabel(dimPrefix, value) {
  if (value == null) return null;
  let v = String(value).trim().replace(/:/g, "：").replace(/\s+/g, "");
  if (!v) return null;
  if (VALID_LABELS.includes(v)) return v;
  if (dimPrefix && !v.startsWith(dimPrefix)) {
    const withPrefix = dimPrefix + v;
    if (VALID_LABELS.includes(withPrefix)) return withPrefix;
  }
  return null;
}

/** 从 AI 结构化字段组装合法标签数组（独立字段永不为空，规避模型偶发返回空 labels） */
function buildLabelsFromResult(result) {
  if (!result) return [];
  const out = new Set();
  const add = (v) => { if (v) out.add(v); };
  add(canonLabel("规模：", result.size));
  add(canonLabel("优先级：", result.priority));
  add(canonLabel("段位：", result.rank));
  add(canonLabel("类型：", result.category));
  add(canonLabel("状态：", result.status));
  if (Array.isArray(result.modules)) for (const m of result.modules) add(canonLabel("模块：", m));
  if (Array.isArray(result.labels)) {
    for (const l of result.labels) {
      const n = String(l).trim().replace(/:/g, "：").replace(/\s+/g, "");
      if (VALID_LABELS.includes(n)) out.add(n);
    }
  }
  return [...out];
}

async function postComment(issueNumber, body) {
  if (!body) return null;
  try {
    const res = await ghAPI(`/issues/${issueNumber}/comments`, {
      method: "POST",
      body: JSON.stringify({ body }),
    });
    return res.id;
  } catch (e) {
    log(`  ⚠️ 评论失败: ${e.message}`);
    return null;
  }
}

async function updateComment(commentId, body) {
  if (!body || !commentId) return;
  try {
    await ghAPI(`/issues/comments/${commentId}`, {
      method: "PATCH",
      body: JSON.stringify({ body }),
    });
  } catch (e) {
    log(`  ⚠️ 更新评论失败: ${e.message}`);
  }
}

// ============================================================
// 工具函数
// ============================================================

/** 从 markdown 中提取图片 URL */
function extractImageUrls(markdown) {
  const urls = [];
  // Markdown: ![alt](url)
  for (const m of markdown.matchAll(/!\[.*?\]\((https?:\/\/[^\s)]+)\)/g)) {
    urls.push(m[1]);
  }
  // HTML: <img src="url">
  for (const m of markdown.matchAll(/<img[^>]+src=["'](https?:\/\/[^\s"']+)["'][^>]*>/gi)) {
    urls.push(m[1]);
  }
  return [...new Set(urls)]; // 去重
}

// ============================================================
// Qwen API（阿里云百炼，兼容 OpenAI 协议）
// ============================================================

function callDeepSeek(messages) {
  const body = JSON.stringify({
    model: CONFIG.DEEPSEEK_MODEL,
    messages,
    temperature: 0.3,
    max_tokens: 8192,
  });

  // 请求体可能很大（含代码 diff），写临时文件避免 shell 转义问题和命令行长度限制
  const tmpFile = `/tmp/sweep-body-${Date.now()}.json`;
  writeFileSync(tmpFile, body, "utf-8");

  const cmd = [
    "curl -s --connect-timeout 15 --max-time 180",
    `-H "Authorization: Bearer ${CONFIG.DEEPSEEK_KEY}"`,
    `-H "Content-Type: application/json"`,
    `--data-binary @${tmpFile}`,
    CONFIG.DEEPSEEK_API,
  ].join(" ");

  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const stdout = execSync(cmd, {
        encoding: "utf-8",
        timeout: 185000,
        stdio: ["pipe", "pipe", "pipe"],
      });
      const data = JSON.parse(stdout);
      if (data.error) {
        throw new Error(`API error: ${JSON.stringify(data.error)}`);
      }
      // 千问 thinking 模式：content 可能为空，实际输出在 reasoning_content
      const msg = data.choices?.[0]?.message;
      if (msg && !msg.content) msg.content = msg.reasoning_content || "";
      try { unlinkSync(tmpFile); } catch {}
      return data;
    } catch (e) {
      if (attempt === 3) {
        try { unlinkSync(tmpFile); } catch {}
        const msg = e.stdout ? e.stdout.toString().slice(0, 200) : e.message;
        throw new Error(`DeepSeek 不可达 (尝试${attempt}次): ${msg}`);
      }
      log(`  ⚠️ DeepSeek 第${attempt}次失败，${2 ** attempt}秒后重试...`);
      const waitMs = 2 ** attempt * 1000;
      const end = Date.now() + waitMs;
      while (Date.now() < end) { /* spin */ }
    }
  }
}

// ============================================================
// AI System Prompt
// ============================================================

const SYSTEM_PROMPT = `你是云观星传项目的 AI 维护助手（LiGuiyu-AI），审查 Python+FastAPI 后端、React+TypeScript 前端代码和 Issue/PR。云观星传是基于通义大模型的科技议题传播分析与表达系统，多智能体协作（科学理解 → 语境分析 → 假设生成 → 策略转译），核心模块含智能体、议会辩论、流程编排、校验层、知识图谱。友善鼓励，用王者荣耀段位评价。

## 标签规范（严格遵守）
必须覆盖全部六个维度，每维度恰好 1 个标签（只有模块可以多个）。输出 JSON 时六个维度分别填入字段：size=规模、priority=优先级、rank=段位、category=类型、modules=模块(数组)、status=状态：
- 规模：规模：XS / 规模：S / 规模：M / 规模：L / 规模：XL
- 优先级：优先级：P0 / 优先级：P1 / 优先级：P2 / 优先级：P3
- 段位：段位：未定级 / 段位：倔强青铜 / 段位：秩序白银 / 段位：荣耀黄金 / 段位：永恒钻石 / 段位：至尊星耀 / 段位：最强王者（只能打1个！）
- 类型：类型：Bug / 类型：功能请求 / 类型：文档 / 类型：数据 / 类型：问题咨询 / 类型：重构
- 模块：模块：智能体 / 模块：议会辩论 / 模块：流程编排 / 模块：校验层 / 模块：知识图谱 / 模块：前端 / 模块：后端API / 模块：部署（可以根据实际情况打多个）
- 状态：状态：需要更多信息 / 状态：等待确认 / 状态：已确认 / 状态：进行中 / 状态：等待审核 / 状态：准备合并 / 状态：已过时

## 审查要求
- 代码逻辑、类型安全、组件设计、潜在 bug、性能问题
- 指出具体文件路径和行号，给出修改示例代码
- 段位评定基于 Issue 清晰度（复现步骤/截图/环境）或 PR 改动质量（合理性/代码质量/说明）

## 输出格式
纯 JSON，不要 markdown 包裹：{"type":"issue或pull_request","summary":"一句话中文总结","size":"规模名","priority":"优先级名","rank":"段位名","category":"类型名","modules":["模块名"],"status":"状态名","rank_reason":"为什么是这个段位","pros":["优点"],"cons":["需要改进的地方"],"comment":"给作者的 Markdown 审查回复","should_close":false,"close_reason":""}`;

// 审查时使用精简版指令，留空间给代码 diff
const REVIEW_PREFIX = "你是云观星传项目的 AI 维护助手（LiGuiyu-AI），审查 Python+FastAPI 后端、React+TypeScript 前端代码。友善鼓励。\n\n## 标签规范（严格遵守）\n必须覆盖全部六个维度，每维度恰好 1 个标签（模块除外，可以多个）。输出 JSON 时六个维度分别填入字段：size=规模、priority=优先级、rank=段位、category=类型、modules=模块(数组)、status=状态：\n- 规模：规模：XS / 规模：S / 规模：M / 规模：L / 规模：XL\n- 优先级：优先级：P0 / 优先级：P1 / 优先级：P2 / 优先级：P3\n- 段位：段位：未定级 / 段位：倔强青铜 / 段位：秩序白银 / 段位：荣耀黄金 / 段位：永恒钻石 / 段位：至尊星耀 / 段位：最强王者（只能打1个）\n- 类型：类型：Bug / 类型：功能请求 / 类型：文档 / 类型：数据 / 类型：问题咨询 / 类型：重构\n- 模块：模块：智能体 / 模块：议会辩论 / 模块：流程编排 / 模块：校验层 / 模块：知识图谱 / 模块：前端 / 模块：后端API / 模块：部署（可以多个）\n- 状态：状态：需要更多信息 / 状态：等待确认 / 状态：已确认 / 状态：进行中 / 状态：等待审核 / 状态：准备合并 / 状态：已过时\n\n审查代码逻辑、类型安全、组件设计、潜在 bug。指出文件行号，给示例代码。\n\n输出 JSON：{\"type\",\"summary\",\"size\",\"priority\",\"rank\",\"category\",\"modules\",\"status\",\"rank_reason\",\"pros\",\"cons\",\"comment\",\"should_close\",\"close_reason\"}\n\n---\n\n";

// ============================================================
// 代码上下文获取
// ============================================================

/** 获取 PR 的实际代码变更 diff */
async function fetchPRDiff(prNumber) {
  try {
    const files = await ghAPI(`/pulls/${prNumber}/files?per_page=100`);
    if (!files.length) return "(无文件变更)";

    let diff = `共 ${files.length} 个文件变更：\n`;
    for (const f of files) {
      diff += `\n--- ${f.filename} (${f.status}: +${f.additions} -${f.deletions}) ---\n`;
      if (f.patch) {
        const patch = f.patch.length > 16000
          ? f.patch.slice(0, 16000) + `\n... (截断，共 ${f.patch.length} 字符)`
          : f.patch;
        diff += "```diff\n" + patch + "\n```\n";
      } else {
        diff += "(二进制或过大，无 patch)\n";
      }
    }
    // 总上限 ~64000 字符
    return diff.length > 64000 ? diff.slice(0, 64000) + "\n... (diff 过长已截断)" : diff;
  } catch (e) {
    return `(获取 diff 失败: ${e.message})`;
  }
}

/** 获取 PR 变更文件概览（仅文件名+统计，WAF 限制不拉全文） */
async function fetchPRFileContents(prNumber) {
  try {
    const files = await ghAPI(`/pulls/${prNumber}/files?per_page=30`);
    return files.slice(0, 15).map(f =>
      `- ${f.filename} (${f.status}: +${f.additions} -${f.deletions})`
    ).join("\n");
  } catch {
    return "";
  }
}

/** 根据文件扩展名猜测语言 */
function guessLang(filename) {
  const ext = (filename || "").split(".").pop();
  const map = { ts: "typescript", tsx: "tsx", js: "javascript", jsx: "jsx",
    json: "json", css: "css", yml: "yaml", yaml: "yaml", md: "markdown",
    py: "python", html: "html", svg: "svg" };
  return map[ext] || "";
}

/** 从 Issue 标题和正文提取搜索关键词 */
function extractKeywords(title, body) {
  const text = (title + " " + (body || "")).toLowerCase();
  // 匹配常见组件/文件名
  const patterns = [
    /(science_agent|context_agent|hypothesis_agent|strategy_agent|evaluator_agent|humanist_agent)/gi,
    /(debate_engine|speaker|parliament|cognitive_parliament)/gi,
    /(pipeline|cross_validator|kg_checker|rag_checker|external_validator|report_generator)/gi,
    /(knowledge|vector_store|kg_builder|experience_store|wikidata_enricher)/gi,
    /(export_service|outputs|analyze|strategies|hypotheses|verify)/gi,
    /(researchoutput|crosscultural|taskcenter|dashboard|knowledgegraph|parliament)/gi,
    /(\.tsx|\.ts|\.py|research|export)/gi,
    /(智能体|议会|辩论|流程|校验|知识图谱|向量|搜索|导出|成果|部署|RAG|AI|Agent)/g,
  ];
  const keywords = [];
  for (const p of patterns) {
    const matches = text.match(p);
    if (matches) keywords.push(...matches);
  }
  return [...new Set(keywords)].slice(0, 6);
}

/** 为 Issue 搜索相关代码文件 */
async function fetchIssueCodeContext(title, body) {
  const keywords = extractKeywords(title, body);
  if (!keywords.length) return "";

  let context = "";
  for (const kw of keywords.slice(0, 4)) {
    try {
      const q = encodeURIComponent(`${kw} repo:${CONFIG.REPO}`);
      const results = await ghAPI(`https://api.github.com/search/code?q=${q}&per_page=3`);
      for (const item of (results.items || []).slice(0, 2)) {
        try {
          const content = await ghAPI(item.url);
          const decoded = Buffer.from(content.content || "", "base64").toString("utf-8");
          const snippet = decoded.length > 6000
            ? decoded.slice(0, 6000) + "\n... (截断)"
            : decoded;
          context += `\n### ${item.path}\n\`\`\`${guessLang(item.path)}\n${snippet}\n\`\`\`\n`;
        } catch { /* 跳过 */ }
      }
    } catch { /* 搜索失败，继续下一个关键词 */ }
  }
  return context.length > 12000 ? context.slice(0, 12000) + "\n... (截断)" : context;
}

async function analyzeItem(item) {
  const isPR = !!item.pull_request;
  const title = item.title || "";
  const body = (item.body || "").slice(0, 15000);
  const author = item.user?.login || "未知";
  const labels = (item.labels || []).map((l) => l.name).join(", ") || "无";

  const context = [
    `类型: ${isPR ? "Pull Request" : "Issue"}`,
    `编号: #${item.number}`,
    `标题: ${title}`,
    `作者: @${author}`,
    `当前标签: ${labels}`,
    `创建: ${item.created_at}`,
    `更新: ${item.updated_at}`,
    `内容:\n${body}`,
  ];

  // ——— PR：拉取实际代码 diff 和新文件内容 ———
  if (isPR) {
    context.push(
      `分支: ${item.head?.ref || "?"} → ${item.base?.ref || "?"}`,
      `文件: ${item.changed_files ?? "?"} | +${item.additions ?? "?"} -${item.deletions ?? "?"}`,
    );
    log(`  📥 获取 PR diff...`);
    const [diff, fileContents] = await Promise.all([
      fetchPRDiff(item.number),
      fetchPRFileContents(item.number),
    ]);
    if (diff) context.push(`## 代码变更 (diff)\n${diff}`);
    if (fileContents) context.push(`## 变更文件内容\n${fileContents}`);
  }

  // ——— Issue：搜索相关代码 ———
  if (!isPR) {
    log(`  🔍 搜索相关代码...`);
    const codeCtx = await fetchIssueCodeContext(title, body);
    if (codeCtx) context.push(`## 相关代码\n${codeCtx}`);
  }

  try {
    // 提取描述中的图片，多模态发送给模型
    const images = extractImageUrls(body);
    if (images.length) log(`  🖼️ 检测到 ${images.length} 张图片`);

    // Issue 无代码 diff，用完整指令；PR 用精简指令留空间给 diff
    const prefix = isPR ? REVIEW_PREFIX : SYSTEM_PROMPT;
    const userMsg = prefix + context.join("\n\n---\n\n");

    // 有图片时用多模态格式（文本 + 图片），否则保持纯文本
    const userContent = images.length > 0
      ? [
          { type: "text", text: userMsg },
          ...images.map(url => ({ type: "image_url", image_url: { url } })),
        ]
      : userMsg;

    const data = callDeepSeek([
      { role: "user", content: userContent },
    ]);

    const content = data.choices?.[0]?.message?.content || "";
    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      log(`  ⚠️ AI 输出无法解析: ${content.slice(0, 150)}`);
      return null;
    }

    const result = JSON.parse(jsonMatch[0]);
    // 规范化 labels：确保是数组，过滤空值（GLM 等模型可能返回空字符串）
    if (result.labels) {
      result.labels = (Array.isArray(result.labels) ? result.labels : [result.labels])
        .filter(l => typeof l === "string" && l.trim());
    }
    // 规范化 pros/cons：模型偶发返回字符串而非数组。buildReviewComment 用 for...of
    // 遍历，字符串会被逐字符迭代，导致评论「一个字一行」。统一转成字符串数组
    // （字符串 → 单元素数组），与上面 labels 的归一化同一模式。
    const toStrArray = (v) =>
      Array.isArray(v)
        ? v.filter((x) => typeof x === "string" && x.trim())
        : typeof v === "string" && v.trim()
          ? [v.trim()]
          : [];
    result.pros = toStrArray(result.pros);
    result.cons = toStrArray(result.cons);
    log(`  📝 ${result.summary || "?"} | 🏆 ${result.rank || "?"}`);
    return result;
  } catch (e) {
    log(`  ❌ AI 失败: ${e.message}`);
    return null;
  }
}

// ============================================================
// LiGuiyu-AI 风格评论
// ============================================================

const RANK_ICONS = {
  "未定级": "❓", "倔强青铜": "🥉", "秩序白银": "🥈",
  "荣耀黄金": "🥇", "永恒钻石": "💎", "至尊星耀": "🌟", "最强王者": "👑",
};

const RANK_EXPLAIN = {
  "未定级": "信息不足，尚无法评估质量",
  "倔强青铜": "初具雏形，仍需补充大量信息",
  "秩序白银": "基本清晰，可以正常处理",
  "荣耀黄金": "描述完整，质量不错",
  "永恒钻石": "高质量，细节到位",
  "至尊星耀": "非常出色，堪称范例",
  "最强王者": "顶级质量，完美无瑕",
};

function buildAckComment(item) {
  const typeStr = item.pull_request ? "PR" : "Issue";
  return [
    "> 🤖 **LiGuiyu-AI** · 正在查看",
    "",
    `👀 收到 ${typeStr} #${item.number}，正在分析……`,
    "",
    "---",
    "<sub>⚙️ 自动响应 · 分析完成后会更新评论</sub>",
  ].join("\n");
}

function buildReviewComment(item, result) {
  const rank = String(result.rank || "未定级").replace(/^段位[：:]/, "").trim() || "未定级";
  const icon = RANK_ICONS[rank] || "❓";
  const explain = RANK_EXPLAIN[rank] || "";

  const lines = [
    "> 🤖 **LiGuiyu-AI** · 审查完成",
    "",
    "### 📋 概要",
    result.summary || "(无法总结)",
    "",
  ];

  if (result.pros?.length > 0) {
    lines.push("### ✅ 优点");
    for (const p of result.pros) lines.push(`- ${p}`);
    lines.push("");
  }

  if (result.cons?.length > 0) {
    lines.push("### ⚠️ 需要注意");
    for (const c of result.cons) lines.push(`- ${c}`);
    lines.push("");
  }

  lines.push(
    `### 🏆 段位评定：${icon} ${rank}`,
    "",
    `> **${rank}** — ${explain}`,
    "",
  );
  if (result.rank_reason) lines.push(result.rank_reason, "");

  const displayLabels = Array.isArray(result.labels)
    ? result.labels.filter(l => typeof l === "string" && l.trim())
    : [];
  if (displayLabels.length > 0) {
    lines.push(
      "### 🔖 标签",
      "",
      displayLabels.map((l) => `\`${l}\``).join(" "),
      "",
    );
  }

  lines.push(
    "---",
    "<details>",
    "<summary>📊 段位排名简介</summary>",
    "",
    "| 段位 | 含义 |",
    "|------|------|",
    "| 👑 最强王者 | 顶级质量，完美无瑕 |",
    "| 🌟 至尊星耀 | 非常出色，堪称范例 |",
    "| 💎 永恒钻石 | 高质量，细节到位 |",
    "| 🥇 荣耀黄金 | 描述完整，质量不错 |",
    "| 🥈 秩序白银 | 基本清晰，可以正常处理 |",
    "| 🥉 倔强青铜 | 初具雏形，仍需补充 |",
    "| ❓ 未定级 | 信息不足，尚无法评估 |",
    "",
    "</details>",
    "",
    `<sub>🤖 自动生成 · 有疑问请 @LiGuiyu-AI · [标签说明](https://github.com/${CONFIG.REPO}/blob/main/docs/labels.md)</sub>`,
  );

  return lines.join("\n");
}

// ============================================================
// 处理单个 Item（两阶段评论，原地更新已有评论）
// ============================================================

/** 查找 Bot 在指定 Issue/PR 上的最新评论 ID */
async function findBotCommentId(issueNumber) {
  try {
    const comments = await ghAPI(
      `/issues/${issueNumber}/comments?per_page=100&sort=created&direction=desc`
    );
    const botComment = comments.find((c) => c.user?.login === CONFIG.BOT_LOGIN);
    return botComment ? botComment.id : null;
  } catch {
    return null;
  }
}

async function processItem(item, reason) {
  const num = item.number;
  const typeStr = item.pull_request ? "PR" : "Issue";

  log(`\n🔍 [${reason}] ${typeStr} #${num}: ${(item.title || "").slice(0, 60)}`);

  // 查找已有机器人评论 → 原地更新，不新建
  const existingId = await findBotCommentId(num);

  // 阶段一：确认评论
  const ackBody = buildAckComment(item);
  let commentId;
  if (existingId) {
    await updateComment(existingId, ackBody);
    commentId = existingId;
    log(`  🔄 原地更新已有评论`);
  } else {
    commentId = await postComment(num, ackBody);
    if (commentId) log(`  👀 确认评论已发`);
  }

  // 阶段二：AI 分析
  const result = await analyzeItem(item);
  if (!result) {
    if (commentId) {
      await updateComment(commentId, ackBody.replace("正在分析……", "分析遇到问题，请稍后重试或 @LiGuiyu-AI"));
    }
    return false;
  }

  // 打标签
  const validNew = buildLabelsFromResult(result);
  if (validNew.length > 0) {
    const existingLabels = (item.labels || []).map((l) => l.name);
    await setLabels(num, [...new Set([...existingLabels, ...validNew])]);
    log(`  🏷️ ${validNew.join(", ")}`);
  }

  // 发布完整审查（更新已有评论）
  const reviewBody = buildReviewComment(item, result);
  if (commentId) {
    await updateComment(commentId, reviewBody);
  } else {
    await postComment(num, reviewBody);
  }
  log(`  ✅ 审查完成`);

  return true;
}

// ============================================================
// 增量扫描
// ============================================================

async function sweepIncremental() {
  log("=".repeat(50));
  log("🔍 增量扫描");

  const state = loadState();
  const now = new Date();
  const windowStart = new Date(now.getTime() - 30 * 60 * 1000);

  const allIssues = await ghAPI(
    `/issues?state=open&since=${windowStart.toISOString()}&sort=updated&direction=desc&per_page=30`
  );
  const botLogin = CONFIG.BOT_LOGIN;
  const candidates = allIssues.filter((i) => i.user?.login !== botLogin);

  if (candidates.length === 0) {
    log("  ℹ️ 没有新 Item");
  } else {
    log(`  📋 ${candidates.length} 个候选`);
    let n = 0;
    for (const item of candidates) {
      if (n >= CONFIG.MAX_ITEMS_PER_RUN) break;
      // PR 需要额外拉取 head.sha（Issues API 不包含）
      if (item.pull_request) {
        try {
          const pr = await ghAPI(item.pull_request.url);
          item.head = pr.head;
          item.base = pr.base;
        } catch { /* 拉取失败用原有数据 */ }
      }
      const num = item.number;
      const last = state.reviewed[num];
      const fingerprint = getContentFingerprint(item);

      // 内容指纹未变 → 只是标签/指派人/评论等元数据变动，跳过
      if (last && fingerprint === last.hash) {
        log(`  ⏭️ #${num} 内容未变，跳过（仅元数据变动）`);
        continue;
      }

      const createdTs = new Date(item.created_at).getTime();
      const reason = !last ? "新创建" : "内容有更新";

      // AI 失败冷却：同一指纹失败后 1 小时内不再重试，避免大 diff 反复超时
      if (last?.aiFailed && last.hash === fingerprint) {
        const cooldownMs = 60 * 60 * 1000; // 1 小时
        if (Date.now() - last.at < cooldownMs) {
          log(`  ⏭️ #${num} AI 上次分析失败，冷却中（${Math.round((cooldownMs - Date.now() + last.at) / 60000)}分钟后重试）`);
          continue;
        }
      }

      const success = await processItem(item, reason);
      state.reviewed[num] = {
        at: Date.now(),
        hash: fingerprint,
        reason,
        ...(success ? {} : { aiFailed: true }),
      };
      saveState(state); // 逐项持久化，防止后续 item 失败导致前面的结果丢失
      n++;
    }
    log(`  ✅ 处理 ${n} 个`);
  }

  await sweepMentions(state, now);
  saveState(state);
}

// ============================================================
// @bot 提及
// ============================================================

async function sweepMentions(state, now = new Date()) {
  log("\n💬 检查 @bot 提及...");

  try {
    const comments = await ghAPI(
      `https://api.github.com/repos/${CONFIG.REPO}/issues/comments?sort=updated&direction=desc&per_page=20`
    );

    const windowStart = now.getTime() - 30 * 60 * 1000;
    let count = 0;

    for (const c of comments) {
      const ct = new Date(c.updated_at).getTime();
      if (ct < windowStart) continue;
      if (c.user?.login === CONFIG.BOT_LOGIN) continue;

      const bodyText = c.body || "";
      const mentioned =
        new RegExp(`@${CONFIG.BOT_LOGIN}\\b`, "i").test(bodyText) ||
        /@bot\b/i.test(bodyText);
      if (!mentioned) continue;

      const num = extractIssueNumber(c.issue_url);
      if (!num) continue;

      const key = `mention_${num}`;
      if (state.reviewed[key] && state.reviewed[key].at >= ct) continue;

      log(`  📣 #${num} 被 @ 提及`);
      try {
        const item = await ghAPI(`/issues/${num}`);
        // PR 需要额外拉取 head.sha（Issues API 不包含）
        if (item.pull_request) {
          const pr = await ghAPI(item.pull_request.url);
          item.head = pr.head;
          item.base = pr.base;
        }
        await processItem(item, "被 @ 提及");
        state.reviewed[key] = { at: now.getTime() };
        // 提及处理后更新内容指纹，下次增量扫描不会产生误判
        state.reviewed[num] = { at: now.getTime(), hash: getContentFingerprint(item), reason: "被 @ 提及" };
        count++;
      } catch (e) {
        log(`  ⚠️ #${num}: ${e.message}`);
        // 仅在无现有真实记录时才写入失败标记，避免覆盖正常指纹
        if (!state.reviewed[num]?.hash) {
          state.reviewed[num] = { at: now.getTime(), hash: getContentFingerprint({ title: "", body: "" }), reason: "被 @ 提及", aiFailed: true };
        }
      }
    }

    if (count === 0) log("  ℹ️ 无新提及");
  } catch (e) {
    log(`  ⚠️ 检查提及失败: ${e.message}`);
  }
}

// ============================================================
// 每日巡检
// ============================================================

async function sweepDaily() {
  log("=".repeat(50));
  log("📅 每日全量巡检");

  const state = loadState();
  const today = new Date().toISOString().slice(0, 10);
  if (state.lastDailySweep === today) {
    log("  ℹ️ 今天已跑过");
    return;
  }

  const [issues, prs] = await Promise.all([
    ghAPI("/issues?state=open&per_page=50&sort=updated&direction=desc"),
    ghAPI("/pulls?state=open&per_page=30&sort=updated&direction=desc"),
  ]);

  const botLogin = CONFIG.BOT_LOGIN;
  const allItems = [
    ...issues.filter((i) => !i.pull_request && i.user?.login !== botLogin),
    ...prs.filter((p) => p.user?.login !== botLogin),
  ];

  log(`  📋 ${allItems.length} 个开放 Item`);

  const now = Date.now();
  const DAY = 24 * 60 * 60 * 1000;
  let staleN = 0, labelN = 0;

  for (const item of allItems) {
    const existingLabels = (item.labels || []).map((l) => l.name);

    // 缺标签 → 补
    if (!existingLabels.some((l) => VALID_LABELS.includes(l))) {
      const key = `labeled_${item.number}`;
      if (!state.reviewed[key]) {
        log(`  🏷️ #${item.number} 缺标签`);
        const result = await analyzeItem(item);
        const newLabels = buildLabelsFromResult(result);
        if (newLabels.length > 0) {
          await setLabels(item.number, [...new Set([...existingLabels, ...newLabels])]);
          labelN++;
        }
        state.reviewed[key] = { at: now };
      }
    }

    // 过时检查
    const age = Math.floor((now - new Date(item.updated_at).getTime()) / DAY);
    if (age >= 60 && existingLabels.length === 0) {
      log(`  🕐 #${item.number} ${age}天 → 过时提醒`);
      await postComment(item.number, [
        "### 🕐 这条 Issue 已经很久没有更新了",
        `最近活动 ${item.updated_at?.slice(0, 10)}（${age} 天前）。`,
        "如果问题还存在说一声就好，Bot 会重新审核～",
      ].join("\n\n"));
      staleN++;
    } else if (age >= 30 && age < 60) {
      const key = `nudge_${item.number}`;
      if (!state.reviewed[key] || now - state.reviewed[key].at > 7 * DAY) {
        log(`  💡 #${item.number} ${age}天 → 友情提醒`);
        await postComment(item.number, `### 💡 友情提醒\n\n这条 Issue 已经 ${age} 天没有更新啦，确认一下问题是否还存在～`);
        state.reviewed[key] = { at: now };
        staleN++;
      }
    }
  }

  state.lastDailySweep = today;
  saveState(state);
  log(`  ✅ 补标签 ${labelN} | 过时处理 ${staleN}`);
}

// ============================================================
// 历史回填：给所有 Issue/PR 打新标签
// ============================================================

async function backfill() {
  log("=".repeat(50));
  log("📦 历史回填模式");

  const state = loadState();
  const now = Date.now();

  log("\n📋 获取所有 Issue...");
  const allIssues = [];
  for (let page = 1; page <= 10; page++) {
    const items = await ghAPI(
      `/issues?state=all&per_page=100&page=${page}&sort=created&direction=asc`
    );
    if (items.length === 0) break;
    allIssues.push(...items.filter((i) => !i.pull_request));
  }

  log("📋 获取所有 PR...");
  const allPRs = [];
  for (let page = 1; page <= 10; page++) {
    const items = await ghAPI(
      `/pulls?state=all&per_page=100&page=${page}&sort=created&direction=asc`
    );
    if (items.length === 0) break;
    allPRs.push(...items);
  }

  const total = allIssues.length + allPRs.length;
  log(`📊 ${allIssues.length} Issue + ${allPRs.length} PR = ${total} 项\n`);

  let processed = 0;
  for (const item of [...allIssues, ...allPRs]) {
    const key = `backfill_${item.number}`;
    if (state.reviewed[key]) continue;

    const typeStr = item.pull_request ? "PR" : "Issue";
    log(`🔍 [回填] ${typeStr} #${item.number}: ${(item.title || "").slice(0, 60)}`);

    const result = await analyzeItem(item);
    const validLabels = buildLabelsFromResult(result);
    if (validLabels.length > 0) {
      await setLabels(item.number, validLabels);
      log(`  🏷️ ${validLabels.join(", ")} | 🏆 ${result.rank || "?"}`);
      processed++;
    }

    state.reviewed[key] = { at: now };
    if (processed % 10 === 0) saveState(state);
  }

  saveState(state);
  log(`\n✅ 回填完成: ${processed} 项`);
}

// ============================================================
// 文件锁（防止 cron 并发导致状态覆盖）
// ============================================================

function acquireLock() {
  if (existsSync(CONFIG.LOCK_FILE)) {
    try {
      const raw = readFileSync(CONFIG.LOCK_FILE, "utf-8");
      const lock = JSON.parse(raw);
      const age = Date.now() - lock.at;
      // 锁文件超过 15 分钟自动视为过期（进程可能被 SIGKILL）
      if (age < 15 * 60 * 1000) {
        log(`⏭️ 已有实例运行中（${Math.round(age / 1000)}秒前启动），跳过本次执行`);
        process.exit(0);
      }
      log(`⚠️ 发现过期锁（${Math.round(age / 1000)}秒未更新），强制接管`);
    } catch {}
  }
  const lock = { pid: process.pid, at: Date.now() };
  writeFileSync(CONFIG.LOCK_FILE, JSON.stringify(lock));
  return true;
}

function releaseLock() {
  try { unlinkSync(CONFIG.LOCK_FILE); } catch {}
}

// 异常退出时也清理锁（15 分钟过期是最后保险）
process.on("exit", () => releaseLock());
process.on("SIGINT", () => { releaseLock(); process.exit(130); });
process.on("SIGTERM", () => { releaseLock(); process.exit(143); });

// ============================================================
// 入口
// ============================================================

async function main() {
  if (!CONFIG.GH_TOKEN) {
    log("❌ 缺少 GH_TOKEN");
    process.exit(1);
  }

  acquireLock();

  await ensureLabelsExist();

  const mode = process.argv[2] || "incremental";
  try {
    if (mode === "daily") { await sweepDaily(); await sweepIncremental(); }
    else if (mode === "backfill") { await backfill(); }
    else { await sweepIncremental(); }
  } catch (e) {
    log(`❌ ${e.message}`);
    releaseLock();
    process.exit(1);
  }

  releaseLock();
  log("🏁 完成\n");
}

main();
