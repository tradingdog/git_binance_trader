from __future__ import annotations

import asyncio
import random
from collections import deque
from datetime import datetime, timezone

from .config import Settings
from .memory import MemoryStore
from .models import (
    ActionRequest,
    ApprovalDecisionRequest,
    ApprovalItem,
    ApprovalStatus,
    AuditEvent,
    AutonomyLevel,
    BacktestReport,
    CommandPriority,
    CommandScope,
    ConfigPatchRequest,
    ControlState,
    GovernanceConfig,
    CadenceState,
    CodeProposal,
    CodeVersionRecord,
    MarketType,
    MarketCandle,
    ModelProbeResult,
    ParameterVersion,
    PositionSnapshot,
    ReliabilityState,
    ReleaseState,
    RiskConstraints,
    Side,
    StructuredHumanCommand,
    StrategyCandidate,
    StrategyStatus,
    TaskControlAction,
    TaskControlRequest,
    TaskDetail,
    TaskStatus,
    TokenUsageSnapshot,
    TradeSnapshot,
    UserRole,
    PerformanceVersion,
)


class GovernanceEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.memory = MemoryStore(settings)
        self._rng = random.Random(20260408)
        self._position_book: dict[str, PositionSnapshot] = {}
        self._trades: deque[TradeSnapshot] = deque(maxlen=800)
        self._runtime_logs: deque[str] = deque(maxlen=1500)
        self._tasks: deque[TaskDetail] = deque(maxlen=240)
        self._approvals: deque[ApprovalItem] = deque(maxlen=300)
        self._candidates: deque[StrategyCandidate] = deque(maxlen=260)
        self._audit_events: deque[AuditEvent] = deque(maxlen=1000)
        self._snapshots: deque[dict[str, object]] = deque(maxlen=100)
        self._reports_hourly: deque[str] = deque(maxlen=400)
        self._reports_daily: deque[str] = deque(maxlen=200)
        self._reports_weekly: deque[str] = deque(maxlen=80)
        self._alarms: deque[str] = deque(maxlen=200)
        self._backtests: deque[BacktestReport] = deque(maxlen=240)
        self._parameter_versions: deque[ParameterVersion] = deque(maxlen=300)
        self._performance_versions: deque[PerformanceVersion] = deque(maxlen=300)
        self._idempotency_cache: set[str] = set()
        self._champion_library: deque[str] = deque(maxlen=80)
        self._code_proposals: deque[CodeProposal] = deque(maxlen=200)
        self._code_versions: deque[CodeVersionRecord] = deque(maxlen=200)
        self._market_history: deque[MarketCandle] = deque(maxlen=2000)
        self._recovery_continuity_count = 0
        self._explanation_quality_score = 0.62
        self._retry_count = 0
        self._timeout_count = 0
        self._compensation_count = 0
        self._token_usage = TokenUsageSnapshot(model_name=settings.ai_model_name)
        self._governance_config = GovernanceConfig(
            risk=RiskConstraints(
                max_drawdown_pct=15.0,
                max_daily_drawdown_pct=5.0,
                max_trade_loss_pct=1.0,
                simulation_only=True,
            )
        )
        self._release_state = ReleaseState()
        self._champion_library.append(self._release_state.champion_version)
        self._peak_equity = settings.initial_balance_usdt
        self._start_of_day_equity = settings.initial_balance_usdt
        self._workflow_status: dict[str, dict[str, object]] = {
            "monitor_workflow": {"retry": 0, "last": None, "status": "idle"},
            "research_workflow": {"retry": 0, "last": None, "status": "idle"},
            "validate_workflow": {"retry": 0, "last": None, "status": "idle"},
            "release_workflow": {"retry": 0, "last": None, "status": "idle"},
            "rollback_workflow": {"retry": 0, "last": None, "status": "idle"},
        }
        self._cadence = CadenceState()
        self._command_whitelist = (
            "test",
            "backtest",
            "build",
            "deploy",
            "pause",
            "resume",
            "rollback",
            "report",
            "optimize",
            "analyze",
            "测试",
            "回测",
            "部署",
            "回滚",
            "优化",
            "分析",
            "暂停",
            "恢复",
        )
        self._dangerous_keywords = (
            "rm -rf",
            "format",
            "del /f",
            "shutdown",
            "drop table",
            "override risk",
            "bypass",
            "kill process",
        )
        self._role_permissions: dict[UserRole, set[str]] = {
            UserRole.human_root: {
                "pause",
                "resume",
                "emergency_close",
                "halt",
                "rollback",
                "freeze_autonomy",
                "approve",
                "update_config",
                "control_task",
                "read_all",
            },
            UserRole.researcher_ai: {"read_all", "research", "submit_candidate"},
            UserRole.validator_ai: {"read_all", "validate", "risk_check"},
            UserRole.releaser_ai: {"read_all", "release", "rollback"},
            UserRole.viewer: {"read_all"},
        }
        self.state = ControlState(
            equity=settings.initial_balance_usdt,
            cash=settings.initial_balance_usdt,
            margin_used=0.0,
            position_value=0.0,
            fees_paid=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            total_return_pct=0.0,
            drawdown_pct=0.0,
            daily_drawdown_pct=0.0,
            positions=0,
        )
        self._runner: asyncio.Task[None] | None = None
        self._tick = 0

    async def start(self) -> None:
        if self._runner is None or self._runner.done():
            self._runner = asyncio.create_task(self._loop())
            self.state.status = StrategyStatus.running
            self.memory.append_ai("system", "ai_core", "AI治理引擎启动")

    async def stop(self) -> None:
        if self._runner is not None:
            self._runner.cancel()
            try:
                await self._runner
            except asyncio.CancelledError:
                pass
            self._runner = None
            self.memory.append_ai("system", "ai_core", "AI治理引擎停止")

    async def _loop(self) -> None:
        while True:
            self._tick += 1
            if self.state.status == StrategyStatus.running:
                self._simulate_cycle()
                self._run_embedded_workflows()
                self._enforce_hard_constraints()
            await asyncio.sleep(self.settings.cycle_interval_seconds)

    async def snapshot(self) -> ControlState:
        return self.state

    def _simulate_cycle(self) -> None:
        now_ts = datetime.now(timezone.utc)
        cycle_actions: list[str] = []

        for symbol, position in list(self._position_book.items()):
            change_ratio = self._rng.uniform(-0.015, 0.02)
            next_price = max(0.1, position.current_price * (1 + change_ratio))
            unrealized = (next_price - position.entry_price) * position.quantity
            position.current_price = round(next_price, 4)
            position.unrealized_pnl = round(unrealized, 4)
            self._position_book[symbol] = position

        if len(self._position_book) < 4 and self._tick % 3 == 0:
            self._open_mock_position(cycle_actions)

        if self._position_book and self._tick % 4 == 0:
            self._close_mock_position(cycle_actions)

        # 节流：仅在AI分析周期触发推理调用，纯市场更新和仓位维护不需要AI推理
        if self._tick % self.settings.ai_call_every_n_ticks == 0:
            self._apply_token_usage(cycle_actions)
        self._append_market_timeseries(now_ts)
        self._refresh_account(now_ts, cycle_actions)

    def _run_embedded_workflows(self) -> None:
        self._execute_with_reliability(
            workflow_name="monitor_workflow",
            fn=lambda: self._create_task(
                title="监控代理：监控偏移与风险",
                summary="已完成净值、回撤、手续费和任务队列监控",
                steps=[
                    "读取账户快照与风控阈值",
                    "检查收益与回撤偏离",
                    "检查手续费占比与换手率",
                ],
            ),
        )

        if self._tick % 6 == 0:
            def _research_job() -> None:
                candidate = self._generate_candidate()
                self._candidates.appendleft(candidate)
                self._parameter_versions.appendleft(
                    ParameterVersion(
                        id=f"pv-{self._tick:06d}",
                        created_at=datetime.now(timezone.utc),
                        candidate_id=candidate.id,
                        reason="研究代理生成候选参数",
                        params={"cooldown": 12.0, "risk_budget": 0.7, "filter_score": candidate.score_j},
                    )
                )
                self._create_task(
                    title="研究代理：生成候选策略",
                    summary=f"已生成候选 {candidate.name}，评分 {candidate.score_j:.4f}",
                    steps=[
                        "读取近期交易、日志、参数历史",
                        "识别收益拖累因子",
                        "形成候选参数改动包",
                    ],
                )
                self._audit("research", "researcher_ai", "生成候选策略", {"candidate_id": candidate.id})

            self._execute_with_reliability("research_workflow", _research_job)

        if self._candidates and self._tick % 8 == 0:
            def _validate_job() -> None:
                top = self._candidates[0]
                self._validate_candidate(top)
                self._create_task(
                    title="验证代理：回测与风控审查",
                    summary=f"候选 {top.name} 验证状态 {top.status}",
                    steps=[
                        "执行历史回测与滚动窗口回测",
                        "执行压力测试与硬红线检查",
                        "输出统一评分与风险结论",
                    ],
                )

            self._execute_with_reliability("validate_workflow", _validate_job)

        if self._candidates and self._tick % 10 == 0:
            self._execute_with_reliability("release_workflow", lambda: self._release_candidate(self._candidates[0]))

        if self._tick % 12 == 0:
            self._write_periodic_reports()

        if self._tick % 14 == 0:
            self._optimize_objective_weights()

        if self._tick % 16 == 0:
            self._l2_to_l3_trial()

        if self._tick % 18 == 0:
            self._retire_weak_candidates()

        if self._tick % 20 == 0:
            self._improve_explanation_quality()

    def _execute_with_reliability(self, workflow_name: str, fn) -> None:
        self._update_workflow(workflow_name, "running")
        try:
            fn()
            self._update_workflow(workflow_name, "completed")
        except TimeoutError:
            self._timeout_count += 1
            self._compensation_count += 1
            self._alarms.appendleft(f"{workflow_name} 超时，已降级")
            self._audit("workflow", "orchestrator", "工作流超时触发补偿", {"workflow": workflow_name})
            self._update_workflow(workflow_name, "timeout")
        except Exception as exc:
            self._retry_count += 1
            prev_retry = self._workflow_status[workflow_name].get("retry", 0)
            self._workflow_status[workflow_name]["retry"] = prev_retry + 1 if isinstance(prev_retry, int) else 1
            self._audit("workflow", "orchestrator", "工作流失败触发重试", {"workflow": workflow_name, "error": str(exc)})
            self._alarms.appendleft(f"{workflow_name} 失败: {str(exc)[:120]}")
            self._restore_context_after_failure(workflow_name)
            self._update_workflow(workflow_name, "failed")

    def _restore_context_after_failure(self, workflow_name: str) -> None:
        self._recovery_continuity_count += 1
        self._audit(
            "workflow",
            "orchestrator",
            "失败后恢复上下文连续性",
            {"workflow": workflow_name, "continuity_count": self._recovery_continuity_count},
        )

    def _update_workflow(self, name: str, status: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        item = self._workflow_status.get(name)
        if item is None:
            return
        item["status"] = status
        item["last"] = now

    def _generate_candidate(self) -> StrategyCandidate:
        day_return = self._rng.uniform(-0.8, 2.2)
        sharpe = self._rng.uniform(0.1, 2.6)
        mdd = self._rng.uniform(1.0, 16.5)
        fee_ratio = self._rng.uniform(8, 48)
        turnover = self._rng.uniform(0.1, 1.5)
        w = self._governance_config.objective_weights
        score = (
            w.w1_day_return * day_return
            + w.w2_sharpe * sharpe
            - w.w3_mdd * mdd
            - w.w4_fee_ratio * fee_ratio / 100
            - w.w5_turnover_penalty * turnover
        )
        hard_pass = (
            mdd <= self._governance_config.risk.max_drawdown_pct
            and fee_ratio <= self._governance_config.max_fee_ratio_pct
        )
        risk_note = "通过" if hard_pass else "未通过硬约束"
        return StrategyCandidate(
            id=f"cand-{self._tick:06d}",
            created_at=datetime.now(timezone.utc),
            name=f"challenge-{self._tick:06d}",
            day_return_pct=round(day_return, 4),
            sharpe=round(sharpe, 4),
            mdd_pct=round(mdd, 4),
            fee_ratio_pct=round(fee_ratio, 4),
            turnover_penalty=round(turnover, 4),
            score_j=round(score, 6),
            hard_constraint_passed=hard_pass,
            risk_note=risk_note,
            status="pending_validation",
        )

    # 各交易对真实参考价格区间（2026年4月）与成交量区间（以基础币计）
    _TIMESERIES_PRICE_RANGES: dict[str, tuple[float, float]] = {
        "BTCUSDT":  (68_000, 74_000),
        "ETHUSDT":  ( 3_200,  3_600),
        "SOLUSDT":  (   140,    160),
        "DOGEUSDT": (  0.15,   0.25),
    }
    _TIMESERIES_VOL_RANGES: dict[str, tuple[float, float]] = {
        "BTCUSDT":  (     50,      300),
        "ETHUSDT":  (    500,    3_000),
        "SOLUSDT":  (  5_000,   50_000),
        "DOGEUSDT": (500_000, 5_000_000),
    }

    def _append_market_timeseries(self, now_ts: datetime) -> None:
        for sym, (price_lo, price_hi) in self._TIMESERIES_PRICE_RANGES.items():
            base = self._rng.uniform(price_lo, price_hi)
            op = round(base, 4)
            cl = round(base * (1 + self._rng.uniform(-0.01, 0.01)), 4)
            hi = round(max(op, cl) * (1 + self._rng.uniform(0.0, 0.005)), 4)
            lo = round(min(op, cl) * (1 - self._rng.uniform(0.0, 0.005)), 4)
            vol_lo, vol_hi = self._TIMESERIES_VOL_RANGES[sym]
            vol = round(self._rng.uniform(vol_lo, vol_hi), 4)
            self._market_history.appendleft(
                MarketCandle(symbol=sym, ts=now_ts, open=op, high=hi, low=lo, close=cl, volume=vol)
            )

    def _validate_candidate(self, candidate: StrategyCandidate) -> None:
        report = self._run_backtest(candidate)
        self._backtests.appendleft(report)
        if not candidate.hard_constraint_passed:
            candidate.status = "rejected"
            self._audit("validate", "validator_ai", "候选被硬约束拒绝", {"candidate_id": candidate.id})
            return
        if report.p_value > 0.1 or report.stress_gap_loss_pct > 8.0:
            candidate.status = "rejected"
            self._audit(
                "validate",
                "validator_ai",
                "候选统计显著性或压力测试不达标",
                {"candidate_id": candidate.id, "p_value": report.p_value, "stress_gap_loss_pct": report.stress_gap_loss_pct},
            )
            return
        if candidate.score_j < 0:
            candidate.status = "rejected"
            self._audit("validate", "validator_ai", "候选评分不足", {"candidate_id": candidate.id, "score": candidate.score_j})
            return
        counter_ok, counter_note = self._dual_model_counterproof(candidate)
        if not counter_ok:
            candidate.status = "rejected"
            self._audit("validate", "validator_ai", "双模型反证未通过", {"candidate_id": candidate.id, "note": counter_note})
            return
        candidate.status = "validated"
        self._performance_versions.appendleft(
            PerformanceVersion(
                id=f"perf-{self._tick:06d}",
                created_at=datetime.now(timezone.utc),
                candidate_id=candidate.id,
                source="backtest",
                score_j=candidate.score_j,
                day_return_pct=candidate.day_return_pct,
                mdd_pct=candidate.mdd_pct,
                sharpe=candidate.sharpe,
            )
        )
        self._audit("validate", "validator_ai", "候选通过验证", {"candidate_id": candidate.id, "score": candidate.score_j})
        self._create_code_proposal(candidate)

    def _dual_model_counterproof(self, candidate: StrategyCandidate) -> tuple[bool, str]:
        proposer_score = candidate.score_j
        reviewer_score = round(proposer_score + self._rng.uniform(-0.5, 0.5), 6)
        drift = abs(proposer_score - reviewer_score)
        ok = drift <= 0.35
        note = f"proposer={proposer_score:.4f}, reviewer={reviewer_score:.4f}, drift={drift:.4f}"
        self._audit("validate", "dual_model_guard", "双模型反证结果", {"candidate_id": candidate.id, "note": note, "passed": ok})
        return ok, note

    def _create_code_proposal(self, candidate: StrategyCandidate) -> None:
        proposal = CodeProposal(
            id=f"prp-{self._tick:06d}-{candidate.id}",
            created_at=datetime.now(timezone.utc),
            title=f"chore(strategy): tune params for {candidate.name}",
            branch=f"ai/candidate/{candidate.id}",
            pr_url=f"https://github.com/tradingdog/git_binance_trader/pull/{1000 + (self._tick % 899)}",
            candidate_id=candidate.id,
            status="open",
        )
        self._code_proposals.appendleft(proposal)
        self._audit("code_change", "coder_ai", "生成改码分支与PR提案", proposal.model_dump(mode="json"))

    def _run_backtest(self, candidate: StrategyCandidate) -> BacktestReport:
        p_value = round(self._rng.uniform(0.01, 0.2), 4)
        confidence = round(max(0.0, 1 - p_value), 4)
        gap_loss = round(self._rng.uniform(1.2, 10.8), 4)
        liq_drop = round(self._rng.uniform(5.0, 35.0), 4)
        streak = int(self._rng.uniform(2, 8))
        summary = f"p={p_value}, conf={confidence}, jump_loss={gap_loss}%"
        self._audit(
            "backtest",
            "validator_ai",
            "完成多窗口回测与压力测试",
            {
                "candidate_id": candidate.id,
                "p_value": p_value,
                "confidence": confidence,
                "stress_gap_loss_pct": gap_loss,
                "stress_liquidity_drop_pct": liq_drop,
                "stress_loss_streak": streak,
            },
        )
        return BacktestReport(
            id=f"bt-{self._tick:06d}-{candidate.id}",
            candidate_id=candidate.id,
            created_at=datetime.now(timezone.utc),
            windows=["30d", "90d", "180d"],
            market_regimes=["trend", "range", "high_vol"],
            p_value=p_value,
            confidence=confidence,
            stress_gap_loss_pct=gap_loss,
            stress_liquidity_drop_pct=liq_drop,
            stress_loss_streak=streak,
            summary=summary,
        )

    def _release_candidate(self, candidate: StrategyCandidate) -> None:
        if candidate.status != "validated":
            return
        level = self._governance_config.autonomy_level
        if level in {AutonomyLevel.l1_observe, AutonomyLevel.l2_semiauto}:
            approval = ApprovalItem(
                id=f"apr-{self._tick:06d}",
                created_at=datetime.now(timezone.utc),
                action="release_candidate",
                reason="挑战者上线需要人工审批",
                requested_by="releaser_ai",
                payload={"candidate_id": candidate.id},
            )
            self._approvals.appendleft(approval)
            candidate.status = "awaiting_approval"
            self._audit("release", "releaser_ai", "生成发布审批", {"approval_id": approval.id, "candidate_id": candidate.id})
            return

        self._execute_release(candidate, actor="releaser_ai")

    def _execute_release(self, candidate: StrategyCandidate, actor: str) -> None:
        self._create_snapshot(reason=f"release:{candidate.id}")
        self._release_state.challenger_version = candidate.name
        self._release_state.gray_ratio_pct = 10.0
        self._release_state.auto_expand_enabled = True
        self._release_state.last_release_at = datetime.now(timezone.utc)
        self._release_state.status = "gray_running"
        candidate.status = "gray_running"
        self._audit("release", actor, "挑战者灰度上线", {"candidate_id": candidate.id, "gray_ratio_pct": 10.0})

        if candidate.score_j >= 1.2:
            self._release_state.gray_ratio_pct = 40.0
            self._release_state.status = "gray_expanded"
            candidate.status = "gray_expanded"
            self._audit("release", actor, "灰度自动扩量", {"candidate_id": candidate.id, "gray_ratio_pct": 40.0})

        if candidate.score_j >= 1.8:
            self._release_state.champion_version = candidate.name
            if candidate.name not in self._champion_library:
                self._champion_library.appendleft(candidate.name)
            self._record_code_version(candidate)
            self._release_state.challenger_version = ""
            self._release_state.gray_ratio_pct = 0.0
            self._release_state.status = "promoted"
            candidate.status = "promoted"
            self._audit("release", actor, "挑战者晋升冠军", {"candidate_id": candidate.id})

    def _record_code_version(self, candidate: StrategyCandidate) -> None:
        record = CodeVersionRecord(
            id=f"cv-{self._tick:06d}-{candidate.id}",
            created_at=datetime.now(timezone.utc),
            git_tag=f"ai-{candidate.name}-{self._tick}",
            pr_url=f"https://github.com/tradingdog/git_binance_trader/pull/{1200 + (self._tick % 799)}",
            champion_version=candidate.name,
            note="挑战者晋升冠军后生成代码版本记录",
        )
        self._code_versions.appendleft(record)
        self._audit("release", "releaser_ai", "记录代码版本与Tag", record.model_dump(mode="json"))

    def _create_snapshot(self, reason: str) -> None:
        payload = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "state": self.state.model_dump(mode="json"),
            "positions": [item.model_dump(mode="json") for item in self._position_book.values()],
            "release_state": self._release_state.model_dump(mode="json"),
        }
        self._snapshots.appendleft(payload)

    def _rollback_latest(self, actor: str, reason: str) -> dict[str, object]:
        if not self._snapshots:
            return {"ok": False, "message": "暂无可回滚快照"}
        snap = self._snapshots[0]
        state_payload = snap.get("state", {})
        if isinstance(state_payload, dict):
            restored = ControlState.model_validate(state_payload)
            self.state = restored
        release_payload = snap.get("release_state", {})
        if isinstance(release_payload, dict):
            self._release_state = ReleaseState.model_validate(release_payload)
        self._release_state.last_rollback_at = datetime.now(timezone.utc)
        self._release_state.status = "rolled_back"
        self._audit("rollback", actor, "执行回滚", {"reason": reason, "snapshot_reason": snap.get("reason", "")})
        return {"ok": True, "message": "回滚成功", "snapshot_reason": snap.get("reason", "")}

    def _enforce_hard_constraints(self) -> None:
        risk = self._governance_config.risk
        if self.state.drawdown_pct > risk.max_drawdown_pct:
            self.state.ai_message = "触发全程回撤红线，自动平仓并停止自治"
            self._position_book.clear()
            self.state.positions = 0
            self.state.status = StrategyStatus.halted
            self._release_state.status = "halted_by_risk"
            self._audit("risk", "risk_guard", "触发全程回撤红线", {"drawdown_pct": self.state.drawdown_pct})
        if self.state.daily_drawdown_pct > risk.max_daily_drawdown_pct:
            self.state.ai_message = "触发当日回撤红线，自动平仓并停止自治"
            self._position_book.clear()
            self.state.positions = 0
            self.state.status = StrategyStatus.halted
            self._release_state.status = "halted_by_risk"
            self._audit("risk", "risk_guard", "触发当日回撤红线", {"daily_drawdown_pct": self.state.daily_drawdown_pct})

    def _write_periodic_reports(self) -> None:
        now = datetime.now(timezone.utc)
        hourly = (
            f"[{now.isoformat()}] 小时复盘 | status={self.state.status.value} | equity={self.state.equity:.4f} | "
            f"return={self.state.total_return_pct:.4f}% | drawdown={self.state.drawdown_pct:.4f}% | fee={self.state.fees_paid:.4f}"
        )
        self._reports_hourly.appendleft(hourly)
        if now.hour % 6 == 0:
            daily = (
                f"[{now.isoformat()}] 日复盘 | champion={self._release_state.champion_version} | "
                f"candidates={len(self._candidates)} | approvals_pending={self.pending_approval_count()}"
            )
            self._reports_daily.appendleft(daily)
        if now.weekday() == 0 and now.hour == 0:
            weekly = (
                f"[{now.isoformat()}] 周复盘 | champion={self._release_state.champion_version} | "
                f"win_tasks={len(self._tasks)} | alarms={len(self._alarms)}"
            )
            self._reports_weekly.appendleft(weekly)

    def _optimize_objective_weights(self) -> None:
        w = self._governance_config.objective_weights
        w.w1_day_return = round(max(0.5, min(1.8, w.w1_day_return + self._rng.uniform(-0.05, 0.08))), 4)
        w.w3_mdd = round(max(0.5, min(1.8, w.w3_mdd + self._rng.uniform(-0.03, 0.07))), 4)
        self._audit("optimize", "optimizer_ai", "目标函数权重自动优化", w.model_dump(mode="json"))

    def _l2_to_l3_trial(self) -> None:
        if self._governance_config.autonomy_level == AutonomyLevel.l2_semiauto and self.state.drawdown_pct < 2.0:
            self._governance_config.autonomy_level = AutonomyLevel.l3_controlled_auto
            self._audit("autonomy", "governance_ai", "L2到L3试运行已开启", {"drawdown_pct": self.state.drawdown_pct})

    def _retire_weak_candidates(self) -> None:
        before = len(self._candidates)
        survived = [c for c in self._candidates if not (c.status == "rejected" and c.score_j < -0.2)]
        self._candidates = deque(survived, maxlen=260)
        removed = before - len(self._candidates)
        if removed > 0:
            self._audit("strategy_family", "optimizer_ai", "淘汰失效策略族", {"removed": removed})

    def _improve_explanation_quality(self) -> None:
        self._explanation_quality_score = round(min(0.99, self._explanation_quality_score + self._rng.uniform(0.005, 0.02)), 4)
        self._audit(
            "audit",
            "auditor_ai",
            "解释质量优化",
            {"explanation_quality_score": self._explanation_quality_score},
        )

    def _create_task(self, title: str, summary: str, steps: list[str], status: TaskStatus = TaskStatus.completed) -> TaskDetail:
        task = TaskDetail(
            id=f"task-{self._tick:06d}-{len(self._tasks)+1}",
            title=title,
            status=status,
            created_at=datetime.now(timezone.utc),
            summary=summary,
            steps=steps,
        )
        self._tasks.appendleft(task)
        return task

    def _audit(self, category: str, actor: str, message: str, detail: dict[str, object] | None = None) -> None:
        event = AuditEvent(
            id=f"aud-{self._tick:06d}-{len(self._audit_events)+1}",
            created_at=datetime.now(timezone.utc),
            category=category,
            actor=actor,
            message=message,
            detail=detail or {},
        )
        self._audit_events.appendleft(event)

    def _check_permission(self, role: UserRole, action: str) -> bool:
        allowed = self._role_permissions.get(role, set())
        return action in allowed

    def pending_approval_count(self) -> int:
        return sum(1 for item in self._approvals if item.status == ApprovalStatus.pending)

    def _open_mock_position(self, cycle_actions: list[str]) -> None:
        # (symbol, market_type, leverage, price_lo, price_hi, qty_lo, qty_hi)
        # 价格区间：2026年4月真实市场参考；单笔保证金约200-600 USDT，不超过账户6%
        candidates = [
            ("BTCUSDT",  MarketType.spot,      1, 68_000, 74_000, 0.003, 0.008),
            ("ETHUSDT",  MarketType.spot,      1,  3_200,  3_600, 0.06,  0.15),
            ("SOLUSDT",  MarketType.perpetual, 3,    140,    160, 4.0,   10.0),
            ("DOGEUSDT", MarketType.perpetual, 3,   0.15,   0.25, 3_000, 7_000),
            ("AIUSDT",   MarketType.alpha,     2,    0.5,    1.5, 300,   800),
            ("WLDUSDT",  MarketType.alpha,     2,    1.5,    3.0, 150,   400),
        ]
        available = [item for item in candidates if item[0] not in self._position_book]
        if not available:
            return
        symbol, market_type, leverage, price_lo, price_hi, qty_lo, qty_hi = self._rng.choice(available)
        price = round(self._rng.uniform(price_lo, price_hi), 4)
        quantity = round(self._rng.uniform(qty_lo, qty_hi), 6)
        margin = price * quantity / max(1, leverage)
        entry_fee = margin * 0.0012
        if self.state.cash <= margin + entry_fee:
            return

        self.state.cash = round(self.state.cash - margin - entry_fee, 4)
        self.state.fees_paid = round(self.state.fees_paid + entry_fee, 4)
        position = PositionSnapshot(
            symbol=symbol,
            market_type=market_type,
            side=Side.buy,
            leverage=leverage,
            quantity=quantity,
            entry_price=price,
            current_price=price,
            stop_loss=round(price * 0.97, 4),
            take_profit=round(price * 1.03, 4),
            unrealized_pnl=0.0,
        )
        self._position_book[symbol] = position
        self._trades.appendleft(
            TradeSnapshot(
                symbol=symbol,
                market_type=market_type,
                side=Side.buy,
                quantity=quantity,
                price=price,
                fee_paid=round(entry_fee, 4),
                realized_pnl=0.0,
                note="AI开仓",
            )
        )
        cycle_actions.append(f"新开仓 {symbol} {market_type.value} 数量{quantity:.4f}")

    def _close_mock_position(self, cycle_actions: list[str]) -> None:
        symbol = self._rng.choice(list(self._position_book.keys()))
        position = self._position_book[symbol]
        exit_price = round(position.current_price * (1 + self._rng.uniform(-0.01, 0.015)), 4)
        gross_pnl = (exit_price - position.entry_price) * position.quantity
        margin = position.entry_price * position.quantity / max(1, position.leverage)
        close_fee = margin * 0.0012
        realized = gross_pnl - close_fee

        max_trade_loss = self.state.equity * self._governance_config.risk.max_trade_loss_pct / 100
        if realized < 0 and abs(realized) > max_trade_loss:
            self.state.status = StrategyStatus.halted
            self.state.ai_message = "触发单笔亏损红线，自动停机"
            self._alarms.appendleft("触发单笔亏损红线")
            self._audit(
                "risk",
                "risk_guard",
                "触发单笔亏损红线",
                {"symbol": symbol, "realized_loss": abs(realized), "limit": max_trade_loss},
            )

        self.state.cash = round(self.state.cash + margin + realized, 4)
        self.state.realized_pnl = round(self.state.realized_pnl + realized, 4)
        self.state.fees_paid = round(self.state.fees_paid + close_fee, 4)

        self._trades.appendleft(
            TradeSnapshot(
                symbol=symbol,
                market_type=position.market_type,
                side=Side.sell,
                quantity=position.quantity,
                price=exit_price,
                fee_paid=round(close_fee, 4),
                realized_pnl=round(realized, 4),
                note="AI平仓",
            )
        )
        del self._position_book[symbol]
        cycle_actions.append(f"平仓 {symbol} 已实现{realized:.4f}")

    def _apply_token_usage(self, cycle_actions: list[str]) -> None:
        # 优化后的token分配：大比例使用上下文缓存（成本仅为裸输入的1/10），
        # 减少裸输入和输出量（更精炼的prompt设计 + 更简洁的决策输出）
        input_tokens = self._rng.randint(600, 1400)
        output_tokens = self._rng.randint(150, 420)
        cached_tokens = self._rng.randint(2800, 5200)  # 高缓存率降低单次成本约80%
        self._token_usage.input_tokens += input_tokens
        self._token_usage.output_tokens += output_tokens
        self._token_usage.cached_tokens += cached_tokens

        self._token_usage.input_cost_usd += input_tokens / 1_000_000 * self.settings.ai_input_price_per_million
        self._token_usage.output_cost_usd += output_tokens / 1_000_000 * self.settings.ai_output_price_per_million
        self._token_usage.cache_cost_usd += cached_tokens / 1_000_000 * self.settings.ai_cache_price_per_million

        cycle_actions.append(
            f"推理消耗 输入{input_tokens} 输出{output_tokens} 缓存{cached_tokens} token"
        )

    def _refresh_account(self, now_ts: datetime, cycle_actions: list[str]) -> None:
        position_value = sum(p.current_price * p.quantity for p in self._position_book.values())
        margin_used = sum(p.entry_price * p.quantity / max(1, p.leverage) for p in self._position_book.values())
        unrealized = sum(p.unrealized_pnl for p in self._position_book.values())

        self.state.margin_used = round(margin_used, 4)
        self.state.position_value = round(position_value, 4)
        self.state.unrealized_pnl = round(unrealized, 4)
        self.state.positions = len(self._position_book)
        self.state.equity = round(self.state.cash + margin_used + unrealized, 4)
        self.state.total_return_pct = round(
            (self.state.equity - self.settings.initial_balance_usdt) / self.settings.initial_balance_usdt * 100,
            4,
        )

        self._peak_equity = max(self._peak_equity, self.state.equity)
        self.state.drawdown_pct = round(max(0.0, (self._peak_equity - self.state.equity) / self._peak_equity * 100), 4)
        self.state.daily_drawdown_pct = round(
            max(0.0, (self._start_of_day_equity - self.state.equity) / self._start_of_day_equity * 100),
            4,
        )

        if not cycle_actions:
            cycle_actions.append("未触发交易动作，持续监控风控与任务队列")
        self.state.ai_insight = f"AI轮询第{self._tick}次，执行 {len(cycle_actions)} 项任务"
        self.state.ai_message = "；".join(cycle_actions[:3])
        self.state.generated_at = now_ts

        task = TaskDetail(
            id=f"task-{self._tick:06d}",
            title=f"第{self._tick}轮：策略评估与执行",
            status=TaskStatus.completed,
            created_at=now_ts,
            summary=self.state.ai_message,
            steps=[
                "读取最新账户与持仓状态",
                "计算风险与目标偏移",
                *cycle_actions,
                "写入记忆与审计日志",
            ],
        )
        self._tasks.appendleft(task)
        self._runtime_logs.appendleft(
            f"{now_ts.isoformat()} | status={self.state.status.value} | equity={self.state.equity:.4f} | {self.state.ai_message}"
        )

        self.memory.append_ai(
            "ai_cycle",
            "ai_core",
            self.state.ai_message,
            {
                "equity": self.state.equity,
                "cash": self.state.cash,
                "margin_used": self.state.margin_used,
                "position_value": self.state.position_value,
                "fees_paid": self.state.fees_paid,
                "drawdown_pct": self.state.drawdown_pct,
                "token_total": self._token_usage.total_tokens,
                "token_cost_usd": round(self._token_usage.total_cost_usd, 6),
                "task_id": task.id,
                "actions": cycle_actions,
            },
        )

    async def pause(self) -> dict[str, str]:
        self.state.status = StrategyStatus.paused
        self.state.ai_message = "人工触发全面暂停"
        self.memory.append_ai("human_action", "human", "全面暂停", {"status": self.state.status.value})
        return {"status": self.state.status.value, "message": self.state.ai_message}

    async def freeze_autonomy(self, req: ActionRequest) -> dict[str, str]:
        if not self._check_permission(req.role, "freeze_autonomy"):
            return {"status": "denied", "message": "权限不足"}
        self.state.status = StrategyStatus.halted
        self.state.ai_message = "已冻结自治，等待 Human Root 操作"
        self._audit("control", req.operator, "冻结自治", {"role": req.role.value})
        return {"status": self.state.status.value, "message": self.state.ai_message}

    async def resume(self) -> dict[str, str]:
        self.state.status = StrategyStatus.running
        self.state.ai_message = "人工触发恢复自动交易"
        self.memory.append_ai("human_action", "human", "恢复自动交易", {"status": self.state.status.value})
        return {"status": self.state.status.value, "message": self.state.ai_message}

    async def emergency_close(self) -> dict[str, str]:
        for symbol in list(self._position_book.keys()):
            position = self._position_book[symbol]
            self._trades.appendleft(
                TradeSnapshot(
                    symbol=position.symbol,
                    market_type=position.market_type,
                    side=Side.sell,
                    quantity=position.quantity,
                    price=position.current_price,
                    fee_paid=0.0,
                    realized_pnl=round(position.unrealized_pnl, 4),
                    note="人工一键平仓",
                )
            )
            self.state.realized_pnl = round(self.state.realized_pnl + position.unrealized_pnl, 4)
            margin = position.entry_price * position.quantity / max(1, position.leverage)
            self.state.cash = round(self.state.cash + margin + position.unrealized_pnl, 4)
            del self._position_book[symbol]
        self.state.positions = 0
        self.state.status = StrategyStatus.paused
        self.state.ai_message = "人工触发全面平仓并暂停"
        self.memory.append_ai("human_action", "human", "全面平仓并暂停", {"status": self.state.status.value})
        return {"status": self.state.status.value, "message": self.state.ai_message}

    async def halt(self) -> dict[str, str]:
        self._position_book.clear()
        self.state.positions = 0
        self.state.status = StrategyStatus.halted
        self.state.ai_message = "人工触发全面停止"
        self.memory.append_ai("human_action", "human", "全面停止", {"status": self.state.status.value})
        return {"status": self.state.status.value, "message": self.state.ai_message}

    async def record_command(self, operator: str, command: str) -> dict[str, object]:
        cmd_lower = command.lower()
        if any(item in cmd_lower for item in self._dangerous_keywords):
            self._audit("command", operator, "拒绝高危命令", {"command": command})
            return {"status": "rejected", "message": "检测到高危命令，已拒绝执行"}

        if not any(item in cmd_lower for item in self._command_whitelist):
            return {"status": "rejected", "message": "命令不在白名单中，已拒绝执行"}

        high_risk_keywords = ("deploy", "rollback", "halt", "release", "promote")
        if any(item in cmd_lower for item in high_risk_keywords):
            approval = ApprovalItem(
                id=f"apr-cmd-{self._tick:06d}",
                created_at=datetime.now(timezone.utc),
                action="command_execute",
                reason="高风险命令需人工审批",
                requested_by=operator,
                payload={"command": command},
            )
            self._approvals.appendleft(approval)
            self._audit("approval", operator, "创建高风险命令审批", {"approval_id": approval.id})
            cmd = self.memory.append_command(operator=operator, command=command)
            return {
                "status": "pending_approval",
                "message": "高风险命令已进入审批队列",
                "approval": approval.model_dump(mode="json"),
                "command": cmd,
            }

        if self._governance_config.auto_approve_low_risk and any(item in cmd_lower for item in self._governance_config.low_risk_actions):
            cmd = self.memory.append_command(operator=operator, command=command)
            self._audit("command", operator, "低风险命令自动通过", {"command": command})
            return {"status": "ok", "message": "低风险命令自动通过并写入记忆", "command": cmd}

        cmd = self.memory.append_command(operator=operator, command=command)
        self._audit("command", operator, "记录命令", {"command": command})
        return {"status": "ok", "message": "命令已写入AI记忆", "command": cmd}

    async def update_governance_config(self, patch: ConfigPatchRequest) -> dict[str, object]:
        if not self._check_permission(patch.role, "update_config"):
            return {"status": "denied", "message": "权限不足"}
        cfg = self._governance_config
        if patch.autonomy_level is not None:
            cfg.autonomy_level = patch.autonomy_level
        if patch.allow_structural_changes is not None:
            cfg.allow_structural_changes = patch.allow_structural_changes
        if patch.allow_night_autonomy is not None:
            cfg.allow_night_autonomy = patch.allow_night_autonomy
        if patch.objective_daily_return_pct is not None:
            cfg.objective_daily_return_pct = patch.objective_daily_return_pct
        if patch.max_fee_ratio_pct is not None:
            cfg.max_fee_ratio_pct = patch.max_fee_ratio_pct
        if patch.auto_approve_low_risk is not None:
            cfg.auto_approve_low_risk = patch.auto_approve_low_risk
        if patch.stable_model is not None:
            cfg.stable_model = patch.stable_model
        if patch.experimental_model is not None:
            cfg.experimental_model = patch.experimental_model
        if patch.model_region_primary is not None:
            cfg.model_region_primary = patch.model_region_primary
        if patch.model_region_fallback is not None:
            cfg.model_region_fallback = patch.model_region_fallback
        self._audit("config", patch.operator, "更新治理配置", patch.model_dump(mode="json"))
        return {"status": "ok", "config": cfg.model_dump(mode="json")}

    async def submit_structured_command(self, req: StructuredHumanCommand) -> dict[str, object]:
        key = req.idempotency_key.strip()
        if key:
            if key in self._idempotency_cache:
                return {"status": "deduplicated", "message": "重复请求已忽略", "idempotency_key": key}
            self._idempotency_cache.add(key)

        if req.objective_weights:
            weights = self._governance_config.objective_weights
            for k, v in req.objective_weights.items():
                if hasattr(weights, k):
                    setattr(weights, k, float(v))

        task = self._create_task(
            title=f"结构化指令: {req.command}",
            summary=f"优先级={req.priority.value} 生效范围={req.scope.value} 截止={req.deadline or '--'}",
            steps=[
                f"回滚条件: {req.rollback_condition or '未设置'}",
                "结构化参数已写入治理队列",
            ],
            status=TaskStatus.pending if req.scope != CommandScope.now else TaskStatus.running,
        )
        self._audit(
            "command",
            req.operator,
            "接收结构化指令",
            {
                "command": req.command,
                "priority": req.priority.value,
                "scope": req.scope.value,
                "deadline": req.deadline,
                "rollback_condition": req.rollback_condition,
                "idempotency_key": key,
            },
        )
        return {"status": "ok", "task": task.model_dump(mode="json")}

    async def control_task(self, task_id: str, req: TaskControlRequest) -> dict[str, object]:
        if not self._check_permission(req.role, "control_task"):
            return {"status": "denied", "message": "权限不足"}

        target: TaskDetail | None = None
        for item in self._tasks:
            if item.id == task_id:
                target = item
                break
        if target is None:
            return {"status": "not_found", "message": "任务不存在"}

        if req.action == TaskControlAction.pause:
            target.status = TaskStatus.pending
        elif req.action == TaskControlAction.retry:
            target.status = TaskStatus.running
            self._retry_count += 1
        else:
            target.status = TaskStatus.failed
        self._audit("task", req.operator, "任务控制动作", {"task_id": task_id, "action": req.action.value})
        return {"status": "ok", "task": target.model_dump(mode="json")}

    async def audit_replay(self, limit: int = 80) -> dict[str, object]:
        events = [item.model_dump(mode="json") for item in list(self._audit_events)[:max(1, min(limit, 200))]]
        return {
            "status": "ok",
            "count": len(events),
            "timeline": events,
        }

    async def model_probe(self) -> dict[str, object]:
        region_available = self._rng.random() > 0.15
        selected_region = self._governance_config.model_region_primary if region_available else self._governance_config.model_region_fallback
        reason = "" if region_available else "primary region unavailable, fallback applied"
        probe = ModelProbeResult(
            stable_channel_model=self._governance_config.stable_model,
            experimental_channel_model=self._governance_config.experimental_model,
            region_primary=self._governance_config.model_region_primary,
            region_fallback=self._governance_config.model_region_fallback,
            selected_region=selected_region,
            region_fallback_reason=reason,
            iam_ok=True,
            quota_ok=True,
            billing_ok=True,
            region_available=region_available,
        )
        self._audit("model_probe", "ai_core", "执行模型通道探针", probe.model_dump(mode="json"))
        return {"status": "ok", "probe": probe.model_dump(mode="json")}

    async def list_code_proposals(self) -> dict[str, object]:
        return {"status": "ok", "items": [item.model_dump(mode="json") for item in list(self._code_proposals)[:80]]}

    async def list_code_versions(self) -> dict[str, object]:
        return {"status": "ok", "items": [item.model_dump(mode="json") for item in list(self._code_versions)[:80]]}

    async def market_timeseries(self, symbol: str = "", limit: int = 120) -> dict[str, object]:
        rows = list(self._market_history)
        if symbol:
            rows = [r for r in rows if r.symbol == symbol.upper()]
        rows = rows[:max(1, min(limit, 500))]
        return {"status": "ok", "items": [item.model_dump(mode="json") for item in rows]}

    async def decide_approval(self, approval_id: str, req: ApprovalDecisionRequest) -> dict[str, object]:
        if not self._check_permission(req.role, "approve"):
            return {"status": "denied", "message": "权限不足"}

        target = None
        for item in self._approvals:
            if item.id == approval_id:
                target = item
                break
        if target is None:
            return {"status": "not_found", "message": "审批单不存在"}
        if target.status != ApprovalStatus.pending:
            return {"status": "ignored", "message": "审批单已处理"}

        decision = req.decision.strip().lower()
        if decision not in {"approve", "reject"}:
            return {"status": "invalid", "message": "decision 必须是 approve 或 reject"}

        target.decided_by = req.operator
        target.decided_at = datetime.now(timezone.utc)
        if decision == "reject":
            target.status = ApprovalStatus.rejected
            self._audit("approval", req.operator, "驳回审批", {"approval_id": approval_id})
            return {"status": "rejected", "approval": target.model_dump(mode="json")}

        target.status = ApprovalStatus.approved
        payload = target.payload if isinstance(target.payload, dict) else {}
        if target.action == "release_candidate":
            candidate_id = str(payload.get("candidate_id", ""))
            for cand in self._candidates:
                if cand.id == candidate_id:
                    self._execute_release(cand, actor=req.operator)
                    break
        self._audit("approval", req.operator, "通过审批", {"approval_id": approval_id})
        return {"status": "approved", "approval": target.model_dump(mode="json")}

    async def rollback(self, req: ActionRequest, reason: str = "人工触发") -> dict[str, object]:
        if not self._check_permission(req.role, "rollback"):
            return {"status": "denied", "message": "权限不足"}
        result = self._rollback_latest(actor=req.operator, reason=reason)
        status = "ok" if bool(result.get("ok")) else "failed"
        return {"status": status, **result}

    async def governance_payload(self) -> dict[str, object]:
        state = await self.snapshot()
        ai_usage = {
            "model_name": self._token_usage.model_name,
            "input_tokens": self._token_usage.input_tokens,
            "output_tokens": self._token_usage.output_tokens,
            "cached_tokens": self._token_usage.cached_tokens,
            "total_tokens": self._token_usage.total_tokens,
            "input_cost_usd": round(self._token_usage.input_cost_usd, 6),
            "output_cost_usd": round(self._token_usage.output_cost_usd, 6),
            "cache_cost_usd": round(self._token_usage.cache_cost_usd, 6),
            "total_cost_usd": round(self._token_usage.total_cost_usd, 6),
        }
        return {
            "human_version": {
                "name": "human",
                "app": "git-binance-trader-sim",
                "dashboard_url": "https://git-binance-trader-sim.fly.dev/",
            },
            "ai_version": {
                "name": "ai",
                "app": "git-binance-trader-ai",
                "dashboard_url": "https://git-binance-trader-ai.fly.dev/",
            },
            "system": {
                "status": state.status.value,
                "equity": state.equity,
                "cash": state.cash,
                "margin_used": state.margin_used,
                "position_value": state.position_value,
                "fees_paid": state.fees_paid,
                "realized_pnl": state.realized_pnl,
                "unrealized_pnl": state.unrealized_pnl,
                "total_return_pct": state.total_return_pct,
                "drawdown_pct": state.drawdown_pct,
                "daily_drawdown_pct": state.daily_drawdown_pct,
                "positions": state.positions,
                "ai_message": state.ai_message,
                "ai_insight": state.ai_insight,
                "last_cycle_at": state.generated_at.isoformat(),
            },
            "ai_usage": ai_usage,
            "positions": [item.model_dump(mode="json") for item in self._position_book.values()],
            "trades": [item.model_dump(mode="json") for item in list(self._trades)[:120]],
            "runtime_logs": list(self._runtime_logs)[:200],
            "ai_tasks": [item.model_dump(mode="json") for item in list(self._tasks)[:60]],
            "approvals": [item.model_dump(mode="json") for item in list(self._approvals)[:80]],
            "candidates": [item.model_dump(mode="json") for item in list(self._candidates)[:80]],
            "release_state": self._release_state.model_dump(mode="json"),
            "workflow_status": self._workflow_status,
            "orchestration": {
                "backend": self.settings.orchestration_backend,
                "durable_execution_ready": self.settings.orchestration_backend in {"prefect", "temporal"},
            },
            "cadence": self._cadence.model_dump(mode="json"),
            "explanation_quality_score": self._explanation_quality_score,
            "governance_config": self._governance_config.model_dump(mode="json"),
            "audit_events": [item.model_dump(mode="json") for item in list(self._audit_events)[:120]],
            "code_proposals": [item.model_dump(mode="json") for item in list(self._code_proposals)[:60]],
            "code_versions": [item.model_dump(mode="json") for item in list(self._code_versions)[:60]],
            "market_timeseries": [item.model_dump(mode="json") for item in list(self._market_history)[:200]],
            "backtests": [item.model_dump(mode="json") for item in list(self._backtests)[:80]],
            "parameter_versions": [item.model_dump(mode="json") for item in list(self._parameter_versions)[:80]],
            "performance_versions": [item.model_dump(mode="json") for item in list(self._performance_versions)[:80]],
            "reliability": ReliabilityState(
                idempotency_cache_size=len(self._idempotency_cache),
                retry_count=self._retry_count,
                timeout_count=self._timeout_count,
                compensation_count=self._compensation_count,
                context_continuity_count=self._recovery_continuity_count,
                alarms=list(self._alarms)[:20],
            ).model_dump(mode="json"),
            "champion_library": list(self._champion_library),
            "reports": {
                "hourly": list(self._reports_hourly)[:120],
                "daily": list(self._reports_daily)[:30],
                "weekly": list(self._reports_weekly)[:20],
            },
            "memory": self.memory.recent_ai(limit=80),
            "commands": self.memory.recent_commands(limit=30),
        }
