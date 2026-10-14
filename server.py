from flask import Flask, jsonify
import yfinance as yf
from datetime import datetime, timedelta
import pytz
import socket

app = Flask(__name__)

# Tickers AEX & AMX (Euronext Amsterdam)
AEX_TICKERS = [
    "ADYEN.AS", "ASM.AS", "ASML.AS", "BESI.AS", "INGA.AS", "PRX.AS", "REN.AS", 
    "SHELL.AS", "UNA.AS", "ABN.AS", "AKZA.AS", "HEIA.AS", "KPN.AS", "NN.AS", 
    "AD.AS", "AALB.AS", "ASRNL.AS", "IMCD.AS", "RAND.AS", "UMG.AS", 
    "WKL.AS", "ARCAD.AS", "ENX.PA", "LIGHT.AS"
]

AMX_TICKERS = [
    "ALLFG.AS", "APAM.AS", "BAMNB.AS", "CRBN.AS", "ECMPA.AS", "FLOW.AS", 
    "FUR.AS", "INPST.AS", "JDEPY", "NEDAP.AS", "OCI.AS", 
    "PHARM.AS", "PNL.AS", "SBMO.AS", "SLIGR.AS", "VPK.AS"
]

# NASDAQ 100 - Top 50
NASDAQ_TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "GOOG", "TSLA", "AVGO", "COST",
    "PEP", "CSCO", "TMUS", "ADBE", "AMD", "NFLX", "INTC", "TXN", "QCOM", "AMGN",
    "HON", "INTU", "AMAT", "BKNG", "SBUX", "ISRG", "GILD", "MDLZ", "LRCX", "ADI",
    "REGN", "VRTX", "ADP", "PANW", "MU", "SNPS", "CDNS", "CSX", "PYPL", "KLAC",
    "ASML", "ORLY", "MAR", "CTAS", "CHTR", "PCAR", "DXCM", "ABNB", "KDP", "NXPI"
]

# NIEUW: Prominente globale beurzen (Japan, Hong Kong, Australië, India, etc.)
GLOBAL_TICKERS = [
    "^N225",   # Nikkei 225 (Japan / Tokio)
    "^HSI",    # Hang Seng Index (Hong Kong)
    "^AXJO",   # S&P/ASX 200 (Australië)
    "^NSEI",   # Nifty 50 (India)
    "^GSPTSE", # TSX Composite (Canada)
    "^FTSE",   # FTSE 100 (Londen, VK)
    "^GDAXI"   # DAX 40 (Duitsland)
]

CACHE_DATA = {
    "timestamp": "--:--:--",
    "aex_open": False,
    "nasdaq_open": False,
    "global_open": False,
    "aex": [],
    "amx": [],
    "nasdaq": [],
    "global": []
}

LAST_EU_FETCH = None
LAST_US_FETCH = None
LAST_GLOBAL_FETCH = None

def has_internet_connection():
    try:
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except Exception:
        return False

def check_market_open(market_type):
    if market_type == "EU":
        tz = pytz.timezone('Europe/Amsterdam')
        now = datetime.now(tz)
        if now.weekday() >= 5: return False
        t = now.hour + now.minute / 60.0
        return 9.0 <= t < 17.5

    elif market_type == "US":
        tz = pytz.timezone('America/New_York')
        now = datetime.now(tz)
        if now.weekday() >= 5: return False
        t = now.hour + now.minute / 60.0
        return 9.5 <= t < 16.0

    elif market_type == "ASIA":
        # Tokio / Japan (01:00 - 07:00 NL-tijd)
        tz = pytz.timezone('Asia/Tokyo')
        now = datetime.now(tz)
        if now.weekday() >= 5: return False
        t = now.hour + now.minute / 60.0
        return 9.0 <= t < 15.0  # Japanse beurstijden

    return False

def fetch_group_data(tickers):
    data_list = []
    try:
        df = yf.download(tickers, period="5d", interval="1d", progress=False)['Close']
        if not df.empty:
            for t in tickers:
                try:
                    series = df[t].dropna() if len(tickers) > 1 else df.dropna()
                    if len(series) >= 2:
                        price = float(series.iloc[-1])
                        prev_close = float(series.iloc[-2])
                        diff = price - prev_close
                        pct = ((price - prev_close) / prev_close) * 100.0
                        
                        clean_name = t.replace("^", "").split('.')[0]
                        data_list.append({
                            "name": clean_name,
                            "price": round(price, 2),
                            "diff": round(diff, 2),
                            "pct": round(pct, 2)
                        })
                except Exception:
                    continue
    except Exception as e:
        print(f"Fout bij ophalen: {e}")
    return data_list

def update_markets_dynamically():
    global CACHE_DATA, LAST_EU_FETCH, LAST_US_FETCH, LAST_GLOBAL_FETCH
    now = datetime.now()

    if not has_internet_connection():
        return

    eu_is_open = check_market_open("EU")
    us_is_open = check_market_open("US")
    global_is_open = check_market_open("ASIA")

    eu_interval = timedelta(seconds=15) if eu_is_open else timedelta(hours=1)
    us_interval = timedelta(seconds=15) if us_is_open else timedelta(hours=1)
    global_interval = timedelta(seconds=15) if global_is_open else timedelta(hours=1)

    if LAST_EU_FETCH is None or (now - LAST_EU_FETCH) >= eu_interval:
        aex_new = fetch_group_data(AEX_TICKERS)
        amx_new = fetch_group_data(AMX_TICKERS)
        if aex_new: CACHE_DATA["aex"] = aex_new
        if amx_new: CACHE_DATA["amx"] = amx_new
        LAST_EU_FETCH = now

    if LAST_US_FETCH is None or (now - LAST_US_FETCH) >= us_interval:
        nasdaq_new = fetch_group_data(NASDAQ_TICKERS)
        if nasdaq_new: CACHE_DATA["nasdaq"] = nasdaq_new
        LAST_US_FETCH = now

    # Haal globale/Aziatische beurzen op
    if LAST_GLOBAL_FETCH is None or (now - LAST_GLOBAL_FETCH) >= global_interval:
        global_new = fetch_group_data(GLOBAL_TICKERS)
        if global_new: CACHE_DATA["global"] = global_new
        LAST_GLOBAL_FETCH = now

    tz = pytz.timezone('Europe/Amsterdam')
    CACHE_DATA["timestamp"] = datetime.now(tz).strftime("%H:%M:%S")
    CACHE_DATA["aex_open"] = eu_is_open
    CACHE_DATA["nasdaq_open"] = us_is_open
    CACHE_DATA["global_open"] = global_is_open

@app.route('/markets', methods=['GET'])
def get_markets():
    update_markets_dynamically()
    return jsonify(CACHE_DATA)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
