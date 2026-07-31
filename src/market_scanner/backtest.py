"""Historical backtest for bullish signal combinations."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yfinance as yf

from .config import PROJECT_ROOT, Settings, load_tickers
from .scanner import _extract_ticker_history
from .signals import (
    SIGNAL_LABELS,
    BACKTEST_WIN_RATES,
    detect_signals,
    is_high_potential,
    score_signals,
)

RESULTS_PATH = PROJECT_ROOT / "config" / "backtest_results.txt"


@dataclass
class SignalStats:
    wins: int = 0
    total: int = 0
    return_sum: float = 0.0

    @property
    def win_rate(self) -> float:
        return (self.wins / self.total * 100) if self.total else 0.0

    @property
    def avg_return(self) -> float:
        return self.return_sum / self.total if self.total else 0.0


@dataclass
class BacktestReport:
    total_setups: int = 0
    overall_wins: int = 0
    overall_return_sum: float = 0.0
    high_potential_setups: int = 0
    high_potential_wins: int = 0
    high_potential_return_sum: float = 0.0
    train_setups: int = 0
    train_wins: int = 0
    train_return_sum: float = 0.0
    test_setups: int = 0
    test_wins: int = 0
    test_return_sum: float = 0.0
    by_signal: dict[str, SignalStats] = field(default_factory=dict)
    by_score_bucket: dict[str, SignalStats] = field(default_factory=dict)
    by_combo: dict[str, SignalStats] = field(default_factory=dict)

    def record(
        self,
        score: int,
        signals: dict[str, bool],
        forward_return: float,
        target_pct: float,
        *,
        is_test_period: bool = False,
    ) -> None:
        win = forward_return >= target_pct
        self.total_setups += 1
        self.overall_return_sum += forward_return
        if win:
            self.overall_wins += 1

        if is_test_period:
            self.test_setups += 1
            self.test_return_sum += forward_return
            if win:
                self.test_wins += 1
        else:
            self.train_setups += 1
            self.train_return_sum += forward_return
            if win:
                self.train_wins += 1

        if is_high_potential(signals):
            self.high_potential_setups += 1
            self.high_potential_return_sum += forward_return
            if win:
                self.high_potential_wins += 1

        bucket = _score_bucket(score)
        if bucket not in self.by_score_bucket:
            self.by_score_bucket[bucket] = SignalStats()
        b = self.by_score_bucket[bucket]
        b.total += 1
        b.return_sum += forward_return
        if win:
            b.wins += 1

        combo_key = _combo_key(signals)
        if combo_key not in self.by_combo:
            self.by_combo[combo_key] = SignalStats()
        c = self.by_combo[combo_key]
        c.total += 1
        c.return_sum += forward_return
        if win:
            c.wins += 1

        for name, active in signals.items():
            if not active:
                continue
            if name not in self.by_signal:
                self.by_signal[name] = SignalStats()
            s = self.by_signal[name]
            s.total += 1
            s.return_sum += forward_return
            if win:
                s.wins += 1


def _combo_key(signals: dict[str, bool]) -> str:
    parts: list[str] = []
    if signals.get("volume_surge"):
        parts.append("volume")
    if signals.get("bullish_engulfing"):
        parts.append("engulfing")
    if any(signals.get(n) for n in ("momentum_up", "strong_close", "breakout_20d")):
        parts.append("confirm")
    return "+".join(parts) if parts else "other"


def _score_bucket(score: int) -> str:
    if score >= 75:
        return "75-100"
    if score >= 60:
        return "60-74"
    if score >= 35:
        return "35-59"
    return "0-34"


def _forward_return(history: pd.DataFrame, idx: int, forward_days: int) -> float | None:
    if idx + forward_days >= len(history):
        return None
    entry = float(history.iloc[idx]["Close"])
    exit_price = float(history.iloc[idx + forward_days]["Close"])
    if entry <= 0:
        return None
    return (exit_price - entry) / entry * 100


def _backtest_history(history: pd.DataFrame, settings: Settings) -> list[tuple[int, dict[str, bool], float, bool]]:
    results: list[tuple[int, dict[str, bool], float, bool]] = []
    lookback = settings.lookback_days
    forward = settings.backtest_forward_days
    min_idx = lookback + 2
    max_idx = len(history) - forward
    split_idx = min_idx + int((max_idx - min_idx) * 0.6)

    for idx in range(min_idx, max_idx):
        window = history.iloc[: idx + 1]
        signals, _, _, _ = detect_signals(
            window,
            lookback,
            settings.bullish_volume_threshold,
            settings.bullish_momentum_pct,
        )
        if not signals:
            continue

        if settings.high_potential_only and not is_high_potential(signals):
            continue

        score = score_signals(signals, high_potential_only=True)
        if score < settings.bullish_min_score:
            continue

        fwd = _forward_return(history, idx, forward)
        if fwd is None:
            continue

        results.append((score, signals, fwd, idx >= split_idx))

    return results


def _fetch_backtest_histories(tickers: list[str], period: str, chunk_size: int) -> dict[str, pd.DataFrame]:
    histories: dict[str, pd.DataFrame] = {}

    for start in range(0, len(tickers), chunk_size):
        chunk = tickers[start : start + chunk_size]
        print(f"[backtest] Stahujem {start + 1}-{start + len(chunk)} / {len(tickers)}...")

        data = yf.download(
            tickers=chunk,
            period=period,
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
        )

        if data.empty:
            time.sleep(3)
            continue

        for ticker in chunk:
            history = _extract_ticker_history(data, ticker)
            if history is not None and len(history) >= 120:
                histories[ticker] = history

        time.sleep(3)

    return histories


def run_backtest(settings: Settings) -> BacktestReport:
    tickers = load_tickers(settings)
    if settings.backtest_max_tickers > 0:
        tickers = tickers[: settings.backtest_max_tickers]

    period = f"{settings.backtest_years}y"
    print(f"[backtest] Obdobie: {period} | tickerov: {len(tickers)}")
    print(f"[backtest] Filter: HIGH POTENTIAL only | min skore: {settings.bullish_min_score}")

    histories = _fetch_backtest_histories(tickers, period, settings.batch_chunk_size)
    report = BacktestReport()

    for history in histories.values():
        events = _backtest_history(history, settings)
        for score, signals, fwd, is_test in events:
            report.record(score, signals, fwd, settings.backtest_target_pct, is_test_period=is_test)

    return report


def format_report(report: BacktestReport, settings: Settings) -> str:
    lines: list[str] = []
    lines.append("=" * 55)
    lines.append("BACKTEST - HIGH POTENTIAL signaly")
    lines.append("=" * 55)
    lines.append(f"Ciel: +{settings.backtest_target_pct}% do {settings.backtest_forward_days} dni")
    lines.append(f"High-potential setupov: {report.high_potential_setups}")

    if report.high_potential_setups:
        hp_wr = report.high_potential_wins / report.high_potential_setups * 100
        hp_avg = report.high_potential_return_sum / report.high_potential_setups
        lines.append(f"Uspesnost (HIGH POTENTIAL): {hp_wr:.1f}% | priemer: {hp_avg:+.2f}%")

    lines.append("")
    lines.append("Pravidla alertu:")
    lines.append("  1. Objemovy spike (samostatne)")
    lines.append("  2. Bullish engulfing + potvrdenie (rast/max/breakout)")
    lines.append("  RSI a MACD sa ignoruju (slaba uspesnost)")

    if not report.by_signal:
        lines.append("")
        lines.append("Ziadne data.")
        return "\n".join(lines)

    lines.append("")
    lines.append("--- Referencna uspesnost signalov ---")
    for name, rate in sorted(BACKTEST_WIN_RATES.items(), key=lambda x: x[1], reverse=True):
        label = SIGNAL_LABELS.get(name, name)
        lines.append(f"  {label}: {rate}%")

    lines.append("")
    lines.append("--- Walk-forward (60% train / 40% test) ---")
    if report.train_setups:
        tr_wr = report.train_wins / report.train_setups * 100
        tr_avg = report.train_return_sum / report.train_setups
        lines.append(f"  Train: {tr_wr:.1f}% ({report.train_wins}/{report.train_setups}), priemer {tr_avg:+.2f}%")
    if report.test_setups:
        te_wr = report.test_wins / report.test_setups * 100
        te_avg = report.test_return_sum / report.test_setups
        lines.append(f"  Test:  {te_wr:.1f}% ({report.test_wins}/{report.test_setups}), priemer {te_avg:+.2f}%")

    lines.append("")
    lines.append("--- Kombinacie signalov ---")
    for combo, s in sorted(report.by_combo.items(), key=lambda x: x[1].win_rate, reverse=True):
        if s.total >= 10:
            lines.append(f"  {combo}: {s.win_rate:.1f}% ({s.wins}/{s.total}), priemer {s.avg_return:+.2f}%")

    lines.append("")
    lines.append("--- Podla skore (high potential) ---")
    for bucket in sorted(report.by_score_bucket.keys(), reverse=True):
        s = report.by_score_bucket[bucket]
        lines.append(
            f"  {bucket}: {s.win_rate:.1f}% ({s.wins}/{s.total}), priemer {s.avg_return:+.2f}%"
        )

    lines.append("=" * 55)
    return "\n".join(lines)


def save_and_print_report(report: BacktestReport, settings: Settings) -> str:
    text = format_report(report, settings)
    print(text)
    RESULTS_PATH.write_text(text + "\n", encoding="utf-8")
    print(f"\n[backtest] Ulozene do {RESULTS_PATH}")
    return text