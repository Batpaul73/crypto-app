import streamlit as st
import requests
import pandas as pd
import ta
import plotly.graph_objects as go
import numpy as np

# ===== Configurazione Pagina =====
st.set_page_config(page_title="Crypto Analyzer PRO", layout="wide")

# ===== Sidebar Settings =====
st.sidebar.title("Impostazioni")
crypto_list = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "AVAX-USDT", "XRP-USDT"]
selected_cryptos = st.sidebar.multiselect("Seleziona le coppie", crypto_list, default=["BTC-USDT"])
interval = st.sidebar.selectbox("Intervallo", ["1m","5m","15m","1h","4h","1d"], index=3)
limit = st.sidebar.slider("Numero di candele", 100, 1000, 300)
dark_mode = st.sidebar.checkbox("Modalità Scura", value=True)

# ===== Tema =====
theme = "plotly_dark" if dark_mode else "plotly_white"

# ===== Funzione dati OKX =====
def get_okx_data(symbol, interval, limit):
    url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}&bar={interval}&limit={limit}"
    response = requests.get(url)
    data = response.json()['data']
    df = pd.DataFrame(data, columns=["ts","o","h","l","c","vol","volCcy"])
    df = df.iloc[::-1].reset_index(drop=True)
    df["time"] = pd.to_datetime(df["ts"], unit='ms')
    df[["o","h","l","c","vol"]] = df[["o","h","l","c","vol"]].astype(float)
    df.rename(columns={"o":"open","h":"high","l":"low","c":"close","vol":"volume"}, inplace=True)
    return df

# ===== Supertrend =====
def supertrend(df, period=10, multiplier=3):
    hl2 = (df["high"] + df["low"]) / 2
    atr = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=period).average_true_range()
    upperband = hl2 + multiplier * atr
    lowerband = hl2 - multiplier * atr
    supertrend = [True] * len(df)
    for i in range(1, len(df)):
        if df["close"][i] > upperband[i-1]:
            supertrend[i] = True
        elif df["close"][i] < lowerband[i-1]:
            supertrend[i] = False
        else:
            supertrend[i] = supertrend[i-1]
            if supertrend[i] and lowerband[i] < lowerband[i-1]:
                lowerband[i] = lowerband[i-1]
            if not supertrend[i] and upperband[i] > upperband[i-1]:
                upperband[i] = upperband[i-1]
    return pd.Series(supertrend)

# ===== Creazione dashboard =====
for symbol in selected_cryptos:
    st.subheader(f"📈 {symbol}")
    df = get_okx_data(symbol, interval, limit)

    # Indicatori
    df["RSI"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    macd = ta.trend.MACD(df["close"])
    df["MACD"] = macd.macd()
    df["MACD_signal"] = macd.macd_signal()
    bb = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2)
    df["BB_high"] = bb.bollinger_hband()
    df["BB_low"] = bb.bollinger_lband()
    df["EMA20"] = df["close"].ewm(span=20).mean()
    df["EMA50"] = df["close"].ewm(span=50).mean()
    df["ADX"] = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14).adx()
    df["Supertrend"] = supertrend(df)

    # Alert RSI
    if df["RSI"].iloc[-1] > 70:
        st.error(f"⚠️ {symbol} RSI > 70 (ipercomprato)")
    elif df["RSI"].iloc[-1] < 30:
        st.success(f"✅ {symbol} RSI < 30 (ipervenduto)")

    # Tabs
    tab1, tab2, tab3 = st.tabs(["Grafico Prezzo", "Indicatori", "Download"])

    # Grafico Prezzo
    with tab1:
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df["time"], open=df["open"], high=df["high"], low=df["low"], close=df["close"], name="Prezzo"))
        fig.add_trace(go.Scatter(x=df["time"], y=df["BB_high"], line=dict(color="gray", dash="dot"), name="BB High"))
        fig.add_trace(go.Scatter(x=df["time"], y=df["BB_low"], line=dict(color="gray", dash="dot"), name="BB Low"))
        fig.add_trace(go.Scatter(x=df["time"], y=df["EMA20"], line=dict(color="orange"), name="EMA 20"))
        fig.add_trace(go.Scatter(x=df["time"], y=df["EMA50"], line=dict(color="blue"), name="EMA 50"))
        fig.update_layout(template=theme, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

    # Indicatori (RSI, MACD, ADX)
    with tab2:
        st.write("### RSI & ADX")
        st.line_chart(df[["RSI","ADX"]])
        st.write("### MACD")
        st.line_chart(df[["MACD","MACD_signal"]])

    # Download dati
    with tab3:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(f"Scarica dati {symbol}", data=csv, file_name=f"{symbol}_data.csv", mime="text/csv")