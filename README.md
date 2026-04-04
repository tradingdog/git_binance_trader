# git_binance_trader

仅用于模拟资金的币安量化交易系统。

## 当前能力
- FastAPI 后端接口
- 模拟账户与风控引擎
- 后台循环执行策略与日报落盘
- 轻量 Web 监控面板（观察者模式）
- 一键暂停交易与紧急平仓
- Fly.io 部署骨架

## 当前策略框架
- 机会评分：结合 24h 动量、流动性、市场类型（现货/永续/Alpha）评分筛选机会。
- 仓位管理：限制总暴露与持仓数量，单笔风险预算默认 0.35%。
- 持仓跟踪：内置止损、止盈与跟踪止盈机制，触发后自动平仓。
- 风险兜底：继续执行全程/单日/单笔亏损红线检查，触发即停机与清仓。

## 已部署地址
- 控制台：https://git-binance-trader-sim.fly.dev/
- 健康检查：https://git-binance-trader-sim.fly.dev/health

## 启动方式
```bash
uvicorn git_binance_trader.main:app --app-dir src --reload
```

## 测试
```bash
pytest
```

## 运行说明
- 服务启动后会按 `CYCLE_INTERVAL_SECONDS` 后台循环执行模拟策略。
- 每日复盘报告默认写入 `reports/` 目录。
- 当前仅允许模拟模式，禁止实盘下单。
- 前端默认只读观察，不提供人工交易控制按钮。
