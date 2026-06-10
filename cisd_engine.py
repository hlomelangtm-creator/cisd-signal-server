import requests
import pandas as pd
import time
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# ── CONFIG ────────────────────────────────────────────────────────────────────
TWELVE_DATA_KEY  = os.environ.get('TWELVE_DATA_KEY')
SERVER_URL       = os.environ.get('SERVER_URL', 'http://localhost:3000')
SAST             = ZoneInfo('Africa/Johannesburg')

INSTRUMENTS = {
    'XAU/USD': 'XAUUSD', 'EUR/USD': 'EURUSD', 'GBP/USD': 'GBPUSD',
    'USD/JPY': 'USDJPY', 'AUD/USD': 'AUDUSD', 'USD/CAD': 'USDCAD',
    'XAG/USD': 'XAGUSD', 'USO/USD': 'USOIL',  'NAS100':  'NAS100',
    'US30':    'US30',   'SPX500':  'SPX500',
}

# ── STAGGERED DATA FETCHING ───────────────────────────────────────────────────
def fetch_candles(symbol, interval='1h'):
    # A hard delay here prevents the loop from slamming the API
    time.sleep(8) 
    url = 'https://api.twelvedata.com/time_series'
    params = {
        'symbol': symbol, 'interval': interval, 'outputsize': 30,
        'apikey': TWELVE_DATA_KEY, 'format': 'JSON'
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        return response.json()
    except Exception:
        return None

def run_scan():
    print(f'Starting throttled scan at {datetime.now(SAST)}')
    for display_name, symbol in INSTRUMENTS.items():
        print(f'Scanning {display_name}...')
        data = fetch_candles(symbol, '1h')
        # Logic to send 'data' to your server goes here
        
    print('Scan complete. Sleeping for 5 minutes...')

def main():
    while True:
        run_scan()
        time.sleep(300) # Wait 5 minutes between full scans

if __name__ == '__main__':
    main()
