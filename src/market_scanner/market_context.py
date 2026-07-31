"""Market regime and relative strength vs benchmark."""

from __future__ import annotations

import pandas as pd

from .scanner import fetch_ticker_data

_BENCHMARK_CACHE: dict[str, pd.DataFrame] = {}


def _benchmark_history(symbol: str, lookback_days: int = 120) -> pd.DataFrame | None:
    if symbol not in _BENCHMARK_CACHE:
        history = fetch_ticker_data(symbol, lookback_days)
        if history is None:
            return None
        _BENCHMARK_CACHE[symbol] = history
    return _BENCHMARK_CACHE[symbol]


def clear_benchmark_cache() -> None:
    _BENCHMARK_CACHE.clear()


def is_bull_regime(symbol: str = "SPY", ma_days: int = 50) -> tuple[bool, str]:
    history = _benchmark_history(symbol, ma_days + 30)
    if history is None or len(history) < ma_days + 1:
        return True, "neznamy rezim (povolene)"

    close = float(history["Close"].iloc[-1])
    ma = float(history["Close"].rolling(ma_days).mean().iloc[-1])
    if close > ma:
        return True, f"bull ({symbol} ${close:.2f} > MA{ma_days} ${ma:.2f})"
    return False, f"bear ({symbol} ${close:.2f} < MA{ma_days} ${ma:.2f})"


def pct_above_ma20(history: pd.DataFrame) -> float | None:
    if history is None or len(history) < 21:
        return None
    close = float(history["Close"].iloc[-1])
    ma20 = float(history["Close"].rolling(20).mean().iloc[-1])
    if ma20 <= 0:
        return None
    return round((close - ma20) / ma20 * 100, 2)


def is_too_extended(history: pd.DataFrame, max_pct: float = 5.0) -> bool:
    pct = pct_above_ma20(history)
    return pct is not None and pct > max_pct


def relative_strength_vs_benchmark(
    history: pd.DataFrame,
    benchmark: str = "IWM",
    lookback_days: int = 20,
) -> float | None:
    if history is None or len(history) < lookback_days + 1:
        return None

    bench = _benchmark_history(benchmark, lookback_days + 35)
    if bench is None or len(bench) < lookback_days + 1:
        return None

    ticker_start = float(history["Close"].iloc[-(lookback_days + 1)])
    ticker_end = float(history["Close"].iloc[-1])
    bench_start = float(bench["Close"].iloc[-(lookback_days + 1)])
    bench_end = float(bench["Close"].iloc[-1])

    if ticker_start <= 0 or bench_start <= 0:
        return None

    ticker_ret = (ticker_end - ticker_start) / ticker_start * 100
    bench_ret = (bench_end - bench_start) / bench_start * 100
    return round(ticker_ret - bench_ret, 2)
