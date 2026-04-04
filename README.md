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

## 数据源说明
- 默认优先使用 Binance 实时接口（`api.binance.com` + `fapi.binance.com`），并自动携带 `BINANCE_API_KEY` 请求头。
- Alpha 在本项目中表示“币安 Alpha/新上市机会分类”，不等同于对冲套利语义。
- Alpha 分类使用 Binance Alpha 官方文档接口：
	- `https://www.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list`
	- `https://www.binance.com/bapi/defi/v1/public/alpha-trade/get-exchange-info`
- 仅出现在官方 Alpha token 列表且交易对信息状态为 `TRADING` 的标的才标记为 alpha。

## 提交规范
- 每次提交标题前缀版本号，示例：`[v0.6.1] feat: 修复 Alpha 分类误判`。

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
- 每小时报告默认写入 `reports/` 目录。
- 当前仅允许模拟模式，禁止实盘下单。
- 前端默认只读观察，不提供人工交易控制按钮。

## 报告与日志
- 最新报告接口：`/api/reports/latest`
- 报告列表接口：`/api/reports`
- 运行日志接口：`/api/logs/tail`
- Fly 命令查看（示例）：
	- `flyctl ssh console -a git-binance-trader-sim -C "ls -lah reports"`
	- `flyctl ssh console -a git-binance-trader-sim -C "cat reports/latest.md"`
	- `flyctl ssh console -a git-binance-trader-sim -C "tail -n 120 logs/strategy.log"`
