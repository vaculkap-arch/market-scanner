"""Scan watchlist for backtest-validated high-potential setups."""

from __future__ import annotations

from .config import Settings, load_tickers
from .enrich import enrich_setup
from .leaderboard import compute_potential_rank, merge_setups, record_last_scan
from .market_context import clear_benchmark_cache, is_bull_regime
from .scanner import fetch_histories_batch, fetch_ticker_data
from .signals import BullishSetup, analyze_bullish


def scan_bullish_setups(settings: Settings, tickers: list[str] | None = None) -> list[BullishSetup]:
    clear_benchmark_cache()
    tickers = tickers or load_tickers(settings)

    bull, regime_label = is_bull_regime()
    if settings.regime_filter and not bull:
        print(f"[warn] Bear rezim trhu: {regime_label} - setupy budu nizsie tier")

    print(
        f"[info] Bullish scan | tickerov: {len(tickers)} | min skore: {settings.bullish_min_score} "
        f"| rezim: {regime_label}"
    )

    setups: list[BullishSetup] = []
    kwargs = dict(
        lookback_days=settings.lookback_days,
        volume_threshold=settings.bullish_volume_threshold,
        momentum_pct=settings.bullish_momentum_pct,
        min_score=settings.bullish_min_score,
        high_potential_only=settings.high_potential_only,
        max_ma20_extension_pct=settings.max_ma20_extension_pct,
        filter_extended=settings.filter_extended,
    )

    if len(tickers) > 20:
        histories = fetch_histories_batch(tickers, settings.lookback_days, settings.batch_chunk_size)
        for ticker, history in histories.items():
            setup = analyze_bullish(ticker, history, **kwargs)
            if setup:
                setups.append(setup)
    else:
        for ticker in tickers:
            history = fetch_ticker_data(ticker, settings.lookback_days)
            if history is None:
                continue
            setup = analyze_bullish(ticker, history, **kwargs)
            if setup:
                setups.append(setup)

    enriched: list[BullishSetup] = []
    print(f"[info] Obohacujem {len(setups)} kandidatov (fundamenty, sentiment, tier)...")
    for setup in setups:
        enriched.append(enrich_setup(setup, settings))

    enriched.sort(key=compute_potential_rank, reverse=True)

    tier_counts = {t: sum(1 for s in enriched if s.tier == t) for t in ("S", "A", "B", "C")}
    print(f"[info] Tier S/A/B/C: {tier_counts}")

    for setup in enriched:
        if setup.tier in ("S", "A"):
            print(
                f"[ALERT] {setup.ticker}: Tier {setup.tier} | rank {compute_potential_rank(setup)} "
                f"| skore {setup.score} | {setup.tier_reason}"
            )

    if enriched:
        merge_setups(enriched)

    record_last_scan(len(enriched))
    return enriched
