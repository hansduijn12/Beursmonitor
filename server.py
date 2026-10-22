import os
import time
import pytz
import yfinance as yf
from datetime import datetime, timedelta
from flask import Flask, jsonify

app = Flask(__name__)

TICKERS_AEX = [
    "ADYEN.AS", "ASM.AS", "ASML.AS", "BESI.AS", "INGA.AS", "PRX.AS", "RELX.AS", "SHELL.AS", "UNA.AS", "ABN.AS",
    "AKZA.AS", "HEIA.AS", "KPN.AS", "NN.AS", "AD.AS", "AALB.AS", "ASRNL.AS", "IMCD.AS", "RAND.AS", "UMG.AS", "WKL.AS"
]

TICKERS_AMX = [
    "ALLFG.AS", "APAM.AS", "ARCAD.AS", "BAMNB.AS", "CORB.AS", "ECMPA.AS", "ENX.PA", "FLOW.AS", "FUR.AS", "INPST.AS",
    "JDEP.AS", "LIGHT.AS", "NEDAP.AS", "OCI.AS", "PHARM.AS", "PNL.AS", "SBMO.AS", "SLIGR.AS", "VPK.AS"
]

TICKERS_NASDAQ = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST", "ASML",
    "PEP", "CSCO", "TMUS", "AZN", "AMD", "NFLX", "INTC", "INTU", "QUALCOMM", "AMGN",
    "TXN", "HON", "AMAT", "BKNG", "SBUX", "VRTX", "MDLZ", "ADP", "ISRG", "GILD",
    "REGN", "ADI", "LRCX", "MU", "MELI", "PANW", "SNPS", "CDNS", "KLAC", "PYPL",
    "CRWD", "ABNB", "ORLY", "MAR", "CTAS", "CHTR", "CSX", "WDAY", "DXCM", "FTNT"
]

COMMODITIES = [
    {"name": "Goud", "ticker": "GC=F"},
    {"name": "Zilver", "ticker": "SI=F"},
    {"name": "Platina", "ticker": "PL=F"},
    {"name": "Palladium", "ticker": "PA=F"},
    {"name": "Brent Olie", "ticker": "BZ=F"},
    {"name": "WTI Olie", "ticker": "CL=F"},
    {"name": "Aardgas", "ticker": "NG=F"},
    {"name": "Koper", "ticker": "HG=F"},
    {"name": "Tarwe", "ticker": "ZW=F"},
    {"name": "Koffie", "ticker": "KC=F"}
]

GLOBAL_MARKETS = [
    {"country": "JAPAN", "name": "Nikkei 225", "ticker": "^N225"},
    {"country": "JAPAN", "name": "TOPIX Index", "ticker": "^TOPX"},
    {"country": "CHINA & HK", "name": "Hang Seng", "ticker": "^HSI"},
    {"country": "CHINA & HK", "name": "Shanghai Comp", "ticker": "000001.SS"},
    {"country": "AUSTRALIE", "name": "ASX 200", "ticker": "^AXJO"},
    {"country": "ZUID-KOREA", "name": "KOSPI Composite", "ticker": "^KS11"},
    {"country": "INDIA", "name": "BSE Sensex", "ticker": "^BSESN"},
    {"country": "INDIA", "name": "NSE Nifty 50", "ticker": "^NSEI"}
]

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

def is_market_visible(tz_name, open_h, open_m, close_h, close_m):
    try:
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        if now.weekday() >= 5:
            return False
        start = now.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
        close_time = now.replace(hour=close_h, minute=close_m, second=0, microsecond=0)
        hide_time = close_time + timedelta(hours=1)
        return start <= now <= hide_time
    except Exception:
        return True

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
                    clean_name = t.split('.')[0].replace('=F', '').replace('^', '')
                    
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

@app.route('/markets')
def markets():
    global CACHE_DATA, LAST_FETCH_TIME
    now_ts = time.time()

    if CACHE_DATA and (now_ts - LAST_FETCH_TIME < CACHE_DURATION_SEC):
        return jsonify(CACHE_DATA)

    tz_nl = pytz.timezone('Europe/Amsterdam')
    now_nl = datetime.now(tz_nl)
    timestamp_str = now_nl.strftime('%H:%M:%S')

    # AEX/AMX in Amsterdamse tijd (09:00 - 17:35)
    aex_open = is_market_open('Europe/Amsterdam', 9, 0, 17, 35)
    aex_visible = is_market_visible('Europe/Amsterdam', 9, 0, 17, 35)

    # NASDAQ in New Yorkse tijd (09:30 - 16:00 ET)
    nasdaq_open = is_market_open('America/New_York', 9, 30, 16, 0)
    nasdaq_visible = is_market_visible('America/New_York', 9, 30, 16, 0)

    aex_data = fetch_quotes_batch(TICKERS_AEX) if aex_visible else []
    amx_data = fetch_quotes_batch(TICKERS_AMX) if aex_visible else []
    nasdaq_data = fetch_quotes_batch(TICKERS_NASDAQ) if nasdaq_visible else []

    comm_tickers = [c["ticker"] for c in COMMODITIES]
    comm_quotes = fetch_quotes_batch(comm_tickers)
    commodities_data = []
    for c in COMMODITIES:
        for q in comm_quotes:
            if c["ticker"].startswith(q["name"]) or q["name"] in c["ticker"]:
                q["fullName"] = c["name"]
                commodities_data.append(q)
                break

    global_tickers = [m["ticker"] for m in GLOBAL_MARKETS]
    global_quotes = fetch_quotes_batch(global_tickers)
    active_globals = []
    for m in GLOBAL_MARKETS:
        for q in global_quotes:
            clean_q = q["name"].replace('^', '').split('.')[0]
            clean_m = m["ticker"].replace('^', '').split('.')[0]
            if clean_q == clean_m or m["ticker"] == q["name"]:
                q["fullName"] = m["name"]
                q["country"] = m["country"]
                active_globals.append(q)
                break

    CACHE_DATA = {
        "timestamp": timestamp_str,
        "aex_open": aex_open,
        "nasdaq_open": nasdaq_open,
        "aex": aex_data,
        "amx": amx_data,
        "nasdaq": nasdaq_data,
        "commodities": commodities_data,
        "active_global": active_globals
    }
    LAST_FETCH_TIME = now_ts

    return jsonify(CACHE_DATA)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
