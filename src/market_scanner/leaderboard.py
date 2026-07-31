"""Persistent ranked list of discovered high-potential stocks."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import PROJECT_ROOT
from .signals import BullishSetup

LEADERBOARD_PATH = PROJECT_ROOT / "config" / "leaderboard.json"
LAST_SCAN_PATH = PROJECT_ROOT / "config" / "last_scan.json"

PROBABILITY_BONUS = {
    "VELMI VYSOKA": 25.0,
    "VYSOKA": 15.0,
    "STREDNA": 5.0,
    "NIZKA": 0.0,
}


def compute_potential_rank(setup: BullishSetup) -> float:
    prob = PROBABILITY_BONUS.get(setup.probability, 0.0)
    volume_bonus = min(setup.volume_ratio * 3.0, 15.0)
    momentum_bonus = min(max(setup.price_change_pct, 0.0) * 0.5, 10.0)
    insider_bonus = 0.0
    if setup.insider_cluster:
        insider_bonus = 20.0
    elif setup.insider_buys > 0:
        insider_bonus = 12.0
    elif setup.insider_net_6m is not None and setup.insider_net_6m > 0:
        insider_bonus = 5.0
    earnings_bonus = 5.0 if setup.earnings_trend == "rastuca" else 0.0
    rs_bonus = min(max(setup.relative_strength_pct or 0.0, 0.0) * 0.8, 12.0)
    tier_bonus = {"S": 30.0, "A": 18.0, "B": 6.0, "C": 0.0}.get(setup.tier, 0.0)
    sentiment_bonus = 5.0 if setup.news_sentiment == "pozitivny" else 0.0
    fund_bonus = 8.0 if setup.revenue_accelerating or setup.earnings_beat is True else 0.0
    if setup.earnings_warning:
        tier_bonus = max(0.0, tier_bonus - 15.0)
    return round(
        setup.score + prob + volume_bonus + momentum_bonus + insider_bonus
        + earnings_bonus + rs_bonus + tier_bonus + sentiment_bonus + fund_bonus,
        1,
    )


def _setup_to_entry(setup: BullishSetup) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    rank = compute_potential_rank(setup)
    return {
        "ticker": setup.ticker,
        "potential_rank": rank,
        "score": setup.score,
        "probability": setup.probability,
        "close_price": setup.close_price,
        "price_change_pct": setup.price_change_pct,
        "volume_ratio": setup.volume_ratio,
        "rsi": setup.rsi,
        "signals": list(setup.active_signals),
        "backtest_hint": setup.backtest_hint,
        "insider_buys": setup.insider_buys,
        "insider_buy_value": setup.insider_buy_value,
        "insider_names": list(setup.insider_names),
        "insider_summary": setup.insider_summary,
        "insider_cluster": setup.insider_cluster,
        "insider_latest_date": setup.insider_latest_date,
        "earnings_summary": setup.earnings_summary,
        "earnings_trend": setup.earnings_trend,
        "earnings_quarters": list(setup.earnings_quarters),
        "entry_ideal": setup.entry_ideal,
        "entry_zone_low": setup.entry_zone_low,
        "entry_zone_high": setup.entry_zone_high,
        "stop_loss": setup.stop_loss,
        "target_price": setup.target_price,
        "entry_action": setup.entry_action,
        "entry_summary": setup.entry_summary,
        "market_bull": setup.market_bull,
        "market_regime": setup.market_regime,
        "relative_strength_pct": setup.relative_strength_pct,
        "pct_above_ma20": setup.pct_above_ma20,
        "extended": setup.extended,
        "short_interest_pct": setup.short_interest_pct,
        "revenue_accelerating": setup.revenue_accelerating,
        "earnings_beat": setup.earnings_beat,
        "days_to_earnings": setup.days_to_earnings,
        "earnings_warning": setup.earnings_warning,
        "fundamentals_summary": setup.fundamentals_summary,
        "news_sentiment": setup.news_sentiment,
        "news_score": setup.news_score,
        "sentiment_summary": setup.sentiment_summary,
        "tier": setup.tier,
        "tier_reason": setup.tier_reason,
        "first_seen": now,
        "last_seen": now,
        "scan_count": 1,
    }


def load_leaderboard() -> list[dict]:
    if not LEADERBOARD_PATH.exists():
        return []
    data = json.loads(LEADERBOARD_PATH.read_text(encoding="utf-8"))
    return sorted(data, key=lambda x: x.get("potential_rank", 0), reverse=True)


def merge_setups(setups: list[BullishSetup]) -> list[dict]:
    existing = {item["ticker"]: item for item in load_leaderboard()}
    now = datetime.now(timezone.utc).isoformat()

    for setup in setups:
        entry = _setup_to_entry(setup)
        ticker = setup.ticker
        if ticker in existing:
            old = existing[ticker]
            entry["first_seen"] = old.get("first_seen", now)
            entry["scan_count"] = old.get("scan_count", 0) + 1
        existing[ticker] = entry
        existing[ticker]["last_seen"] = now

    ranked = sorted(existing.values(), key=lambda x: x["potential_rank"], reverse=True)
    LEADERBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEADERBOARD_PATH.write_text(json.dumps(ranked, indent=2, ensure_ascii=False), encoding="utf-8")
    return ranked


def clear_leaderboard() -> None:
    if LEADERBOARD_PATH.exists():
        LEADERBOARD_PATH.unlink()
    if LAST_SCAN_PATH.exists():
        LAST_SCAN_PATH.unlink()


def record_last_scan(setups_found: int = 0) -> str:
    now = datetime.now(timezone.utc).isoformat()
    LAST_SCAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAST_SCAN_PATH.write_text(
        json.dumps({"at": now, "setups_found": setups_found}, indent=2),
        encoding="utf-8",
    )
    return now


def get_last_scan() -> dict | None:
    if not LAST_SCAN_PATH.exists():
        return None
    return json.loads(LAST_SCAN_PATH.read_text(encoding="utf-8"))


def latest_board_timestamp(board: list[dict]) -> str | None:
    timestamps = [item.get("last_seen", "") for item in board if item.get("last_seen")]
    return max(timestamps) if timestamps else None