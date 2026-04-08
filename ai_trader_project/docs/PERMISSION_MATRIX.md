# 权限矩阵（AI治理项目）

## 角色定义
- Human Root: 唯一最高权限，具备冻结自治、回滚、审批、配置变更、任务控制。
- Researcher AI: 仅研究与提交候选，不允许发布与改配置。
- Validator AI: 仅验证与风控审查，不允许改配置。
- Releaser AI: 仅发布与回滚链路，不允许改代码。
- Viewer: 只读。

## 动作矩阵
| 动作 | human_root | researcher_ai | validator_ai | releaser_ai | viewer |
|---|---|---|---|---|---|
| pause/resume/emergency_close/halt | Y | N | N | N | N |
| freeze_autonomy | Y | N | N | N | N |
| rollback | Y | N | N | Y | N |
| approve | Y | N | N | N | N |
| update_config | Y | N | N | N | N |
| control_task | Y | N | N | N | N |
| submit_candidate | N | Y | N | N | N |
| validate/risk_check | N | N | Y | N | N |
| release | N | N | N | Y | N |
| read_all | Y | Y | Y | Y | Y |

## 审批规则
- 高风险动作（deploy/release/rollback/halt/promote）必须进入审批队列。
- 低风险动作可根据配置 `auto_approve_low_risk` 自动通过。

## 安全边界
- 禁止实盘模式；风险闸门默认 SIMULATION。
- Human Root 是唯一可修改治理配置和审批决策的角色。
