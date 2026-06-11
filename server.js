# ─────────────────────────────────────────────────────────────────────────────
# CISD ENGINE v2 — Fixed, Rate-Limited, Full Signal Detection
# 6 instruments | TwelveData free tier safe | Posts signals to server
# ─────────────────────────────────────────────────────────────────────────────

import requests
import pandas as pd
import numpy as np
import time
import os
from datetime import datetime
from zoneinfo import ZoneInfo

TWELVE_DATA_KEY = os.environ.get('TWELVE_DATA_KEY', 'YOUR_TWELVE_DATA_KEY')
SERVER_URL      = os.environ.get('SERVER_URL',      'http://localhost:3000')
WEBHOOK_SECRET  = os.environ.get('WEBHOOK_SECRET',  'CISD_TEE_2025')
SAST            = ZoneInfo('Africa/Johannesburg')
SCAN_INTERVAL   = 300
API_DELAY       = 12

INSTRUMENTS = {
    'XAU/USD': 'XAUUSD',
    'EUR/USD': 'EURUSD',
    'GBP/USD': 'GBPUSD',
    'USD/JPY': 'USDJPY',
    'NAS100':  'NAS100',
    'US30':    'US30',
}

SL_TP_CONFIG = {
    'XAUUSD': {'sl_atr': 1.2, 'tp_atr': 2.5, 'min_rr': 1.8},
    'NAS100': {'sl_atr': 1.0, 'tp_atr': 2.0, 'min_rr': 1.8},
    'US30':   {'sl_atr': 1.0, 'tp_atr': 2.0, 'min_rr': 1.8},
    'EURUSD': {'sl_atr': 1.0, 'tp_atr': 2.2, 'min_rr': 2.0},
    'GBPUSD': {'sl_atr': 1.2, 'tp_atr': 2.5, 'min_rr': 1.8},
    'USDJPY': {'sl_atr': 1.0, 'tp_atr': 2.2, 'min_rr': 2.0},
}

def get_session():
    h = datetime.now(SAST).hour
    if 9  <= h < 12: return 'LONDON', True
    if 15 <= h < 18: return 'NY',     True
    return None, False

def fetch_candles(symbol, interval='4h', outputsize=60):
    url = 'https://api.twelvedata.com/time_series'
    params = {
        'symbol': symbol, 'interval': interval,
        'outputsize': outputsize, 'apikey': TWELVE_DATA_KEY,
        'format': 'JSON', 'timezone': 'Africa/Johannesburg',
    }
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=15)
            data = r.json()
            if 'values' not in data:
                print(f'  [API] {symbol}: {data.get("message", data.get("code", "error"))}')
                return None
            df = pd.DataFrame(data['values'])
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.sort_values('datetime').reset_index(drop=True)
            for col in ['open','high','low','close']:
                df[col] = pd.to_numeric(df[col])
            return df
        except Exception as e:
            print(f'  [FETCH] Attempt {attempt+1}: {e}')
            time.sleep(5)
    return None

def detect_structure(df, period=5):
    if df is None or len(df) < period * 4:
        return 'NEUTRAL'
    highs, lows = [], []
    for i in range(period, len(df) - period):
        if df['high'].iloc[i] == df['high'].iloc[i-period:i+period+1].max():
            highs.append(float(df['high'].iloc[i]))
        if df['low'].iloc[i] == df['low'].iloc[i-period:i+period+1].min():
            lows.append(float(df['low'].iloc[i]))
    if len(highs) < 2 or len(lows) < 2:
        return 'NEUTRAL'
    hh = highs[-1] > highs[-2]
    hl = lows[-1]  > lows[-2]
    lh = highs[-1] < highs[-2]
    ll = lows[-1]  < lows[-2]
    if hh and hl: return 'BULLISH'
    if lh and ll: return 'BEARISH'
    if lh or ll:  return 'BEARISH'
    if hh or hl:  return 'BULLISH'
    return 'NEUTRAL'

def get_swings(df, length=8):
    highs, lows = [], []
    for i in range(length, len(df) - length):
        if df['high'].iloc[i] == df['high'].iloc[i-length:i+length+1].max():
            highs.append((i, float(df['high'].iloc[i])))
        if df['low'].iloc[i] == df['low'].iloc[i-length:i+length+1].min():
            lows.append((i, float(df['low'].iloc[i])))
    return highs, lows

def detect_cisd(df, tolerance=0.7, swing_len=8, lookback=10):
    if df is None or len(df) < swing_len * 3:
        return {'cisd': 'NONE', 'sweep': False, 'bsl': False}
    c, o, h, l = df['close'].values, df['open'].values, df['high'].values, df['low'].values
    n = len(df)
    swing_highs, swing_lows = get_swings(df, swing_len)
    last_wicked_high_bar = -999
    last_wicked_low_bar  = -999
    for sh_idx, sh_price in swing_highs:
        for i in range(sh_idx + 1, n):
            if h[i] >= sh_price:
                last_wicked_high_bar = i
                break
    for sl_idx, sl_price in swing_lows:
        for i in range(sl_idx + 1, n):
            if l[i] <= sl_price:
                last_wicked_low_bar = i
                break
    bars_since_high = (n - 1) - last_wicked_high_bar
    bars_since_low  = (n - 1) - last_wicked_low_bar
    # Bear
    for i in range(n-1, 0, -1):
        if c[i-1] > o[i-1] and c[i] < o[i]:
            bp_bar, bp_open = i, o[i]
            for j in range(bp_bar + 1, n):
                if c[j] < bp_open:
                    highest = max(c[bp_bar:j+1])
                    init, top = bp_bar+1, bp_open
                    while init < j:
                        if c[init] < o[init]: top = o[init]; init += 1
                        else: break
                    denom = top - bp_open
                    if abs(denom) > 0.0001 and (highest - bp_open) / denom > tolerance:
                        bsl = bars_since_high <= lookback and last_wicked_high_bar > 0
                        return {'cisd': 'BEAR', 'sweep': bsl, 'bsl': bsl}
                    break
            break
    # Bull
    for i in range(n-1, 0, -1):
        if c[i-1] < o[i-1] and c[i] > o[i]:
            bp_bar, bp_open = i, o[i]
            for j in range(bp_bar + 1, n):
                if c[j] > bp_open:
                    lowest = min(c[bp_bar:j+1])
                    init, bottom = bp_bar+1, bp_open
                    while init < j:
                        if c[init] > o[init]: bottom = o[init]; init += 1
                        else: break
                    denom = bp_open - bottom
                    if abs(denom) > 0.0001 and (bp_open - lowest) / denom > tolerance:
                        ssl = bars_since_low <= lookback and last_wicked_low_bar > 0
                        return {'cisd': 'BULL', 'sweep': ssl, 'bsl': False}
                    break
            break
    return {'cisd': 'NONE', 'sweep': False, 'bsl': False}

def get_atr(df, period=14):
    df = df.copy()
    df['pc'] = df['close'].shift(1)
    df['tr'] = np.maximum(df['high']-df['low'],
               np.maximum(abs(df['high']-df['pc']), abs(df['low']-df['pc'])))
    val = df['tr'].rolling(period).mean().iloc[-1]
    return float(val) if not np.isnan(val) else float(df['tr'].mean())

def calc_sl_tp(inst_id, signal, price, df):
    cfg = SL_TP_CONFIG.get(inst_id, {'sl_atr': 1.2, 'tp_atr': 2.5, 'min_rr': 1.8})
    atr = get_atr(df)
    swing_highs, swing_lows = get_swings(df, 5)
    if signal == 'BEAR':
        sl = (max(p for _,p in swing_highs[-3:]) + atr*0.5) if swing_highs else price + atr*cfg['sl_atr']
        lb = [p for _,p in swing_lows if p < price]
        tp = (min(lb) - atr*0.3) if lb else price - atr*cfg['tp_atr']
    else:
        sl = (min(p for _,p in swing_lows[-3:]) - atr*0.5) if swing_lows else price - atr*cfg['sl_atr']
        ha = [p for _,p in swing_highs if p > price]
        tp = (max(ha) + atr*0.3) if ha else price + atr*cfg['tp_atr']
    sl_d = abs(price - sl)
    tp_d = abs(price - tp)
    rr   = round(tp_d / sl_d, 2) if sl_d > 0 else 0
    if rr < cfg['min_rr']:
        tp   = (price - sl_d*cfg['min_rr']) if signal == 'BEAR' else (price + sl_d*cfg['min_rr'])
        rr   = round(abs(price-tp)/sl_d, 2)
    return {'sl': round(sl,5), 'tp': round(tp,5), 'rr': rr, 'atr': round(atr,5)}

def anti_manip(df, signal):
    if df is None or len(df) < 5 or signal == 'NONE':
        return {'is_manipulation': False, 'reason': 'Clean', 'confidence': 0}
    c,o,h,l = df['close'].values,df['open'].values,df['high'].values,df['low'].values
    n = len(df)
    score, reasons = 0, []
    last4 = [c[i]-o[i] for i in range(n-5,n-1)]
    if signal == 'BULL' and sum(1 for x in last4 if x < 0) >= 3:
        score += 30; reasons.append('Isolated in bearish candles')
    if signal == 'BEAR' and sum(1 for x in last4 if x > 0) >= 3:
        score += 30; reasons.append('Isolated in bullish candles')
    ranges  = [h[i]-l[i] for i in range(max(0,n-20),n)]
    avg_rng = np.mean(ranges) if ranges else 1
    if avg_rng > 0 and (h[-1]-l[-1])/avg_rng > 0.65:
        score += 35; reasons.append(f'Daily range {round((h[-1]-l[-1])/avg_rng*100)}% consumed')
    body = abs(c[-1]-o[-1]); rng = h[-1]-l[-1]
    if rng > 0 and body/rng < 0.25:
        score += 25; reasons.append('Signal candle mostly wick')
    return {'is_manipulation': score>=50, 'reason': ' | '.join(reasons) if reasons else 'Clean', 'confidence': min(score,100)}

def grade(signal, structure, sweep, killzone):
    if signal == 'NONE': return 'NONE'
    aligned = (signal=='BEAR' and structure=='BEARISH') or (signal=='BULL' and structure=='BULLISH')
    if not aligned:           return 'TRAP'
    if sweep and killzone:    return 'A+'
    if killzone:              return 'A'
    return 'B'

def post_signal(payload):
    try:
        r = requests.post(f'{SERVER_URL}/webhook', json=payload, timeout=8)
        status = '✓' if r.status_code == 200 else f'✗ {r.status_code}'
        print(f'  [{status}] {payload["instrument"]} → {payload["signal"]} | Q:{payload.get("quality","?")} | SL:{payload.get("sl")} TP:{payload.get("tp")} RR:{payload.get("rr")}')
    except Exception as e:
        print(f'  [✗] Post failed: {e}')

def scan_one(symbol, inst_id):
    print(f'  {inst_id}...', end=' ', flush=True)
    df = fetch_candles(symbol, '4h', 60)
    if df is None:
        print('NO DATA')
        return
    price          = float(df['close'].iloc[-1])
    session, in_kz = get_session()
    structure      = detect_structure(df)
    cisd           = detect_cisd(df)
    raw_sig        = cisd['cisd']
    blocked        = None

    if structure == 'BEARISH' and raw_sig == 'BULL':
        blocked = 'H4 LH/LL — bull blocked'; raw_sig = 'NONE'
    elif structure == 'BULLISH' and raw_sig == 'BEAR':
        blocked = 'H4 HH/HL — bear blocked'; raw_sig = 'NONE'

    manip = anti_manip(df, raw_sig)
    if manip['is_manipulation'] and raw_sig != 'NONE':
        blocked = f'MANIP {manip["confidence"]}%: {manip["reason"]}'; raw_sig = 'NONE'

    sl_tp   = calc_sl_tp(inst_id, raw_sig, price, df) if raw_sig != 'NONE' else {'sl':None,'tp':None,'rr':None,'atr':None}
    quality = grade(raw_sig, structure, cisd['sweep'], in_kz)

    post_signal({
        'secret': WEBHOOK_SECRET, 'instrument': inst_id,
        'signal': raw_sig, 'sweep': cisd['sweep'],
        'h1cisd': False, 'bsl': cisd['bsl'], 'price': price,
        'h4_structure': structure, 'quality': quality,
        'sl': sl_tp['sl'], 'tp': sl_tp['tp'],
        'rr': sl_tp['rr'], 'atr': sl_tp['atr'],
        'manipulation': manip['is_manipulation'],
        'manip_confidence': manip['confidence'],
        'manip_reason': manip['reason'],
        'blocked_reason': blocked,
        'killzone': in_kz, 'session': session,
    })
    time.sleep(API_DELAY)

def main():
    print('CISD Engine v2')
    print(f'Server:      {SERVER_URL}')
    print(f'API Key:     {"SET ✓" if TWELVE_DATA_KEY != "YOUR_TWELVE_DATA_KEY" else "NOT SET ✗"}')
    print(f'Instruments: {list(INSTRUMENTS.values())}')
    print(f'Scan every:  {SCAN_INTERVAL//60} minutes\n')
    while True:
        try:
            now = datetime.now(SAST).strftime('%H:%M:%S SAST')
            session, in_kz = get_session()
            print(f'\n{"="*50}')
            print(f'SCAN {now} | {session or "DEAD ZONE"} | KZ:{in_kz}')
            print(f'{"="*50}')
            for symbol, inst_id in INSTRUMENTS.items():
                try:
                    scan_one(symbol, inst_id)
                except Exception as e:
                    print(f'  [ERROR] {inst_id}: {e}')
            print(f'Done. Next scan in {SCAN_INTERVAL//60} min.')
        except Exception as e:
            print(f'[FATAL] {e}')
        time.sleep(SCAN_INTERVAL)

if __name__ == '__main__':
    main()
