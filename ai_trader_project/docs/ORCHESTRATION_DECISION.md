# 编排引擎选型记录

## 结论
- 当前阶段选择: Prefect（优先流程编排可视化与运维友好）。
- 选择方式: 先以内嵌工作流保持最小可用，再迁移到 Prefect durable execution。

## 选择理由
- 现阶段目标是快速观察治理流程与失败补偿路径，Prefect UI 对流程状态、重试、告警更直观。
- 团队当前更需要流程编排与运维可视化，而非复杂长事务一致性。

## 放弃项与保留项
- 暂不选 Temporal 的原因: 学习/维护成本更高，短期投入产出比不优。
- 保留项: 当后续进入跨服务强一致长事务时，重新评估 Temporal。

## 下一步迁移清单
- 把 monitor/research/validate/release/rollback 迁移为 Prefect flow/task。
- 对接任务超时、重试、补偿与告警通知。
- 接入 flow run 级幂等键与上下文恢复。
