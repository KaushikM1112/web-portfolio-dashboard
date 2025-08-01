"""
Inas Investing – Live Portfolio Tracker (Web Dashboard)
Streamlit app to track a mixed high‑risk portfolio (ASX ETFs & stocks, crypto, and AU crypto ETFs)
with near‑real‑time refresh and hour‑by‑hour performance.

How to run locally:
1) Save this file as app.py
2) Create `requirements.txt` with:
   yfinance
   streamlit
   pandas
   numpy
   pytz
3) Install deps:  `pip install -r requirements.txt`
4) Run:  `streamlit run app.py`

How to deploy to Streamlit Community Cloud (free):
1) Create a GitHub repo and add `app.py` and `requirements.txt`.
2) Go to https://share.streamlit.io, connect your GitHub, choose the repo and `app.py` as the entry point.
3) (Optional) Add secrets later if you integrate Sheets/DB.
4) Click Deploy.

Notes:
• ASX tickers use suffix .AX (e.g., NDQ.AX, VGS.AX).  
• Crypto uses Yahoo symbols like BTC-USD, ETH-USD.  
• Hourly tracking uses Yahoo Finance 1h interval data (where available).  
• Market data isn't guaranteed and can be delayed; confirm prices in your broker.
"""
from datetime import datetime, timedelta
import json
import numpy as np
import pandas as pd
import pytz
import yfinance as yf
import streamlit as st

AUS_TZ = pytz.timezone("Australia/Melbourne")

# ---------- User-configurable defaults ----------
DEFAULT_TICKERS = [
    # Tech / growth ETFs (ASX)
    "NDQ.AX", "VGS.AX", "A200.AX", "FANG.AX",
    # Thematic/speculative ETFs (ASX)
    "CRYP.AX", "HACK.AX", "ROBO.AX",
    # Leveraged ETFs (ASX)
    "GGUS.AX", "GEAR.AX",
    # Small caps (ASX examples)
    "ZIP.AX", "BNR.AX", "IVZ.AX",
    # Crypto (direct)
    "BTC-USD", "ETH-USD",
    # AU crypto ETFs
    "EBTC.AX", "ETHT.AX",
]

HOLDINGS_PATH = "holdings.json"

# ---------- Persistence helpers ----------
def load_holdings(path: str = HOLDINGS_PATH) -> pd.DataFrame:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        df = pd.DataFrame(data)
    except Exception:
        df = pd.DataFrame({
            "Ticker": DEFAULT_TICKERS,
            "Quantity": [0.0] * len(DEFAULT_TICKERS),
            "CostBasis_AUD": [0.0] * len(DEFAULT_TICKERS),
            "Notes": [""] * len(DEFAULT_TICKERS),
        })
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0.0)
    df["CostBasis_AUD"] = pd.to_numeric(df["CostBasis_AUD"], errors="coerce").fillna(0.0)
    df["Ticker"] = df["Ticker"].astype(str)
    if "Notes" not in df.columns:
        df["Notes"] = ""
    return df

def save_holdings(df: pd.DataFrame, path: str = HOLDINGS_PATH) -> None:
    data = df.to_dict(orient="list")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------- Pricing helpers ----------
@st.cache_data(ttl=60)
def fetch_quotes(tickers: list[str]) -> pd.DataFrame:
    """Fetch latest quote snapshot for tickers. Cached for 60 seconds."""
    if not tickers:
        return pd.DataFrame()
    t = yf.Tickers(" ".join(tickers))
    rows = []
    for tk, obj in t.tickers.items():
        try:
            info = obj.fast_info  # quicker snapshot
            price = info.get("last_price")
            currency = info.get("currency")
            prev_close = info.get("previous_close")
            open_price = info.get("open")
            rows.append({
                "Ticker": tk,
                "Price": price,
                "PrevClose": prev_close,
                "Open": open_price,
                "Currency": currency,
            })
        except Exception:
            rows.append({"Ticker": tk, "Price": np.nan, "PrevClose": np.nan, "Open": np.nan, "Currency": None})
    return pd.DataFrame(rows)

@st.cache_data(ttl=300)
def fetch_hourly_change(ticker: str) -> float:
    """Return % change over the last hour using 1h interval, if available."""
    try:
        end = datetime.now(tz=pytz.UTC)
        start = end - timedelta(hours=6)
        hist = yf.download(ticker, interval="1h", start=start, end=end, progress=False)
        if hist is None or hist.empty or len(hist) < 2:
            return np.nan
        last = hist["Close"].iloc[-1]
        prev = hist["Close"].iloc[-2]
        if prev and prev != 0:
            return (last / prev - 1) * 100.0
    except Exception:
        pass
    return np.nan

@st.cache_data(ttl=120)
def get_audusd() -> float:
    """Approximate AUDUSD FX rate to convert USD -> AUD."""
    try:
        fx = yf.download("AUDUSD=X", period="1d", interval="5m", progress=False)["Close"].dropna()
        return float(fx.iloc[-1])
    except Exception:
        return 0.67  # fallback

def compute_portfolio(holdings: pd.DataFrame, quotes: pd.DataFrame) -> pd.DataFrame:
    df = holdings.merge(quotes, on="Ticker", how="left")
    audusd = get_audusd()

    def to_aud(row):
        price = row.get("Price")
        cur = row.get("Currency")
        if pd.isna(price):
            return np.nan
        if cur == "USD":
            return price / audusd  # USD -> AUD
        return price  # assume already AUD (ASX)
    df["Price_AUD"] = df.apply(to_aud, axis=1)

    df["MarketValue_AUD"] = df["Price_AUD"] * df["Quantity"]
    df["Cost_AUD"] = df["CostBasis_AUD"] * df["Quantity"]
    df["Unrealised_PnL_AUD"] = df["MarketValue_AUD"] - df["Cost_AUD"]

    # Intraday % change vs PrevClose
    df["Intraday_%"] = (df["Price"] / df["PrevClose"] - 1.0) * 100.0

    # Hourly % change (per ticker)
    hourly_changes = []
    for tk in df["Ticker"].tolist():
        hourly_changes.append(fetch_hourly_change(tk))
    df["Hour_%"] = hourly_changes

    return df

# ---------- UI ----------
st.set_page_config(page_title="Inas Investing – Live Tracker", layout="wide")
st.title("📈 Inas Investing – Live Portfolio Tracker (Web Dashboard)")

with st.sidebar:
    st.markdown("### Settings")
    refresh_sec = st.number_input("Auto-refresh seconds", min_value=30, max_value=600, value=60, step=10)
    st.caption("Data cached briefly to reduce API calls. Prices can be delayed.")
    st.markdown("---")
    st.markdown("**Tickers to track** (add/remove as needed):")

holdings = load_holdings()

# Editable holdings table
edited = st.data_editor(
    holdings,
    num_rows="dynamic",
    use_container_width=True,
    key="holdings_editor",
    column_config={
        "Ticker": st.column_config.TextColumn(help="e.g., NDQ.AX, VGS.AX, BTC-USD"),
        "Quantity": st.column_config.NumberColumn(format="%0.6f"),
        "CostBasis_AUD": st.column_config.NumberColumn(help="Average entry price in AUD"),
        "Notes": st.column_config.TextColumn(),
    },
)

col_s1, col_s2 = st.columns([1,1])
with col_s1:
    if st.button("💾 Save holdings (local file)"):
        save_holdings(edited)
        st.success("Saved to holdings.json (local session storage).")
with col_s2:
    if st.button("↻ Reload from file"):
        holdings = load_holdings()
        st.rerun()

# Import / Export holdings (for Streamlit Cloud persistence)
st.markdown("### Import / Export holdings (for Streamlit Cloud)")
col_u, col_d = st.columns(2)
with col_u:
    up = st.file_uploader("Upload holdings.json", type=["json"])
    if up is not None:
        try:
            data = json.loads(up.read().decode("utf-8"))
            edited = pd.DataFrame(data)
            st.success("Loaded holdings from uploaded file.")
        except Exception as e:
            st.error(f"Upload failed: {e}")
with col_d:
    st.download_button(
        label="Download current holdings.json",
        data=edited.to_json(orient="list", force_ascii=False, indent=2),
        file_name="holdings.json",
        mime="application/json",
    )

# Fetch quotes & compute portfolio
quotes = fetch_quotes(edited["Ticker"].tolist())
portfolio = compute_portfolio(edited, quotes)

# Summary KPIs
total_mv = float(portfolio["MarketValue_AUD"].sum(skipna=True))
total_cost = float(portfolio["Cost_AUD"].sum(skipna=True))
unreal = total_mv - total_cost
intraday_mv = float((portfolio["MarketValue_AUD"] * (portfolio["Intraday_%"] / 100.0)).sum(skipna=True))
hour_mv = float((portfolio["MarketValue_AUD"] * (portfolio["Hour_%"] / 100.0)).sum(skipna=True))

k1, k2, k3, k4 = st.columns(4)
k1.metric("Portfolio Value (AUD)", f"{total_mv:,.0f}")
k2.metric("Unrealised P/L (AUD)", f"{unreal:,.0f}")
k3.metric("Est. Intraday Move (AUD)", f"{intraday_mv:,.0f}")
k4.metric("Last Hour Move (AUD)", f"{hour_mv:,.0f}")

st.markdown("---")

# Detailed table
show_cols = [
    "Ticker", "Quantity", "CostBasis_AUD", "Price", "Currency", "Price_AUD",
    "MarketValue_AUD", "Unrealised_PnL_AUD", "Intraday_%", "Hour_%", "Notes"
]
fmt = portfolio[show_cols].copy()
fmt = fmt.sort_values("MarketValue_AUD", ascending=False)

st.subheader("Holdings detail")
st.dataframe(fmt.style.format({
    "Quantity": "{:.6f}",
    "CostBasis_AUD": "{:.4f}",
    "Price": "{:.4f}",
    "Price_AUD": "{:.4f}",
    "MarketValue_AUD": "{:,.0f}",
    "Unrealised_PnL_AUD": "{:,.0f}",
    "Intraday_%": "{:.2f}%",
    "Hour_%": "{:.2f}%",
}), use_container_width=True)

# Mini charts: Hourly sparkline per ticker (where data available)
st.subheader("Hourly price (last 24h)")
for tk in fmt["Ticker"].tolist():
    try:
        end = datetime.now(tz=pytz.UTC)
        start = end - timedelta(hours=24)
        hist = yf.download(tk, interval="1h", start=start, end=end, progress=False)
        if hist is None or hist.empty:
            continue
        series = hist["Close"].dropna()
        if series.empty:
            continue
        st.line_chart(series, height=150, use_container_width=True)
        st.caption(f"{tk} – hourly closes (last 24h)")
    except Exception:
        continue

st.markdown("---")
last_update = datetime.now(AUS_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
st.caption(f"Last update: {last_update}. Tip: leave this tab open to auto-refresh via interactions.")
