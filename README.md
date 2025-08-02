# Inas Investing – Web Dashboard (latest fixes)
- No Pandas Styler in table (uses Streamlit `column_config`).
- Safe JSON export (cleans NaN/Inf and blank rows).
- Numeric coercion before display to avoid TypeError.
Deploy on https://share.streamlit.io with `app.py` as main file.
