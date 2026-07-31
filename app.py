"""Market Scanner - Streamlit dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

# Streamlit Cloud installs deps from requirements.txt; ensure src/ is importable.
_SRC = Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from market_scanner.bullish_scan import scan_bullish_setups
from market_scanner.config import PROJECT_ROOT, load_settings, load_tickers
from market_scanner.leaderboard import clear_leaderboard, get_last_scan, latest_board_timestamp, load_leaderboard, merge_setups
from market_scanner.market_hours import is_us_market_open, market_status, now_eastern
from market_scanner.notifier import notify, record_gmail_sent, should_send_gmail_for_setup, telegram_configured
from market_scanner.entry import compute_entry_levels
from market_scanner.scanner import fetch_ticker_data
from market_scanner.signals import detect_signals

BACKTEST_FILE = PROJECT_ROOT / "config" / "backtest_results.txt"

_CUSTOM_CSS = """
@import url("https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap");

:root {
    --bg-0: #06080f;
    --bg-1: #0c1222;
    --bg-2: #121a2e;
    --card: rgba(18, 26, 46, 0.72);
    --card-border: rgba(148, 163, 184, 0.12);
    --accent: #10b981;
    --accent-2: #06b6d4;
    --accent-glow: rgba(16, 185, 129, 0.25);
    --text: #e2e8f0;
    --muted: #94a3b8;
    --danger: #f87171;
    --warn: #fbbf24;
    --radius: 16px;
    --shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
}

.stApp {
    background:
        radial-gradient(ellipse 80% 50% at 50% -20%, rgba(16, 185, 129, 0.12), transparent),
        radial-gradient(ellipse 60% 40% at 100% 0%, rgba(6, 182, 212, 0.08), transparent),
        linear-gradient(180deg, var(--bg-0) 0%, var(--bg-1) 50%, var(--bg-0) 100%);
    font-family: "DM Sans", "Segoe UI", sans-serif;
    color: var(--text);
}

.block-container {
    padding-top: 1.5rem;
    max-width: 1400px;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a0f1a 0%, #0d1526 100%);
    border-right: 1px solid var(--card-border);
}
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 {
    font-family: "DM Sans", "Segoe UI", sans-serif;
    font-weight: 700;
    letter-spacing: -0.02em;
}

.hero {
    background: var(--card);
    backdrop-filter: blur(12px);
    border: 1px solid var(--card-border);
    border-radius: 20px;
    padding: 1.75rem 2rem;
    margin-bottom: 1.25rem;
    box-shadow: var(--shadow);
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--accent), var(--accent-2));
}
.hero-title {
    font-size: 2.4rem;
    font-weight: 700;
    margin: 0;
    letter-spacing: -0.03em;
    background: linear-gradient(135deg, #fff 0%, var(--accent) 50%, var(--accent-2) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.hero-sub {
    color: var(--muted);
    margin: 0.35rem 0 0 0;
    font-size: 1.05rem;
}
.hero-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    margin-top: 1rem;
}
.chip {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.35rem 0.85rem;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 600;
    border: 1px solid var(--card-border);
    background: rgba(255,255,255,0.04);
    color: var(--muted);
}
.chip-open { color: var(--accent); border-color: rgba(16,185,129,0.35); background: rgba(16,185,129,0.1); }
.chip-closed { color: var(--danger); border-color: rgba(248,113,113,0.35); background: rgba(248,113,113,0.1); }

.main .block-container [data-testid="stMetric"] {
    background: var(--card);
    backdrop-filter: blur(10px);
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
    padding: 1rem 1.1rem;
    box-shadow: var(--shadow);
}
.main .block-container [data-testid="stMetricLabel"] {
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--muted) !important;
}
.main .block-container [data-testid="stMetricValue"] {
    font-family: "JetBrains Mono", monospace;
    font-size: 1.35rem !important;
    font-weight: 600;
    color: var(--text) !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem;
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 14px;
    padding: 0.4rem;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px;
    font-weight: 600;
    color: var(--muted);
    padding: 0.55rem 1.2rem;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, rgba(16,185,129,0.2), rgba(6,182,212,0.15)) !important;
    color: var(--accent) !important;
}
.stTabs [data-baseweb="tab-highlight"] { display: none; }
.stTabs [data-baseweb="tab-border"] { display: none; }

.panel-card {
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
    padding: 1.25rem 1.4rem;
    margin: 0.75rem 0;
    box-shadow: var(--shadow);
}
.panel-title {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--muted);
    margin-bottom: 0.6rem;
}
.ticker-head {
    font-size: 1.75rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin: 0;
}
.ticker-rank {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.85rem;
    color: var(--accent);
    font-weight: 600;
}
.prob-badge {
    display: inline-block;
    padding: 0.3rem 0.75rem;
    border-radius: 8px;
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    background: rgba(16,185,129,0.15);
    color: var(--accent);
    border: 1px solid rgba(16,185,129,0.3);
}
.signal-pill {
    display: inline-block;
    padding: 0.28rem 0.7rem;
    margin: 0.2rem 0.25rem 0.2rem 0;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 500;
    background: rgba(6, 182, 212, 0.12);
    color: #67e8f9;
    border: 1px solid rgba(6, 182, 212, 0.25);
}
.legend-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    padding: 0.75rem 1rem;
    background: rgba(255,255,255,0.03);
    border-radius: 10px;
    border: 1px solid var(--card-border);
    font-size: 0.82rem;
    color: var(--muted);
    margin-top: 0.5rem;
}
.legend-dot {
    display: inline-block;
    width: 10px; height: 10px;
    border-radius: 50%;
    margin-right: 0.35rem;
    vertical-align: middle;
}

div[data-testid="stDataFrame"] {
    border: 1px solid var(--card-border);
    border-radius: var(--radius);
    overflow: hidden;
    box-shadow: var(--shadow);
}

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, var(--accent), #059669) !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    letter-spacing: 0.02em;
    box-shadow: 0 4px 14px var(--accent-glow);
}
.stButton > button[kind="secondary"] {
    border-radius: 12px !important;
    border-color: var(--card-border) !important;
}

.stDownloadButton > button {
    border-radius: 12px !important;
    border: 1px solid var(--card-border) !important;
    background: rgba(255,255,255,0.04) !important;
}

h1, h2, h3 { font-family: "DM Sans", "Segoe UI", sans-serif !important; letter-spacing: -0.02em; }
.section-head {
    font-size: 1.35rem !important;
    font-weight: 700 !important;
    margin-bottom: 0.25rem !important;
}
"""


def _inject_css() -> None:
    st.markdown(f"<style>{_CUSTOM_CSS}</style>", unsafe_allow_html=True)


st.set_page_config(page_title="Market Scanner", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
_inject_css()


@st.cache_data(ttl=300)
def _ticker_count(source: str) -> int:
    settings = load_settings()
    settings = replace(settings, watchlist_source=source)
    return len(load_tickers(settings))


@st.cache_data(ttl=3600)
def _index_ticker_sets() -> dict[str, set[str]]:
    from market_scanner.russell2000 import load_russell2000_tickers
    from market_scanner.sp500 import load_sp500_tickers

    return {
        "Russell 2000": set(load_russell2000_tickers()),
        "S&P 500": set(load_sp500_tickers()),
    }


def _filter_board_by_index(board: list[dict], index_label: str) -> list[dict]:
    allowed = _index_ticker_sets().get(index_label, set())
    if not allowed:
        return board
    return [item for item in board if item["ticker"] in allowed]


def _board_count_for_index(board: list[dict], index_label: str) -> int:
    return len(_filter_board_by_index(board, index_label))


def _format_local_time(iso_value: str | None) -> str:
    if not iso_value:
        return "—"
    dt = datetime.fromisoformat(iso_value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo("Europe/Bratislava")).strftime("%d.%m.%Y %H:%M")


def _last_update_label(board: list[dict]) -> str:
    scan = get_last_scan()
    if scan and scan.get("at"):
        return _format_local_time(scan["at"])
    return _format_local_time(latest_board_timestamp(board))


def _leaderboard_df(items: list[dict]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame()
    rows = []
    for i, item in enumerate(items, 1):
        insider = item.get("insider_summary") or "-"
        if item.get("insider_cluster"):
            insider = f"CLUSTER: {insider}"
        rs = item.get("relative_strength_pct")
        rows.append({
            "#": i,
            "Ticker": item["ticker"],
            "Tier": item.get("tier", "C"),
            "Potencial": item["potential_rank"],
            "Skore": item["score"],
            "Insider": insider,
            "Kvartaly": item.get("earnings_summary", "-")[:40] + ("..." if len(item.get("earnings_summary", "")) > 40 else ""),
            "Pravdepodobnost": item["probability"],
            "RS %": float(rs) if rs is not None else None,
            "Cena": f"${item['close_price']:.2f}",
            "Vstup": f"${item['entry_ideal']:.2f}" if item.get("entry_ideal") else "-",
            "Stop": f"${item['stop_loss']:.2f}" if item.get("stop_loss") else "-",
            "Ciel": f"${item['target_price']:.2f}" if item.get("target_price") else "-",
            "Zmena %": f"{item['price_change_pct']:+.1f}%",
            "Objem x": round(item["volume_ratio"], 1),
            "Signaly": ", ".join(item.get("signals", [])),
            "Aktualizovany": _format_local_time(item.get("last_seen")),
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=600, show_spinner=False)
def _cached_ticker_history(ticker: str, lookback_days: int = 20) -> pd.DataFrame | None:
    return fetch_ticker_data(ticker, lookback_days)


def _resolve_chart_levels(item: dict, history: pd.DataFrame | None = None) -> dict | None:
    """Entry levels from leaderboard, or computed live when history is available."""
    if item.get("entry_ideal"):
        return {
            "entry_ideal": item["entry_ideal"],
            "entry_zone_low": item.get("entry_zone_low"),
            "entry_zone_high": item.get("entry_zone_high"),
            "stop_loss": item.get("stop_loss"),
            "target_price": item.get("target_price"),
            "close_price": item.get("close_price"),
        }

    if history is None or history.empty:
        return None

    signals, _, _, _ = detect_signals(history, 20, 2.0, 2.0)
    close = float(history.iloc[-1]["Close"])
    entry = compute_entry_levels(history, signals, close)
    if entry is None:
        return None

    return {
        "entry_ideal": entry.entry_ideal,
        "entry_zone_low": entry.entry_zone_low,
        "entry_zone_high": entry.entry_zone_high,
        "stop_loss": entry.stop_loss,
        "target_price": entry.target_price,
        "close_price": close,
    }


def _price_chart(ticker: str, history: pd.DataFrame, levels: dict | None = None) -> go.Figure | None:
    if history is None or history.empty:
        return None

    fig = go.Figure(data=[go.Candlestick(
        x=history.index, open=history["Open"], high=history["High"],
        low=history["Low"], close=history["Close"], name=ticker,
        increasing_line_color="#10b981", increasing_fillcolor="#10b981",
        decreasing_line_color="#f87171", decreasing_fillcolor="#f87171",
    )])

    ma20 = history["Close"].rolling(20).mean()
    fig.add_trace(go.Scatter(
        x=history.index, y=ma20, name="MA20",
        line=dict(color="#ffaa00", width=1.5),
        hovertemplate="MA20: $%{y:.2f}<extra></extra>",
    ))

    y_bounds: list[float] = [float(history["Low"].min()), float(history["High"].max())]

    if levels:
        zone_low = levels.get("entry_zone_low")
        zone_high = levels.get("entry_zone_high")
        if zone_low and zone_high:
            y_bounds.extend([zone_low, zone_high])
            fig.add_hrect(
                y0=zone_low, y1=zone_high,
                fillcolor="rgba(0, 220, 120, 0.22)",
                line_width=2,
                line_color="rgba(0, 220, 120, 0.85)",
                annotation_text=f"BUY ZONA ${zone_low:.2f} – ${zone_high:.2f}",
                annotation_position="top left",
                annotation_font_size=11,
                annotation_font_color="#00dd77",
            )

        if levels.get("entry_ideal"):
            y = levels["entry_ideal"]
            y_bounds.append(y)
            fig.add_hline(
                y=y, line_dash="dash", line_color="#00ff88", line_width=2,
                annotation_text=f"Vstup ${y:.2f}",
                annotation_position="right",
                annotation_font_color="#00ff88",
            )

        if levels.get("stop_loss"):
            y = levels["stop_loss"]
            y_bounds.append(y)
            fig.add_hline(
                y=y, line_dash="dot", line_color="#ff5555", line_width=2,
                annotation_text=f"Stop ${y:.2f}",
                annotation_position="right",
                annotation_font_color="#ff5555",
            )

        if levels.get("target_price"):
            y = levels["target_price"]
            y_bounds.append(y)
            fig.add_hline(
                y=y, line_dash="dot", line_color="#55bbff", line_width=2,
                annotation_text=f"Ciel ${y:.2f}",
                annotation_position="right",
                annotation_font_color="#55bbff",
            )

        close = levels.get("close_price")
        if close:
            y_bounds.append(close)
            fig.add_hline(
                y=close, line_dash="solid", line_color="#ffffff", line_width=1,
                annotation_text=f"Aktualne ${close:.2f}",
                annotation_position="left",
                annotation_font_color="#cccccc",
            )

    pad = (max(y_bounds) - min(y_bounds)) * 0.08 or 1.0
    fig.update_yaxes(range=[min(y_bounds) - pad, max(y_bounds) + pad])

    fig.update_layout(
        title=dict(text=f"{ticker}", font=dict(size=16, color="#e2e8f0")),
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(12, 18, 34, 0.85)",
        height=500,
        margin=dict(l=10, r=80, t=40, b=10),
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        font=dict(family="DM Sans, sans-serif", color="#94a3b8"),
        xaxis=dict(gridcolor="rgba(148,163,184,0.08)", showgrid=True),
        yaxis=dict(gridcolor="rgba(148,163,184,0.08)", showgrid=True),
    )
    return fig


def _tradingview_widget(ticker: str, height: int = 600) -> str:
    """Live interactive TradingView Advanced Chart widget."""
    container_id = f"tv_{ticker.replace('.', '_').replace('-', '_')}"
    return f"""
    <div class="tradingview-widget-container" style="height:{height}px;width:100%">
      <div id="{container_id}" style="height:100%;width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "autosize": true,
        "symbol": "{ticker}",
        "interval": "D",
        "timezone": "Europe/Bratislava",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#0c1222",
        "backgroundColor": "#0c1222",
        "gridColor": "rgba(148, 163, 184, 0.08)",
        "enable_publishing": false,
        "hide_side_toolbar": false,
        "allow_symbol_change": true,
        "withdateranges": true,
        "details": true,
        "studies": ["STD;SMA", "Volume@tv-basicstudies"],
        "container_id": "{container_id}"
      }});
      </script>
    </div>
    """


def _signal_pills(signals: list[str]) -> str:
    if not signals:
        return ""
    pills = "".join(f'<span class="signal-pill">{s}</span>' for s in signals)
    return f'<div style="margin-top:0.5rem">{pills}</div>'


def _chart_legend() -> str:
    return """
    <div class="legend-bar">
        <span><span class="legend-dot" style="background:rgba(0,220,120,0.6)"></span>Buy zona</span>
        <span><span class="legend-dot" style="background:#00ff88"></span>Vstup</span>
        <span><span class="legend-dot" style="background:#ff5555"></span>Stop</span>
        <span><span class="legend-dot" style="background:#55bbff"></span>Ciel</span>
        <span><span class="legend-dot" style="background:#ffaa00"></span>MA20</span>
    </div>
    """


def main() -> None:
    settings = load_settings()
    board = load_leaderboard()
    market_open = is_us_market_open()
    last_update = _last_update_label(board)
    status_chip = "chip-open" if market_open else "chip-closed"
    status_label = "OTVORENA" if market_open else "ZATVORENA"

    with st.sidebar:
        st.markdown("### 📋 Tabulka")
        default_index = 0 if settings.watchlist_source in ("russell2000", "both") else 1
        index_view = st.radio(
            "Index",
            options=["Russell 2000", "S&P 500"],
            index=default_index,
            horizontal=True,
            label_visibility="collapsed",
            key="index_view",
        )
        r2k_total = _ticker_count("russell2000")
        sp_total = _ticker_count("sp500")
        r2k_hits = _board_count_for_index(board, "Russell 2000")
        sp_hits = _board_count_for_index(board, "S&P 500")
        st.caption(f"Russell 2000: {r2k_hits}/{r2k_total} · S&P 500: {sp_hits}/{sp_total}")

        st.divider()
        st.markdown("### ⚙️ Ovládanie")
        st.caption("Nastavenia scanu a alertov")
        min_score = st.slider("Min skore", 35, 100, settings.bullish_min_score)
        vol_threshold = st.slider("Objem x", 1.5, 5.0, float(settings.bullish_volume_threshold), 0.1)
        send_email = st.checkbox(
            "Gmail alert",
            value=bool(settings.gmail_address),
            help=f"Tier {settings.gmail_min_tier}+ a skore >= {settings.gmail_min_score}",
        )
        send_telegram = st.checkbox(
            "Telegram alert",
            value=telegram_configured(settings),
            disabled=not telegram_configured(settings),
        )
        if not telegram_configured(settings):
            st.caption("Telegram: dopln TELEGRAM_BOT_TOKEN a TELEGRAM_CHAT_ID do .env")
        force_scan = st.checkbox("Scan mimo hodin", value=False)
        insider_only = st.checkbox("Len s insider nakupom", value=False)
        st.divider()
        run_scan = st.button("▶ Spustit scan", type="primary", use_container_width=True)
        if st.button("🗑 Vymazat zoznam", use_container_width=True):
            clear_leaderboard()
            st.rerun()

    filtered_board = _filter_board_by_index(board, index_view)
    insider_count = sum(1 for x in filtered_board if x.get("insider_buys", 0) > 0)

    st.markdown(
        f"""
        <div class="hero">
            <p class="hero-title">Market Scanner</p>
            <p class="hero-sub">AI agent · Russell 2000 & S&P 500 · bullish setupy</p>
            <div class="hero-meta">
                <span class="chip {status_chip}">● Burza {status_label}</span>
                <span class="chip">🕐 ET {now_eastern().strftime("%H:%M")}</span>
                <span class="chip">📋 {index_view}</span>
                <span class="chip">🏆 {len(filtered_board)} v tabulke</span>
                <span class="chip">🔄 Posledna aktualizacia: {last_update}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Burza", status_label)
    c2.metric("Cas ET", now_eastern().strftime("%H:%M"))
    c3.metric("Posledny scan", last_update)
    c4.metric("V tabulke", len(filtered_board))
    c5.metric("Insider nakupy", insider_count)
    c6.metric("Index", index_view)
    st.caption(market_status())

    tab_top, tab_scan, tab_backtest = st.tabs(["🏆 Top zoznam", "📡 Live Scan", "📊 Backtest"])

    with tab_top:
        st.markdown(f'<p class="section-head">Najpotencialnejsie akcie — {index_view}</p>', unsafe_allow_html=True)
        st.caption(
            f"Posledna aktualizacia: {last_update} (SK cas) · "
            f"Zoradene podla Potential Rank · zobrazenych {len(filtered_board)} z {index_view}"
        )

        display_board = filtered_board
        if insider_only:
            display_board = [x for x in display_board if x.get("insider_buys", 0) > 0]

        if display_board:
            df = _leaderboard_df(display_board)
            tickers = [item["ticker"] for item in display_board]

            st.caption("💡 Klikni na riadok v tabulke pre zobrazenie detailu a grafu")
            table_event = st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="board_table",
                column_config={
                    "#": st.column_config.NumberColumn(width="small"),
                    "Potencial": st.column_config.ProgressColumn(min_value=0, max_value=120, format="%.1f"),
                    "Ticker": st.column_config.TextColumn(width="small"),
                },
            )

            st.download_button(
                "⬇ Stiahnut CSV",
                df.to_csv(index=False).encode("utf-8"),
                file_name=f"top_akcie_{'russell2000' if index_view == 'Russell 2000' else 'sp500'}.csv",
                mime="text/csv",
            )

            if st.session_state.get("selected_ticker") not in tickers:
                st.session_state["selected_ticker"] = tickers[0]

            selected_rows = table_event.selection["rows"] if table_event and table_event.selection else []
            if selected_rows:
                clicked_ticker = tickers[selected_rows[0]]
                if clicked_ticker != st.session_state["selected_ticker"]:
                    st.session_state["selected_ticker"] = clicked_ticker

            st.markdown('<p class="section-head">Detail tickera</p>', unsafe_allow_html=True)
            selected = st.selectbox(
                "Vyber ticker",
                tickers,
                index=tickers.index(st.session_state["selected_ticker"]),
                label_visibility="collapsed",
            )
            st.session_state["selected_ticker"] = selected
            item = next(x for x in display_board if x["ticker"] == selected)
            ticker_history = _cached_ticker_history(selected, 20)
            chart_levels = _resolve_chart_levels(item, ticker_history)
            col_a, col_b = st.columns([1, 2], gap="large")
            with col_a:
                rank_num = display_board.index(item) + 1
                st.markdown(
                    f"""
                    <div class="panel-card">
                        <div class="ticker-rank">#{rank_num} RANK</div>
                        <p class="ticker-head">{item['ticker']}</p>
                        <span class="prob-badge">{item['probability']}</span>
                        <span class="prob-badge" style="margin-left:0.5rem">Tier {item.get('tier', 'C')}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                m1, m2 = st.columns(2)
                m1.metric("Potential", item["potential_rank"])
                m2.metric("Skore", f"{item['score']}/100")
                st.caption(f"Aktualizovany: {_format_local_time(item.get('last_seen'))}")
                if item.get("tier_reason"):
                    tier = item.get("tier", "C")
                    if tier == "S":
                        st.success(f"Tier {tier}: {item['tier_reason']}")
                    elif tier == "A":
                        st.info(f"Tier {tier}: {item['tier_reason']}")
                    else:
                        st.warning(f"Tier {tier}: {item['tier_reason']}")
                st.markdown('<div class="panel-card">', unsafe_allow_html=True)
                st.markdown('<div class="panel-title">Insider aktivita</div>', unsafe_allow_html=True)
                if item.get("insider_buys", 0) > 0:
                    st.success(item.get("insider_summary", ""))
                    if item.get("insider_names"):
                        st.caption("Manazeri: " + ", ".join(item["insider_names"]))
                else:
                    st.info("Ziadny insider nakup v poslednych 90 dnoch")
                st.markdown("</div>", unsafe_allow_html=True)

                st.markdown(
                    f'<div class="panel-card"><div class="panel-title">Backtest</div>'
                    f'<span style="color:var(--muted)">{item.get("backtest_hint", "")}</span></div>',
                    unsafe_allow_html=True,
                )
                entry_summary = item.get("entry_summary")
                entry_action = item.get("entry_action", "")
                if chart_levels and not entry_summary:
                    entry_summary = (
                        f"Idealny vstup ${chart_levels['entry_ideal']:.2f} "
                        f"(zona ${chart_levels['entry_zone_low']:.2f}"
                        f"-${chart_levels['entry_zone_high']:.2f})"
                    )
                if chart_levels or item.get("entry_ideal"):
                    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
                    st.markdown('<div class="panel-title">Odporucany vstup</div>', unsafe_allow_html=True)
                    levels_src = chart_levels or item
                    if entry_action == "vstup_teraz":
                        st.success(entry_summary or "")
                    elif entry_action == "cakat_pullback":
                        st.warning(entry_summary or "")
                    else:
                        st.info(entry_summary or "")
                    ec1, ec2, ec3 = st.columns(3)
                    ec1.metric("Vstup", f"${levels_src['entry_ideal']:.2f}")
                    ec2.metric("Stop", f"${levels_src['stop_loss']:.2f}")
                    ec3.metric("Ciel", f"${levels_src['target_price']:.2f}")
                    st.caption(
                        f"Buy zona ${levels_src['entry_zone_low']:.2f} – "
                        f"${levels_src['entry_zone_high']:.2f}"
                    )
                    st.markdown("</div>", unsafe_allow_html=True)
                quarters = item.get("earnings_quarters", [])
                if quarters:
                    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
                    st.markdown('<div class="panel-title">Posledne 4 kvartaly</div>', unsafe_allow_html=True)
                    eq_df = pd.DataFrame([
                        {
                            "Obdobie": q["period"],
                            "Trzby": q["revenue_fmt"],
                            "Cisty zisk": q["net_income_fmt"],
                            "EPS": q.get("eps", "n/a"),
                            "Trzby QoQ": f"{q['revenue_qoq_pct']:+.1f}%" if q.get("revenue_qoq_pct") is not None else "-",
                            "Marza": f"{q['net_margin_pct']:.1f}%" if q.get("net_margin_pct") is not None else "-",
                        }
                        for q in quarters
                    ])
                    st.dataframe(eq_df, use_container_width=True, hide_index=True)
                    trend = item.get("earnings_trend", "")
                    if trend == "rastuca":
                        st.success(f"Trend trzieb: {trend}")
                    elif trend == "klesajuca":
                        st.warning(f"Trend trzieb: {trend}")
                    st.markdown("</div>", unsafe_allow_html=True)
                signals = item.get("signals", [])
                if signals:
                    st.markdown(
                        f'<div class="panel-card"><div class="panel-title">Aktivne signaly</div>'
                        f"{_signal_pills(signals)}</div>",
                        unsafe_allow_html=True,
                    )
            with col_b:
                chart_mode = st.radio(
                    "Typ grafu",
                    ["📈 TradingView (live)", "📊 Market Scanner (buy zona)"],
                    horizontal=True,
                    label_visibility="collapsed",
                    key="chart_mode",
                )
                if chart_mode.startswith("📈"):
                    components.html(_tradingview_widget(selected, height=600), height=610)
                    st.caption(
                        "Plne interaktivny TradingView graf — zoom, timeframy, indikatory, kreslenie. "
                        "Symbol vies zmenit priamo v grafe."
                    )
                else:
                    st.markdown('<div class="panel-card" style="padding:0.75rem">', unsafe_allow_html=True)
                    if ticker_history is None:
                        st.warning(
                            "Yahoo Finance docasne limituje poziadavky (rate limit). "
                            "Pockaj 1–2 minuty a obnov stranku (F5)."
                        )
                    else:
                        fig = _price_chart(selected, ticker_history, chart_levels)
                        if fig:
                            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True})
                            if chart_levels:
                                st.markdown(_chart_legend(), unsafe_allow_html=True)
                            else:
                                st.caption("Nepodarilo sa vypocitat vstupnu zonu pre tento ticker.")
                    st.markdown("</div>", unsafe_allow_html=True)
        elif insider_only:
            st.warning(f"Ziadne {index_view} akcie s insider nakupom v zozname.")
        else:
            st.info(f"V {index_view} zatial nie su ziadne akcie. Spusti scan v bočnom paneli alebo prepni index.")

    with tab_scan:
        if run_scan:
            if not force_scan and settings.market_hours_only and not is_us_market_open():
                st.warning(market_status())
            else:
                scan_settings = replace(settings, bullish_min_score=min_score,
                                        bullish_volume_threshold=vol_threshold)
                with st.spinner("Skenujem..."):
                    setups = scan_bullish_setups(scan_settings)
                if setups and (send_email or send_telegram):
                    for s in setups:
                        gmail_ok = send_email and should_send_gmail_for_setup(s, settings)
                        notify(
                            s.message,
                            settings,
                            subject=f"Tier {s.tier}: {s.ticker} ({s.score}/100)",
                            gmail=gmail_ok,
                            telegram=send_telegram,
                        )
                        if gmail_ok:
                            record_gmail_sent(s)
                st.success(f"Hotovo — {len(setups)} setupov, zoznam aktualizovany")
                st.rerun()

        if board:
            scan_index_view = st.radio(
                "Index tabulky",
                options=["Russell 2000", "S&P 500"],
                horizontal=True,
                key="scan_index_view",
            )
            scan_board = _filter_board_by_index(board, scan_index_view)
            st.caption(f"{scan_index_view}: {len(scan_board)} akcii")
            st.dataframe(_leaderboard_df(scan_board), use_container_width=True, hide_index=True)
        else:
            st.info("Ziadne vysledky")

    with tab_backtest:
        st.markdown('<p class="section-head">Backtest vysledky</p>', unsafe_allow_html=True)
        if BACKTEST_FILE.exists():
            st.markdown('<div class="panel-card">', unsafe_allow_html=True)
            st.code(BACKTEST_FILE.read_text(encoding="utf-8"), language=None)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning("Spusti: py -m market_scanner.main --backtest")


if __name__ == "__main__":
    main()