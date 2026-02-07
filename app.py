import streamlit as st
import google.generativeai as genai
import feedparser
import urllib.parse
import datetime
import pytz
import yfinance as ticker_data
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(page_title="FX AI-Analyst Pro", page_icon="💹", layout="wide")
JST = pytz.timezone('Asia/Tokyo')

if 'history' not in st.session_state:
    st.session_state.history = []

# --- 1. 市場データ取得（エラーを無視して続行する設定） ---
@st.cache_data(ttl=1800) # キャッシュを30分に延長（重要：アクセス回数を減らす）
def fetch_safe_data():
    current_rate = 150.0
    df_d = pd.DataFrame()
    try:
        fx = ticker_data.Ticker("JPY=X")
        df_d = fx.history(period="30d", interval="1d")
        if not df_d.empty:
            current_rate = round(df_d['Close'].iloc[-1], 3)
    except:
        pass # エラーが起きても何もしない（アプリを止めない）
    
    return df_d, current_rate

# --- 2. ニュース取得 ---
@st.cache_data(ttl=1800)
def fetch_safe_news():
    try:
        query = urllib.parse.quote('USD JPY "ドル円" when:1d')
        rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
        feed = feedparser.parse(rss_url)
        return [f"・{e.title}" for e in feed.entries[:5]]
    except:
        return ["ニュースを取得できませんでした。"]

# 実行
df_d, current_rate = fetch_safe_data()
news_list = fetch_safe_news()

st.title("💹 FX AI-Analyst 安定稼働版")

# ステータス表示
c1, c2, c3 = st.columns(3)
c1.metric("USD/JPY", f"{current_rate}円")
c2.metric("データ取得", "成功" if not df_d.empty else "通信制限中(待機)")
c3.metric("予測履歴", f"{len(st.session_state.history)}件")

if not df_d.empty:
    fig = go.Figure(data=[go.Candlestick(x=df_d.index, open=df_d['Open'], high=df_d['High'], low=df_d['Low'], close=df_d['Close'])])
    fig.update_layout(height=350, template="plotly_dark", margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

if st.button("🚀 AIに24時間予測を命令する", use_container_width=True, type="primary"):
    with st.spinner("AIが考え中..."):
        try:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            model = genai.GenerativeModel('gemini-1.5-flash') # より制限の緩いモデルに変更
            
            prompt = f"ドル円{current_rate}円。ニュース：\n" + "\n".join(news_list) + "\n24時間後を[BUY/SELL/HOLD]で判定せよ。"
            response = model.generate_content(prompt)
            
            res_text = response.text
            judgment = "BUY" if "[BUY]" in res_text.upper() else "SELL" if "[SELL]" in res_text.upper() else "HOLD"
            
            st.session_state.history.append({"time": datetime.datetime.now(JST), "pred": judgment, "rate": current_rate})
            st.subheader(f"🔮 判定: {judgment}")
            st.write(res_text)
        except Exception as e:
            if "429" in str(e):
                st.error("AIが疲れ気味です（無料枠の上限）。1時間ほど休ませてあげてください。")
            else:
                st.error(f"エラーが発生しました: {e}")

# 簡易履歴表示
if st.session_state.history:
    st.subheader("📜 今回の履歴")
    for h in reversed(st.session_state.history):
        st.caption(f"{h['time'].strftime('%H:%M')} | {h['pred']} | {h['rate']}円")
