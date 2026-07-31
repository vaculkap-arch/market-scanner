"""Download price and volume data from Yahoo Finance."""

from __future__ import annotations

import time
from dataclasses import dataclass

import pandas as pd
import yfinance as yf

try:
    from yfinance.exceptions import YFRateLimitError
except ImportError:
    YFRateLimitError = None  # type: ignore[misc, assignment]


def _is_rate_limit_message(msg: str) -> bool:
    msg = msg.lower()
    return "rate limit" in msg or "too many requests" in msg


def _is_rate_limit_error(exc: BaseException) -> bool:
    if YFRateLimitError is not None and isinstance(exc, YFRateLimitError):
        return True
    return _is_rate_limit_message(str(exc))


def _history_with_retry(fetch, retries: int = 3, pause: float = 2.0) -> pd.DataFrame | None:
    for attempt in range(retries):
        try:
            history = fetch()
            if history is None or history.empty:
                return None
            return history
        except Exception as exc:
            if _is_rate_limit_error(exc) and attempt < retries - 1:
                wait = pause * (2 ** attempt)
                print(f"[warn] Yahoo rate limit, cakam {wait:.0f}s...")
                time.sleep(wait)
                continue
            print(f"[warn] Yahoo chyba: {exc}")
            return None
    return None


@dataclass(frozen=True)
class TickerSnapshot:
    ticker: str
    current_volume: int
    avg_volume: float
    volume_ratio: float
    close_price: float
    price_change_pct: float


def _snapshot_from_history(ticker: str, history: pd.DataFrame, lookback_days: int) -> TickerSnapshot | None:
    if history.empty or len(history) < lookback_days + 1:
        return None

    today = history.iloc[-1]
    prior = history.iloc[-(lookback_days + 1) : -1]

    current_volume = int(today["Volume"])
    avg_volume = float(prior["Volume"].mean())

    if avg_volume <= 0:
        return None

    volume_ratio = current_volume / avg_volume
    prev_close = float(history.iloc[-2]["Close"])
    close_price = float(today["Close"])
    price_change_pct = ((close_price - prev_close) / prev_close) * 100 if prev_close else 0.0

    return TickerSnapshot(
        ticker=ticker,
        current_volume=current_volume,
        avg_volume=avg_volume,
        volume_ratio=volume_ratio,
        close_price=close_price,
        price_change_pct=price_change_pct,
    )


def _extract_ticker_history(data: pd.DataFrame, ticker: str) -> pd.DataFrame | None:
    if isinstance(data.columns, pd.MultiIndex):
        if ticker not in data.columns.get_level_values(0):
            return None
        history = data[ticker].dropna(how="all")
    else:
        history = data.dropna(how="all")

    if history.empty:
        return None

    return history


def fetch_ticker_data(ticker: str, lookback_days: int) -> pd.DataFrame | None:
    period = f"{lookback_days + 35}d"

    def _fetch() -> pd.DataFrame:
        return yf.Ticker(ticker).history(period=period, interval="1d")

    history = _history_with_retry(_fetch)
    if history is None or len(history) < lookback_days + 1:
        return None

    return history


def analyze_ticker(ticker: str, lookback_days: int) -> TickerSnapshot | None:
    history = fetch_ticker_data(ticker, lookback_days)
    if history is None:
        return None
    return _snapshot_from_history(ticker, history, lookback_days)


def fetch_histories_batch(
    tickers: list[str],
    lookback_days: int,
    chunk_size: int = 100,
) -> dict[str, pd.DataFrame]:
    histories: dict[str, pd.DataFrame] = {}
    period = f"{lookback_days + 35}d"
    min_rows = lookback_days + 2
    total = len(tickers)

    def _download_chunk(chunk: list[str]) -> pd.DataFrame | None:
        def _download() -> pd.DataFrame:
            return yf.download(
                tickers=chunk,
                period=period,
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                threads=False,
                progress=False,
            )

        return _history_with_retry(_download, retries=2, pause=5.0)

    def _collect(chunk: list[str], data: pd.DataFrame | None) -> None:
        if data is None or data.empty:
            return
        for ticker in chunk:
            if ticker in histories:
                continue
            history = _extract_ticker_history(data, ticker)
            if history is not None and len(history) >= min_rows:
                histories[ticker] = history

    # A rate-limited batch fails almost entirely; a healthy batch only misses
    # the delisted names. Use the miss-rate to tell them apart so we retry
    # rate-limited tickers but do not waste time re-fetching delisted ones.
    rate_limit_miss_rate = 0.5
    retry_pool: list[str] = []
    pause = 2.0

    for start in range(0, total, chunk_size):
        chunk = tickers[start : start + chunk_size]
        print(f"[batch] Spracovavam {start + 1}-{start + len(chunk)} z {total}...")

        data = _download_chunk(chunk)
        _collect(chunk, data)

        missing = [t for t in chunk if t not in histories]
        miss_rate = len(missing) / len(chunk) if chunk else 0.0

        if miss_rate >= rate_limit_miss_rate:
            retry_pool.extend(missing)
            pause = min(pause + 3.0, 20.0)
            print(
                f"[batch] Vysoka chybovost {len(missing)}/{len(chunk)} "
                f"(pravdepodobne rate limit), pauza {pause:.0f}s"
            )
        else:
            pause = max(pause - 0.5, 2.0)

        time.sleep(pause)

    retry_pool = [t for t in dict.fromkeys(retry_pool) if t not in histories]
    retry_round = 0
    retry_chunk = max(20, chunk_size // 4)

    while retry_pool and retry_round < 3:
        retry_round += 1
        cooldown = 30 * retry_round
        print(
            f"[batch] Retry kolo {retry_round}: {len(retry_pool)} tickerov, "
            f"cakam {cooldown}s..."
        )
        time.sleep(cooldown)

        for start in range(0, len(retry_pool), retry_chunk):
            chunk = retry_pool[start : start + retry_chunk]
            data = _download_chunk(chunk)
            _collect(chunk, data)
            time.sleep(5)

        retry_pool = [t for t in retry_pool if t not in histories]

    if retry_pool:
        print(
            f"[batch] {len(retry_pool)} tickerov sa nepodarilo stiahnut "
            "(delistovane alebo pretrvavajuci limit)."
        )

    return histories


def analyze_tickers_batch(
    tickers: list[str],
    lookback_days: int,
    chunk_size: int = 100,
) -> list[TickerSnapshot]:
    snapshots: list[TickerSnapshot] = []
    histories = fetch_histories_batch(tickers, lookback_days, chunk_size)

    for ticker, history in histories.items():
        snapshot = _snapshot_from_history(ticker, history, lookback_days)
        if snapshot is not None:
            snapshots.append(snapshot)

    return snapshots