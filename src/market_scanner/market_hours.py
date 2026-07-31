"""US stock market session hours (NYSE/NASDAQ) with holidays."""

from __future__ import annotations

from datetime import date, datetime, time
from functools import lru_cache
from zoneinfo import ZoneInfo

import pandas_market_calendars as mcal

EASTERN = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)


@lru_cache(maxsize=1)
def _nyse() -> mcal.MarketCalendar:
    return mcal.get_calendar("NYSE")


def now_eastern() -> datetime:
    return datetime.now(EASTERN)


def is_trading_day(day: date | None = None) -> bool:
    day = day or now_eastern().date()
    schedule = _nyse().schedule(start_date=day, end_date=day)
    return not schedule.empty


def is_us_market_open(now: datetime | None = None) -> bool:
    now = now or now_eastern()

    if not is_trading_day(now.date()):
        return False

    return MARKET_OPEN <= now.time() < MARKET_CLOSE


def market_status(now: datetime | None = None) -> str:
    now = now or now_eastern()
    open_str = MARKET_OPEN.strftime("%H:%M")
    close_str = MARKET_CLOSE.strftime("%H:%M")
    today = now.date()

    if not is_trading_day(today):
        if now.weekday() >= 5:
            return f"vikend (burza {open_str}-{close_str} ET, Po-Pi)"
        return f"sviatok US burzy ({today.strftime('%Y-%m-%d')}, teraz {now.strftime('%H:%M')} ET)"

    if is_us_market_open(now):
        return f"OTVORENA do {close_str} ET (teraz {now.strftime('%H:%M')} ET)"

    if now.time() < MARKET_OPEN:
        return f"este zatvorena, otvorenie o {open_str} ET (teraz {now.strftime('%H:%M')} ET)"

    return f"zatvorena po {close_str} ET (teraz {now.strftime('%H:%M')} ET)"