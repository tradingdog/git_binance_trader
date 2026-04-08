# 审计日志规范（AI治理项目）

## 目标
- 保证所有关键治理动作可追踪、可回放、可追责。

## 事件结构
- id: 审计事件唯一ID
- created_at: 事件时间（UTC）
- category: 分类（command/config/release/rollback/risk/workflow/task/backtest）
- actor: 触发者（human/researcher_ai/validator_ai/releaser_ai/risk_guard）
- message: 摘要
- detail: 结构化上下文（候选ID、审批ID、风险值、评分、异常信息）

## 存储与查询
- 引擎内保持最近事件缓冲区。
- 治理总览载荷输出 `audit_events`。
- 审计回放接口：`GET /api/audit/replay?limit=N`。

## 责任链要求
- 每个高风险动作必须记录：发起人、审批人、决策结果、执行结果。
- 每次参数更新必须记录更新来源与关键字段。

## 回放要求
- 按时间逆序输出最近N条事件。
- 同时保留 category + actor + detail，便于复盘定位。
