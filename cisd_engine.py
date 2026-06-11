# ─────────────────────────────────────────────────────────────────────────────
# CISD ENGINE — Optimized & Functional
# ─────────────────────────────────────────────────────────────────────────────

import requests
import pandas as pd
import time
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# ── CONFIG ────────────────────────────────────────────────────────────────────
TWELVE_DATA_KEY  = os.environ.get('TWELVE_DATA_KEY')
SERVER_URL       = os.environ.get('SERVER_URL', 'http://localhost:3000')
WEBHOOK_SECRET   = os.environ.get('WEBHOOK_SECRET', 'CISD_TEE_2025')
SAST             = ZoneInfo('Africa/Johannesburg')

INSTRUMENTS = {
    'XAU/USD': 'XAUUSD', 'EUR/USD': 'EURUSD', 'GBP/USD': 'GBPUSD',
    'USD/JPY': 'USDJPY', 'NAS100': 'NAS100', 'US30': 'US30',
}

# ── DATA FETCHING ─────────────────────────────────────────────────────────────
def fetch_candles(symbol, interval='1h', outputsize=30):
    url = 'https://api.twelvedata.com/time_series'
    params = {
        'symbol': symbol, 'interval': interval, 'outputsize': outputsize,
        'apikey': TWELVE_DATA_KEY, 'format': 'JSON', 'timezone': 'Africa/Johannesburg',
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if 'values' in data:
            return data['values']
        return None
    except Exception as e:
        print(f"Fetch Error: {e}")
        return None

# ── SEND DATA TO DASHBOARD ───────────────────────────────────────────────────
def post_signal(instrument, data):
    payload = {
        'secret': WEBHOOK_SECRET,
        'instrument': instrument,
        'data': data
    }
    try:
        requests.post(f'{SERVER_URL}/webhook', json=payload, timeout=5)
    except Exception as e:
        print(f"Post Error: {e}")

# ── MAIN LOOP ────────────────────────────────────────────────────────────────
def run_scan():
    print(f'Starting scan at {datetime.now(SAST)}')
    for display_name, symbol in INSTRUMENTS.items():
        print(f'Scanning {display_name}...')
        data = fetch_candles(symbol)
        
        if data:
            post_signal(display_name, data)
        
        time.sleep(10) # Maintain 6 requests/min (under 8/min limit)
        
    print('Full scan cycle complete.')

def main():
    while True:
        run_scan()
        time.sleep(300) # 5-minute wait

if __name__ == '__main__':
    main()
