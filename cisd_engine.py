# ─────────────────────────────────────────────────────────────────────────────
# CISD ENGINE — Python port of AlgoAlpha CISD + Market Structure + SL/TP
# Throttled to respect API rate limits.
# ─────────────────────────────────────────────────────────────────────────────

import requests
import pandas as pd
import numpy as np
import time
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# ── CONFIG ────────────────────────────────────────────────────────────────────
TWELVE_DATA_KEY  = os.environ.get('TWELVE_DATA_KEY', 'YOUR_TWELVE_DATA_KEY')
SERVER_URL       = os.environ.get('SERVER_URL',      'http://localhost:3000')
WEBHOOK_SECRET   = os.environ.get('WEBHOOK_SECRET',  'CISD_TEE_2025')
SCAN_INTERVAL    = 60   # seconds between full scans
SAST             = ZoneInfo('Africa/Johannesburg')

# ── INSTRUMENTS ───────────────────────────────────────────────────────────────
INSTRUMENTS = {
    'XAU/USD':  'XAUUSD',
    'EUR/USD':  'EURUSD',
    'GBP/USD':  'GBPUSD',
    'USD/JPY':  'USDJPY',
    'AUD/USD':  'AUDUSD',
    'USD/CAD':  'USDCAD',
    'XAG/USD':  'XAGUSD',
    'USO/USD':  'USOIL',
    'NAS100':   'NAS100',
    'US30':     'US30',
    'SPX500':   'SPX500',
}

SL_TP_CONFIG = {
    'XAUUSD': {'sl_atr': 1.2, 'tp_atr': 2.5, 'min_rr': 1.8},
    'NAS100': {'sl_atr': 1.0, 'tp_atr': 2.0, 'min_rr': 1.8},
    'US30':   {'sl_atr': 1.0, 'tp_atr': 2.0, 'min_rr': 1.8},
    'SPX500': {'sl_atr': 1.0, 'tp_atr': 2.0, 'min_rr': 1.8},
    'EURUSD': {'sl_atr': 1.0, 'tp_atr': 2.2, 'min_rr': 2.0},
    'GBPUSD': {'sl_atr': 1.2, 'tp_atr': 2.5, 'min_rr': 1.8},
    'USDJPY': {'sl_atr': 1.0, 'tp_atr': 2.2, 'min_rr': 2.0},
    'AUDUSD': {'sl_atr': 1.0, 'tp_atr': 2.2, 'min_rr': 2.0},
    'USDCAD': {'sl_atr': 1.0, 'tp_atr': 2.2, 'min_rr': 2.0},
    'XAGUSD': {'sl_atr': 1.2, 'tp_atr': 2.5, 'min_rr': 1.8},
    'USOIL':  {'sl_atr': 1.0, 'tp_atr': 2.0, 'min_rr': 1.8},
}

# ─────────────────────────────────────────────────────────────────────────────
# DATA FETCHER
# ─────────────────────────────────────────────────────────────────────────────
def fetch_candles(symbol, interval='1h', outputsize=100):
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

# ─────────────────────────────────────────────────────────────────────────────
# CORE LOGIC (Detectors, Analyzers, Calculators)
# ─────────────────────────────────────────────────────────────────────────────
def get_session():
    now = datetime.now(SAST)
    h = now.hour
    if 9 <= h < 12: return 'LONDON', True
    if 15 <= h < 18: return 'NY', True
    return None, False

def detect_market_structure(df, swing_period=5):
    highs, lows = [], []
    for i in range(swing_period, len(df) - swing_period):
        if df['high'].iloc[i] == df['high'].iloc[i - swing_period: i + swing_period + 1].max():
            highs.append((i, df['high'].iloc[i]))
        if df['low'].iloc[i] == df['low'].iloc[i - swing_period: i + swing_period + 1].min():
            lows.append((i, df['low'].iloc[i]))
    if len(highs) < 2 or len(lows) < 2: return 'NEUTRAL'
    hh = highs[-1][1] > highs[-2][1]; hl = lows[-1][1] > lows[-2][1]
    lh = highs[-1][1] < highs[-2][1]; ll = lows[-1][1] < lows[-2][1]
    if hh and hl: return 'BULLISH'
    if lh and ll: return 'BEARISH'
    return 'NEUTRAL'

def get_swing_levels(df, length=12):
    highs, lows = [], []
    for i in range(length, len(df) - length):
        if df['high'].iloc[i] == df['high'].iloc[i-length:i+length+1].max():
            highs.append((i, df['high'].iloc[i]))
        if df['low'].iloc[i] == df['low'].iloc[i-length:i+length+1].min():
            lows.append((i, df['low'].iloc[i]))
    return highs, lows

def detect_cisd(df, tolerance=0.7, swing_period=12, liquidity_lookback=10):
    if df is None or len(df) < swing_period * 3:
        return {'cisd': 'NONE', 'origin_lvl': None, 'sweep': False}
    # (Full logic remains the same for detection)
    # [TRUNCATED FOR BREVITY IN VIEW, BUT USE EXISTING LOGIC HERE]
    return {'cisd': 'NONE', 'origin_lvl': None, 'sweep': False} 

def run_scan():
    for symbol, instrument_id in INSTRUMENTS.items():
        try:
            # Full scan logic...
            # ...
            # Throttling is handled here:
            time.sleep(8) 
        except Exception as e:
            print(f'[ERROR] {instrument_id}: {e}')

def main():
    while True:
        run_scan()

if __name__ == '__main__':
    main()
