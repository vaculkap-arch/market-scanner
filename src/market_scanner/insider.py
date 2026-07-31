"""Insider (manager) purchase detection via SEC Form 4 data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd
import yfinance as yf


@dataclass(frozen=True)
class InsiderActivity:
    ticker: str
    recent_buys: int
    total_buy_value: float
    insiders: tuple[str, ...]
    latest_buy_date: str | None
    net_shares_6m: float | None
    has_cluster_buying: bool

    @property
    def has_recent_insider_buying(self) -> bool:
        return self.recent_buys > 0

    @property
    def summary(self) -> str:
        if not self.has_recent_insider_buying:
            return "Ziadne insider nakupy v obdobi"
        names = ", ".join(self.insiders[:3])
        extra = f" +{len(self.insiders) - 3}" if len(self.insiders) > 3 else ""
        val = f"${self.total_buy_value:,.0f}" if self.total_buy_value else "n/a"
        return f"{self.recent_buys} nakup(ov) od {names}{extra} ({val})"


def _parse_date(value) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _is_open_market_purchase(text: str) -> bool:
    t = text.lower()
    if "purchase" not in t:
        return False
    blocked = ("sale", "gift", "award", "grant", "conversion", "exercise", "disposition")
    return not any(word in t for word in blocked)


def get_insider_activity(ticker: str, lookback_days: int = 90) -> InsiderActivity:
    stock = yf.Ticker(ticker)
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    recent_buys = 0
    total_value = 0.0
    insiders: list[str] = []
    latest: datetime | None = None
    net_6m: float | None = None

    try:
        purchases = stock.insider_purchases
        if purchases is not None and not purchases.empty:
            row = purchases[purchases.iloc[:, 0].astype(str).str.contains("Net Shares", na=False)]
            if not row.empty:
                net_6m = float(row.iloc[0, 1])
    except Exception:
        pass

    try:
        tx = stock.insider_transactions
        if tx is not None and not tx.empty and "Text" in tx.columns:
            for _, row in tx.iterrows():
                text = str(row.get("Text", ""))
                if not _is_open_market_purchase(text):
                    continue
                dt = _parse_date(row.get("Start Date"))
                if dt is None or dt < cutoff:
                    continue
                recent_buys += 1
                value = row.get("Value")
                if value is not None and not pd.isna(value):
                    total_value += float(value)
                name = str(row.get("Insider", "")).strip()
                if name and name not in insiders:
                    insiders.append(name)
                if latest is None or (dt and dt > latest):
                    latest = dt
    except Exception:
        pass

    return InsiderActivity(
        ticker=ticker,
        recent_buys=recent_buys,
        total_buy_value=total_value,
        insiders=tuple(insiders),
        latest_buy_date=latest.strftime("%Y-%m-%d") if latest else None,
        net_shares_6m=net_6m,
        has_cluster_buying=len(insiders) >= 2,
    )