# Inas Investing – Web Dashboard Repo

This package gives you a **ready-to-deploy GitHub repository** for your Streamlit-based live portfolio tracker.

## 📁 Repository structure

```
inas-investing-tracker/
├─ app.py                 # Dashboard app
├─ requirements.txt       # Python dependencies
├─ README.md              # This guide
├─ .gitignore             # Keeps your repo clean
├─ sample_holdings.json   # Optional template for starting positions
└─ .streamlit/
   └─ secrets.toml        # (Optional) for API keys if you add a DB later
```

## ✅ Files included

- `app.py` – Streamlit dashboard
- `requirements.txt` – dependencies
- `.gitignore` – repo hygiene
- `sample_holdings.json` – example data
- (Create `.streamlit/secrets.toml` later if you add Sheets/DB)

## 🚀 Quick start (local)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## 🌐 Deploy to Streamlit Community Cloud (free)

1. Create a GitHub repo (Public recommended): `inas-investing-tracker`.
2. Upload these files.
3. Go to https://share.streamlit.io → New app → select your repo → main file `app.py` → Deploy.
4. You’ll get a public URL in ~1–2 minutes.

### App updates

- Push changes to GitHub; Streamlit automatically redeploys.

## 💾 Persistence options on the web

Because Streamlit Cloud’s disk can reset, use one of these:

### Option A: Upload/Download holdings (simple, no external services)

Use the built-in **Import/Export** section in the app (already included).  
Download your `holdings.json` after editing; next time you visit, Upload it back.

### Option B: Google Sheets backend (always saved)

- Add a Google service account; put credentials in `.streamlit/secrets.toml`.
- Use `gspread` / `google-auth` to read/write holdings. (Can be added later.)

### Option C: Database (Supabase/Firestore)

- Add connection details to `secrets.toml` and use their Python client libraries.

## 📏 Ticker format reference

- **ASX**: add `.AX` (e.g., `NDQ.AX`, `VGS.AX`, `A200.AX`, `ZIP.AX`).
- **Crypto (Yahoo)**: `BTC-USD`, `ETH-USD` etc.
- **AU crypto ETFs**: `EBTC.AX`, `ETHT.AX`, or `CRYP.AX` (crypto stocks).

> Data is from Yahoo Finance; it may be delayed and rate-limited. Verify prices in your broker before trading.

## 🧰 Troubleshooting

- **ModuleNotFoundError** → ensure `requirements.txt` is in the repo root.
- **Slow/empty charts** → reduce tickers; Yahoo may throttle. Try again later.
- **Wrong currency** → non‑AUD symbols get converted using `AUDUSD=X`; verify FX if precision matters.
- **ASX symbol not found** → ensure the `.AX` suffix is present.

## 🏁 Pre-fill request

Send me your tickers, quantities, and average cost (AUD); I’ll generate a tailored `holdings.json`.
