"""Bullish signals tuned by backtest win rates."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .entry import compute_entry_levels

# Backtest win rates (% uspesnost +5% do 5 dni, 120 tickerov, 2 roky)
BACKTEST_WIN_RATES = {
    "volume_surge": 22.6,
    "bullish_engulfing": 22.6,
    "momentum_up": 20.8,
    "bullish_candle": 20.7,
    "strong_close": 20.1,
    "breakout_20d": 20.0,
    "rsi_recovery": 19.7,
    "macd_cross": 17.3,
}

# Slabe signaly - neposielaju alert samostatne
LOW_VALUE_SIGNALS = frozenset({"rsi_recovery", "macd_cross"})

# Vahy len z top signalov (normalizovane na 100)
_tier_sum = sum(v for k, v in BACKTEST_WIN_RATES.items() if k not in LOW_VALUE_SIGNALS)
SIGNAL_WEIGHTS = {
    k: round(v / _tier_sum * 100)
    for k, v in BACKTEST_WIN_RATES.items()
    if k not in LOW_VALUE_SIGNALS
}
_weight_total = sum(SIGNAL_WEIGHTS.values())
if _weight_total != 100:
    SIGNAL_WEIGHTS["volume_surge"] += 100 - _weight_total

SIGNAL_LABELS = {
    "volume_surge": "Objemovy spike",
    "bullish_engulfing": "Bullish engulfing",
    "momentum_up": "Silny denny rast",
    "bullish_candle": "Zelena sviecka",
    "strong_close": "Zatvorenie pri maxime",
    "breakout_20d": "Breakout 20d high",
    "rsi_recovery": "RSI odraz",
    "macd_cross": "MACD cross",
}

CONFIRMATION_SIGNALS = frozenset({"momentum_up", "strong_close", "breakout_20d", "bullish_candle"})


@dataclass(frozen=True)
class BullishSetup:
    ticker: str
    score: int
    probability: str
    active_signals: tuple[str, ...]
    close_price: float
    price_change_pct: float
    volume_ratio: float
    rsi: float | None
    backtest_hint: str
    insider_buys: int = 0
    insider_buy_value: float = 0.0
    insider_names: tuple[str, ...] = ()
    insider_summary: str = ""
    insider_cluster: bool = False
    insider_latest_date: str | None = None
    insider_net_6m: float | None = None
    earnings_summary: str = ""
    earnings_trend: str = ""
    earnings_quarters: tuple[dict, ...] = ()
    entry_ideal: float = 0.0
    entry_zone_low: float = 0.0
    entry_zone_high: float = 0.0
    stop_loss: float = 0.0
    target_price: float = 0.0
    entry_action: str = ""
    entry_summary: str = ""
    market_bull: bool = True
    market_regime: str = ""
    relative_strength_pct: float | None = None
    pct_above_ma20: float | None = None
    extended: bool = False
    short_interest_pct: float | None = None
    revenue_accelerating: bool = False
    earnings_beat: bool | None = None
    days_to_earnings: int | None = None
    earnings_warning: str = ""
    fundamentals_summary: str = ""
    news_sentiment: str = ""
    news_score: float = 0.0
    sentiment_summary: str = ""
    tier: str = "C"
    tier_reason: str = ""

    @property
    def message(self) -> str:
        signals_text = ", ".join(self.active_signals)
        rsi_text = f"{self.rsi:.0f}" if self.rsi is not None else "n/a"
        insider_line = f"Insider: {self.insider_summary}\n" if self.insider_buys else ""
        earnings_line = f"Kvartaly: {self.earnings_summary}\n" if self.earnings_summary else ""
        entry_line = f"Vstup: {self.entry_summary}\n" if self.entry_summary else ""
        context_line = ""
        if self.market_regime:
            context_line += f"Rezim: {self.market_regime}\n"
        if self.relative_strength_pct is not None:
            context_line += f"Relative Strength vs IWM: {self.relative_strength_pct:+.1f}%\n"
        if self.fundamentals_summary:
            context_line += f"Fundamenty: {self.fundamentals_summary}\n"
        if self.sentiment_summary:
            context_line += f"Sentiment: {self.sentiment_summary}\n"
        tier_line = f"Tier {self.tier}: {self.tier_reason}\n"
        return (
            f"HIGH POTENTIAL SETUP: {self.ticker}\n"
            f"{tier_line}"
            f"Skore: {self.score}/100 ({self.probability})\n"
            f"Backtest: {self.backtest_hint}\n"
            f"{context_line}"
            f"{insider_line}"
            f"{earnings_line}"
            f"{entry_line}"
            f"Signaly: {signals_text}\n"
            f"Cena: ${self.close_price:.2f} ({self.price_change_pct:+.1f}%)\n"
            f"Objem: {self.volume_ratio:.1f}x priemer | RSI: {rsi_text}"
        )


def _rsi(series: pd.Series, period: int = 14) -> float | None:
    if len(series) < period + 1:
        return None
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, pd.NA)
    value = 100 - (100 / (1 + rs))
    last = value.iloc[-1]
    return float(last) if pd.notna(last) else None


def _macd_bullish_cross(close: pd.Series) -> bool:
    if len(close) < 35:
        return False
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    if len(macd) < 2:
        return False
    return float(macd.iloc[-2]) <= float(signal.iloc[-2]) and float(macd.iloc[-1]) > float(signal.iloc[-1])


def detect_signals(
    history: pd.DataFrame,
    lookback_days: int,
    volume_threshold: float,
    momentum_pct: float,
) -> tuple[dict[str, bool], float, float, float | None]:
    if len(history) < lookback_days + 2:
        return {}, 0.0, 0.0, None

    today = history.iloc[-1]
    yesterday = history.iloc[-2]
    prior = history.iloc[-(lookback_days + 1) : -1]

    open_ = float(today["Open"])
    high = float(today["High"])
    low = float(today["Low"])
    close = float(today["Close"])
    volume = float(today["Volume"])
    avg_volume = float(prior["Volume"].mean())

    prev_close = float(yesterday["Close"])
    price_change_pct = ((close - prev_close) / prev_close) * 100 if prev_close else 0.0
    volume_ratio = volume / avg_volume if avg_volume > 0 else 0.0

    day_range = high - low
    close_position = (close - low) / day_range if day_range > 0 else 0.0
    prior_high = float(prior["High"].max())

    y_open = float(yesterday["Open"])
    y_close = float(yesterday["Close"])
    engulfing = (
        close > open_
        and y_close < y_open
        and open_ <= y_close
        and close >= y_open
    )

    rsi_val = _rsi(history["Close"])
    rsi_prev = _rsi(history["Close"].iloc[:-1]) if len(history) > 15 else None
    rsi_recovery = (
        rsi_prev is not None
        and rsi_val is not None
        and rsi_prev < 40
        and rsi_val > rsi_prev
        and rsi_val < 72
    )

    signals = {
        "volume_surge": volume_ratio >= volume_threshold,
        "bullish_candle": close > open_,
        "strong_close": close_position >= 0.70 and close > open_,
        "momentum_up": price_change_pct >= momentum_pct,
        "breakout_20d": close > prior_high,
        "bullish_engulfing": engulfing,
        "rsi_recovery": rsi_recovery,
        "macd_cross": _macd_bullish_cross(history["Close"]),
    }

    return signals, price_change_pct, volume_ratio, rsi_val


def score_signals(signals: dict[str, bool], high_potential_only: bool = True) -> int:
    if high_potential_only:
        total = sum(
            SIGNAL_WEIGHTS[name]
            for name, active in signals.items()
            if active and name in SIGNAL_WEIGHTS
        )
    else:
        total = sum(
            round(BACKTEST_WIN_RATES.get(name, 0))
            for name, active in signals.items()
            if active
        )
    return min(100, total)


def is_high_potential(signals: dict[str, bool]) -> bool:
    """Len kombinacie s najvyssou backtest uspesnostou."""
    if signals.get("volume_surge"):
        return True

    if signals.get("bullish_engulfing"):
        return any(signals.get(name) for name in CONFIRMATION_SIGNALS)

    return False


def combo_probability(signals: dict[str, bool]) -> str:
    has_volume = signals.get("volume_surge", False)
    has_engulfing = signals.get("bullish_engulfing", False)
    confirmations = sum(1 for name in CONFIRMATION_SIGNALS if signals.get(name))

    if has_volume and has_engulfing:
        return "VELMI VYSOKA"
    if has_volume and confirmations >= 2:
        return "VELMI VYSOKA"
    if has_volume and confirmations >= 1:
        return "VYSOKA"
    if has_volume:
        return "VYSOKA"
    if has_engulfing and confirmations >= 2:
        return "VYSOKA"
    if has_engulfing:
        return "STREDNA"
    return "NIZKA"


def backtest_hint(signals: dict[str, bool]) -> str:
    active = [name for name, on in signals.items() if on and name in BACKTEST_WIN_RATES]
    if not active:
        return "bez dat"
    best = max(active, key=lambda n: BACKTEST_WIN_RATES[n])
    rate = BACKTEST_WIN_RATES[best]
    label = SIGNAL_LABELS.get(best, best)
    return f"top signal {label} ({rate}% historicka uspesnost)"


def analyze_bullish(
    ticker: str,
    history: pd.DataFrame,
    lookback_days: int = 20,
    volume_threshold: float = 2.0,
    momentum_pct: float = 2.0,
    min_score: int = 35,
    high_potential_only: bool = True,
    max_ma20_extension_pct: float = 5.0,
    filter_extended: bool = True,
) -> BullishSetup | None:
    signals, price_change_pct, volume_ratio, rsi = detect_signals(
        history, lookback_days, volume_threshold, momentum_pct
    )
    if not signals:
        return None

    if high_potential_only and not is_high_potential(signals):
        return None

    score = score_signals(signals, high_potential_only=high_potential_only)
    if score < min_score:
        return None

    active = tuple(
        SIGNAL_LABELS[name]
        for name, on in signals.items()
        if on and name in SIGNAL_WEIGHTS
    )
    if not active:
        return None

    close_price = float(history.iloc[-1]["Close"])

    from .market_context import is_too_extended, pct_above_ma20, relative_strength_vs_benchmark

    above_ma20 = pct_above_ma20(history)
    extended = is_too_extended(history, max_ma20_extension_pct)
    if filter_extended and extended:
        return None

    rs = relative_strength_vs_benchmark(history, "IWM", lookback_days)
    entry = compute_entry_levels(history, signals, close_price)

    return BullishSetup(
        ticker=ticker,
        score=score,
        probability=combo_probability(signals),
        active_signals=active,
        close_price=close_price,
        price_change_pct=price_change_pct,
        volume_ratio=volume_ratio,
        rsi=rsi,
        backtest_hint=backtest_hint(signals),
        entry_ideal=entry.entry_ideal if entry else 0.0,
        entry_zone_low=entry.entry_zone_low if entry else 0.0,
        entry_zone_high=entry.entry_zone_high if entry else 0.0,
        stop_loss=entry.stop_loss if entry else 0.0,
        target_price=entry.target_price if entry else 0.0,
        entry_action=entry.action if entry else "",
        entry_summary=entry.summary if entry else "",
        relative_strength_pct=rs,
        pct_above_ma20=above_ma20,
        extended=extended,
    )