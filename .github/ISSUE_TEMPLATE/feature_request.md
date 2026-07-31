---
name: 功能请求
description: 有新的想法或建议？告诉我们
title: "[Feat] <模块>：<简短描述>"
labels: ["enhancement"]
body:
  - type: markdown
    attributes:
      value: |
        > [!NOTE]
        > 功能请求前请确认：不是已有功能、不是已完成列表里有的、已经拉了最新代码（`git pull origin main`）。
  - type: textarea
    id: motivation
    attributes:
      label: 背景与动机
      description: 为什么需要这个功能？解决什么问题？
      placeholder: 做传播分析时经常需要...
    validations:
      required: true
  - type: textarea
    id: proposal
    attributes:
      label: 方案描述
      description: 你期望怎么实现？（不一定要技术方案，用日常语言描述即可）
      placeholder: 希望能增加一个...页面/接口/能力
    validations:
      required: true
  - type: textarea
    id: data
    attributes:
      label: 数据需求（可选）
      description: 是否需要新数据 / 语料 / 受众画像？由谁提供？
      placeholder: 需要补充某国媒体报道语料...
  - type: dropdown
    id: module
    attributes:
      label: 涉及模块
      description: 这个功能主要需要改哪部分？
      options:
        - 不确定 / 需讨论
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
        > 💡 功能确认后记得点击右侧 **Assignees** 认领，或用评论区「我来做这个」认领，避免重复开发。
