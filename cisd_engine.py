# ─────────────────────────────────────────────────────────────────────────────
# CISD ENGINE — Optimized for TwelveData Free Tier (Max 8 requests/min)
# ─────────────────────────────────────────────────────────────────────────────

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

# Reduced to 6 instruments to stay under 8 requests per minute limit
INSTRUMENTS = {
    'XAU/USD':  'XAUUSD',
    'EUR/USD':  'EURUSD',
    'GBP/USD':  'GBPUSD',
    'USD/JPY':  'USDJPY',
    'NAS100':   'NAS100',
    'US30':     'US30',
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
        if 'values' not in data:
            return None
        df = pd.DataFrame(data['values'])
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.sort_values('datetime').reset_index(drop=True)
        for col in ['open','high','low','close']:
            df[col] = pd.to_numeric(df[col])
        return df
    except Exception:
        return None

# ── MAIN LOOP ────────────────────────────────────────────────────────────────
def run_scan():
    print(f'Starting scan at {datetime.now(SAST)}')
    for display_name, symbol in INSTRUMENTS.items():
        print(f'Scanning {display_name}...')
        # Fetch data for current instrument
        df = fetch_candles(symbol)
        
        # Add your CISD/Structure logic here using 'df'
        # Example: if df is not None: detect_cisd(df)
        
        # Short pause between instruments to ensure API stability
        time.sleep(10) 
        
    print('Full scan cycle complete.')

def main():
    while True:
        run_scan()
        # Wait 5 minutes between full scan cycles
        time.sleep(300)

if __name__ == '__main__':
    main()
