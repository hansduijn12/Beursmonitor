import os
import time
import pytz
import yfinance as yf
from datetime import datetime
from flask import Flask, jsonify

app = Flask(__name__)

# Een compacte en snelle selectie om de server licht en stabiel te houden
TICKERS_AEX = ["ADYEN.AS", "ASM.AS", "ASML.AS", "BESI.AS", "INGA.AS", "PRX.AS", "RELX.AS", "SHELL.AS", "UNA.AS", "ABN.AS"]
TICKERS_AMX = ["ALLFG.AS", "APAM.AS", "ARCAD.AS", "BAMNB.AS", "CORB.AS", "FLOW.AS", "FUR.AS", "INPST.AS", "JDEP.AS", "LIGHT.AS"]
TICKERS_NASDAQ = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST", "PEP"]

CACHE_DATA = None
LAST_FETCH_TIME = 0
CACHE_DURATION_SEC = 60 

def is_market_open(tz_name, open_h, open_m, close_h, close_m):
    try:
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        if now.weekday() >= 5:
            return False
        start = now.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
        end = now.replace(hour=close_h, minute=close_m, second=0, microsecond=0)
        return start <= now <= end
    except Exception:
        return False

def fetch_quotes_batch(ticker_list):
    results = []
    if not ticker_list:
        return results
    try:
        tickers_str = " ".join(ticker_list)
        data = yf.Tickers(tickers_str)
        for t in ticker_list:
            try:
                info = data.tickers[t].fast_info
                price = info.last_price
                prev_close = info.previous_close
                if price is not None and prev_close is not None and prev_close != 0:
                    diff = price - prev_close
                    pct = (diff / prev_close) * 100.0
                    clean_name = t.split('.')[0]
                    results.append({
                        "name": clean_name,
                        "fullName": clean_name,
                        "price": round(float(price), 2),
                        "diff": round(float(diff), 2),
                        "pct": round(float(pct), 2)
                    })
            except Exception:
                continue
    except Exception:
        pass
    return results

def get_fresh_data():
    tz_nl = pytz.timezone('Europe/Amsterdam')
    now_nl = datetime.now(tz_nl)
    timestamp_str = now_nl.strftime('%H:%M:%S')

    aex_open = is_market_open('Europe/Amsterdam', 9, 0, 17, 35)
    nasdaq_open = is_market_open('America/New_York', 15, 30, 22, 0)

    aex_data = fetch_quotes_batch(TICKERS_AEX)
    amx_data = fetch_quotes_batch(TICKERS_AMX)
    nasdaq_data = fetch_quotes_batch(TICKERS_NASDAQ)

    return {
        "timestamp": timestamp_str,
        "aex_open": aex_open,
        "nasdaq_open": nasdaq_open,
        "aex": aex_data,
        "amx": amx_data,
        "nasdaq": nasdaq_data
    }

@app.route('/markets')
def markets():
    global CACHE_DATA, LAST_FETCH_TIME
    now_ts = time.time()

    # Gebruik de cache als deze minder dan 60 seconden oud is
    if CACHE_DATA and (now_ts - LAST_FETCH_TIME < CACHE_DURATION_SEC):
        return jsonify(CACHE_DATA)

    # Anders halen we verse data op en slaan we deze op in de cache
    CACHE_DATA = get_fresh_data()
    LAST_FETCH_TIME = now_ts

    return jsonify(CACHE_DATA)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
