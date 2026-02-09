import streamlit as st
import google.generativeai as genai
import feedparser
import urllib.parse
import datetime
import pytz
import yfinance as ticker_data
import plotly.graph_objects as go
import pandas as pd

# 1. ページ設定
st.set_page_config(page_title="FX AI-Analyst Stable", layout="wide")
JST = pytz.timezone('Asia/Tokyo')

if 'history' not in st.session_state:
    st.session_state.history = []

# 2. データ取得関数（バグ回避のため get_data に統一）
@st.cache_data(ttl=600)
def get_data():
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

# 3. UI表示
st.title("💹 FX AI-Analyst (Global Stable)")
st.metric("USD/JPY", f"{current_rate}円")

if not df_history.empty:
    fig = go.Figure(data=[go.Candlestick(x=df_history.index, open=df_history['Open'], high=df_history['High'], low=df_history['Low'], close=df_history['Close'])])
    fig.update_layout(height=400, template="plotly_dark", margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# 4. 予測実行（Proモデルへの変更と詳細エラー表示）
if st.button("🚀 AI予測を実行する", use_container_width=True, type="primary"):
    with st.spinner("AIと通信中..."):
        try:
            api_key = st.secrets["GEMINI_API_KEY"]
            genai.configure(api_key=api_key)
            
            # 【重要】地域制限をパスしやすいと言われる 'gemini-1.5-pro' に変更
            model = genai.GenerativeModel('gemini-1.5-pro')
            
            prompt = f"現在のドル円は{current_rate}円です。24時間後の予測を[BUY/SELL/HOLD]で判定し、日本語で理由を述べてください。"
            response = model.generate_content(prompt)
            
            if response.text:
                res_text = response.text
                judgment = "BUY" if "[BUY]" in res_text.upper() else "SELL" if "[SELL]" in res_text.upper() else "HOLD"
                st.session_state.history.append({"time": datetime.datetime.now(JST), "rate": current_rate, "pred": judgment})
                st.subheader(f"🔮 AI判定: {judgment}")
                st.markdown(res_text)
                
        except Exception as e:
            st.error("🚨 通信エラーが発生しました")
            if "location" in str(e).lower():
                st.warning("Googleの地域制限により、現在このAIモデルは利用できません。")
                st.info("解決策: 1時間ほど待つか、Streamlit Cloudの画面右下から 'Reboot App' を試すと、接続先が変わって直ることがあります。")
            else:
                st.code(str(e))

if st.session_state.history:
    st.divider()
    for h in reversed(st.session_state.history):
        st.write(f"【{h['time'].strftime('%H:%M')}】 {h['pred']} ({h['rate']}円)")
