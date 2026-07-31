"""Market cap lookup and small/mid-cap classification."""

from __future__ import annotations

import yfinance as yf

SMALL_CAP_MIN = 300_000_000
SMALL_CAP_MAX = 2_000_000_000
MID_CAP_MAX = 10_000_000_000


def get_market_cap(ticker: str) -> int | None:
    info = yf.Ticker(ticker).info
    cap = info.get("marketCap")
    if cap is None:
        return None
    return int(cap)


def classify_cap(market_cap: int) -> str:
    if market_cap < SMALL_CAP_MIN:
        return "micro-cap"
    if market_cap <= SMALL_CAP_MAX:
        return "small-cap"
    if market_cap <= MID_CAP_MAX:
        return "mid-cap"
    return "large-cap"


def is_target_cap(market_cap: int, min_cap: int, max_cap: int) -> bool:
    return min_cap <= market_cap <= max_cap