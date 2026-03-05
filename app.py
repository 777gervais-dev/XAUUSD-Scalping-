# ============================================================
#   XAUUSD SCALPING PRO — Streamlit Dashboard v3
#   ✅ Tendance stabilisée (confirmation + verrou + votes stricts)
#   ✅ Prix en temps réel
#   ✅ BUY/SELL + Indicateurs complets
# ============================================================

import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="XAUUSD Scalping Pro",
    page_icon="🥇",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
body, .stApp { background-color: #05050f; color: #e0e0ff; }
.stMetric label { color: #888 !important; font-size: 11px !important; }
.stMetric [data-testid="metric-container"] {
    background: #0d0d1a; border-radius: 8px;
    padding: 10px; border: 1px solid #1a1a30;
}
.buy-box  { background: rgba(0,255,136,0.08); border: 2px solid #00ff88; border-radius: 10px; padding: 16px; text-align: center; }
.sell-box { background: rgba(255,68,68,0.08);  border: 2px solid #ff4444; border-radius: 10px; padding: 16px; text-align: center; }
.neut-box { background: rgba(255,204,0,0.08);  border: 2px solid #ffcc00; border-radius: 10px; padding: 16px; text-align: center; }
.sig-title { font-size: 28px; font-weight: 900; letter-spacing: 2px; }
.sig-force { font-size: 13px; margin-top: 4px; }
.stable-badge { display:inline-block; background:#1a1a30; border-radius:20px; padding:3px 14px; font-size:11px; margin-top:6px; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# SESSION STATE
# ──────────────────────────────────────────────
def init_state():
    defaults = {
        "hist"           : [],
        "hist15"         : [],
        "votes"          : [],
        "tick15"         : 0,
        "confirmed_dir"  : "NEUTRE",
        "confirmed_force": "─",
        "confirm_count"  : 0,
        "lock_dir"       : "NEUTRE",
        "lock_time"      : 0,
        "lock_duration"  : 60,
        "confirm_needed" : 5,
        "vote_threshold" : 0.80,
        "levels": {
            "ENTRY_HIGH": 5161.0, "ENTRY_LOW": 5157.0,
            "STOP_LOSS":  5150.0, "TP1": 5167.0,
            "TP2": 5172.0,        "TP3": 5185.0,
        }
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ──────────────────────────────────────────────
# INDICATEURS
# ──────────────────────────────────────────────
def ema(arr, n):
    if len(arr) < n: return None
    k, e = 2 / (n + 1), arr[0]
    for p in arr[1:]: e = p * k + e * (1 - k)
    return round(e, 2)

def rsi(arr, n=14):
    if len(arr) < n + 1: return None
    sl = arr[-(n+1):]
    g = sum(max(sl[i]-sl[i-1], 0) for i in range(1, len(sl)))
    l = sum(max(sl[i-1]-sl[i], 0) for i in range(1, len(sl)))
    if l == 0: return 100.0
    return round(100 - 100 / (1 + g/l), 1)

def atr(arr, n=14):
    if len(arr) < n + 1: return None
    sl = arr[-(n+1):]
    trs = [abs(sl[i]-sl[i-1]) for i in range(1, len(sl))]
    return round(sum(trs)/n, 2)

def macd(arr):
    if len(arr) < 26: return None
    e12, e26 = ema(arr, 12), ema(arr, 26)
    return round(e12-e26, 2) if e12 and e26 else None

# ──────────────────────────────────────────────
# ANALYSE BRUTE
# ──────────────────────────────────────────────
def analyze_m5(hist, price):
    if len(hist) < 5: return "NEUTRE", 0, 0
    e9, e21 = ema(hist, 9), ema(hist, 21)
    r       = rsi(hist)
    rising  = hist[-1] > hist[-5]
    buy = sell = 0
    if e9  and price > e9:       buy  += 1
    elif e9:                     sell += 1
    if e9 and e21 and e9 > e21:  buy  += 1
    elif e9 and e21:             sell += 1
    if r and r > 55:             buy  += 1
    elif r and r < 45:           sell += 1
    if rising:                   buy  += 1
    else:                        sell += 1
    dir_ = "BUY" if buy >= 3 else "SELL" if sell >= 3 else "NEUTRE"
    return dir_, min(buy, 5), min(sell, 5)

def analyze_m15(hist15, price):
    e50, e200 = ema(hist15, 50), ema(hist15, 200)
    r, a      = rsi(hist15), atr(hist15)
    if not e50 or not e200: return "NEUTRE"
    if a and a < 0.3: return "NEUTRE"
    if price > e50 > e200 and r and r > 50: return "BUY"
    if price < e50 < e200 and r and r < 50: return "SELL"
    return "NEUTRE"

def vote_dir(votes, threshold):
    if len(votes) < 5: return "NEUTRE", 0, 0
    b = votes.count("BUY"); s = votes.count("SELL"); t = len(votes)
    if b >= t * threshold:  return "BUY",  b, s
    if s >= t * threshold:  return "SELL", b, s
    return "NEUTRE", b, s

def raw_signal(price, hist, hist15, votes, threshold):
    dm5, buy, sell = analyze_m5(hist, price)
    dm15           = analyze_m15(hist15, price)
    dvote, vb, vs  = vote_dir(votes, threshold)
    dir_ = force = "NEUTRE"
    if dm15=="BUY"  and dm5=="BUY"  and dvote=="BUY":  dir_="BUY";  force="FORT"
    elif dm15=="SELL" and dm5=="SELL" and dvote=="SELL": dir_="SELL"; force="FORT"
    elif dm5=="BUY"  and dvote=="BUY":  dir_="BUY";  force="MODÉRÉ"
    elif dm5=="SELL" and dvote=="SELL": dir_="SELL"; force="MODÉRÉ"
    elif dm5 != "NEUTRE": dir_=dm5; force="FAIBLE"
    return {"dir":dir_,"force":force,"dm15":dm15,"dm5":dm5,
            "dvote":dvote,"buy":buy,"sell":sell,"vbuy":vb,"vsell":vs}

# ──────────────────────────────────────────────
# STABILISATION DU SIGNAL
# ──────────────────────────────────────────────
def stabilize(raw_dir, raw_force):
    now          = time.time()
    lock_expired = (now - st.session_state.lock_time) >= st.session_state.lock_duration
    current_lock = st.session_state.lock_dir

    if raw_dir == current_lock:
        st.session_state.confirm_count = 0
        return current_lock, st.session_state.confirmed_force

    if raw_dir != "NEUTRE" and raw_dir != current_lock:
        if lock_expired:
            st.session_state.confirm_count += 1
            if st.session_state.confirm_count >= st.session_state.confirm_needed:
                st.session_state.lock_dir        = raw_dir
                st.session_state.lock_time       = now
                st.session_state.confirmed_dir   = raw_dir
                st.session_state.confirmed_force = raw_force
                st.session_state.confirm_count   = 0
        else:
            st.session_state.confirm_count = 0

    return st.session_state.confirmed_dir, st.session_state.confirmed_force

# ──────────────────────────────────────────────
# RÉCUPÉRATION DU PRIX
# ──────────────────────────────────────────────
@st.cache_data(ttl=10)
def get_price():
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get("https://data-asg.goldprice.org/dbXRates/USD",
                         headers=headers, timeout=6)
        p = float(r.json()["items"][0]["xauPrice"])
        if p > 100: return round(p, 2), "GoldPrice.org"
    except: pass
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF?interval=1m&range=1d",
            headers=headers, timeout=8)
        p = float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
        if p > 100: return round(p, 2), "Yahoo Finance"
    except: pass
    try:
        r = requests.get(
            "https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAU/USD",
            headers=headers, timeout=6)
        p = float(r.json()[0]["spreadProfilePrices"][0]["ask"])
        if p > 100: return round(p, 2), "Swissquote"
    except: pass
    return None, None

# ──────────────────────────────────────────────
# INTERFACE
# ──────────────────────────────────────────────
st.markdown("## 🥇 XAUUSD Scalping Pro")
st.caption("Signal stabilisé · Confirmation 5 ticks · Verrou 60s · Votes 80%")
st.divider()

price, source = get_price()

if price:
    hist = (st.session_state.hist + [price])[-200:]
    st.session_state.hist = hist

    st.session_state.tick15 += 1
    if st.session_state.tick15 % 3 == 0:
        st.session_state.hist15 = (st.session_state.hist15 + [price])[-200:]

    dm5, _, _ = analyze_m5(hist, price)
    votes = (st.session_state.votes + [dm5])[-10:]
    st.session_state.votes = votes

    sig = raw_signal(price, hist, st.session_state.hist15,
                     votes, st.session_state.vote_threshold)
    stable_dir, stable_force = stabilize(sig["dir"], sig["force"])

    levels  = st.session_state.levels
    entry   = (levels["ENTRY_HIGH"] + levels["ENTRY_LOW"]) / 2
    pnl     = round(price - entry, 2)
    bar_pct = min(max(
        (price - levels["STOP_LOSS"]) / (levels["TP3"] - levels["STOP_LOSS"]), 0), 1)

    # ── PRIX ──
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("💰 XAU/USD", f"{price:.2f} $",
                         delta=f"{pnl:+.2f} pips vs entrée")
    with col2: st.metric("📡 Source", source)
    with col3: st.metric("📊 Ticks",  f"{len(hist)}/200")

    st.progress(bar_pct,
        text=f"SL {levels['STOP_LOSS']}  ───  Entrée {levels['ENTRY_LOW']}–{levels['ENTRY_HIGH']}  ───  TP3 {levels['TP3']}")
    st.divider()

    # ── SIGNAL STABILISÉ ──
    if stable_dir == "BUY":
        css, color, icon = "buy-box", "#00ff88", "▲ BUY"
    elif stable_dir == "SELL":
        css, color, icon = "sell-box", "#ff4444", "▼ SELL"
    else:
        css, color, icon = "neut-box", "#ffcc00", "─ NEUTRE"

    lock_remaining    = max(0, int(st.session_state.lock_duration - (time.time() - st.session_state.lock_time)))
    confirm_progress  = min(st.session_state.confirm_count, st.session_state.confirm_needed)

    st.markdown(f"""
    <div class="{css}">
        <div class="sig-title" style="color:{color}">{icon}</div>
        <div class="sig-force" style="color:{color}">Force : {stable_force}</div>
        <div class="stable-badge">🔒 Verrou : {lock_remaining}s restantes</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    brut = sig["dir"]
    with col1: st.metric("Signal brut",
                         f"{'▲' if brut=='BUY' else '▼' if brut=='SELL' else '─'} {brut}")
    with col2: st.metric("Confirmations",
                         f"{confirm_progress}/{st.session_state.confirm_needed}",
                         delta="En cours..." if confirm_progress > 0 else "Stable")
    with col3: st.metric("Signal stable",
                         f"{'▲' if stable_dir=='BUY' else '▼' if stable_dir=='SELL' else '─'} {stable_dir}")

    st.divider()

    # ── PARAMÈTRES DE STABILISATION ──
    with st.expander("⚙️ Régler la stabilité du signal"):
        st.caption("Plus les valeurs sont élevées → signal plus stable mais plus lent")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.session_state.confirm_needed = st.slider(
                "Confirmations nécessaires", 3, 15, st.session_state.confirm_needed)
        with col2:
            st.session_state.lock_duration = st.slider(
                "Verrou (secondes)", 30, 300, st.session_state.lock_duration, step=10)
        with col3:
            pct = st.slider("Seuil votes (%)", 60, 95,
                            int(st.session_state.vote_threshold * 100))
            st.session_state.vote_threshold = pct / 100
        st.info(f"Réglages : {st.session_state.confirm_needed} ticks · "
                f"{st.session_state.lock_duration}s · "
                f"{int(st.session_state.vote_threshold*100)}% votes")

    st.divider()

    # ── MTF ──
    st.markdown("#### 📊 Multi-Timeframe")
    def di(d): return "🟢 BUY" if d=="BUY" else "🔴 SELL" if d=="SELL" else "🟡 NEUTRE"
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("M15 Macro",      di(sig["dm15"]))
    with col2: st.metric("M5  Micro",      di(sig["dm5"]))
    with col3: st.metric(f"Votes {len(votes)}/10", di(sig["dvote"]),
                         delta=f"B:{sig['vbuy']} S:{sig['vsell']}")

    st.divider()

    # ── INDICATEURS ──
    st.markdown("#### 📈 Indicateurs")
    r_v=rsi(hist); a_v=atr(hist); m_v=macd(hist)
    e9=ema(hist,9); e21=ema(hist,21); e50=ema(hist,50); e200=ema(hist,200)

    col1,col2,col3,col4 = st.columns(4)
    with col1: st.metric("RSI(14)", r_v or "─",
                         delta="Surachat" if r_v and r_v>70 else "Survente" if r_v and r_v<30 else "Normal")
    with col2: st.metric("ATR(14)", a_v or "─",
                         delta="Fort" if a_v and a_v>1 else "Faible")
    with col3: st.metric("MACD",    m_v or "─")
    with col4: st.metric("B/S",     f"{sig['buy']}/5 · {sig['sell']}/5")

    col1,col2,col3,col4 = st.columns(4)
    def ed(v): return (f"↑+{round(price-v,2)}" if price>v else f"↓{round(price-v,2)}") if v else "─"
    with col1: st.metric("EMA 9",   e9   or "─", delta=ed(e9))
    with col2: st.metric("EMA 21",  e21  or "─", delta=ed(e21))
    with col3: st.metric("EMA 50",  e50  or "─", delta=ed(e50))
    with col4: st.metric("EMA 200", e200 or "─", delta=ed(e200))

    st.divider()

    # ── GRAPHIQUE ──
    if len(hist) >= 5:
        st.markdown("#### 📉 Graphique")
        st.line_chart(pd.DataFrame({"Prix XAU/USD": hist[-60:]}), color=["#00ff88"])

    st.divider()

    # ── NIVEAUX ──
    st.markdown("#### 📡 Signal Telegram")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"🔴 **Stop Loss** : `{levels['STOP_LOSS']}`")
        st.markdown(f"🟡 **Entrée Haute** : `{levels['ENTRY_HIGH']}`")
        st.markdown(f"🟡 **Entrée Basse** : `{levels['ENTRY_LOW']}`")
    with col2:
        st.markdown(f"🟢 **TP 1** : `{levels['TP1']}`")
        st.markdown(f"🟢 **TP 2** : `{levels['TP2']}`")
        st.markdown(f"🟢 **TP 3** : `{levels['TP3']}`")

    with st.expander("✏️ Modifier les niveaux"):
        with st.form("edit"):
            c1, c2 = st.columns(2)
            with c1:
                eh=st.number_input("Entrée Haute",value=levels["ENTRY_HIGH"])
                el=st.number_input("Entrée Basse",value=levels["ENTRY_LOW"])
                sl=st.number_input("Stop Loss",   value=levels["STOP_LOSS"])
            with c2:
                tp1=st.number_input("TP 1",value=levels["TP1"])
                tp2=st.number_input("TP 2",value=levels["TP2"])
                tp3=st.number_input("TP 3",value=levels["TP3"])
            if st.form_submit_button("✅ Appliquer"):
                st.session_state.levels = {
                    "ENTRY_HIGH":eh,"ENTRY_LOW":el,"STOP_LOSS":sl,
                    "TP1":tp1,"TP2":tp2,"TP3":tp3}
                st.success("✅ Niveaux mis à jour !")
else:
    st.error("⚠️ Prix non disponible — vérifie ta connexion")

st.divider()
st.caption(f"⏱ {datetime.now().strftime('%H:%M:%S')} · Auto-refresh 10s")
st.caption("⚠️ Outil éducatif — Ne pas trader sans gestion du risque")
time.sleep(0.5)
st.rerun()
