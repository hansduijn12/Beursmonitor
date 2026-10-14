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

# NASDAQ 100 - Top 50 grootste tech- en groeibedrijven
NASDAQ_TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "GOOG", "TSLA", "AVGO", "COST",
    "PEP", "CSCO", "TMUS", "ADBE", "AMD", "NFLX", "INTC", "TXN", "QCOM", "AMGN",
    "HON", "INTU", "AMAT", "BKNG", "SBUX", "ISRG", "GILD", "MDLZ", "LRCX", "ADI",
    "REGN", "VRTX", "ADP", "PANW", "MU", "SNPS", "CDNS", "CSX", "PYPL", "KLAC",
    "ASML", "ORLY", "MAR", "CTAS", "CHTR", "PCAR", "DXCM", "ABNB", "KDP", "NXPI"
]

# Buffers & Timestamps
CACHE_DATA = {
    "timestamp": "--:--:--",
    "aex_open": False,
    "nasdaq_open": False,
    "aex": [],
    "amx": [],
    "nasdaq": []
}

LAST_EU_FETCH = None
LAST_US_FETCH = None
LAST_OFFLINE_CHECK = None  # Houdt de tijd bij van de laatste offline-poging

def has_internet_connection():
    """Controleert of de laptop/server een actieve internetverbinding heeft"""
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
        holidays_eu = [(1, 1), (5, 1), (12, 25), (12, 26)]
        if (now.month, now.day) in holidays_eu: return False
        t = now.hour + now.minute / 60.0
        return 9.0 <= t < 17.5

    elif market_type == "US":
        tz = pytz.timezone('America/New_York')
        now = datetime.now(tz)
        if now.weekday() >= 5: return False
        holidays_us = [(1, 1), (6, 19), (7, 4), (12, 25)]
        if (now.month, now.day) in holidays_us: return False
        t = now.hour + now.minute / 60.0
        return 9.5 <= t < 16.0 # 15:30 - 22:00 NL tijd

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
                        
                        # --- HIER ZITTEN DE NIEUWE BEREKENINGEN ---
                        diff = price - prev_close                      # Verschil in EUR/USD
                        pct = ((price - prev_close) / prev_close) * 100.0  # Percentage
                        
                        clean_name = t.split('.')[0]
                        data_list.append({
                            "name": clean_name,
                            "price": round(price, 2),
                            "diff": round(diff, 2),   # <-- VOOR DE ESP32
                            "pct": round(pct, 2)
                        })
                except Exception:
                    continue
    except Exception as e:
        print(f"Fout bij ophalen: {e}")
    return data_list

def update_markets_dynamically():
    global CACHE_DATA, LAST_EU_FETCH, LAST_US_FETCH, LAST_OFFLINE_CHECK
    
    now = datetime.now()

    # 1. Controleer op internetverbinding
    if not has_internet_connection():
        if LAST_OFFLINE_CHECK is None or (now - LAST_OFFLINE_CHECK) >= timedelta(hours=1):
            print(f"[{now.strftime('%H:%M:%S')}] WAARSCHUWING: Geen internetverbinding. Volgende controle over 1 uur.")
            LAST_OFFLINE_CHECK = now
        return

    LAST_OFFLINE_CHECK = None

    eu_is_open = check_market_open("EU")
    us_is_open = check_market_open("US")

    eu_interval = timedelta(seconds=15) if eu_is_open else timedelta(hours=1)
    us_interval = timedelta(seconds=15) if us_is_open else timedelta(hours=1)

    # 2. Europese markten (AEX & AMX)
    if LAST_EU_FETCH is None or (now - LAST_EU_FETCH) >= eu_interval:
        status_text = "LIVE (15s)" if eu_is_open else "RUST (1 uur)"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Ophalen AEX/AMX... [{status_text}]")
        aex_new = fetch_group_data(AEX_TICKERS)
        amx_new = fetch_group_data(AMX_TICKERS)
        if aex_new: CACHE_DATA["aex"] = aex_new
        if amx_new: CACHE_DATA["amx"] = amx_new
        LAST_EU_FETCH = now

    # 3. NASDAQ 100 Top 50
    if LAST_US_FETCH is None or (now - LAST_US_FETCH) >= us_interval:
        status_text = "LIVE (15s)" if us_is_open else "RUST (1 uur)"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Ophalen NASDAQ 100... [{status_text}]")
        nasdaq_new = fetch_group_data(NASDAQ_TICKERS)
        if nasdaq_new: CACHE_DATA["nasdaq"] = nasdaq_new
        LAST_US_FETCH = now

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
