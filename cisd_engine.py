# ─────────────────────────────────────────────────────────────────────────────
# CISD ENGINE — Python port of AlgoAlpha CISD + Market Structure + SL/TP
# ─────────────────────────────────────────────────────────────────────────────

import requests
import pandas as pd
import numpy as np
import time
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# ── CONFIG ────────────────────────────────────────────────────────────────────
TWELVE_DATA_KEY  = os.environ.get('TWELVE_DATA_KEY', 'YOUR_TWELVE_DATA_KEY')
SERVER_URL       = os.environ.get('SERVER_URL',      'http://localhost:3000')
WEBHOOK_SECRET   = os.environ.get('WEBHOOK_SECRET',  'CISD_TEE_2025')
SCAN_INTERVAL    = 60   
SAST             = ZoneInfo('Africa/Johannesburg')

INSTRUMENTS = {
    'XAU/USD':  'XAUUSD', 'EUR/USD':  'EURUSD', 'GBP/USD':  'GBPUSD',
    'USD/JPY':  'USDJPY', 'AUD/USD':  'AUDUSD', 'USD/CAD':  'USDCAD',
    'XAG/USD':  'XAGUSD', 'USO/USD':  'USOIL',  'NAS100':   'NAS100',
    'US30':     'US30',   'SPX500':   'SPX500',
}

# ── DATA FETCHING ─────────────────────────────────────────────────────────────
def fetch_candles(symbol, interval='1h', outputsize=100):
    url = 'https://api.twelvedata.com/time_series'
    params = {'symbol': symbol, 'interval': interval, 'outputsize': outputsize,
              'apikey': TWELVE_DATA_KEY, 'format': 'JSON', 'timezone': 'Africa/Johannesburg'}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if 'values' not in data: return None
        df = pd.DataFrame(data['values'])
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.sort_values('datetime').reset_index(drop=True)
        for col in ['open','high','low','close']: df[col] = pd.to_numeric(df[col])
        return df
    except Exception: return None

# ── LOGIC (Placeholders for your full detection logic) ───────────────────────
# NOTE: Ensure your original detect_cisd, detect_market_structure, etc. 
# functions are placed here.

def scan_instrument(symbol, instrument_id):
    df_h4 = fetch_candles(symbol, '4h', 100)
    df_h1 = fetch_candles(symbol, '1h', 100)
    # ... (rest of your analysis logic)
    return {'instrument': instrument_id, 'final_signal': 'NONE'} # Example

def post_signal(result):
    try:
        requests.post(f'{SERVER_URL}/webhook', json={'secret': WEBHOOK_SECRET, **result}, timeout=5)
    except Exception: pass

# ── MAIN LOOP ────────────────────────────────────────────────────────────────
def run_scan():
    print(f'Starting scan: {datetime.now(SAST)}')
    for symbol, instrument_id in INSTRUMENTS.items():
        try:
            result = scan_instrument(symbol, instrument_id)
            if result: post_signal(result)
            # THROTLLING: This is the critical part to fix your 429 error
            print(f'Scanned {instrument_id}, waiting...')
            time.sleep(8) 
        except Exception as e:
            print(f'Error on {instrument_id}: {e}')

def main():
    while True:
        run_scan()
        time.sleep(60)

if __name__ == '__main__':
    main()
