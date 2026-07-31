"""News and sentiment from Yahoo Finance (+ optional Alpha Vantage)."""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests
import yfinance as yf

from .config import Settings

_POSITIVE = re.compile(
    r"\b(beat|surge|soar|rally|upgrade|growth|record|bullish|profit|strong|wins?)\b",
    re.I,
)
_NEGATIVE = re.compile(
    r"\b(miss|plunge|drop|downgrade|lawsuit|cut|weak|loss|bearish|fraud|probe)\b",
    re.I,
)


@dataclass(frozen=True)
class SentimentSnapshot:
    label: str
    score: float
    news_count: int
    headlines: tuple[str, ...]
    summary: str
    trends_spike: bool = False


def _score_headlines(headlines: list[str]) -> tuple[str, float]:
    if not headlines:
        return "neutralny", 0.0

    pos = sum(1 for h in headlines if _POSITIVE.search(h))
    neg = sum(1 for h in headlines if _NEGATIVE.search(h))
    score = (pos - neg) / max(len(headlines), 1)

    if score >= 0.25:
        return "pozitivny", round(score, 2)
    if score <= -0.25:
        return "negativny", round(score, 2)
    return "neutralny", round(score, 2)


def _alpha_vantage_sentiment(ticker: str, settings: Settings) -> SentimentSnapshot | None:
    key = settings.alpha_vantage_api_key
    if not key:
        return None
    try:
        resp = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "NEWS_SENTIMENT",
                "tickers": ticker,
                "apikey": key,
                "limit": 10,
            },
            timeout=15,
        )
        resp.raise_for_status()
        feed = resp.json().get("feed", [])
        if not feed:
            return None
        scores = [float(item.get("overall_sentiment_score", 0)) for item in feed]
        avg = sum(scores) / len(scores)
        headlines = tuple(item.get("title", "")[:80] for item in feed[:5])
        label = "pozitivny" if avg > 0.15 else "negativny" if avg < -0.15 else "neutralny"
        return SentimentSnapshot(
            label=label,
            score=round(avg, 2),
            news_count=len(feed),
            headlines=headlines,
            summary=f"Alpha Vantage sentiment {label} ({avg:+.2f})",
        )
    except Exception:
        return None


def get_sentiment(ticker: str, settings: Settings) -> SentimentSnapshot:
    av = _alpha_vantage_sentiment(ticker, settings)
    if av is not None:
        return av

    headlines: list[str] = []
    try:
        news = yf.Ticker(ticker).news or []
        headlines = [item.get("title", "") for item in news[:12] if item.get("title")]
    except Exception:
        pass

    label, score = _score_headlines(headlines)
    return SentimentSnapshot(
        label=label,
        score=score,
        news_count=len(headlines),
        headlines=tuple(headlines[:5]),
        summary=f"Spravy: {label} ({len(headlines)} clankov)",
    )
