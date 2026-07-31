"""Market scanner CLI - bullish signals, volume spikes, backtest."""

from __future__ import annotations

import argparse
import time

import schedule

from market_scanner.analytics import scan_watchlist
from market_scanner.backtest import run_backtest, save_and_print_report
from market_scanner.bullish_scan import scan_bullish_setups
from market_scanner.config import load_settings
from market_scanner.leaderboard import load_leaderboard
from market_scanner.market_hours import is_us_market_open, market_status
from market_scanner.notifier import notify, record_gmail_sent, should_send_gmail_for_setup
from market_scanner.russell2000 import download_russell2000_tickers
from market_scanner.sp500 import download_sp500_tickers


def _notify_bullish_setup(setup, settings) -> None:
    gmail = should_send_gmail_for_setup(setup, settings)
    if not gmail:
        print(
            f"[skip] Gmail: {setup.ticker} tier {setup.tier} skore {setup.score} "
            f"(min tier {settings.gmail_min_tier}, min skore {settings.gmail_min_score})"
        )
    notify(
        setup.message,
        settings,
        subject=f"Tier {setup.tier}: {setup.ticker} ({setup.score}/100)",
        gmail=gmail,
    )
    if gmail:
        record_gmail_sent(setup)


def run_scan() -> None:
    settings = load_settings()
    mode = settings.scan_mode

    if mode == "volume":
        alerts = scan_watchlist(settings)
        for alert in alerts:
            notify(alert.message, settings, subject=f"Volume spike: {alert.snapshot.ticker}", gmail=False)
        return

    if mode == "both":
        setups = scan_bullish_setups(settings)
        for setup in setups:
            _notify_bullish_setup(setup, settings)
        alerts = scan_watchlist(settings)
        for alert in alerts:
            notify(alert.message, settings, subject=f"Volume spike: {alert.snapshot.ticker}", gmail=False)
        _print_top_picks()
        return

    setups = scan_bullish_setups(settings)
    for setup in setups:
        _notify_bullish_setup(setup, settings)
    _print_top_picks()


def _print_top_picks(limit: int = 10) -> None:
    board = load_leaderboard()
    if not board:
        return
    print("\n--- TOP ZOZNAM (podla potencialu) ---")
    for i, item in enumerate(board[:limit], 1):
        print(
            f"  #{i} {item['ticker']} | rank {item['potential_rank']} | "
            f"skore {item['score']} | {item['probability']}"
        )


def run_scan_if_open(force: bool = False) -> None:
    settings = load_settings()
    if settings.market_hours_only and not force and not is_us_market_open():
        print(f"[skip] {market_status()}")
        return
    run_scan()


def run_daemon() -> None:
    settings = load_settings()
    print("Market Scanner - NON-STOP")
    print(f"Rezim: {settings.scan_mode} | interval: {settings.scan_interval_minutes} min")
    print(market_status())

    schedule.every(settings.scan_interval_minutes).minutes.do(run_scan_if_open)
    run_scan_if_open()

    last_status = ""
    while True:
        schedule.run_pending()
        status = market_status()
        if status != last_status:
            print(f"[agent] {status}")
            last_status = status
        time.sleep(30)


def main() -> None:
    parser = argparse.ArgumentParser(description="Market scanner")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--test-email", action="store_true", help="Otestuj vsetky notifikacne kanaly")
    parser.add_argument("--test-notify", action="store_true", help="Alias pre --test-email")
    parser.add_argument("--update-russell2000", action="store_true")
    parser.add_argument("--update-sp500", action="store_true")
    parser.add_argument("--update-watchlists", action="store_true", help="Aktualizuj Russell 2000 aj S&P 500")
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--top", action="store_true", help="Zobraz top zoznam najdenych akcii")
    args = parser.parse_args()

    if args.update_russell2000:
        tickers = download_russell2000_tickers()
        print(f"Russell 2000: {len(tickers)} tickerov")
        return

    if args.update_sp500:
        tickers = download_sp500_tickers()
        print(f"S&P 500: {len(tickers)} tickerov")
        return

    if args.update_watchlists:
        r2k = download_russell2000_tickers()
        sp = download_sp500_tickers()
        combined = sorted(set(r2k) | set(sp))
        print(f"Russell 2000: {len(r2k)} | S&P 500: {len(sp)} | spolocne: {len(combined)}")
        return

    if args.top:
        _print_top_picks(limit=50)
        return

    settings = load_settings()

    if args.backtest:
        report = run_backtest(settings)
        save_and_print_report(report, settings)
        return

    if args.test_email or args.test_notify:
        notify("Test Market Scanner - notifikacie funguju.", settings, subject="Market Scanner - test")
        print("[ok] Test odoslany (Gmail / Telegram / Discord podla .env)")
        return

    if args.once:
        run_scan_if_open(force=args.force)
        return

    run_daemon()


if __name__ == "__main__":
    main()