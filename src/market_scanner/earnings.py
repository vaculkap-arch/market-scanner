"""Last 4 quarterly earnings - key metrics only."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import yfinance as yf


@dataclass(frozen=True)
class QuarterlyEarnings:
    period: str
    revenue: float | None
    net_income: float | None
    eps: float | None
    revenue_qoq_pct: float | None
    net_margin_pct: float | None


@dataclass(frozen=True)
class EarningsSummary:
    ticker: str
    quarters: tuple[QuarterlyEarnings, ...]
    revenue_trend: str
    summary_line: str


def _quarter_label(date_val) -> str:
    try:
        dt = pd.Timestamp(date_val)
        q = (dt.month - 1) // 3 + 1
        return f"Q{q} {dt.year}"
    except Exception:
        return str(date_val)[:7]


def _format_money(value: float | None) -> str:
    if value is None:
        return "n/a"
    abs_v = abs(value)
    if abs_v >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if abs_v >= 1_000_000:
        return f"${value / 1_000_000:.0f}M"
    return f"${value:,.0f}"


def _get_row(df: pd.DataFrame, names: list[str], col) -> float | None:
    for name in names:
        if name in df.index:
            val = df.loc[name, col]
            if val is not None and not pd.isna(val):
                return float(val)
    return None


def get_earnings_summary(ticker: str) -> EarningsSummary | None:
    try:
        df = yf.Ticker(ticker).quarterly_income_stmt
    except Exception:
        return None

    if df is None or df.empty:
        return None

    cols = list(df.columns[:4])
    quarters: list[QuarterlyEarnings] = []

    for i, col in enumerate(cols):
        revenue = _get_row(df, ["Total Revenue", "Operating Revenue", "Revenue"], col)
        net_income = _get_row(
            df,
            ["Net Income", "Net Income Common Stockholders", "Net Income From Continuing Operation Net Minority Interest"],
            col,
        )
        eps = _get_row(df, ["Diluted EPS", "Basic EPS"], col)

        prev_col = cols[i + 1] if i + 1 < len(cols) else None
        prev_revenue = None
        if prev_col is not None:
            prev_revenue = _get_row(df, ["Total Revenue", "Operating Revenue", "Revenue"], prev_col)

        revenue_qoq = None
        if revenue is not None and prev_revenue and prev_revenue != 0:
            revenue_qoq = (revenue - prev_revenue) / prev_revenue * 100

        margin = None
        if revenue and revenue != 0 and net_income is not None:
            margin = net_income / revenue * 100

        quarters.append(
            QuarterlyEarnings(
                period=_quarter_label(col),
                revenue=revenue,
                net_income=net_income,
                eps=eps,
                revenue_qoq_pct=round(revenue_qoq, 1) if revenue_qoq is not None else None,
                net_margin_pct=round(margin, 1) if margin is not None else None,
            )
        )

    if not quarters:
        return None

    qoq_values = [q.revenue_qoq_pct for q in quarters if q.revenue_qoq_pct is not None]
    if len(qoq_values) >= 2 and sum(qoq_values[:2]) > 0:
        trend = "rastuca"
    elif qoq_values and qoq_values[0] is not None and qoq_values[0] < 0:
        trend = "klesajuca"
    else:
        trend = "stabilna"

    latest = quarters[0]
    qoq_txt = f"{latest.revenue_qoq_pct:+.1f}% QoQ" if latest.revenue_qoq_pct is not None else ""
    summary = (
        f"{latest.period}: trzby {_format_money(latest.revenue)}, "
        f"EPS {latest.eps if latest.eps is not None else 'n/a'}, "
        f"marza {latest.net_margin_pct if latest.net_margin_pct is not None else 'n/a'}% {qoq_txt}"
    ).strip()

    return EarningsSummary(ticker=ticker, quarters=tuple(quarters), revenue_trend=trend, summary_line=summary)


def earnings_to_dict(summary: EarningsSummary) -> dict:
    return {
        "trend": summary.revenue_trend,
        "summary": summary.summary_line,
        "quarters": [
            {
                "period": q.period,
                "revenue": q.revenue,
                "revenue_fmt": _format_money(q.revenue),
                "net_income": q.net_income,
                "net_income_fmt": _format_money(q.net_income),
                "eps": q.eps,
                "revenue_qoq_pct": q.revenue_qoq_pct,
                "net_margin_pct": q.net_margin_pct,
            }
            for q in summary.quarters
        ],
    }