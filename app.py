
from datetime import datetime, timedelta
import json
import numpy as np
import pandas as pd
import pytz
import yfinance as yf
import streamlit as st

AUS_TZ = pytz.timezone("Australia/Melbourne")

# --- Safe JSON export helper to avoid NaN/Inf issues in downloads ---
def df_to_json_str(df: pd.DataFrame) -> str:
    """Convert a holdings DataFrame to a JSON string safely for download."""
    df = df.copy()
    if "Ticker" in df.columns:
        df = df[~df["Ticker"].isna() & (df["Ticker"].astype(str).str.strip() != "")]
    for col in ("Quantity", "CostBasis_AUD"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.replace([np.inf, -np.inf], np.nan).where(pd.notnull(df), None)
    data = df.to_dict(orient="list")
    return json.dumps(data, ensure_ascii=False, indent=2)

DEFAULT_TICKERS = [
    "NDQ.AX", "VGS.AX", "A200.AX", "FANG.AX",
    "CRYP.AX", "HACK.AX", "ROBO.AX",
    "GGUS.AX", "GEAR.AX",
    "ZIP.AX", "BNR.AX", "IVZ.AX",
    "BTC-USD", "ETH-USD",
    "EBTC.AX", "ETHT.AX",
]
HOLDINGS_PATH = "holdings.json"

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

@st.cache_data(ttl=60)
def fetch_quotes(tickers: list[str]) -> pd.DataFrame:
    if not tickers:
        return pd.DataFrame()
    t = yf.Tickers(" ".join(tickers))
    rows = []
    for tk, obj in t.tickers.items():
        try:
            info = obj.fast_info
            rows.append({
                "Ticker": tk,
                "Price": info.get("last_price"),
                "PrevClose": info.get("previous_close"),
                "Open": info.get("open"),
                "Currency": info.get("currency"),
            })
        except Exception:
            rows.append({"Ticker": tk, "Price": np.nan, "PrevClose": np.nan, "Open": np.nan, "Currency": None})
    return pd.DataFrame(rows)

@st.cache_data(ttl=300)
def fetch_hourly_change(ticker: str) -> float:
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
    try:
        fx = yf.download("AUDUSD=X", period="1d", interval="5m", progress=False)["Close"].dropna()
        return float(fx.iloc[-1])
    except Exception:
        return 0.67

def compute_portfolio(holdings: pd.DataFrame, quotes: pd.DataFrame) -> pd.DataFrame:
    df = holdings.merge(quotes, on="Ticker", how="left")
    audusd = get_audusd()
    def to_aud(row):
        price = row.get("Price")
        cur = row.get("Currency")
        if pd.isna(price): return np.nan
        return price / audusd if cur == "USD" else price
    df["Price_AUD"] = df.apply(to_aud, axis=1)
    df["MarketValue_AUD"] = df["Price_AUD"] * df["Quantity"]
    df["Cost_AUD"] = df["CostBasis_AUD"] * df["Quantity"]
    df["Unrealised_PnL_AUD"] = df["MarketValue_AUD"] - df["Cost_AUD"]
    df["Intraday_%"] = (df["Price"] / df["PrevClose"] - 1.0) * 100.0
    df["Hour_%"] = [fetch_hourly_change(tk) for tk in df["Ticker"].tolist()]
    return df

st.set_page_config(page_title="Inas Investing – Live Tracker", layout="wide")
st.title("📈 Inas Investing – Live Portfolio Tracker (Web Dashboard)")

with st.sidebar:
    st.markdown("### Settings")
    refresh_sec = st.number_input("Auto-refresh seconds", min_value=30, max_value=600, value=60, step=10)
    st.caption("Data cached briefly to reduce API calls. Prices can be delayed.")
    st.markdown("---")
    st.markdown("**Tickers to track** (add/remove as needed):")

holdings = load_holdings()

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

c1, c2 = st.columns(2)
with c1:
    if st.button("💾 Save holdings (local file)"):
        save_holdings(edited)
        st.success("Saved to holdings.json (local session storage).")
with c2:
    if st.button("↻ Reload from file"):
        holdings = load_holdings()
        st.rerun()

st.markdown("### Import / Export holdings (for Streamlit Cloud)")
u1, u2 = st.columns(2)
with u1:
    up = st.file_uploader("Upload holdings.json", type=["json"])
    if up is not None:
        try:
            data = json.loads(up.read().decode("utf-8"))
            df = pd.DataFrame(data)
            for col in ("Ticker", "Quantity", "CostBasis_AUD", "Notes"):
                if col not in df.columns:
                    df[col] = None
            df["Ticker"] = df["Ticker"].astype(str)
            for col in ("Quantity", "CostBasis_AUD"):
                df[col] = pd.to_numeric(df[col], errors="coerce")
            edited = df
            st.success("Loaded holdings from uploaded file.")
        except Exception as e:
            st.error(f"Upload failed: {e}")
with u2:
    st.download_button(
        label="Download current holdings.json",
        data=df_to_json_str(edited),
        file_name="holdings.json",
        mime="application/json",
    )

quotes = fetch_quotes(edited["Ticker"].tolist())
portfolio = compute_portfolio(edited, quotes)

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

cols = [
    "Ticker","Quantity","CostBasis_AUD","Price","Currency","Price_AUD",
    "MarketValue_AUD","Unrealised_PnL_AUD","Intraday_%","Hour_%","Notes"
]
fmt = portfolio[cols].copy().sort_values("MarketValue_AUD", ascending=False)
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

st.subheader("Hourly price (last 24h)")
for tk in fmt["Ticker"].tolist():
    try:
        end = datetime.now(tz=pytz.UTC)
        start = end - timedelta(hours=24)
        hist = yf.download(tk, interval="1h", start=start, end=end, progress=False)
        if hist is None or hist.empty:
            continue
        series = hist["Close"].dropna()
        if series.empty: continue
        st.line_chart(series, height=150, use_container_width=True)
        st.caption(f"{tk} – hourly closes (last 24h)")
    except Exception:
        continue

st.markdown("---")
last_update = datetime.now(AUS_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
st.caption(f"Last update: {last_update}. Tip: leave this tab open to auto-refresh via interactions.")
