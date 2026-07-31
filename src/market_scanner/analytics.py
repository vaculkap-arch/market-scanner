"""Detect unusual volume spikes across a watchlist."""

from __future__ import annotations

from dataclasses import dataclass

from .config import Settings, load_tickers
from .market_cap import classify_cap, get_market_cap, is_target_cap
from .scanner import TickerSnapshot, analyze_ticker, analyze_tickers_batch


@dataclass(frozen=True)
class VolumeAlert:
    snapshot: TickerSnapshot
    threshold: float
    lookback_days: int
    market_cap: int | None
    cap_class: str | None

    @property
    def message(self) -> str:
        s = self.snapshot
        pct = (s.volume_ratio - 1) * 100
        direction = "+" if s.price_change_pct >= 0 else ""
        cap_line = ""
        if self.market_cap is not None and self.cap_class is not None:
            cap_line = f"Trhova kapitalizacia: ${self.market_cap / 1e9:.2f}B ({self.cap_class})\n"
        return (
            f"VOLUME SPIKE: {s.ticker}\n"
            f"{cap_line}"
            f"Objem: {s.current_volume:,} ({pct:.0f}% nad priemerom)\n"
            f"Priemerny objem ({self.lookback_days}d): {s.avg_volume:,.0f}\n"
            f"Cena: ${s.close_price:.2f} ({direction}{s.price_change_pct:.1f}%)"
        )


INDEX_WATCHLIST_SOURCES = frozenset({"russell2000", "sp500", "both"})


def _should_filter_cap(settings: Settings) -> bool:
    if settings.watchlist_source in INDEX_WATCHLIST_SOURCES:
        return False
    return settings.filter_market_cap


def _check_cap_filter(ticker: str, settings: Settings) -> tuple[bool, int | None, str | None]:
    if not _should_filter_cap(settings):
        return True, None, None

    market_cap = get_market_cap(ticker)
    cap_class = classify_cap(market_cap) if market_cap is not None else None

    if market_cap is None:
        print(f"[skip] {ticker}: neznamy market cap")
        return False, None, None

    if not is_target_cap(market_cap, settings.min_market_cap, settings.max_market_cap):
        print(f"[skip] {ticker}: {cap_class} (${market_cap / 1e9:.2f}B) - mimo rozsah")
        return False, market_cap, cap_class

    return True, market_cap, cap_class


def scan_watchlist(settings: Settings, tickers: list[str] | None = None) -> list[VolumeAlert]:
    tickers = tickers or load_tickers(settings)
    source = settings.watchlist_source
    print(f"[info] Zdroj: {source}, tickerov: {len(tickers)}")

    alerts: list[VolumeAlert] = []

    if len(tickers) > 20:
        snapshots = analyze_tickers_batch(tickers, settings.lookback_days, settings.batch_chunk_size)
        snapshot_map = {s.ticker: s for s in snapshots}

        for ticker in tickers:
            snapshot = snapshot_map.get(ticker)
            if snapshot is None:
                continue

            if snapshot.volume_ratio >= settings.volume_spike_threshold:
                alerts.append(
                    VolumeAlert(
                        snapshot=snapshot,
                        threshold=settings.volume_spike_threshold,
                        lookback_days=settings.lookback_days,
                        market_cap=None,
                        cap_class=source if source in INDEX_WATCHLIST_SOURCES else None,
                    )
                )
                print(f"[ALERT] {ticker}: objem {snapshot.volume_ratio:.1f}x priemeru")
    else:
        for ticker in tickers:
            ok, market_cap, cap_class = _check_cap_filter(ticker, settings)
            if not ok:
                continue

            snapshot = analyze_ticker(ticker, settings.lookback_days)
            if snapshot is None:
                print(f"[skip] {ticker}: nedostatok dat")
                continue

            cap_label = f", {cap_class}" if cap_class else ""
            if snapshot.volume_ratio >= settings.volume_spike_threshold:
                alerts.append(
                    VolumeAlert(
                        snapshot=snapshot,
                        threshold=settings.volume_spike_threshold,
                        lookback_days=settings.lookback_days,
                        market_cap=market_cap,
                        cap_class=cap_class,
                    )
                )
                print(f"[ALERT] {ticker}{cap_label}: objem {snapshot.volume_ratio:.1f}x priemeru")
            else:
                print(f"[ok] {ticker}{cap_label}: objem {snapshot.volume_ratio:.1f}x priemeru")

    print(f"[info] Hotovo. Nájdených alertov: {len(alerts)}")
    return alerts