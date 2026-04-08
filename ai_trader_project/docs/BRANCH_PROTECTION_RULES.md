# 主干保护建议规则

> 该文档用于记录需要在 GitHub 仓库设置中启用的保护规则。

## 目标分支
- main
- release/*

## 必开规则
- 禁止直接 push（Require pull request before merging）
- 至少 1 个审批通过
- 必须通过状态检查：
  - ai-governance-ci / test-and-security
- 关闭强制管理员绕过

## 高风险改动要求
- 修改以下路径必须人工审批：
  - ai_trader_project/src/ai_trader_project/engine.py
  - ai_trader_project/src/ai_trader_project/main.py
  - ai_trader_project/src/ai_trader_project/models.py
  - ai_trader_project/.env.example

## 风险说明
- 该规则文件是执行依据，实际生效依赖 GitHub 分支保护设置。
