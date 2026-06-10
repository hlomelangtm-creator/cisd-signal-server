# ─────────────────────────────────────────────────────────────────────────────
# CISD ENGINE — Python port of AlgoAlpha CISD + Market Structure + SL/TP
# Runs every minute, fetches OHLC candles, detects signals, posts to server
# ─────────────────────────────────────────────────────────────────────────────

import requests
import pandas as pd
import numpy as np
import time
import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# ── CONFIG ────────────────────────────────────────────────────────────────────
TWELVE_DATA_KEY  = os.environ.get('TWELVE_DATA_KEY', 'YOUR_TWELVE_DATA_KEY')
SERVER_URL       = os.environ.get('SERVER_URL',      'http://localhost:3000')
WEBHOOK_SECRET   = os.environ.get('WEBHOOK_SECRET',  'CISD_TEE_2025')
SCAN_INTERVAL    = 60   # seconds between full scans
SAST             = ZoneInfo('Africa/Johannesburg')

# ── INSTRUMENTS ───────────────────────────────────────────────────────────────
# TwelveData symbol : dashboard instrument ID
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

# ATR multipliers for SL/TP per instrument type
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
# 1. DATA FETCHER
# ─────────────────────────────────────────────────────────────────────────────
def fetch_candles(symbol, interval='1h', outputsize=100):
    """Fetch OHLC candles from TwelveData."""
    url = 'https://api.twelvedata.com/time_series'
    params = {
        'symbol':     symbol,
        'interval':   interval,
        'outputsize': outputsize,
        'apikey':     TWELVE_DATA_KEY,
        'format':     'JSON',
        'timezone':   'Africa/Johannesburg',
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if 'values' not in data:
            print(f'[FETCH ERROR] {symbol}: {data.get("message","unknown")}')
            return None
        df = pd.DataFrame(data['values'])
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.sort_values('datetime').reset_index(drop=True)
        for col in ['open','high','low','close']:
            df[col] = pd.to_numeric(df[col])
        return df
    except Exception as e:
        print(f'[FETCH ERROR] {symbol}: {e}')
        return None

# ─────────────────────────────────────────────────────────────────────────────
# 2. SESSION DETECTOR
# ─────────────────────────────────────────────────────────────────────────────
def get_session():
    now  = datetime.now(SAST)
    h    = now.hour
    if 9  <= h < 12: return 'LONDON', True
    if 15 <= h < 18: return 'NY',     True
    return None, False

# ─────────────────────────────────────────────────────────────────────────────
# 3. MARKET STRUCTURE ANALYSER (H4)
# Detects HH/HL (bullish) or LH/LL (bearish) using pivot points
# ─────────────────────────────────────────────────────────────────────────────
def detect_market_structure(df, swing_period=5):
    """
    Returns: 'BULLISH', 'BEARISH', or 'NEUTRAL'
    Logic:
      - Find last 4 pivot highs and lows
      - HH + HL = BULLISH (higher highs AND higher lows)
      - LH + LL = BEARISH (lower highs AND lower lows)
      - Mixed    = NEUTRAL
    """
    highs, lows = [], []

    for i in range(swing_period, len(df) - swing_period):
        window_h = df['high'].iloc[i - swing_period: i + swing_period + 1]
        window_l = df['low'].iloc[i - swing_period: i + swing_period + 1]
        if df['high'].iloc[i] == window_h.max():
            highs.append((i, df['high'].iloc[i]))
        if df['low'].iloc[i] == window_l.min():
            lows.append((i, df['low'].iloc[i]))

    if len(highs) < 2 or len(lows) < 2:
        return 'NEUTRAL'

    # Last 2 pivot highs and lows
    last_highs = [h[1] for h in highs[-2:]]
    last_lows  = [l[1] for l in lows[-2:]]

    hh = last_highs[-1] > last_highs[-2]  # Higher High
    hl = last_lows[-1]  > last_lows[-2]   # Higher Low
    lh = last_highs[-1] < last_highs[-2]  # Lower High
    ll = last_lows[-1]  < last_lows[-2]   # Lower Low

    if hh and hl:  return 'BULLISH'
    if lh and ll:  return 'BEARISH'
    if lh or ll:   return 'BEARISH'  # partial bearish evidence
    if hh or hl:   return 'BULLISH'  # partial bullish evidence
    return 'NEUTRAL'

# ─────────────────────────────────────────────────────────────────────────────
# 4. SWING HIGH/LOW DETECTOR
# Direct port of ta.pivothigh / ta.pivotlow from Pine Script
# ─────────────────────────────────────────────────────────────────────────────
def get_swing_levels(df, length=12):
    """Returns lists of (index, price) for swing highs and lows."""
    swing_highs, swing_lows = [], []
    for i in range(length, len(df) - length):
        if df['high'].iloc[i] == df['high'].iloc[i-length:i+length+1].max():
            swing_highs.append((i, df['high'].iloc[i]))
        if df['low'].iloc[i] == df['low'].iloc[i-length:i+length+1].min():
            swing_lows.append((i, df['low'].iloc[i]))
    return swing_highs, swing_lows

# ─────────────────────────────────────────────────────────────────────────────
# 5. CISD DETECTOR
# Port of AlgoAlpha Pine Script bear_potential / bull_potential logic
# ─────────────────────────────────────────────────────────────────────────────
def detect_cisd(df, tolerance=0.7, swing_period=12, liquidity_lookback=10):
    """
    Returns dict:
      cisd       : 'BEAR', 'BULL', or 'NONE'
      origin_lvl : price level where CISD originated
      sweep      : True if liquidity was swept before CISD
      bsl        : True if buy side liquidity was swept
      ssl        : True if sell side liquidity was swept
    """
    if df is None or len(df) < swing_period * 3:
        return {'cisd': 'NONE', 'origin_lvl': None, 'sweep': False, 'bsl': False, 'ssl': False}

    closes = df['close'].values
    opens  = df['open'].values
    highs  = df['high'].values
    lows   = df['low'].values
    n      = len(df)

    swing_highs, swing_lows = get_swing_levels(df, swing_period)

    # Track last wicked levels (liquidity sweeps)
    last_wicked_high = None
    last_wicked_high_bar = -999
    last_wicked_low  = None
    last_wicked_low_bar  = -999

    for sh_idx, sh_price in swing_highs:
        for i in range(sh_idx + 1, n):
            if highs[i] >= sh_price:
                last_wicked_high     = sh_price
                last_wicked_high_bar = i
                break

    for sl_idx, sl_price in swing_lows:
        for i in range(sl_idx + 1, n):
            if lows[i] <= sl_price:
                last_wicked_low     = sl_price
                last_wicked_low_bar = i
                break

    # ── BEAR CISD detection ──
    # Look for: bearish engulfing candle (close[1]>open[1] and close<open)
    # followed by price closing below the open of that candle
    bear_potentials = []
    for i in range(1, n):
        if closes[i-1] > opens[i-1] and closes[i] < opens[i]:
            bear_potentials.append((i, opens[i]))

    cisd_bear = False
    bear_origin = None
    for bp_bar, bp_open in reversed(bear_potentials):
        # Check if any subsequent bar closed below this level
        for j in range(bp_bar + 1, n):
            if closes[j] < bp_open:
                # Tolerance check — same as Pine Script
                highest = max(closes[bp_bar:j+1])
                init    = bp_bar + 1
                top     = bp_open
                while init < j:
                    if closes[init] < opens[init]:
                        top = opens[init]
                        init += 1
                    else:
                        break
                if top != bp_open and abs(top - bp_open) > 0.0001:
                    ratio = (highest - bp_open) / (top - bp_open)
                    if ratio > tolerance:
                        cisd_bear  = True
                        bear_origin = bp_open
                        break
        if cisd_bear:
            break

    # ── BULL CISD detection ──
    bull_potentials = []
    for i in range(1, n):
        if closes[i-1] < opens[i-1] and closes[i] > opens[i]:
            bull_potentials.append((i, opens[i]))

    cisd_bull   = False
    bull_origin = None
    for bp_bar, bp_open in reversed(bull_potentials):
        for j in range(bp_bar + 1, n):
            if closes[j] > bp_open:
                lowest = min(closes[bp_bar:j+1])
                init   = bp_bar + 1
                bottom = bp_open
                while init < j:
                    if closes[init] > opens[init]:
                        bottom = opens[init]
                        init  += 1
                    else:
                        break
                if bottom != bp_open and abs(bp_open - bottom) > 0.0001:
                    ratio = (bp_open - lowest) / (bp_open - bottom)
                    if ratio > tolerance:
                        cisd_bull   = True
                        bull_origin = bp_open
                        break
        if cisd_bull:
            break

    # ── Determine signal and sweep ──
    bars_since_high = (n - 1) - last_wicked_high_bar if last_wicked_high else 999
    bars_since_low  = (n - 1) - last_wicked_low_bar  if last_wicked_low  else 999

    if cisd_bear:
        bsl    = bars_since_high <= liquidity_lookback and last_wicked_high is not None
        return {'cisd': 'BEAR', 'origin_lvl': bear_origin, 'sweep': bsl, 'bsl': bsl, 'ssl': False}

    if cisd_bull:
        ssl    = bars_since_low <= liquidity_lookback and last_wicked_low is not None
        return {'cisd': 'BULL', 'origin_lvl': bull_origin, 'sweep': ssl, 'bsl': False, 'ssl': ssl}

    return {'cisd': 'NONE', 'origin_lvl': None, 'sweep': False, 'bsl': False, 'ssl': False}

# ─────────────────────────────────────────────────────────────────────────────
# 6. ATR CALCULATOR
# ─────────────────────────────────────────────────────────────────────────────
def calculate_atr(df, period=14):
    """Average True Range — used for SL/TP placement."""
    df = df.copy()
    df['prev_close'] = df['close'].shift(1)
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['prev_close']),
            abs(df['low']  - df['prev_close'])
        )
    )
    return df['tr'].rolling(period).mean().iloc[-1]

# ─────────────────────────────────────────────────────────────────────────────
# 7. SL/TP CALCULATOR
# ─────────────────────────────────────────────────────────────────────────────
def calculate_sl_tp(instrument_id, signal, current_price, df_h1, df_h4):
    """
    SL: placed beyond the most recent swing high/low + ATR buffer
    TP: next structural level + ATR extension
    Returns: { sl, tp, rr, sl_pips, tp_pips }
    """
    cfg  = SL_TP_CONFIG.get(instrument_id, {'sl_atr': 1.2, 'tp_atr': 2.5, 'min_rr': 1.8})
    atr  = calculate_atr(df_h1)

    swing_highs_h4, swing_lows_h4 = get_swing_levels(df_h4, 5)

    if signal == 'BEAR':
        # SL above most recent swing high on H4
        if swing_highs_h4:
            recent_high = max([p for _, p in swing_highs_h4[-3:]])
            sl = recent_high + (atr * 0.5)
        else:
            sl = current_price + (atr * cfg['sl_atr'])

        # TP at next swing low below current price
        lows_below = [(i, p) for i, p in swing_lows_h4 if p < current_price]
        if lows_below:
            tp = min([p for _, p in lows_below[-3:]]) - (atr * 0.3)
        else:
            tp = current_price - (atr * cfg['tp_atr'])

    else:  # BULL
        # SL below most recent swing low on H4
        if swing_lows_h4:
            recent_low = min([p for _, p in swing_lows_h4[-3:]])
            sl = recent_low - (atr * 0.5)
        else:
            sl = current_price - (atr * cfg['sl_atr'])

        # TP at next swing high above current price
        highs_above = [(i, p) for i, p in swing_highs_h4 if p > current_price]
        if highs_above:
            tp = max([p for _, p in highs_above[-3:]]) + (atr * 0.3)
        else:
            tp = current_price + (atr * cfg['tp_atr'])

    sl_dist = abs(current_price - sl)
    tp_dist = abs(current_price - tp)
    rr      = round(tp_dist / sl_dist, 2) if sl_dist > 0 else 0

    # Enforce minimum RR — extend TP if needed
    if rr < cfg['min_rr']:
        if signal == 'BEAR':
            tp = current_price - (sl_dist * cfg['min_rr'])
        else:
            tp = current_price + (sl_dist * cfg['min_rr'])
        tp_dist = abs(current_price - tp)
        rr = round(tp_dist / sl_dist, 2)

    return {
        'sl':      round(sl, 5),
        'tp':      round(tp, 5),
        'rr':      rr,
        'sl_dist': round(sl_dist, 5),
        'tp_dist': round(tp_dist, 5),
        'atr':     round(atr, 5),
    }

# ─────────────────────────────────────────────────────────────────────────────
# 8. ANTI-MANIPULATION FILTER
# Flags signals that are likely stop hunts / liquidity grabs
# ─────────────────────────────────────────────────────────────────────────────
def anti_manipulation_check(df, signal, instrument_id):
    """
    Returns: { is_manipulation: bool, reason: str, confidence: int 0-100 }

    Checks:
    1. Isolation check — signal candle surrounded by opposite colour
    2. Daily range check — >60% of avg range already consumed
    3. Spike check — signal candle has abnormally large wick vs body
    4. Structure conflict — signal goes against H4 market structure
    """
    if df is None or len(df) < 10:
        return {'is_manipulation': False, 'reason': 'Insufficient data', 'confidence': 0}

    reasons      = []
    manipulation = False
    score        = 0  # higher = more likely manipulation

    closes = df['close'].values
    opens  = df['open'].values
    highs  = df['high'].values
    lows   = df['low'].values
    n      = len(df)

    # ── Check 1: Candle Isolation ──
    # Signal candle is opposite colour to surrounding candles
    if n >= 5:
        last_5_bull = sum(1 for i in range(n-5, n-1) if closes[i] > opens[i])
        last_5_bear = sum(1 for i in range(n-5, n-1) if closes[i] < opens[i])
        if signal == 'BULL' and last_5_bear >= 3:
            score  += 30
            reasons.append('Signal isolated — 3+ bearish candles surround it')
        if signal == 'BEAR' and last_5_bull >= 3:
            score  += 30
            reasons.append('Signal isolated — 3+ bullish candles surround it')

    # ── Check 2: Daily Range Consumption ──
    # If price has moved >65% of avg daily range before NY open
    daily_ranges = []
    for i in range(max(0, n-20), n):
        daily_ranges.append(highs[i] - lows[i])
    avg_range    = np.mean(daily_ranges) if daily_ranges else 0
    today_range  = highs[-1] - lows[-1]
    if avg_range > 0:
        range_pct = today_range / avg_range
        if range_pct > 0.65:
            score  += 35
            reasons.append(f'Daily range {round(range_pct*100)}% consumed — move may be exhausted')

    # ── Check 3: Wick/Body Ratio ──
    # Abnormally large wick on signal candle = rejection / manipulation
    last_body  = abs(closes[-1] - opens[-1])
    last_range = highs[-1] - lows[-1]
    if last_range > 0:
        body_ratio = last_body / last_range
        if body_ratio < 0.25:
            score  += 25
            reasons.append(f'Signal candle is {round(body_ratio*100)}% body — mostly wick (potential fake)')

    # ── Check 4: Momentum Conflict ──
    # Last 3 candles closing opposite to signal direction
    if n >= 4:
        last_3 = [(closes[i] - opens[i]) for i in range(n-4, n-1)]
        if signal == 'BULL' and all(c < 0 for c in last_3):
            score  += 20
            reasons.append('Last 3 candles bearish — momentum conflicts with buy signal')
        if signal == 'BEAR' and all(c > 0 for c in last_3):
            score  += 20
            reasons.append('Last 3 candles bullish — momentum conflicts with sell signal')

    is_manip = score >= 50
    reason   = ' | '.join(reasons) if reasons else 'No manipulation detected'

    return {
        'is_manipulation': is_manip,
        'reason':          reason,
        'confidence':      min(score, 100),
        'checks':          len(reasons),
    }

# ─────────────────────────────────────────────────────────────────────────────
# 9. H1 CISD CONFIRMATION CHECK
# Checks if H1 has confirmed the same direction as H4
# ─────────────────────────────────────────────────────────────────────────────
def check_h1_confirmation(df_h1, signal):
    """Returns True if H1 CISD aligns with signal direction."""
    result = detect_cisd(df_h1)
    return result['cisd'] == signal

# ─────────────────────────────────────────────────────────────────────────────
# 10. FULL INSTRUMENT SCAN
# ─────────────────────────────────────────────────────────────────────────────
def scan_instrument(symbol, instrument_id):
    """Full scan of one instrument across all timeframes."""
    print(f'[SCAN] {instrument_id}...')

    # Fetch candles for H4, H1, M15
    df_h4 = fetch_candles(symbol, '4h',  100)
    df_h1 = fetch_candles(symbol, '1h',  100)
    df_m15= fetch_candles(symbol, '15min', 100)

    if df_h4 is None or df_h1 is None:
        print(f'[SKIP] {instrument_id} — data unavailable')
        return None

    current_price = float(df_h1['close'].iloc[-1])
    session, in_kz = get_session()

    # ── Step 1: H4 Market Structure ──
    h4_structure = detect_market_structure(df_h4, swing_period=5)

    # ── Step 2: CISD on H4 (primary bias) ──
    cisd_h4 = detect_cisd(df_h4, tolerance=0.7, swing_period=12)

    # ── Step 3: CISD on H1 (confirmation) ──
    cisd_h1 = detect_cisd(df_h1, tolerance=0.7, swing_period=12)

    # ── Step 4: CISD on M15 (entry trigger) ──
    cisd_m15 = detect_cisd(df_m15, tolerance=0.7, swing_period=6) if df_m15 is not None else {'cisd': 'NONE'}

    # ── Step 5: Determine final signal direction ──
    # Rule: H4 structure MUST agree with CISD signal
    # If H4 is BEARISH → only BEAR signals pass
    # If H4 is BULLISH → only BULL signals pass
    raw_signal = cisd_h4['cisd']

    if h4_structure == 'BEARISH' and raw_signal == 'BULL':
        final_signal = 'NONE'   # Counter-trend — blocked
        blocked_reason = 'H4 structure BEARISH — bullish CISD blocked (trap risk)'
    elif h4_structure == 'BULLISH' and raw_signal == 'BEAR':
        final_signal = 'NONE'   # Counter-trend — blocked
        blocked_reason = 'H4 structure BULLISH — bearish CISD blocked (trap risk)'
    else:
        final_signal   = raw_signal
        blocked_reason = None

    # ── Step 6: Anti-manipulation check ──
    manip = anti_manipulation_check(df_h1, final_signal, instrument_id) if final_signal != 'NONE' else \
            {'is_manipulation': False, 'reason': 'No signal', 'confidence': 0}

    # Block manipulated signals
    if manip['is_manipulation'] and final_signal != 'NONE':
        blocked_reason = f'MANIPULATION DETECTED ({manip["confidence"]}%): {manip["reason"]}'
        final_signal   = 'NONE'

    # ── Step 7: H1 confirmation ──
    h1_confirmed = cisd_h1['cisd'] == final_signal if final_signal != 'NONE' else False

    # ── Step 8: SL/TP calculation ──
    sl_tp = None
    if final_signal != 'NONE':
        sl_tp = calculate_sl_tp(instrument_id, final_signal, current_price, df_h1, df_h4)

    # ── Step 9: Signal quality grade ──
    quality = grade_signal(
        final_signal, h4_structure, cisd_h4['sweep'],
        in_kz, h1_confirmed, manip['is_manipulation']
    )

    result = {
        'instrument':     instrument_id,
        'symbol':         symbol,
        'price':          round(current_price, 5),
        'session':        session,
        'killzone':       in_kz,

        # Market structure
        'h4_structure':   h4_structure,
        'h4_hh_hl':       h4_structure == 'BULLISH',
        'h4_lh_ll':       h4_structure == 'BEARISH',

        # CISD signals
        'cisd_h4':        cisd_h4['cisd'],
        'cisd_h1':        cisd_h1['cisd'],
        'cisd_m15':       cisd_m15['cisd'],
        'final_signal':   final_signal,

        # Checklist
        'sweep':          cisd_h4['sweep'],
        'bsl':            cisd_h4['bsl'],
        'ssl':            cisd_h4['ssl'],
        'h1cisd':         h1_confirmed,

        # Quality
        'quality':        quality,
        'blocked_reason': blocked_reason,

        # Anti-manipulation
        'manipulation':        manip['is_manipulation'],
        'manip_confidence':    manip['confidence'],
        'manip_reason':        manip['reason'],

        # SL/TP
        'sl':   sl_tp['sl']      if sl_tp else None,
        'tp':   sl_tp['tp']      if sl_tp else None,
        'rr':   sl_tp['rr']      if sl_tp else None,
        'atr':  sl_tp['atr']     if sl_tp else None,

        'timestamp': datetime.now(SAST).isoformat(),
    }

    return result

def grade_signal(signal, h4_structure, sweep, killzone, h1_confirmed, is_manip):
    """Grade signal A+/A/B/C/TRAP/NONE based on confluence."""
    if signal == 'NONE': return 'NONE'
    if is_manip:         return 'TRAP'

    aligned = (signal == 'BEAR' and h4_structure == 'BEARISH') or \
              (signal == 'BULL' and h4_structure == 'BULLISH')

    if aligned and sweep and killzone and h1_confirmed: return 'A+'
    if aligned and sweep and killzone:                  return 'A'
    if aligned and killzone:                            return 'B'
    if aligned:                                         return 'C'
    return 'TRAP'

# ─────────────────────────────────────────────────────────────────────────────
# 11. POST SIGNAL TO SERVER
# ─────────────────────────────────────────────────────────────────────────────
def post_signal(result):
    """Send signal result to the Node.js server."""
    payload = {
        'secret':     WEBHOOK_SECRET,
        'instrument': result['instrument'],
        'signal':     result['final_signal'],
        'sweep':      result['sweep'],
        'h1cisd':     result['h1cisd'],
        'bsl':        result['bsl'],
        'price':      result['price'],
        'h4_structure': result['h4_structure'],
        'quality':    result['quality'],
        'sl':         result['sl'],
        'tp':         result['tp'],
        'rr':         result['rr'],
        'manipulation': result['manipulation'],
        'manip_confidence': result['manip_confidence'],
        'manip_reason': result['manip_reason'],
        'blocked_reason': result['blocked_reason'],
        'killzone':   result['killzone'],
        'session':    result['session'],
    }
    try:
        r = requests.post(
            f'{SERVER_URL}/webhook',
            json=payload,
            timeout=5
        )
        print(f'[POST] {result["instrument"]} → {result["final_signal"]} | Q:{result["quality"]} | {r.status_code}')
    except Exception as e:
        print(f'[POST ERROR] {result["instrument"]}: {e}')

# ─────────────────────────────────────────────────────────────────────────────
# 12. MAIN SCAN LOOP
# ─────────────────────────────────────────────────────────────────────────────
def run_scan():
    """Scan all instruments and post results."""
    print(f'\n{"="*60}')
    print(f'CISD ENGINE SCAN — {datetime.now(SAST).strftime("%Y-%m-%d %H:%M:%S SAST")}')
    session, in_kz = get_session()
    print(f'Session: {session or "DEAD ZONE"} | Killzone: {in_kz}')
    print(f'{"="*60}')

    for symbol, instrument_id in INSTRUMENTS.items():
        try:
            result = scan_instrument(symbol, instrument_id)
            if result:
                post_signal(result)
                # Log high quality signals
                if result['quality'] in ['A+', 'A']:
                    print(f'  ★ HIGH QUALITY: {instrument_id} {result["final_signal"]} '
                          f'Q:{result["quality"]} SL:{result["sl"]} TP:{result["tp"]} RR:{result["rr"]}')
            time.sleep(1.5)  # rate limit between API calls
        except Exception as e:
            print(f'[ERROR] {instrument_id}: {e}')

    print(f'Scan complete.\n')

def main():
    print('CISD Engine starting...')
    print(f'Server: {SERVER_URL}')
    print(f'API Key: {"SET" if TWELVE_DATA_KEY != "YOUR_TWELVE_DATA_KEY" else "NOT SET — add TWELVE_DATA_KEY env var"}')

    while True:
        try:
            run_scan()
        except Exception as e:
            print(f'[FATAL] Scan loop error: {e}')
        print(f'Next scan in {SCAN_INTERVAL} seconds...')
        time.sleep(SCAN_INTERVAL)

if __name__ == '__main__':
    main()
