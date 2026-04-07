# git_binance_trader_ai (独立AI项目)

这是与人类项目完全分离的 AI 版本工程。

## 特性
- 深色治理看板（专业仪表风格）
- 人类最高权限动作：全面暂停、恢复、全面平仓、全面停止
- AI 行为可见化：实时显示 AI 最近动作和系统状态
- 人类输入框：将指令写入 AI 指令记忆文件
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
