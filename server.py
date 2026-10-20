import os
import time
import threading
import pytz
import yfinance as yf
from datetime import datetime
from flask import Flask, jsonify

app = Flask(__name__)

# Beperkte, snelle lijst per markt om geheugen/timeout te voorkomen
TICKERS_AEX = ["ADYEN.AS", "ASM.AS", "ASML.AS", "BESI.AS", "INGA.AS", "PRX.AS", "RELX.AS", "SHELL.AS", "UNA.AS", "ABN.AS"]
TICKERS_AMX = ["ALLFG.AS", "APAM.AS", "ARCAD.AS", "BAMNB.AS", "CORB.AS", "FLOW.AS", "FUR.AS", "INPST.AS", "JDEP.AS", "LIGHT.AS"]
TICKERS_NASDAQ = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST", "PEP"]

CACHE_DATA = {
    "timestamp": "--:--:--",
    "aex_open": True,
    "nasdaq_open": True,
    "aex": [],
    "amx": [],
    "nasdaq": []
}

def fetch_quotes_safe(ticker_list):
    results = []
    if not ticker_list:
        return results
    try:
        # Download alles in 1 snelle batch
        data = yf.download(tickers=ticker_list, period="1d", interval="1m", progress=False)
        for t in ticker_list:
            try:
                # Probeer de meest recente prijs en sluitkoers op te halen
                price = float(data['Close'][t].dropna().iloc[-1])
                prev_close = float(data['Close'][t].dropna().iloc[-2]) if len(data['Close'][t].dropna()) > 1 else price
                diff = price - prev_close
                pct = (diff / prev_close) * 100.0 if prev_close != 0 else 0.0
                
                clean_name = t.split('.')[0]
                results.append({
                    "name": clean_name,
                    "fullName": clean_name,
                    "price": round(price, 2),
                    "diff": round(diff, 2),
                    "pct": round(pct, 2)
                })
            except Exception:
                continue
    except Exception as e:
        print(f"Fout bij ophalen {ticker_list}: {e}")
    return results

def update_data_loop():
    global CACHE_DATA
    while True:
        try:
            tz_nl = pytz.timezone('Europe/Amsterdam')
            now_nl = datetime.now(tz_nl)
            timestamp_str = now_nl.strftime('%H:%M:%S')

            aex_data = fetch_quotes_safe(TICKERS_AEX)
            amx_data = fetch_quotes_safe(TICKERS_AMX)
            nasdaq_data = fetch_quotes_safe(TICKERS_NASDAQ)

            CACHE_DATA = {
                "timestamp": timestamp_str,
                "aex_open": True,
                "nasdaq_open": True,
                "aex": aex_data,
                "amx": amx_data,
                "nasdaq": nasdaq_data
            }
            print(f"[{timestamp_str}] Data succesvol ververst in achtergrond!")
        except Exception as e:
            print(f"Fout in achtergrond-loop: {e}")
        
        # Wacht 60 seconden voor de volgende verversing
        time.sleep(60)

# Start de achtergrond-thread zodra de app opstart
threading.Thread(target=update_data_loop, daemon=True).start()

@app.route('/markets')
def markets():
    # Geeft DIRECT de gecashte data terug (0ms wachttijd voor ESP32!)
    return jsonify(CACHE_DATA)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
