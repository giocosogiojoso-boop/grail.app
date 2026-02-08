import streamlit as st
import google.generativeai as genai
import feedparser
import urllib.parse
import datetime
import pytz
import yfinance as ticker_data
import plotly.graph_objects as go
import pandas as pd

# 基本設定
st.set_page_config(page_title="FX AI-Analyst 2026", page_icon="💹", layout="wide")
JST = pytz.timezone('Asia/Tokyo')

if 'history' not in st.session_state:
    st.session_state.history = []

@st.cache_data(ttl=900)
def get_market_data():
    rate, df, news = 150.0, pd.DataFrame(), []
    try:
        fx = ticker_data.Ticker("JPY=X")
        df = fx.history(period="30d", interval="1d")
        if not df.empty: rate = round(df['Close'].iloc[-1], 3)
    except: pass
    try:
        query = urllib.parse.quote('USD JPY "ドル円" when:1d')
        rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
        news = [f"・{e.title}" for e in feedparser.parse(rss_url).entries[:5]]
    except: news = ["ニュース取得失敗"]
    return df, rate, news

df_history, current_rate, news_list = get_market_data()

st.title("💹 FX AI-Analyst (最終安定版)")
st.metric("USD/JPY", f"{current_rate}円")

if not df_history.empty:
    fig = go.Figure(data=[go.Candlestick(x=df_history.index, open=df_history['Open'], high=df_history['High'], low=df_history['Low'], close=df_history['Close'])])
    fig.update_layout(height=400, template="plotly_dark", margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

if st.button("🚀 AI予測を実行する", use_container_width=True, type="primary"):
    with st.spinner("AI分析中..."):
        try:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            
            # --- ここが修正の核心：複数の名前を試す ---
            success = False
            # 候補1: 標準名, 候補2: フルネーム, 候補3: 2.0版
            for model_name in ['gemini-1.5-flash', 'models/gemini-1.5-flash', 'gemini-2.0-flash']:
                try:
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(f"ドル円{current_rate}円。24時間後を[BUY/SELL/HOLD]で判定し理由を述べて。")
                    res_text = response.text
                    success = True
                    break # 成功したらループを抜ける
                except:
                    continue
            
            if success:
                judgment = "BUY" if "[BUY]" in res_text.upper() else "SELL" if "[SELL]" in res_text.upper() else "HOLD"
                st.session_state.history.append({"time": datetime.datetime.now(JST), "rate": current_rate, "pred": judgment})
                st.subheader(f"🔮 AI判定: {judgment}")
                st.markdown(res_text)
            else:
                st.error("利用可能なAIモデルが見つかりません。APIキーが有効か確認してください。")
        except Exception as e:
            st.error(f"エラー: {e}")

if st.session_state.history:
    st.divider()
    for h in reversed(st.session_state.history):
        st.write(f"【{h['time'].strftime('%H:%M')}】 {h['pred']} ({h['rate']}円)")
