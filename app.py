import streamlit as st
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone

st.set_page_config(page_title="Crypto Live Analyzer", page_icon="📊", layout="wide")
st.title("📊 Crypto Live Analyzer")
st.caption("تحليل حي للعقود الدائمة USDT — إشارات تعليمية وليست توصيات مالية.")

EXCHANGES = {
    "Binance Futures": (ccxt.binanceusdm, "future"),
    "Bybit Futures": (ccxt.bybit, "swap"),
    "OKX Futures": (ccxt.okx, "swap"),
    "Bitget Futures": (ccxt.bitget, "swap"),
    "KuCoin Futures": (ccxt.kucoinfutures, "swap"),
}
FRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]

@st.cache_resource
def exchange_for(name):
    cls, kind = EXCHANGES[name]
    return cls({"enableRateLimit": True, "timeout": 15000,
                "options": {"defaultType": kind}})

def get_symbol(ex, base):
    base = base.upper().replace("/USDT", "").replace("USDT", "").strip()
    markets = ex.load_markets()
    found = []
    for sym, m in markets.items():
        if (m.get("active") is not False and m.get("base") == base
            and m.get("quote") == "USDT" and m.get("swap")
            and m.get("settle") in (None, "USDT")):
            found.append((sym, m))
    if not found:
        raise ValueError(f"لا يوجد عقد دائم USDT للعملة {base}")
    for sym, m in found:
        if m.get("settle") == "USDT" and m.get("linear"):
            return sym
    return found[0][0]

def get_data(ex, symbol, frame):
    rows = ex.fetch_ohlcv(symbol, timeframe=frame, limit=250)
    if not rows or len(rows) < 210:
        raise ValueError("بيانات الشموع غير كافية.")
    df = pd.DataFrame(rows, columns=["time","open","high","low","close","volume"])
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    return df

def analyze(df):
    c, h, l, v = df.close, df.high, df.low, df.volume
    e20 = c.ewm(span=20, adjust=False).mean()
    e50 = c.ewm(span=50, adjust=False).mean()
    e200 = c.ewm(span=200, adjust=False).mean()
    d = c.diff()
    gain = d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-d.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rsi = 100 - 100/(1 + gain/loss.replace(0, np.nan))
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    sig = macd.ewm(span=9, adjust=False).mean()
    prev = c.shift()
    tr = pd.concat([h-l, (h-prev).abs(), (l-prev).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    volavg = v.rolling(20).mean()
    i = len(df)-2  # آخر شمعة مغلقة
    price = float(c.iloc[i])
    av = float(atr.iloc[i]) if pd.notna(atr.iloc[i]) else price*0.01
    rv = float(rsi.iloc[i]) if pd.notna(rsi.iloc[i]) else 50
    long = (20 if price > e20.iloc[i] else 0) + (15 if e20.iloc[i] > e50.iloc[i] else 0) + (15 if e50.iloc[i] > e200.iloc[i] else 0) + (15 if macd.iloc[i] > sig.iloc[i] else 0) + (10 if 50 < rv < 70 else 0)
    short = (20 if price < e20.iloc[i] else 0) + (15 if e20.iloc[i] < e50.iloc[i] else 0) + (15 if e50.iloc[i] < e200.iloc[i] else 0) + (15 if macd.iloc[i] < sig.iloc[i] else 0) + (10 if 30 < rv < 50 else 0)
    if pd.notna(volavg.iloc[i]) and v.iloc[i] > volavg.iloc[i]:
        long += 10 if price > c.iloc[i-1] else 0
        short += 10 if price < c.iloc[i-1] else 0
    side, score = ("WAIT", max(long, short)) if long == short or max(long, short) < 45 else (("LONG", long) if long > short else ("SHORT", short))
    if side == "LONG":
        sl, t1, t2, t3 = price-1.5*av, price+1.5*av, price+2.5*av, price+3.5*av
    elif side == "SHORT":
        sl, t1, t2, t3 = price+1.5*av, price-1.5*av, price-2.5*av, price-3.5*av
    else:
        sl = t1 = t2 = t3 = None
    return dict(side=side, score=int(score), price=price, rsi=rv, atr=av,
                ema20=float(e20.iloc[i]), ema50=float(e50.iloc[i]), ema200=float(e200.iloc[i]),
                sl=sl, t1=t1, t2=t2, t3=t3, candle=df.time.iloc[i])

def fmt(x):
    return "—" if x is None else f"{x:,.8g}"

with st.sidebar:
    st.header("إعدادات التحليل")
    coin = st.text_input("رمز العملة", "BTC").upper().strip()
    choice = st.selectbox("المنصة", ["تلقائي — الانتقال بين المنصات"] + list(EXCHANGES))
    frame = st.selectbox("الفريم", FRAMES, index=4)
    seconds = st.selectbox("تحديث تلقائي (ثانية)", [15, 30, 60, 120], index=1)
    go = st.button("ابدأ التحليل", type="primary", use_container_width=True)

if go:
    st.session_state["scan_started"] = True

@st.fragment(run_every=f"{seconds}s")
def live_scan():
    if not st.session_state.get("scan_started"):
        st.info("اختر العملة والمنصة والفريم ثم اضغط «ابدأ التحليل».")
        return
    if not coin:
        st.warning("أدخل رمز العملة.")
        return
    choices = list(EXCHANGES) if choice.startswith("تلقائي") else [choice]
    errors, result = [], None
    for name in choices:
        try:
            ex = exchange_for(name)
            symbol = get_symbol(ex, coin)
            df = get_data(ex, symbol, frame)
            result = (name, symbol, df, analyze(df))
            break
        except Exception as err:
            errors.append(f"{name}: {str(err)[:220]}")
    if result is None:
        st.error("تعذر جلب البيانات من المنصات المتاحة.")
        for e in errors:
            st.caption(e)
        st.info("قد تكون واجهة المنصة محجوبة من خادم الاستضافة أو لا يتوفر عقد لهذه العملة.")
        return
    name, symbol, df, r = result
    st.caption(f"المصدر: {name} | العقد: {symbol} | آخر شمعة مغلقة: {r['candle'].strftime('%Y-%m-%d %H:%M UTC')}")
    a,b,c = st.columns(3)
    a.metric("الإشارة", {"LONG":"شراء / LONG","SHORT":"بيع / SHORT","WAIT":"انتظار"}[r["side"]])
    b.metric("قوة الشروط الفنية", f"{r['score']} / 100")
    c.metric("RSI", f"{r['rsi']:.1f}")
    if r["side"] == "WAIT":
        st.warning("لا توجد إشارة دخول قوية حالياً.")
    else:
        st.success("إشارة فنية مرصودة — تحقق من السيولة والتمويل والانزلاق.")
        cols = st.columns(5)
        for col, label, value in zip(cols, ["دخول مرجعي","وقف الخسارة","الهدف 1","الهدف 2","الهدف 3"], [r["price"],r["sl"],r["t1"],r["t2"],r["t3"]]):
            col.metric(label, fmt(value))
    with st.expander("المؤشرات الفنية"):
        st.dataframe(pd.DataFrame({"المؤشر":["EMA 20","EMA 50","EMA 200","ATR","RSI"],
            "القيمة":[r["ema20"],r["ema50"],r["ema200"],r["atr"],r["rsi"]]}), hide_index=True, use_container_width=True)
    st.subheader("حركة السعر — آخر 100 شمعة")
    st.line_chart(df.tail(100).set_index("time")["close"], use_container_width=True)
    st.caption("آخر تحديث: " + datetime.now(timezone.utc).strftime("%H:%M:%S UTC"))
    if errors:
        with st.expander("منصات لم تستجب"):
            for e in errors: st.write(e)
    st.warning("تنبيه: تحليل فني آلي تعليمي فقط، لا ينفذ صفقات ولا يضمن الربح. تداول العقود والرافعة المالية قد يؤدي إلى خسارة رأس المال.")

live_scan()
