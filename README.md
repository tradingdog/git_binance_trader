# git_binance_trader

仅用于模拟资金的币安量化交易系统。

## 当前能力
- FastAPI 后端接口
- 模拟账户与风控引擎
- 后台循环执行策略、净值历史落盘与每小时报告写盘
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
- 为保证真实性，已关闭任何随机/种子伪造行情回退；当 API 拉取失败时该轮策略将跳过交易。
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

## 观察面板能力
- 持仓上方新增净值曲线图，支持 1 小时、4 小时、日线、周线切换，默认展示 1 小时。
- 净值曲线新增 X/Y 坐标轴与悬浮提示，可查看某一点的时间和净值。
- 各时间窗（1小时/4小时/日线/周线）按真实时间范围计算，并支持横轴拖动回看历史窗口。
- 净值历史持久化到持久目录，重启后仍可继续展示最近一周净值走势。
- 存储守护策略默认要求至少保留 1500MB 可用空间；不足时自动裁剪旧报告、旧净值历史和旧日志。
- 成交明细和日志面板支持滚动大窗口，默认展示 500 条，可切换 1000/2000/5000 条。
- 日志面板提供一键复制功能，便于复盘与排查。

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
- 每小时报告、运行日志、净值历史默认写入 `data/` 持久目录下的子目录。
- 当前仅允许模拟模式，禁止实盘下单。
- 前端默认只读观察，不提供人工交易控制按钮。

## 报告与日志
- 最新报告接口：`/api/reports/latest`
- 报告列表接口：`/api/reports`
- 运行日志接口：`/api/logs/tail`
- 持久卷建议：Fly 使用 2GB 卷挂载到 `/data`，并设置 `PERSISTENT_DATA_DIR=/data`。
- Fly 命令查看（示例）：
	- `flyctl ssh console -a git-binance-trader-sim -C "ls -lah /data/reports"`
	- `flyctl ssh console -a git-binance-trader-sim -C "cat /data/reports/latest.md"`
	- `flyctl ssh console -a git-binance-trader-sim -C "tail -n 120 /data/logs/strategy.log"`
