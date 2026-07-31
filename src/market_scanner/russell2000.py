"""Russell 2000 ticker list download and cache."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd
import requests

from .config import PROJECT_ROOT

RUSSELL2000_PATH = PROJECT_ROOT / "config" / "russell2000.txt"
RUSSELL2000_CSV_URL = (
    "https://raw.githubusercontent.com/ikoniaris/Russell2000/master/russell_2000_components.csv"
)


def normalize_ticker(symbol: str) -> str:
    return symbol.strip().upper().replace(".", "-")


def download_russell2000_tickers() -> list[str]:
    response = requests.get(RUSSELL2000_CSV_URL, timeout=60)
    response.raise_for_status()
    df = pd.read_csv(StringIO(response.text))
    tickers = sorted({normalize_ticker(t) for t in df["Ticker"] if str(t).strip()})
    RUSSELL2000_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUSSELL2000_PATH.write_text("\n".join(tickers) + "\n", encoding="utf-8")
    return tickers


def load_russell2000_tickers(refresh: bool = False) -> list[str]:
    if refresh or not RUSSELL2000_PATH.exists():
        return download_russell2000_tickers()

    tickers: list[str] = []
    for line in RUSSELL2000_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            tickers.append(normalize_ticker(line))

    if not tickers:
        return download_russell2000_tickers()

    return tickers
