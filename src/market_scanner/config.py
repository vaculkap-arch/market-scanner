"""Load configuration from environment and watchlist file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WATCHLIST_PATH = PROJECT_ROOT / "config" / "watchlist.txt"


def _env(key: str, default: str | None = None) -> str | None:
    """Read from process env first, then Streamlit Cloud secrets if available."""
    value = os.getenv(key)
    if value is not None and value != "":
        return value
    try:
        import streamlit as st

        secrets = getattr(st, "secrets", None)
        if secrets is not None and key in secrets:
            secret = secrets[key]
            if secret is None:
                return default
            return str(secret)
    except Exception:
        pass
    return default


def _env_bool(key: str, default: str = "true") -> bool:
    return (_env(key, default) or default).lower() == "true"


@dataclass(frozen=True)
class Settings:
    watchlist_source: str
    scan_mode: str
    volume_spike_threshold: float
    lookback_days: int
    scan_interval_minutes: int
    batch_chunk_size: int
    market_hours_only: bool
    bullish_min_score: int
    bullish_volume_threshold: float
    bullish_momentum_pct: float
    high_potential_only: bool
    backtest_forward_days: int
    backtest_target_pct: float
    backtest_years: int
    backtest_max_tickers: int
    insider_lookback_days: int
    filter_market_cap: bool
    min_market_cap: int
    max_market_cap: int
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    discord_webhook_url: str | None
    gmail_address: str | None
    gmail_app_password: str | None
    gmail_to: str | None
    gmail_min_score: int
    gmail_min_tier: str
    gmail_cooldown_hours: int
    regime_filter: bool
    max_ma20_extension_pct: float
    min_relative_strength_pct: float
    filter_extended: bool
    earnings_warn_days: int
    enable_sentiment: bool
    alpha_vantage_api_key: str | None


def load_settings() -> Settings:
    return Settings(
        watchlist_source=(_env("WATCHLIST_SOURCE", "file") or "file").lower(),
        scan_mode=(_env("SCAN_MODE", "bullish") or "bullish").lower(),
        volume_spike_threshold=float(_env("VOLUME_SPIKE_THRESHOLD", "3.0") or "3.0"),
        lookback_days=int(_env("LOOKBACK_DAYS", "20") or "20"),
        scan_interval_minutes=int(_env("SCAN_INTERVAL_MINUTES", "60") or "60"),
        batch_chunk_size=int(_env("BATCH_CHUNK_SIZE", "100") or "100"),
        market_hours_only=_env_bool("MARKET_HOURS_ONLY", "true"),
        bullish_min_score=int(_env("BULLISH_MIN_SCORE", "55") or "55"),
        bullish_volume_threshold=float(_env("BULLISH_VOLUME_THRESHOLD", "2.0") or "2.0"),
        bullish_momentum_pct=float(_env("BULLISH_MOMENTUM_PCT", "2.0") or "2.0"),
        high_potential_only=_env_bool("HIGH_POTENTIAL_ONLY", "true"),
        backtest_forward_days=int(_env("BACKTEST_FORWARD_DAYS", "5") or "5"),
        backtest_target_pct=float(_env("BACKTEST_TARGET_PCT", "5.0") or "5.0"),
        backtest_years=int(_env("BACKTEST_YEARS", "2") or "2"),
        backtest_max_tickers=int(_env("BACKTEST_MAX_TICKERS", "500") or "500"),
        insider_lookback_days=int(_env("INSIDER_LOOKBACK_DAYS", "90") or "90"),
        filter_market_cap=_env_bool("FILTER_MARKET_CAP", "true"),
        min_market_cap=int(_env("MIN_MARKET_CAP", "300000000") or "300000000"),
        max_market_cap=int(_env("MAX_MARKET_CAP", "10000000000") or "10000000000"),
        telegram_bot_token=_env("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=_env("TELEGRAM_CHAT_ID") or None,
        discord_webhook_url=_env("DISCORD_WEBHOOK_URL") or None,
        gmail_address=_env("GMAIL_ADDRESS") or None,
        gmail_app_password=_env("GMAIL_APP_PASSWORD") or None,
        gmail_to=_env("GMAIL_TO") or None,
        gmail_min_score=int(_env("GMAIL_MIN_SCORE", "60") or "60"),
        gmail_min_tier=(_env("GMAIL_MIN_TIER", "A") or "A").upper(),
        gmail_cooldown_hours=int(_env("GMAIL_COOLDOWN_HOURS", "24") or "24"),
        regime_filter=_env_bool("REGIME_FILTER", "true"),
        max_ma20_extension_pct=float(_env("MAX_MA20_EXTENSION_PCT", "5.0") or "5.0"),
        min_relative_strength_pct=float(_env("MIN_RELATIVE_STRENGTH_PCT", "0.0") or "0.0"),
        filter_extended=_env_bool("FILTER_EXTENDED", "true"),
        earnings_warn_days=int(_env("EARNINGS_WARN_DAYS", "2") or "2"),
        enable_sentiment=_env_bool("ENABLE_SENTIMENT", "true"),
        alpha_vantage_api_key=_env("ALPHA_VANTAGE_API_KEY") or None,
    )


def load_watchlist(path: Path = WATCHLIST_PATH) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Watchlist not found: {path}")

    tickers: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        tickers.append(line.upper())

    if not tickers:
        raise ValueError(f"Watchlist is empty: {path}")

    return tickers


def load_tickers(settings: Settings) -> list[str]:
    source = settings.watchlist_source

    if source == "russell2000":
        from .russell2000 import load_russell2000_tickers

        return load_russell2000_tickers()

    if source == "sp500":
        from .sp500 import load_sp500_tickers

        return load_sp500_tickers()

    if source == "both":
        from .russell2000 import load_russell2000_tickers
        from .sp500 import load_sp500_tickers

        return sorted(set(load_russell2000_tickers()) | set(load_sp500_tickers()))

    return load_watchlist()