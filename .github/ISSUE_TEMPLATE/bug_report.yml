---
name: Bug 报告
description: 发现了一个 Bug，来报告吧
title: "[Bug] <模块/页面>：<简短描述>"
body:
  - type: markdown
    attributes:
      value: |
        > [!NOTE]
        > 提 Issue 前请确认：不是重复提交、已经拉了最新代码（`git pull origin main`）、仓库里没有已修复的 PR。
  - type: textarea
    id: description
    attributes:
      label: Bug 描述
      description: 发生了什么问题？
      placeholder: 清楚地描述你遇到的 bug
    validations:
      required: true
  - type: textarea
    id: steps
    attributes:
      label: 复现步骤
      description: 怎么触发这个 bug？
      placeholder: |
        1. 打开页面...
        2. 点击...
        3. 看到错误
    validations:
      required: true
  - type: textarea
    id: expected
    attributes:
      label: 期望行为
      description: 原本期待发生什么？
      placeholder: 应该看到...
  - type: textarea
    id: screenshot
    attributes:
      label: 截图（可选）
      description: 有截图的话拖拽上传
  - type: input
    id: environment
    attributes:
      label: 运行环境
      description: 浏览器 / 设备 / 操作系统
      placeholder: 如 Chrome 120 / Windows 11
  - type: dropdown
    id: module
    attributes:
      label: 涉及模块
      description: 这个问题最可能和哪部分代码相关？
      options:
        - 不确定 / 需排查
        - 后端 API（api/）
        - 前端界面（frontend/）
        - 智能体 Agent（src/agents/）
        - 议会辩论（src/parliament/）
        - 知识图谱与数据（src/knowledge/、data/）
        - 校验层（src/verification/）
        - 流程编排（src/pipeline.py）
        - 部署与脚本（scripts/、docker-compose.yml）
    validations:
      required: true
  - type: markdown
    attributes:
      value: |
        ---
        > 💡 提完 Issue 后可以点击右侧 **Assignees** 认领这个任务，动手修复时记得先开分支、做完交 PR（详见 [CONTRIBUTING.md](../../CONTRIBUTING.md)）。
