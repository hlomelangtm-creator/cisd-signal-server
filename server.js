// ─────────────────────────────────────────────────────────────────────────────
// CISD SIGNAL SERVER
// Receives TradingView webhooks → stores signal state → serves to dashboard
// Deploy on Render.com (free tier) — see README.md for full setup guide
// ─────────────────────────────────────────────────────────────────────────────

const express = require('express');
const cors    = require('cors');
const app     = express();

app.use(cors());
app.use(express.json());

// ── SECRET TOKEN ──────────────────────────────────────────────────────────────
// Set this as environment variable WEBHOOK_SECRET on Render
// TradingView will send this in every alert message for security
const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET || 'CISD_TEE_2025';

// ── SIGNAL STATE STORE ────────────────────────────────────────────────────────
// Holds the latest CISD state for every instrument
// Updated every time TradingView fires an alert
let signalState = {
  XAUUSD: { cisd: 'NONE', sweep: false, killzone: false, bsl: false, h1cisd: false, session: null, price: null, time: null },
  NAS100: { cisd: 'NONE', sweep: false, killzone: false, bsl: false, h1cisd: false, session: null, price: null, time: null },
  EURUSD: { cisd: 'NONE', sweep: false, killzone: false, bsl: false, h1cisd: false, session: null, price: null, time: null },
  GBPUSD: { cisd: 'NONE', sweep: false, killzone: false, bsl: false, h1cisd: false, session: null, price: null, time: null },
  USDJPY: { cisd: 'NONE', sweep: false, killzone: false, bsl: false, h1cisd: false, session: null, price: null, time: null },
  AUDUSD: { cisd: 'NONE', sweep: false, killzone: false, bsl: false, h1cisd: false, session: null, price: null, time: null },
  USDCAD: { cisd: 'NONE', sweep: false, killzone: false, bsl: false, h1cisd: false, session: null, price: null, time: null },
  XAGUSD: { cisd: 'NONE', sweep: false, killzone: false, bsl: false, h1cisd: false, session: null, price: null, time: null },
  USOIL:  { cisd: 'NONE', sweep: false, killzone: false, bsl: false, h1cisd: false, session: null, price: null, time: null },
  US30:   { cisd: 'NONE', sweep: false, killzone: false, bsl: false, h1cisd: false, session: null, price: null, time: null },
  SPX500: { cisd: 'NONE', sweep: false, killzone: false, bsl: false, h1cisd: false, session: null, price: null, time: null },
  UK100:  { cisd: 'NONE', sweep: false, killzone: false, bsl: false, h1cisd: false, session: null, price: null, time: null },
  XPTUSD: { cisd: 'NONE', sweep: false, killzone: false, bsl: false, h1cisd: false, session: null, price: null, time: null },
};

// ── SIGNAL LOG ────────────────────────────────────────────────────────────────
let signalLog = []; // last 50 alerts received

// ── SESSION HELPER ────────────────────────────────────────────────────────────
function getSession() {
  const now  = new Date();
  const sast = new Date(now.toLocaleString('en-US', { timeZone: 'Africa/Johannesburg' }));
  const h    = sast.getHours();
  if (h >= 9  && h < 12) return 'LONDON';
  if (h >= 15 && h < 18) return 'NY';
  return null;
}

function isKillzone() { return getSession() !== null; }

// ── PARSE TRADINGVIEW ALERT ───────────────────────────────────────────────────
// TradingView sends alert message as plain text or JSON string
// We support both formats — see README for exact message templates
function parseAlert(body) {
  // If TradingView sends raw JSON body
  if (typeof body === 'object' && body.instrument) return body;

  // If TradingView sends as { message: "..." } string
  const msg = body.message || body.text || body.alert || '';
  if (!msg) return null;

  try {
    // Try parsing as JSON string embedded in message
    const parsed = JSON.parse(msg);
    return parsed;
  } catch {
    // Parse structured plain text format:
    // "SECRET:CISD_TEE_2025 INSTRUMENT:XAUUSD SIGNAL:BEAR SWEEP:true H1:true"
    const get = (key) => {
      const m = msg.match(new RegExp(`${key}:([^\\s]+)`, 'i'));
      return m ? m[1] : null;
    };
    return {
      secret:     get('SECRET'),
      instrument: get('INSTRUMENT'),
      signal:     get('SIGNAL'),    // BEAR / BULL / NONE
      sweep:      get('SWEEP') === 'true',
      h1cisd:     get('H1') === 'true',
      bsl:        get('BSL') === 'true',
      price:      parseFloat(get('PRICE')) || null,
    };
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// ROUTES
// ─────────────────────────────────────────────────────────────────────────────

// ── HEALTH CHECK ──────────────────────────────────────────────────────────────
app.get('/', (req, res) => {
  res.json({
    status:    'CISD Signal Server Online',
    version:   '1.0.0',
    session:   getSession() || 'DEAD ZONE',
    killzone:  isKillzone(),
    timestamp: new Date().toISOString(),
    instruments: Object.keys(signalState).length
  });
});

// ── WEBHOOK ENDPOINT — receives TradingView alerts ────────────────────────────
// POST /webhook
// Body: { secret, instrument, signal, sweep, h1cisd, bsl, price }
app.post('/webhook', (req, res) => {
  const parsed = parseAlert(req.body);

  if (!parsed) {
    return res.status(400).json({ error: 'Could not parse alert body' });
  }

  // Security check
  if (parsed.secret !== WEBHOOK_SECRET) {
    console.warn(`[SECURITY] Bad secret from ${req.ip}`);
    return res.status(403).json({ error: 'Invalid secret' });
  }

  const inst = (parsed.instrument || '').toUpperCase().replace('/', '');
  const sig  = (parsed.signal     || 'NONE').toUpperCase();

  if (!signalState[inst]) {
    return res.status(400).json({ error: `Unknown instrument: ${inst}` });
  }

  const session  = getSession();
  const killzone = isKillzone();
  const now      = new Date().toISOString();

  // Update signal state — includes SL/TP and market structure from Python engine
  signalState[inst] = {
    cisd:         sig,
    sweep:        parsed.sweep   === true || parsed.sweep   === 'true',
    h1cisd:       parsed.h1cisd  === true || parsed.h1cisd  === 'true',
    bsl:          parsed.bsl     === true || parsed.bsl     === 'true',
    killzone:     killzone,
    session:      session,
    price:        parsed.price        || null,
    // Market structure
    h4_structure: parsed.h4_structure || null,
    h4_hh_hl:     parsed.h4_hh_hl    || false,
    h4_lh_ll:     parsed.h4_lh_ll    || false,
    // Signal quality
    quality:      parsed.quality      || null,
    blocked_reason: parsed.blocked_reason || null,
    // Anti-manipulation
    manipulation:      parsed.manipulation      || false,
    manip_confidence:  parsed.manip_confidence  || 0,
    manip_reason:      parsed.manip_reason      || null,
    // SL/TP
    sl:  parsed.sl  || null,
    tp:  parsed.tp  || null,
    rr:  parsed.rr  || null,
    atr: parsed.atr || null,
    time: now,
  };

  // Add to log
  signalLog.unshift({
    time:       now,
    instrument: inst,
    signal:     sig,
    session:    session,
    killzone:   killzone,
    price:      parsed.price,
  });
  if (signalLog.length > 50) signalLog.pop();

  console.log(`[SIGNAL] ${now} | ${inst} | ${sig} | KZ:${killzone} | ${session || 'DEAD'}`);

  res.json({ ok: true, instrument: inst, signal: sig, session, killzone });
});

// ── GET ALL SIGNALS — polled by dashboard every 10 seconds ───────────────────
// GET /signals
app.get('/signals', (req, res) => {
  res.json({
    signals:   signalState,
    log:       signalLog.slice(0, 20),
    session:   getSession() || null,
    killzone:  isKillzone(),
    timestamp: new Date().toISOString(),
  });
});

// ── GET SINGLE INSTRUMENT ─────────────────────────────────────────────────────
// GET /signals/XAUUSD
app.get('/signals/:instrument', (req, res) => {
  const inst = req.params.instrument.toUpperCase();
  if (!signalState[inst]) return res.status(404).json({ error: 'Not found' });
  res.json({ instrument: inst, ...signalState[inst] });
});

// ── MANUAL OVERRIDE — for testing without TradingView ────────────────────────
// POST /override  { secret, instrument, signal, sweep, h1cisd, bsl }
app.post('/override', (req, res) => {
  const { secret, instrument, signal, sweep, h1cisd, bsl } = req.body;
  if (secret !== WEBHOOK_SECRET) return res.status(403).json({ error: 'Invalid secret' });

  const inst = (instrument || '').toUpperCase();
  if (!signalState[inst]) return res.status(400).json({ error: 'Unknown instrument' });

  signalState[inst] = {
    ...signalState[inst],
    cisd:    (signal || 'NONE').toUpperCase(),
    sweep:   !!sweep,
    h1cisd:  !!h1cisd,
    bsl:     !!bsl,
    killzone: isKillzone(),
    session:  getSession(),
    time:    new Date().toISOString(),
  };

  res.json({ ok: true, updated: signalState[inst] });
});

// ── START ─────────────────────────────────────────────────────────────────────
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`CISD Signal Server running on port ${PORT}`);
  console.log(`Session: ${getSession() || 'DEAD ZONE'} | Killzone: ${isKillzone()}`);
});
