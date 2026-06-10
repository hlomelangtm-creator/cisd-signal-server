import requests
import pandas as pd
import time
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# ── CONFIG ────────────────────────────────────────────────────────────────────
TWELVE_DATA_KEY  = os.environ.get('TWELVE_DATA_KEY', 'YOUR_TWELVE_DATA_KEY')
SERVER_URL       = os.environ.get('SERVER_URL',      'http://localhost:3000')
WEBHOOK_SECRET   = os.environ.get('WEBHOOK_SECRET',  'CISD_TEE_2025')
SAST             = ZoneInfo('Africa/Johannesburg')

INSTRUMENTS = {
    'XAU/USD': 'XAUUSD', 'EUR/USD': 'EURUSD', 'GBP/USD': 'GBPUSD',
    'USD/JPY': 'USDJPY', 'AUD/USD': 'AUDUSD', 'USD/CAD': 'USDCAD',
    'XAG/USD': 'XAGUSD', 'USO/USD': 'USOIL',  'NAS100':  'NAS100',
    'US30':    'US30',   'SPX500':  'SPX500',
}

# ── DATA FETCHING WITH STRICT THROTTLING ──
def fetch_candles(symbol, interval='1h'):
    # Standardizing to 1 request per call
    time.sleep(10) # 10-second wait per request ensures we stay well under 8/min
    url = 'https://api.twelvedata.com/time_series'
    params = {
        'symbol': symbol, 'interval': interval, 'outputsize': 30,
        'apikey': TWELVE_DATA_KEY, 'format': 'JSON'
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        return r.json()
    except Exception:
        return None

def run_scan():
    print(f'Starting throttled scan at {datetime.now(SAST)}')
    for display_name, symbol in INSTRUMENTS.items():
        print(f'Scanning {display_name}...')
        # Fetch data (the 10s sleep inside fetch_candles handles the rate limit)
        data = fetch_candles(symbol, '1h')
        
        # Add your logic here to process 'data' and send to your server
        # Example: if 'values' in data: send_to_server(data)
        
    print('Scan cycle complete.')

def main():
    while True:
        run_scan()
        # Wait a few minutes before starting the next full cycle
        time.sleep(300) 

if __name__ == '__main__':
    main()
