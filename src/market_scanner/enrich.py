"""Enrich bullish setups with market, fundamental and sentiment data."""

from __future__ import annotations

from dataclasses import replace

from .config import Settings
from .earnings import earnings_to_dict, get_earnings_summary
from .fundamentals import get_fundamentals
from .insider import get_insider_activity
from .market_context import is_bull_regime
from .sentiment import get_sentiment
from .signals import BullishSetup
from .tier import compute_tier


def enrich_with_insider(setup: BullishSetup, lookback_days: int = 90) -> BullishSetup:
    activity = get_insider_activity(setup.ticker, lookback_days)
    signals = list(setup.active_signals)
    if activity.has_recent_insider_buying:
        label = "Insider nakup (manazer)"
        if activity.has_cluster_buying:
            label = "Insider cluster nakup (2+ manazerov)"
        if label not in signals:
            signals = signals + [label]
    return replace(
        setup,
        active_signals=tuple(signals),
        insider_buys=activity.recent_buys,
        insider_buy_value=activity.total_buy_value,
        insider_names=activity.insiders,
        insider_summary=activity.summary,
        insider_cluster=activity.has_cluster_buying,
        insider_latest_date=activity.latest_buy_date,
        insider_net_6m=activity.net_shares_6m,
    )


def enrich_with_earnings(setup: BullishSetup) -> BullishSetup:
    summary = get_earnings_summary(setup.ticker)
    if summary is None:
        return setup
    data = earnings_to_dict(summary)
    return replace(
        setup,
        earnings_summary=summary.summary_line,
        earnings_trend=summary.revenue_trend,
        earnings_quarters=tuple(data["quarters"]),
    )


def enrich_with_fundamentals(setup: BullishSetup, settings: Settings) -> BullishSetup:
    fund = get_fundamentals(setup.ticker, settings.earnings_warn_days)
    signals = list(setup.active_signals)
    if fund.revenue_accelerating and "Trzby zrychluju" not in signals:
        signals.append("Trzby zrychluju")
    if fund.earnings_beat is True and "Earnings beat" not in signals:
        signals.append("Earnings beat")
    if fund.short_interest_pct is not None and fund.short_interest_pct >= 10:
        label = f"Vysoky short ({fund.short_interest_pct:.0f}%)"
        if label not in signals:
            signals.append(label)
    return replace(
        setup,
        active_signals=tuple(signals),
        short_interest_pct=fund.short_interest_pct,
        revenue_accelerating=fund.revenue_accelerating,
        earnings_beat=fund.earnings_beat,
        days_to_earnings=fund.days_to_earnings,
        earnings_warning=fund.earnings_warning,
        fundamentals_summary=fund.summary,
    )


def enrich_with_market_regime(setup: BullishSetup) -> BullishSetup:
    bull, label = is_bull_regime()
    return replace(setup, market_bull=bull, market_regime=label)


def enrich_with_sentiment(setup: BullishSetup, settings: Settings) -> BullishSetup:
    if not settings.enable_sentiment:
        return setup
    snap = get_sentiment(setup.ticker, settings)
    signals = list(setup.active_signals)
    if snap.label == "pozitivny" and "Pozitivny sentiment" not in signals:
        signals.append("Pozitivny sentiment")
    return replace(
        setup,
        active_signals=tuple(signals),
        news_sentiment=snap.label,
        news_score=snap.score,
        sentiment_summary=snap.summary,
    )


def enrich_setup(setup: BullishSetup, settings: Settings) -> BullishSetup:
    setup = enrich_with_market_regime(setup)
    setup = enrich_with_insider(setup, settings.insider_lookback_days)
    setup = enrich_with_earnings(setup)
    setup = enrich_with_fundamentals(setup, settings)
    setup = enrich_with_sentiment(setup, settings)
    return compute_tier(setup, settings)
