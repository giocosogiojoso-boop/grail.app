import streamlit as st
import google.generativeai as genai
import feedparser
import urllib.parse
import datetime
import pytz
import yfinance as ticker_data
import plotly.graph_objects as go
import pandas as pd

# 1. 基本設定
st.set_page_config(page_title="FX AI-Analyst Stable", layout="wide")
JST = pytz.timezone('Asia/Tokyo')

if 'history' not in st.session_state:
    st.session_state.history = []

@st.cache_data(ttl=600)
def get_market_data():
    rate, df, news = 150.0, pd.DataFrame(), []
    try:
        fx = ticker_data.Ticker("JPY=X")
        df = fx.history(period="30d", interval="1d")
        if not df.empty: rate = round(df['Close'].iloc[-1], 3)
    except: pass
    try:
        query = urllib.parse.quote('USD JPY "ドル円" when:1d')
        rss = feedparser.parse(f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja")
        news = [f"・{e.title}" for e in rss.entries[:5]]
    except: news = ["ニュース取得制限中"]
    return df, rate, news

df_history, current_rate, news_list = get_data()

# UI表示
st.title("💹 FX AI-Analyst (Global Stable)")
st.metric("USD/JPY", f"{current_rate}円")

if not df_history.empty:
    fig = go.Figure(data=[go.Candlestick(x=df_history.index, open=df_history['Open'], high=df_history['High'], low=df_history['Low'], close=df_history['Close'])])
    fig.update_layout(height=400, template="plotly_dark", margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# 2. 予測実行（地域制限対策版）
if st.button("🚀 AI予測を実行する", use_container_width=True, type="primary"):
    with st.spinner("AIと通信中..."):
        try:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            
            # 【重要】地域制限に強い 'gemini-1.5-pro' を使用
            model = genai.GenerativeModel('gemini-1.5-pro')
            
            prompt = f"USD/JPY is {current_rate}. Predict next 24h as [BUY/SELL/HOLD] in Japanese."
            response = model.generate_content(prompt)
            
            if response.text:
                res_text = response.text
                judgment = "BUY" if "[BUY]" in res_text.upper() else "SELL" if "[SELL]" in res_text.upper() else "HOLD"
                st.session_state.history.append({"time": datetime.datetime.now(JST), "rate": current_rate, "pred": judgment})
                st.subheader(f"🔮 AI判定: {judgment}")
                st.markdown(res_text)
                
        except Exception as e:
            if "location" in str(e).lower():
                st.error("お使いのサーバーの地域ではこのAIモデルが制限されています。")
                st.info("解決策: Streamlit Cloudの設定で 'App sharing' を一度オフにしてからオンにするか、時間を置いて試してください。")
            else:
                st.error(f"エラー: {e}")

if st.session_state.history:
    st.divider()
    for h in reversed(st.session_state.history):
        st.write(f"【{h['time'].strftime('%H:%M')}】 {h['pred']} ({h['rate']}円)")
