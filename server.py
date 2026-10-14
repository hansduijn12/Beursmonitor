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

# PROMINENTE WERELDBEURZEN & HUN TIJDZONES / BEURSTIJDEN
GLOBAL_MARKETS = [
    {"ticker": "^N225",   "name": "Nikkei 225 (Japan)",     "tz": "Asia/Tokyo",        "open": 9.0,  "close": 15.0},
    {"ticker": "^HSI",    "name": "Hang Seng (Hong Kong)",  "tz": "Asia/Hong_Kong",    "open": 9.5,  "close": 16.0},
    {"ticker": "^AXJO",   "name": "ASX 200 (Australie)",   "tz": "Australia/Sydney",  "open": 10.0, "close": 16.0},
    {"ticker": "^NSEI",   "name": "Nifty 50 (India)",       "tz": "Asia/Kolkata",      "open": 9.25, "close": 15.5},
    {"ticker": "^FTSE",   "name": "FTSE 100 (Londen)",      "tz": "Europe/London",     "open": 8.0,  "close": 16.5},
    {"ticker": "^GDAXI",  "name": "DAX 40 (Duitsland)",     "tz": "Europe/Berlin",     "open": 9.0,  "close": 17.5},
    {"ticker": "^GSPTSE", "name": "TSX Comp. (Canada)",     "tz": "America/Toronto",   "open": 9.5,  "close": 16.0}
]

CACHE_DATA = {
    "timestamp": "--:--:--",
    "aex_open": False,
    "nasdaq_open": False,
    "aex": [],
    "amx": [],
    "nasdaq": [],
    "active_global": []  # Bevat alleen prominente beurzen die NU open zijn
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

    return False

def is_global_market_open(m_info):
    try:
        tz = pytz.timezone(m_info["tz"])
        now = datetime.now(tz)
        if now.weekday() >= 5: return False
        t = now.hour + now.minute / 60.0
        return m_info["open"] <= t < m_info["close"]
    except Exception:
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

    eu_interval = timedelta(seconds=15) if eu_is_open else timedelta(hours=1)
    us_interval = timedelta(seconds=15) if us_is_open else timedelta(hours=1)

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

    # Haal data op van alle actieve wereldbeurzen
    if LAST_GLOBAL_FETCH is None or (now - LAST_GLOBAL_FETCH) >= timedelta(seconds=30):
        active_tickers = [m["ticker"] for m in GLOBAL_MARKETS if is_global_market_open(m)]
        
        if active_tickers:
            glob_data = fetch_group_data(active_tickers)
            # Voeg mooie namen toe
            for item in glob_data:
                for m in GLOBAL_MARKETS:
                    if m["ticker"].replace("^", "") == item["name"]:
                        item["fullName"] = m["name"]
            CACHE_DATA["active_global"] = glob_data
        else:
            CACHE_DATA["active_global"] = []
        LAST_GLOBAL_FETCH = now

    tz = pytz.timezone('Europe/Amsterdam')
    CACHE_DATA["timestamp"] = datetime.now(tz).strftime("%H:%M:%S")
    CACHE_DATA["aex_open"] = eu_is_open
    CACHE_DATA["nasdaq_open"] = us_is_open

@app.route('/markets', methods=['GET'])
def get_markets():
    update_markets_dynamically()
    return jsonify(CACHE_DATA)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
