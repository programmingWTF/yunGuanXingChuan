---
name: Pull Request
title: "<type>(<scope>): <简短描述>"
---

<!--
提交 PR 前请先阅读：
- CONTRIBUTING.md  https://github.com/programmingWTF/yunGuanXingChuan/blob/main/CONTRIBUTING.md
- GitHub 协作入门   https://github.com/programmingWTF/yunGuanXingChuan/blob/main/docs/github-guide.md

标题格式：<type>(<scope>): <简短描述>，例如：
  feat(kg): 知识图谱增加连通分量分区浏览
  fix(parliament): 修复辩论发言全文换行显示
-->

## 关联 Issue

> 有对应 Issue 请写在这里，合并后会自动关闭。格式：`Closes #编号`（可多个：`Closes #1, closes #2`）

Closes #编号

（如果没有对应 Issue，请先创建一个再关联，方便队友知道你在做什么）

---

## 改动内容

**做了什么**：
- 

**为什么这样做**：
- 

---

## 如何验证

- [ ] 后端：`python -m pytest tests/` 通过
- [ ] 前端：`npm run build` 通过（涉及前端改动时）
- [ ] 手动测试步骤：

---

## 截图（涉及 UI 改动必填）

> 把改动前后的界面截图直接拖进来，方便 Reviewer 直观确认。

（截图）

---

## 数据说明（涉及 `data/` 改动必填）

- 数据来源：
- 涉及文件：

---

## 检查清单

- [ ] 已从 `main` 拉取最新代码
- [ ] 提交信息符合 `<type>(<scope>): <描述>` 规范（scope 必填）
- [ ] `git status` 确认未夹带 `.env`、`node_modules`、临时文件
- [ ] 未提交任何 API Key / 敏感信息
- [ ] 至少一人 Review 通过后再合并
