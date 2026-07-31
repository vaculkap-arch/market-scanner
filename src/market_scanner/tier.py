"""Trade quality tiers S/A/B/C based on multi-factor analysis."""

from __future__ import annotations

from dataclasses import replace

from .config import Settings
from .signals import BullishSetup

TIER_ORDER = {"S": 4, "A": 3, "B": 2, "C": 1}


def _has_volume_surge(setup: BullishSetup) -> bool:
    return any("Objemovy spike" in s or "spike" in s.lower() for s in setup.active_signals)


def _score_in_sweet_spot(score: int) -> bool:
    return 60 <= score <= 74


def compute_tier(setup: BullishSetup, settings: Settings) -> BullishSetup:
    reasons: list[str] = []
    score = setup.score

    if setup.earnings_warning:
        return replace(setup, tier="C", tier_reason=f"Blizke earnings: {setup.earnings_warning}")

    if setup.extended:
        return replace(setup, tier="C", tier_reason="Prilis nad MA20 (extended)")

    if settings.regime_filter and not setup.market_bull:
        return replace(setup, tier="C", tier_reason=f"Bear rezim: {setup.market_regime}")

    rs = setup.relative_strength_pct
    rs_ok = rs is not None and rs >= settings.min_relative_strength_pct
    fund_ok = (
        setup.earnings_trend == "rastuca"
        or setup.revenue_accelerating
        or setup.earnings_beat is True
    )
    insider_ok = setup.insider_buys > 0
    insider_cluster = setup.insider_cluster
    sentiment_ok = setup.news_sentiment in ("pozitivny", "neutralny")
    short_squeeze = setup.short_interest_pct is not None and setup.short_interest_pct >= 10.0

    # Tier S
    s_checks = [
        _score_in_sweet_spot(score),
        _has_volume_surge(setup),
        rs_ok,
        setup.market_bull,
        not setup.extended,
        insider_ok or fund_ok,
        sentiment_ok,
    ]
    if all(s_checks):
        if insider_cluster:
            reasons.append("insider cluster")
        if fund_ok:
            reasons.append("silne fundamenty")
        if rs_ok and rs is not None:
            reasons.append(f"RS +{rs:.1f}%")
        if short_squeeze:
            reasons.append("vysoky short")
        return replace(setup, tier="S", tier_reason="Super setup: " + ", ".join(reasons))

    # Tier A
    a_checks = [
        score >= settings.bullish_min_score,
        _has_volume_surge(setup) or "Bullish engulfing" in setup.active_signals,
        (rs_ok or setup.market_bull),
        sentiment_ok,
    ]
    if all(a_checks):
        if fund_ok:
            reasons.append("fundamenty OK")
        if insider_ok:
            reasons.append("insider")
        if rs_ok and rs is not None:
            reasons.append(f"RS +{rs:.1f}%")
        return replace(setup, tier="A", tier_reason="Silny setup: " + (", ".join(reasons) or "technika+rezim"))

    # Tier B
    if score >= settings.bullish_min_score and setup.probability in ("VELMI VYSOKA", "VYSOKA", "STREDNA"):
        return replace(setup, tier="B", tier_reason="High-potential technicky setup")

    return replace(setup, tier="C", tier_reason="Slabsi setup")


def tier_meets_minimum(tier: str, minimum: str) -> bool:
    return TIER_ORDER.get(tier, 0) >= TIER_ORDER.get(minimum, 0)
