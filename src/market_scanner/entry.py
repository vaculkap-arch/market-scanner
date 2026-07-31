"""Entry price zones from support, MA20 and breakout levels."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class EntryRecommendation:
    entry_ideal: float
    entry_zone_low: float
    entry_zone_high: float
    stop_loss: float
    target_price: float
    risk_reward: float
    action: str
    summary: str


_ACTION_LABELS = {
    "vstup_teraz": "Vstup teraz pri aktualnej cene",
    "cakat_pullback": "Cakat na pullback k MA20/podpore",
    "limit_order": "Limitny prikaz v buy zone",
}


def compute_entry_levels(
    history: pd.DataFrame,
    signals: dict[str, bool],
    close_price: float,
    lookback: int = 20,
) -> EntryRecommendation | None:
    if len(history) < lookback + 2 or close_price <= 0:
        return None

    prior = history.iloc[-(lookback + 1) : -1]
    today = history.iloc[-1]

    ma20 = float(history["Close"].rolling(20).mean().iloc[-1])
    low_5d = float(prior["Low"].tail(5).min())
    low_20d = float(prior["Low"].min())
    high_20d = float(prior["High"].max())
    today_low = float(today["Low"])

    supports = sorted(
        [x for x in (ma20, low_5d, low_20d, today_low) if x < close_price * 0.999],
        reverse=True,
    )
    primary_support = supports[0] if supports else close_price * 0.97

    pct_above_ma20 = ((close_price - ma20) / ma20 * 100) if ma20 else 0.0
    is_breakout = signals.get("breakout_20d", False)

    if is_breakout:
        if close_price <= high_20d * 1.015:
            entry_ideal = close_price
            entry_zone_low = max(high_20d * 0.995, today_low)
            entry_zone_high = close_price * 1.01
            action = "vstup_teraz"
        else:
            entry_ideal = high_20d
            entry_zone_low = high_20d * 0.995
            entry_zone_high = min(close_price, high_20d * 1.02)
            action = "cakat_pullback"
    elif pct_above_ma20 > 3:
        entry_ideal = ma20
        entry_zone_low = ma20 * 0.98
        entry_zone_high = ma20 * 1.02
        action = "cakat_pullback"
    elif pct_above_ma20 <= 1.5:
        entry_ideal = close_price
        entry_zone_low = max(today_low, primary_support * 0.995)
        entry_zone_high = close_price * 1.01
        action = "vstup_teraz"
    else:
        entry_ideal = round((primary_support + close_price) / 2, 2)
        entry_zone_low = primary_support
        entry_zone_high = close_price
        action = "limit_order"

    if entry_zone_low > entry_zone_high:
        entry_zone_low, entry_zone_high = entry_zone_high, entry_zone_low

    stop_loss = min(entry_zone_low * 0.97, low_20d * 0.98)
    if stop_loss >= entry_ideal:
        stop_loss = entry_ideal * 0.95

    risk = entry_ideal - stop_loss
    target_rr = entry_ideal + risk * 2 if risk > 0 else close_price * 1.05
    target_pct = entry_ideal * 1.05
    target_price = min(target_rr, target_pct) if risk > 0 else target_pct
    risk_reward = (target_price - entry_ideal) / risk if risk > 0 else 0.0

    summary = (
        f"{_ACTION_LABELS[action]} | ideal ${entry_ideal:.2f} "
        f"(zona ${entry_zone_low:.2f}-${entry_zone_high:.2f}) | "
        f"stop ${stop_loss:.2f} | ciel ${target_price:.2f} (R/R {risk_reward:.1f})"
    )

    return EntryRecommendation(
        entry_ideal=round(entry_ideal, 2),
        entry_zone_low=round(entry_zone_low, 2),
        entry_zone_high=round(entry_zone_high, 2),
        stop_loss=round(stop_loss, 2),
        target_price=round(target_price, 2),
        risk_reward=round(risk_reward, 1),
        action=action,
        summary=summary,
    )
