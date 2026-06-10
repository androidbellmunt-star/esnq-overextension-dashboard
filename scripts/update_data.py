import json, math, os, time
from datetime import datetime
import requests
import pandas as pd
import yfinance as yf

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

TICKERS = {
    "QQQ": "QQQ",
    "SPY": "SPY",
    "SMH": "SMH",
    "XLK": "XLK",
    "XLP": "XLP",
    "HYG": "HYG",
    "IEF": "IEF",
    "VIX": "^VIX",
    "VXN": "^VXN",
    "USDJPY": "JPY=X"
}

def fetch_prices():
    last_err = None

    for attempt in range(5):
        try:
            df = yf.download(
                list(TICKERS.values()),
                period="6mo",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False
            )["Adj Close"].dropna(how="all")

            if df.empty:
                raise ValueError("No data returned from Yahoo Finance")

            df.columns = [k for k in TICKERS.keys()]
            df = df.dropna()

            if df.empty:
                raise ValueError("Downloaded data became empty after dropna()")

            return df

        except Exception as e:
            last_err = e
            wait_seconds = 15 * (attempt + 1)
            print(f"Download attempt {attempt + 1} failed: {e}. Retrying in {wait_seconds}s...")
            time.sleep(wait_seconds)

    print(f"All download attempts failed: {last_err}")
    return None

def ret(a, b):
    return a / b - 1

def realized_vol(series):
    r = (series / series.shift(1)).apply(math.log).dropna()
    if len(r) < 2:
        return 0.0
    return r.std() * math.sqrt(252) * 100

def classify_state(score):
    if score >= 7.5:
        return "Very overextended", "red"
    if score >= 6:
        return "Overextended", "red"
    if score >= 4:
        return "Stretched", "amber"
    return "Normal", "green"

def run_model(df):
    last = df.iloc[-1]
    prev5 = df.iloc[-6] if len(df) >= 6 else df.iloc[0]
    ma5 = df.tail(5).mean()

    nq_es_spread = ret(last["QQQ"], prev5["QQQ"]) - ret(last["SPY"], prev5["SPY"])
    tech_def = ret(last["XLK"], prev5["XLK"]) - ret(last["XLP"], prev5["XLP"])
    dispersion = int(nq_es_spread > 0.02) + int(tech_def > 0.03)

    ext_spy = last["SPY"] / ma5["SPY"] - 1
    ext_qqq = last["QQQ"] / ma5["QQQ"] - 1
    extension = int(ext_spy > 0.01 or ext_qqq > 0.015) + int(ext_spy > 0.02 or ext_qqq > 0.03)

    rv_spy = realized_vol(df["SPY"].tail(21))
    rv_qqq = realized_vol(df["QQQ"].tail(21))
    vol = int((last["VXN"] - last["VIX"]) > 8 or rv_qqq > rv_spy * 1.2) + int((last["VXN"] - last["VIX"]) > 11 or rv_qqq > rv_spy * 1.35)

    smh_lead = ret(last["SMH"], prev5["SMH"]) - ret(last["SPY"], prev5["SPY"])
    concentration = int(smh_lead > 0.03) + int(smh_lead > 0.06)

    hyg_ief = last["HYG"] / last["IEF"]
    prev_hyg_ief = prev5["HYG"] / prev5["IEF"]
    usdjpy = float(last["USDJPY"])
    regime = "Green"

    if hyg_ief < prev_hyg_ief * 0.995 or usdjpy > 158.5 or last["VIX"] > 20 or last["VXN"] > 28:
        regime = "Amber"
    if hyg_ief < prev_hyg_ief * 0.99 or usdjpy > 160 or last["VIX"] > 25 or last["VXN"] > 32:
        regime = "Red"

    total = float(dispersion + extension + vol + concentration)
    state, state_class = classify_state(total)

    if regime == "Red" and total >= 6:
        correction_risk, action_bias = "High", "Defensive"
    elif total >= 7.5:
        correction_risk, action_bias = "High", "Reduce / hedge"
    elif total >= 6:
        correction_risk, action_bias = "Elevated", "No chase"
    elif total >= 4:
        correction_risk, action_bias = "Moderate", "Selective"
    else:
        correction_risk, action_bias = "Low", "Trend allowed"

    regime_text = {
        "Green": "Credit/liquidity supportive",
        "Amber": "Watch stress building",
        "Red": "Backdrop can amplify downside"
    }[regime]

    hist_dates, hist_nq, hist_score = [], [], []
    for i in range(5, len(df)):
        seg = df.iloc[:i+1]
        last2 = seg.iloc[-1]
        prev52 = seg.iloc[-6]
        ma52 = seg.tail(5).mean()

        d = int(ret(last2["QQQ"], prev52["QQQ"]) - ret(last2["SPY"], prev52["SPY"]) > 0.02) + int(ret(last2["XLK"], prev52["XLK"]) - ret(last2["XLP"], prev52["XLP"]) > 0.03)
        e = int(last2["SPY"] / ma52["SPY"] - 1 > 0.01 or last2["QQQ"] / ma52["QQQ"] - 1 > 0.015) + int(last2["SPY"] / ma52["SPY"] - 1 > 0.02 or last2["QQQ"] / ma52["QQQ"] - 1 > 0.03)
        rv_spy2 = realized_vol(seg["SPY"].tail(21))
        rv_qqq2 = realized_vol(seg["QQQ"].tail(21))
        v = int((last2["VXN"] - last2["VIX"]) > 8 or rv_qqq2 > rv_spy2 * 1.2) + int((last2["VXN"] - last2["VIX"]) > 11 or rv_qqq2 > rv_spy2 * 1.35)
        c = int(ret(last2["SMH"], prev52["SMH"]) - ret(last2["SPY"], prev52["SPY"]) > 0.03) + int(ret(last2["SMH"], prev52["SMH"]) - ret(last2["SPY"], prev52["SPY"]) > 0.06)

        hist_dates.append(seg.index[-1].strftime("%Y-%m-%d"))
        hist_nq.append(round(float(last2["QQQ"]), 2))
        hist_score.append(float(d + e + v + c))

    component_table = [
        {"name": "Dispersion", "value": f"{dispersion} | nq-spread={nq_es_spread:.3f}", "status": "Hot" if dispersion >= 1 else "Calm", "class": "amber" if dispersion == 1 else ("red" if dispersion == 2 else "green")},
        {"name": "Extension", "value": f"{extension} | qqq={ext_qqq:.3%}", "status": "Stretched" if extension >= 1 else "Normal", "class": "amber" if extension == 1 else ("red" if extension == 2 else "green")},
        {"name": "Vol", "value": f"{vol} | VXN-VIX={last['VXN'] - last['VIX']:.2f}", "status": "Rising" if vol >= 1 else "Contained", "class": "amber" if vol == 1 else ("red" if vol == 2 else "green")},
        {"name": "Leadership", "value": f"{concentration} | smh-lead={smh_lead:.3f}", "status": "Narrow" if concentration >= 1 else "Broad", "class": "amber" if concentration == 1 else ("red" if concentration == 2 else "green")},
        {"name": "Regime", "value": f"HYG/IEF={hyg_ief:.4f} | USDJPY={usdjpy:.2f}", "status": regime, "class": state_class if regime != "Green" else "green"}
    ]

    result = {
        "updated_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "regime": regime,
        "regime_text": regime_text,
        "correction_risk": correction_risk,
        "action_bias": action_bias,
        "total_score": total,
        "state": state,
        "state_class": state_class,
        "component_table": component_table,
        "history": {"dates": hist_dates, "nq": hist_nq, "score": hist_score}
    }
    return result

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=20)

def main():
    df = fetch_prices()

    if df is None:
        msg = (
            "ES/NQ dashboard update\n"
            "Data source temporarily unavailable.\n"
            "Yahoo Finance returned no data after multiple retries."
        )
        send_telegram(msg)
        return

    result = run_model(df)

    out = os.path.join(os.path.dirname(__file__), "..", "data", "latest.json")
    with open(out, "w") as f:
        json.dump(result, f, indent=2)

    msg = (
        f"ES/NQ dashboard update\n"
        f"Date: {result['updated_date']}\n"
        f"Backdrop: {result['regime']} ({result['regime_text']})\n"
        f"Tactical score: {result['total_score']:.1f}\n"
        f"Tactical state: {result['state']}\n"
        f"Composite stance: {result['action_bias']}\n"
        f"Risk: {result['correction_risk']}\n"
        f"Interpretation: {result['regime_text']}"
    )
    send_telegram(msg)

if __name__ == "__main__":
    main()