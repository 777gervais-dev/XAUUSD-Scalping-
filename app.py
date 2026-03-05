# ============================================================
#   XAUUSD SCALPING PRO — Streamlit Dashboard
#   Prix en temps réel · BUY/SELL · Indicateurs complets
#   Déployable sur Streamlit Cloud (gratuit)
# ============================================================

import streamlit as st
import requests
import time
import pandas as pd
from collections import deque
from datetime import datetime

# ──────────────────────────────────────────────
# CONFIG PAGE
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="XAUUSD Scalping Pro",
    page_icon="🥇",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ──────────────────────────────────────────────
# CSS CUSTOM (style sombre professionnel)
# ──────────────────────────────────────────────
st.markdown("""
<style>
body, .stApp { background-color: #05050f; color: #e0e0ff; }
.stMetric label { color: #888 !important; font-size: 11px !important; }
.stMetric [data-testid="metric-container"] { background: #0d0d1a; border-radius: 8px; padding: 10px; border: 1px solid #1a1a30; }
div[data-testid="column"] { padding: 4px !important; }
.buy-box  { background: rgba(0,255,136,0.08); border: 2px solid #00ff88; border-radius: 10px; padding: 16px; text-align: center; }
.sell-box { background: rgba(255,68,68,0.08);  border: 2px solid #ff4444; border-radius: 10px; padding: 16px; text-align: center; }
.neut-box { background: rgba(255,204,0,0.08);  border: 2px solid #ffcc00; border-radius: 10px; padding: 16px; text-align: center; }
.sig-title { font-size: 28px; font-weight: 900; letter-spacing: 2px; }
.sig-force { font-size: 13px; margin-top: 4px; }
.level-row { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #111; font-size: 13px; }
hr { border-color: #1a1a30 !important; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# SESSION STATE — historique des prix
# ──────────────────────────────────────────────
if "hist"    not in st.session_state: st.session_state.hist    = []
if "hist15"  not in st.session_state: st.session_state.hist15  = []
if "votes"   not in st.session_state: st.session_state.votes   = []
if "tick15"  not in st.session_state: st.session_state.tick15  = 0
if "levels"  not in st.session_state:
    st.session_state.levels = {
        "ENTRY_HIGH": 5161.0, "ENTRY_LOW": 5157.0,
        "STOP_LOSS":  5150.0, "TP1": 5167.0, "TP2": 5172.0, "TP3": 5185.0
    }

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
    g = sum(max(sl[i]-sl[i-1],0) for i in range(1,len(sl)))
    l = sum(max(sl[i-1]-sl[i],0) for i in range(1,len(sl)))
    if l == 0: return 100.0
    return round(100 - 100/(1 + g/l), 1)

def atr(arr, n=14):
    if len(arr) < n + 1: return None
    sl = arr[-(n+1):]
    trs = [abs(sl[i]-sl[i-1]) for i in range(1,len(sl))]
    return round(sum(trs)/n, 2)

def macd(arr):
    if len(arr) < 26: return None
    e12, e26 = ema(arr,12), ema(arr,26)
    return round(e12-e26,2) if e12 and e26 else None

# ──────────────────────────────────────────────
# LOGIQUE SIGNAL
# ──────────────────────────────────────────────
def analyze_m5(hist, price):
    if len(hist) < 3: return "NEUTRE", 0, 0
    e9, e21, r = ema(hist,9), ema(hist,21), rsi(hist)
    rising = hist[-1] > hist[-3]
    buy = sell = 0
    if e9  and price > e9:  buy  += 1
    elif e9:                sell += 1
    if e9 and e21 and e9 > e21: buy  += 1
    elif e9 and e21:            sell += 1
    if r and r > 55: buy  += 1
    elif r and r < 45: sell += 1
    if rising: buy += 1
    else:      sell += 1
    dir_ = "BUY" if buy >= 3 else "SELL" if sell >= 3 else "NEUTRE"
    return dir_, min(buy,5), min(sell,5)

def analyze_m15(hist15, price):
    e50, e200 = ema(hist15,50), ema(hist15,200)
    r, a = rsi(hist15), atr(hist15)
    if not e50 or not e200: return "NEUTRE"
    if a and a < 0.3: return "NEUTRE"
    if price > e50 > e200 and r and r > 50: return "BUY"
    if price < e50 < e200 and r and r < 50: return "SELL"
    return "NEUTRE"

def vote_dir(votes):
    if len(votes) < 5: return "NEUTRE", 0, 0
    b = votes.count("BUY"); s = votes.count("SELL"); t = len(votes)
    return ("BUY" if b >= t*0.7 else "SELL" if s >= t*0.7 else "NEUTRE"), b, s

def final_signal(price, hist, hist15, votes):
    dm5, buy, sell = analyze_m5(hist, price)
    dm15           = analyze_m15(hist15, price)
    dvote, vb, vs  = vote_dir(votes)
    dir_ = force = "NEUTRE"
    if dm15=="BUY"  and dm5=="BUY"  and dvote=="BUY":  dir_="BUY";  force="FORT"
    elif dm15=="SELL" and dm5=="SELL" and dvote=="SELL": dir_="SELL"; force="FORT"
    elif dm5=="BUY"  and dvote=="BUY":  dir_="BUY";  force="MODÉRÉ"
    elif dm5=="SELL" and dvote=="SELL": dir_="SELL"; force="MODÉRÉ"
    elif dm5 != "NEUTRE": dir_=dm5; force="FAIBLE"
    return {"dir":dir_,"force":force,"dm15":dm15,"dm5":dm5,"dvote":dvote,
            "buy":buy,"sell":sell,"vbuy":vb,"vsell":vs}

# ──────────────────────────────────────────────
# RÉCUPÉRATION DU PRIX
# ──────────────────────────────────────────────
@st.cache_data(ttl=10)
def get_price():
    headers = {"User-Agent":"Mozilla/5.0"}
    # Source 1 : GoldPrice
    try:
        r = requests.get("https://data-asg.goldprice.org/dbXRates/USD", headers=headers, timeout=6)
        p = float(r.json()["items"][0]["xauPrice"])
        if p > 100: return round(p,2), "GoldPrice.org"
    except: pass
    # Source 2 : Yahoo Finance
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF?interval=1m&range=1d", headers=headers, timeout=8)
        p = float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
        if p > 100: return round(p,2), "Yahoo Finance"
    except: pass
    # Source 3 : Swissquote
    try:
        r = requests.get("https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAU/USD", headers=headers, timeout=6)
        p = float(r.json()[0]["spreadProfilePrices"][0]["ask"])
        if p > 100: return round(p,2), "Swissquote"
    except: pass
    return None, None

# ──────────────────────────────────────────────
# INTERFACE
# ──────────────────────────────────────────────
st.markdown("## 🥇 XAUUSD Scalping Pro")
st.caption("Prix en temps réel · BUY/SELL automatique · Multi-Timeframe")
st.divider()

# ── Récupération du prix ──
price, source = get_price()

if price:
    hist = st.session_state.hist
    hist.append(price)
    if len(hist) > 200: hist = hist[-200:]
    st.session_state.hist = hist

    st.session_state.tick15 += 1
    if st.session_state.tick15 % 3 == 0:
        st.session_state.hist15.append(price)
        if len(st.session_state.hist15) > 200:
            st.session_state.hist15 = st.session_state.hist15[-200:]

    dm5, _, _ = analyze_m5(hist, price)
    votes = st.session_state.votes + [dm5]
    votes = votes[-10:]
    st.session_state.votes = votes

    sig = final_signal(price, hist, st.session_state.hist15, votes)
    levels = st.session_state.levels
    entry  = (levels["ENTRY_HIGH"] + levels["ENTRY_LOW"]) / 2
    pnl    = round(price - entry, 2)

    # ── PRIX PRINCIPAL ──
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💰 XAU/USD", f"{price:.2f} $",
                  delta=f"{pnl:+.2f} pips vs entrée")
    with col2:
        st.metric("📡 Source", source)
    with col3:
        st.metric("📊 Ticks", f"{len(hist)}/200")

    # ── BARRE PROGRESSION SL → TP3 ──
    bar_pct = min(max((price - levels["STOP_LOSS"]) / (levels["TP3"] - levels["STOP_LOSS"]), 0), 1)
    st.progress(bar_pct, text=f"SL {levels['STOP_LOSS']}  ──────  Entrée {levels['ENTRY_LOW']}–{levels['ENTRY_HIGH']}  ──────  TP3 {levels['TP3']}")

    st.divider()

    # ── SIGNAL BUY / SELL ──
    dir_  = sig["dir"]
    force = sig["force"]
    if dir_ == "BUY":
        icon, css = "▲ BUY", "buy-box"
        color_txt = "#00ff88"
    elif dir_ == "SELL":
        icon, css = "▼ SELL", "sell-box"
        color_txt = "#ff4444"
    else:
        icon, css = "─ NEUTRE", "neut-box"
        color_txt = "#ffcc00"

    st.markdown(f"""
    <div class="{css}">
        <div class="sig-title" style="color:{color_txt}">{icon}</div>
        <div class="sig-force" style="color:{color_txt}">Force : {force}</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # ── MULTI-TIMEFRAME ──
    st.markdown("#### 📊 Analyse Multi-Timeframe")
    col1, col2, col3 = st.columns(3)
    def dir_icon(d):
        return "🟢 BUY" if d=="BUY" else "🔴 SELL" if d=="SELL" else "🟡 NEUTRE"
    with col1: st.metric("M15 — Macro",     dir_icon(sig["dm15"]))
    with col2: st.metric("M5  — Micro",     dir_icon(sig["dm5"]))
    with col3: st.metric(f"Votes {len(votes)}/10", dir_icon(sig["dvote"]),
                         delta=f"B:{sig['vbuy']} S:{sig['vsell']}")

    st.divider()

    # ── INDICATEURS ──
    st.markdown("#### 📈 Indicateurs Temps Réel")
    r_val  = rsi(hist)
    a_val  = atr(hist)
    m_val  = macd(hist)
    e9_v   = ema(hist,9)
    e21_v  = ema(hist,21)
    e50_v  = ema(hist,50)
    e200_v = ema(hist,200)

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("RSI (14)", r_val or "─",
                         delta="Surach." if r_val and r_val>70 else "Surven." if r_val and r_val<30 else "Normal")
    with col2: st.metric("ATR (14)", a_val or "─",
                         delta="Fort" if a_val and a_val>1 else "Faible")
    with col3: st.metric("MACD",    m_val or "─")
    with col4: st.metric("Score BUY/SELL", f"{sig['buy']}/5  {sig['sell']}/5")

    # EMAs
    st.markdown("**EMA :**")
    col1,col2,col3,col4 = st.columns(4)
    def ema_delta(val):
        if val is None: return "─"
        return f"↑ +{round(price-val,2)}" if price>val else f"↓ {round(price-val,2)}"
    with col1: st.metric("EMA 9",   e9_v or "─",   delta=ema_delta(e9_v))
    with col2: st.metric("EMA 21",  e21_v or "─",  delta=ema_delta(e21_v))
    with col3: st.metric("EMA 50",  e50_v or "─",  delta=ema_delta(e50_v))
    with col4: st.metric("EMA 200", e200_v or "─", delta=ema_delta(e200_v))

    st.divider()

    # ── GRAPHIQUE PRIX ──
    if len(hist) >= 2:
        st.markdown("#### 📉 Graphique du Prix")
        df = pd.DataFrame({"Prix XAU/USD": hist[-60:]})
        st.line_chart(df, color=["#00ff88"])

    st.divider()

    # ── NIVEAUX SIGNAL TELEGRAM ──
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

    with st.expander("✏️ Modifier les niveaux du signal"):
        with st.form("edit_levels"):
            c1, c2 = st.columns(2)
            with c1:
                eh = st.number_input("Entrée Haute", value=levels["ENTRY_HIGH"])
                el = st.number_input("Entrée Basse", value=levels["ENTRY_LOW"])
                sl = st.number_input("Stop Loss",    value=levels["STOP_LOSS"])
            with c2:
                tp1 = st.number_input("TP 1", value=levels["TP1"])
                tp2 = st.number_input("TP 2", value=levels["TP2"])
                tp3 = st.number_input("TP 3", value=levels["TP3"])
            if st.form_submit_button("✅ Appliquer"):
                st.session_state.levels = {
                    "ENTRY_HIGH":eh,"ENTRY_LOW":el,"STOP_LOSS":sl,
                    "TP1":tp1,"TP2":tp2,"TP3":tp3
                }
                st.success("Niveaux mis à jour !")

else:
    st.error("⚠️ Prix non disponible — vérifie ta connexion internet")

# ──────────────────────────────────────────────
# HEURE + AUTO-REFRESH
# ──────────────────────────────────────────────
st.divider()
st.caption(f"⏱ Dernière mise à jour : {datetime.now().strftime('%H:%M:%S')}  ·  Actualisation auto toutes les 10s")
st.caption("⚠️ Outil éducatif — Ne pas trader sans gestion du risque")

# Auto-refresh toutes les 10 secondes
time.sleep(0.5)
st.rerun()
