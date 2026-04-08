# AI项目更新日志

## v0.1.5 - 2026-04-08
- 新增 GitHub Actions 工作流：`.github/workflows/ai-governance-ci.yml`，对 AI 子项目启用测试、风险模式闸门（强制 SIMULATION）与 gitleaks 密钥扫描。
- 新增 `CODEOWNERS`，为 AI 项目与 CI 配置提供审阅责任锚点。
- 新增治理文档与交付物：
	- 权限矩阵文档 `ai_trader_project/docs/PERMISSION_MATRIX.md`
	- 审计日志规范 `ai_trader_project/docs/AUDIT_LOG_SPEC.md`
	- 主干保护规则说明 `ai_trader_project/docs/BRANCH_PROTECTION_RULES.md`
	- 回测/压力测试/候选榜单模板 `ai_trader_project/reports/templates/*.md`
- 清单推进：P0/P1/P2 阶段项与对应交付物完成状态已回填勾选，Step1/Step2/Step3 标记完成。

## v0.1.4 - 2026-04-08
- 新增结构化指令通道：`/api/ai/command/structured` 支持优先级、生效范围、目标权重、截止时间、回滚条件与幂等键，避免重复执行。
- 新增任务控制通道：`/api/tasks/{task_id}/control` 支持暂停/重试/终止，补齐任务队列的人机协同控制能力。
- 新增审计回放接口：`/api/audit/replay`，支持按时间线回放治理事件，强化可追责与可解释。
- 引擎新增可靠性能力：幂等缓存、失败重试计数、超时补偿计数、告警缓冲；治理载荷新增 `reliability` 字段。
- 引擎新增回测执行器与压力测试摘要：多窗口回测、显著性指标（`p_value`、`confidence`）、极端场景指标写入 `backtests`。
- 新增参数版本库与绩效版本库：治理载荷新增 `parameter_versions` 与 `performance_versions`，满足策略版本追踪。
- 风控增强：新增单笔亏损红线自动停机逻辑（按 `max_trade_loss_pct` 判定）。
- 前端看板新增结构化指令中心、任务控制按钮、可靠性状态面板，并展示周报数据。
- 测试扩展并通过：`python -m pytest -q` 结果 `6 passed`。

## v0.1.3 - 2026-04-08
- 按 `AUTONOMY_IMPLEMENTATION_CHECKLIST.md` 推进治理闭环：后端新增 RBAC 权限校验、审批流、候选策略评分与硬约束短路、冠军-挑战者灰度发布、快照回滚与审计事件链路。
- 新增治理 API：`/api/actions/freeze-autonomy`、`/api/actions/rollback`、`/api/governance/config`、`/api/governance/approvals/{approval_id}`，并统一接入 Human Root 角色动作权限。
- 治理看板扩展为八模块可视化：自治总控、目标与红线、审批队列、实验与回测中心、灰度发布中心、回滚与审计中心、报告面板与现有交易评估模块联动。
- 规则增强：高风险命令自动进入审批队列；命令白名单补充中文关键词（测试/回测/部署/回滚/优化/分析/暂停/恢复）。
- 测试更新并通过：`python -m pytest -q` 结果 `5 passed`，覆盖治理负载结构与新增治理动作接口。

## v0.1.2 - 2026-04-08
- 全链重构 AI 治理看板与引擎数据面：补齐净值、现金余额、保证金占用、持仓市值、手续费、已实现/未实现盈亏、总收益率、全程回撤、当日回撤、持仓数等核心评估指标。
- 新增头部 AI 成本看板：显示 Token 总消耗、输入/输出 Token、美元总成本，并支持按模型价格参数自动核算。
- 新增“AI正在做什么”可展开任务详情：点击任务标题可查看中文步骤明细，降低黑盒感。
- 新增持仓明细、成交记录、运行日志、AI行为记忆、人类命令历史等面板，支持完整评估 AI 运行效果。
- 后端 `/api/ai/governance` 与 `/api/dashboard` 输出扩展：包含 `ai_usage`、`positions`、`trades`、`runtime_logs`、`ai_tasks` 等结构化数据。
- 测试增强：新增看板数据结构断言与健康接口字段验证，当前 AI 项目测试通过（4项）。

## v0.1.1 - 2026-04-08
- 新增 `AUTONOMY_IMPLEMENTATION_CHECKLIST.md`，超详细拆解 AI 可控自治系统从治理底座到多代理闭环的分阶段执行清单。
- 清单覆盖：权限拆分、CI闸门、审计链路、目标函数机器可读化、五代理闭环、冠军-挑战者、灰度发布、自动回滚、前端8大模块、验收标准与阶段路线图。

## v0.1.0 - 2026-04-08
- 初始化独立 AI 项目（与人类项目完全分离）。
- 新增 AI 治理控制台（深色专业看板）：人类可执行全面暂停、恢复、全面平仓、全面停止。
- 新增 AI 行为记忆与人类指令记忆（JSONL 持久化）。
- 新增独立 Fly 配置（独立 app/独立网址）。
