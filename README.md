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
- 机会评分（v2）：现货/永续/Alpha 三套独立评分模型，避免单一权重跨市场失真。
- 热点因子：在动量与流动性基础上，新增放量强度、波动挤压突破、跨市场强弱、社交热度代理、新币行为等因子。
- 仓位管理：限制总暴露与持仓数量，单笔风险预算默认 0.35%。
- 小时自适应：每小时根据平仓胜率、已实现盈亏与手续费表现自动收紧或放宽关键参数（开仓阈值、持仓上限、单仓预算等）。
- 持仓跟踪：内置止损、止盈与跟踪止盈机制，触发后自动平仓。
- 风险兜底：继续执行全程/单日/单笔亏损红线检查，触发即停机与清仓。

## 手续费口径
- 模拟撮合已纳入手续费：开仓和平仓均按市场类型费率扣费，收益按净口径（扣费后）统计。
- 默认费率（可通过环境变量覆盖）：
	- 现货 Maker/Taker：`SPOT_MAKER_FEE_RATE=0.00075`、`SPOT_TAKER_FEE_RATE=0.00075`
	- 永续 Maker/Taker：`PERPETUAL_MAKER_FEE_RATE=0.00018`、`PERPETUAL_TAKER_FEE_RATE=0.00045`
	- Alpha 分类币种复用现货双费率（不单独配置 Alpha 费率）。
- 下单类型自动选择：策略常规下单默认按 Maker 费率；`risk_guard` 风控/紧急类成交默认按 Taker 费率。
- 兼容说明：若仍使用旧变量 `SPOT_FEE_RATE` / `PERPETUAL_FEE_RATE`，系统会自动回退填充对应市场的 Maker/Taker。
- 看板与每小时报告会展示累计手续费，成交明细会展示每笔手续费。

## 数据源说明
- 默认优先使用 Binance 实时接口（`api.binance.com` + `fapi.binance.com`），并自动携带 `BINANCE_API_KEY` 请求头。
- 标的安全过滤：现货与永续均通过 Binance `exchangeInfo` 二次校验，仅 `TRADING` 状态交易对允许进入策略池，杜绝 `SETTLING` 等非交易状态标的被误交易。
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
- 净值曲线支持鼠标滚轮缩放时间视窗，拖拽时禁用文本选中，避免误框选下方时间标签。
- 净值历史持久化到持久目录，重启后仍可继续展示最近一周净值走势。
- 存储守护策略默认要求至少保留 1500MB 可用空间；不足时自动裁剪旧报告、旧净值历史和旧日志。
- 成交明细和日志面板支持滚动大窗口，默认展示 500 条，可切换 1000/2000/5000 条。
- 成交明细和日志面板采用静默刷新，接口波动时保留上次有效数据，不会反复回退到“加载中...”。
- 日志面板提供一键复制功能，便于复盘与排查。
- 后台策略与前端软刷新默认每 5 秒更新一次，浮动盈亏更接近实时。
- 页面已固定滚动条占位，软刷新时面板宽度不再跳动。
- 页面整体采用统一栅格和稳定列宽策略，长内容不会再把不同区块撑出不一致的宽度观感。
- 持仓、观察池、成交明细已升级为专业仪表盘表格样式，支持粘性表头、横向滚动保护、等宽数字和盈亏颜色区分。
- 持仓开始的核心面板已切换为单列全宽展示，表头与列内容统一居中，避免左右分栏导致的阅读割裂。
- 新增“策略逻辑看板”，可观察热点因子定义、小时级自适应参数与近 1 小时调参依据，以及候选标的因子打分明细。
- 策略逻辑看板已支持中文参数名与调参历史时间线；现货与永续候选默认剔除前20类大市值币对及稳定币对，减少低波动大币与稳定币占用策略资源。
- 仓位资金控制已升级为“双目标”（总暴露比例 + 目标保证金利用率），避免仅按暴露率控制导致保证金长期利用率偏低。

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
- 策略参数对比：每次小时级自适应后自动写入 `reports/strategy-compare.jsonl`，并产出 `reports/strategy-compare-latest.md` 便于对照改动前后收益表现。
- 持久卷建议：Fly 使用 2GB 卷挂载到 `/data`，并设置 `PERSISTENT_DATA_DIR=/data`。
- Fly 命令查看（示例）：
	- `flyctl ssh console -a git-binance-trader-sim -C "ls -lah /data/reports"`
	- `flyctl ssh console -a git-binance-trader-sim -C "cat /data/reports/latest.md"`
	- `flyctl ssh console -a git-binance-trader-sim -C "tail -n 120 /data/logs/strategy.log"`
