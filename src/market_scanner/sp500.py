"""S&P 500 ticker list download and cache."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd
import requests

from .config import PROJECT_ROOT

SP500_PATH = PROJECT_ROOT / "config" / "sp500.txt"
SP500_CSV_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
)


def normalize_ticker(symbol: str) -> str:
    return symbol.strip().upper().replace(".", "-")


def download_sp500_tickers() -> list[str]:
    response = requests.get(SP500_CSV_URL, timeout=60)
    response.raise_for_status()
    df = pd.read_csv(StringIO(response.text))
    tickers = sorted({normalize_ticker(t) for t in df["Symbol"] if str(t).strip()})
    SP500_PATH.parent.mkdir(parents=True, exist_ok=True)
    SP500_PATH.write_text("\n".join(tickers) + "\n", encoding="utf-8")
    return tickers


def load_sp500_tickers(refresh: bool = False) -> list[str]:
    if refresh or not SP500_PATH.exists():
        return download_sp500_tickers()

    tickers: list[str] = []
    for line in SP500_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            tickers.append(normalize_ticker(line))

    if not tickers:
        return download_sp500_tickers()

    return tickers
