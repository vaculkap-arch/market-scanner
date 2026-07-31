"""Fundamental filters: short interest, earnings calendar, revenue acceleration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from .earnings import get_earnings_summary


@dataclass(frozen=True)
class FundamentalSnapshot:
    short_interest_pct: float | None
    revenue_accelerating: bool
    earnings_beat: bool | None
    days_to_earnings: int | None
    earnings_warning: str
    debt_to_equity: float | None
    summary: str


def _days_until(ts) -> int | None:
    try:
        dt = pd.Timestamp(ts).tz_localize(None) if pd.Timestamp(ts).tzinfo else pd.Timestamp(ts)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return (dt.to_pydatetime().date() - now.date()).days
    except Exception:
        return None


def _revenue_accelerating(ticker: str) -> bool:
    summary = get_earnings_summary(ticker)
    if summary is None or len(summary.quarters) < 3:
        return False
    qoq = [q.revenue_qoq_pct for q in summary.quarters if q.revenue_qoq_pct is not None]
    if len(qoq) < 2:
        return False
    return qoq[0] is not None and qoq[1] is not None and qoq[0] > qoq[1]


def _earnings_beat(ticker: str) -> bool | None:
    try:
        stock = yf.Ticker(ticker)
        history = stock.earnings_history
        if history is None or history.empty:
            return None
        row = history.iloc[0]
        surprise = row.get("epsDifference") or row.get("surprisePercent")
        if surprise is None or pd.isna(surprise):
            return None
        return float(surprise) > 0
    except Exception:
        return None


def get_fundamentals(ticker: str, earnings_warn_days: int = 2) -> FundamentalSnapshot:
    short_pct: float | None = None
    debt_to_equity: float | None = None
    days_to_earnings: int | None = None
    earnings_warning = ""

    try:
        info = yf.Ticker(ticker).info or {}
        raw_short = info.get("shortPercentOfFloat") or info.get("shortPercentOfSharesOutstanding")
        if raw_short is not None:
            short_pct = round(float(raw_short) * 100, 2) if float(raw_short) < 1 else round(float(raw_short), 2)
        raw_de = info.get("debtToEquity")
        if raw_de is not None:
            debt_to_equity = round(float(raw_de), 1)
    except Exception:
        pass

    try:
        cal = yf.Ticker(ticker).calendar
        if isinstance(cal, dict):
            earnings_date = cal.get("Earnings Date")
            if isinstance(earnings_date, list) and earnings_date:
                days_to_earnings = _days_until(earnings_date[0])
            elif earnings_date is not None:
                days_to_earnings = _days_until(earnings_date)
        elif cal is not None and not getattr(cal, "empty", True):
            if "Earnings Date" in cal.index:
                val = cal.loc["Earnings Date"].iloc[0]
                if isinstance(val, list) and val:
                    days_to_earnings = _days_until(val[0])
                else:
                    days_to_earnings = _days_until(val)
    except Exception:
        pass

    if days_to_earnings is not None and 0 <= days_to_earnings <= earnings_warn_days:
        earnings_warning = f"Pozor: earnings o {days_to_earnings} dni"

    revenue_acc = _revenue_accelerating(ticker)
    beat = _earnings_beat(ticker)

    parts: list[str] = []
    if short_pct is not None:
        parts.append(f"short {short_pct:.1f}%")
    if revenue_acc:
        parts.append("trzby zrychluju")
    if beat is True:
        parts.append("earnings beat")
    elif beat is False:
        parts.append("earnings miss")
    if earnings_warning:
        parts.append(earnings_warning)

    return FundamentalSnapshot(
        short_interest_pct=short_pct,
        revenue_accelerating=revenue_acc,
        earnings_beat=beat,
        days_to_earnings=days_to_earnings,
        earnings_warning=earnings_warning,
        debt_to_equity=debt_to_equity,
        summary=", ".join(parts) if parts else "bez extra dat",
    )
