import streamlit as st
import google.generativeai as genai
import feedparser
import urllib.parse
import datetime
import pytz
import yfinance as ticker_data
import plotly.graph_objects as go
import pandas as pd
import time

# --- アプリ基本設定 ---
st.set_page_config(page_title="FX AI-Analyst Pro", page_icon="💹", layout="wide")
JST = pytz.timezone('Asia/Tokyo')

# ブラウザメモリに履歴を保存
if 'history' not in st.session_state:
    st.session_state.history = []

# --- 1. 市場データ・ニュース取得（エラー対策強化） ---
@st.cache_data(ttl=600) # キャッシュを10分に延ばしてアクセス制限を回避
def fetch_market_info():
    current_rate = 150.0 # 取得失敗時のデフォルト値
    df_d = pd.DataFrame()
    news = []
    
    try:
        fx = ticker_data.Ticker("JPY=X")
        df_d = fx.history(period="60d", interval="1d")
        if not df_d.empty:
            current_rate = round(df_d['Close'].iloc[-1], 3)
    except Exception as e:
        st.warning("為替データの取得制限がかかっています。しばらく待ってからリロードしてください。")

    try:
        query = urllib.parse.quote('USD JPY "ドル円" when:1d')
        rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
        feed = feedparser.parse(rss_url)
        news = [f"・{e.title}" for e in feed.entries[:8]]
    except:
        news = ["ニュースを取得できませんでした。"]
    
    return df_d, current_rate, news

# --- メイン処理 ---
df_d, current_rate, news_list = fetch_market_info()

# --- UI構築 ---
st.title("💹 ドル円 AI実戦司令塔 (Stable Lite)")

cols = st.columns(4)
cols[0].metric("USD/JPY", f"{current_rate}円")
cols[1].metric("JST時刻", datetime.datetime.now(JST).strftime('%H:%M'))
cols[2].metric("データ状態", "制限中" if df_d.empty else "正常")
cols[3].metric("履歴数", f"{len(st.session_state.history)}件")

if not df_d.empty:
    fig = go.Figure(data=[go.Candlestick(x=df_d.index, open=df_d['Open'], high=df_d['High'], low=df_d['Low'], close=df_d['Close'])])
    fig.update_layout(height=400, template="plotly_dark", margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

col_main, col_sub = st.columns([2, 1])

with col_main:
    if st.button("🚀 最新分析と予測を実行", use_container_width=True, type="primary"):
        with st.spinner("AIが分析中..."):
            try:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                model = genai.GenerativeModel('gemini-2.0-flash')
                prompt = f"現在のドル円は{current_rate}円です。以下のニュースから24時間後の[BUY/SELL/HOLD]を判定し理由を述べてください。\n" + "\n".join(news_list)
                response = model.generate_content(prompt)
                
                res_text = response.text
                judgment = "BUY" if "[BUY]" in res_text.upper() else "SELL" if "[SELL]" in res_text.upper() else "HOLD"
                
                st.session_state.history.append({
                    "time": datetime.datetime.now(JST),
                    "rate": current_rate,
                    "pred": judgment
                })
                st.subheader(f"🔮 AI判定: {judgment}")
                st.write(res_text)
            except Exception as e:
                st.error(f"AI分析エラー: {e}")

with col_sub:
    st.subheader("📰 最新ニュース")
    for n in news_list[:5]: st.caption(n)
    st.divider()
    st.subheader("📜 今回のログ")
    for h in reversed(st.session_state.history):
        st.write(f"【{h['time'].strftime('%H:%M')}】 {h['pred']} ({h['rate']}円)")
