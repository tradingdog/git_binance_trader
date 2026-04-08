# git_binance_trader_ai (独立AI项目)

这是与人类项目完全分离的 AI 版本工程。

## 特性
- 深色治理看板（专业仪表风格）
- 人类最高权限动作：全面暂停、恢复、全面平仓、全面停止
- 新增自治控制动作：冻结自治、一键回滚冠军
- AI 行为可见化：支持“AI正在做什么”任务标题点击展开中文步骤详情
- 人类输入框：将指令写入 AI 指令记忆文件
- 结构化指令中心：支持优先级/生效范围/目标权重/回滚条件/幂等键
- 任务队列控制：支持暂停、重试、终止
- 评估指标完整可视化：净值、现金余额、保证金占用、持仓市值、手续费、已实现/未实现盈亏、总收益率、全程/当日回撤
- 交易与运行面板：持仓明细、成交记录、运行日志、AI行为记忆、人类命令历史
- Token 与美元成本看板：显示输入/输出/缓存 token 与累计成本
- 回测与可靠性面板：多窗口回测摘要、可靠性计数（重试/超时/补偿）与告警
- 审计回放接口：支持按时间线回放治理事件
- 独立记忆文件：
  - `memory/ai-memory.jsonl`
  - `memory/human-commands.jsonl`

## 运行
```bash
uvicorn ai_trader_project.main:app --app-dir src --host 0.0.0.0 --port 8100
```

## 测试
```bash
pytest tests
```

## Fly 独立部署
```bash
flyctl deploy -c fly.toml --app git-binance-trader-ai
```

默认地址：
- https://git-binance-trader-ai.fly.dev/
