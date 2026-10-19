import os
import pytz
import yfinance as yf
from datetime import datetime
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
    "PEP", "CSCO", "TMUS", "AZN", "AMD", "NFLX", "INTC", "INTU", "QUALCOMM", "AMGN"
]

# De 10 belangrijkste grondstoffen
COMMODITIES = [
    {"name": "Goud", "ticker": "GC=F"},
    {"name": "Zilver", "ticker": "SI=F"},
    {"name": "Brent Olie", "ticker": "BZ=F"},
    {"name": "WTI Olie", "ticker": "CL=F"},
    {"name": "Aardgas", "ticker": "NG=F"},
    {"name": "Koper", "ticker": "HG=F"},
    {"name": "Platina", "ticker": "PL=F"},
    {"name": "Tarwe", "ticker": "ZW=F"},
    {"name": "Koffie", "ticker": "KC=F"},
    {"name": "Mais", "ticker": "ZC=F"}
]

# Belangrijkste Wereldbeurzen
GLOBAL_MARKETS = [
    {"name": "Nikkei 225", "ticker": "^N225"},
    {"name": "Hang Seng", "ticker": "^HSI"},
    {"name": "Shanghai Comp", "ticker": "000001.SS"},
    {"name": "ASX 200", "ticker": "^AXJO"},
    {"name": "KOSPI", "ticker": "^KS11"},
    {"name": "Sensex", "ticker": "^BSESN"},
    {"name": "FTSE 100", "ticker": "^FTSE"},
    {"name": "DAX 40", "ticker": "^GDAXI"}
]

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

def fetch_quotes(ticker_list):
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
                    clean_name = t.split('.')[0].replace('=F', '')
                    results.append({
                        "name": clean_name,
                        "price": round(price, 2),
                        "diff": round(diff, 2),
                        "pct": round(pct, 2)
                    })
            except Exception:
                continue
    except Exception:
        pass
    return results

@app.route('/markets')
def markets():
    tz_nl = pytz.timezone('Europe/Amsterdam')
    now_nl = datetime.now(tz_nl)
    timestamp_str = now_nl.strftime('%H:%M:%S')

    # Bepaal openingstijden voor de header-indicator
    aex_open = is_market_open('Europe/Amsterdam', 9, 0, 17, 35)
    nasdaq_open = is_market_open('America/New_York', 15, 30, 22, 0)

    # Ophalen van alle datafeeds (blijft 24/7 actief met laatste/actuele prijzen)
    aex_data = fetch_quotes(TICKERS_AEX)
    amx_data = fetch_quotes(TICKERS_AMX)
    nasdaq_data = fetch_quotes(TICKERS_NASDAQ)

    # Grondstoffen
    comm_tickers = [c["ticker"] for c in COMMODITIES]
    comm_quotes = fetch_quotes(comm_tickers)
    commodities_data = []
    for c in COMMODITIES:
        for q in comm_quotes:
            if c["ticker"].startswith(q["name"]):
                q["fullName"] = c["name"]
                commodities_data.append(q)
                break

    # Wereldbeurzen
    global_tickers = [m["ticker"] for m in GLOBAL_MARKETS]
    global_quotes = fetch_quotes(global_tickers)
    active_globals = []
    for m in GLOBAL_MARKETS:
        for q in global_quotes:
            if q["name"] == m["ticker"].replace('^', '').split('.')[0]:
                q["fullName"] = m["name"]
                active_globals.append(q)
                break

    return jsonify({
        "timestamp": timestamp_str,
        "aex_open": aex_open,
        "nasdaq_open": nasdaq_open,
        "aex": aex_data,
        "amx": amx_data,
        "nasdaq": nasdaq_data,
        "commodities": commodities_data,
        "active_global": active_globals
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
