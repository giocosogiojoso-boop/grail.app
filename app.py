import streamlit as st
import google.generativeai as genai
import feedparser
import urllib.parse
import datetime
import pytz
import yfinance as ticker_data
import plotly.graph_objects as go
import pandas as pd

# --- アプリ基本設定 ---
st.set_page_config(page_title="FX AI-Analyst Pro", page_icon="💹", layout="wide")
JST = pytz.timezone('Asia/Tokyo')

# --- セッション状態（スプレッドシートを使わず、一時的にブラウザに保存） ---
if 'history' not in st.session_state:
    st.session_state.history = []

# --- 1. 市場データ・ニュース取得 ---
@st.cache_data(ttl=300)
def fetch_market_info():
    fx = ticker_data.Ticker("JPY=X")
    df_d = fx.history(period="60d", interval="1d")
    df_h = fx.history(period="5d", interval="1h")
    
    try:
        tnx = ticker_data.Ticker("^TNX").history(period="1d")['Close'].iloc[-1]
        vix = ticker_data.Ticker("^VIX").history(period="1d")['Close'].iloc[-1]
    except:
        tnx, vix = 0.0, 0.0

    df_d['RSI'] = 100 - (100 / (1 + (df_d['Close'].diff().where(lambda x: x > 0, 0).rolling(14).mean() / 
                                     -df_d['Close'].diff().where(lambda x: x < 0, 0).rolling(14).mean())))

    query = urllib.parse.quote('USD JPY "ドル円" when:1d')
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
    feed = feedparser.parse(rss_url)
    news = [f"・{e.title}" for e in feed.entries[:8]]
    
    return df_d, df_h, round(tnx, 3), round(vix, 2), news

# --- 2. 自動判定ロジック（メモリ上で行う） ---
def check_predictions(current_price):
    now = datetime.datetime.now(JST)
    for entry in st.session_state.history:
        # 実戦用：86400秒(24時間) / テスト用：60秒
        target_seconds = 86400 
        
        if entry['status'] == 'Pending' and (now - entry['time']).total_seconds() >= target_seconds:
            is_win = False
            if entry['pred'] == "BUY" and current_price > entry['rate']: is_win = True
            elif entry['pred'] == "SELL" and current_price < entry['rate']: is_win = True
            elif entry['pred'] == "HOLD" and abs(current_price - entry['rate']) < 0.15: is_win = True
            
            entry['status'] = 'Win' if is_win else 'Loss'
            entry['final_rate'] = current_price

# --- メイン処理 ---
df_d, df_h, us10y, vix, news_list = fetch_market_info()
current_rate = round(df_d['Close'].iloc[-1], 3)
check_predictions(current_rate)

# 的中率計算
total = sum(1 for x in st.session_state.history if x['status'] in ['Win', 'Loss'])
wins = sum(1 for x in st.session_state.history if x['status'] == 'Win')
win_rate = (wins / total * 100) if total > 0 else 0

# --- UI構築 ---
st.title("💹 ドル円 AI実戦司令塔 (Lite)")

cols = st.columns(5)
cols[0].metric("USD/JPY", f"{current_rate}円")
cols[1].metric("米10年債", f"{us10y}%")
cols[2].metric("VIX", vix)
cols[3].metric("AI的中率", f"{win_rate:.1f}%", f"判定済:{total}件")
cols[4].metric("JST時刻", datetime.datetime.now(JST).strftime('%H:%M'))

c_left, c_right = st.columns(2)
def create_fig(df):
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
    fig.update_layout(height=300, margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False, template="plotly_dark")
    return fig
c_left.plotly_chart(create_fig(df_d), use_container_width=True)
c_right.plotly_chart(create_fig(df_h), use_container_width=True)

st.divider()

col_main, col_sub = st.columns([2, 1])

with col_main:
    if st.button("🚀 最新分析と24時間予測を実行", use_container_width=True, type="primary"):
        with st.spinner("分析中..."):
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            model = genai.GenerativeModel('gemini-2.0-flash') # 安定版のflash
            
            prompt = f"2026年現在のFXトレーダーとして分析せよ。ドル円:{current_rate}、米金利:{us10y}。以下ニュースを読み、24時間後の[BUY/SELL/HOLD]を理由と共に判定せよ。\n" + "\n".join(news_list)
            response = model.generate_content(prompt)
            judgment = "BUY" if "[BUY]" in response.text.upper() else "SELL" if "[SELL]" in response.text.upper() else "HOLD"
            
            st.session_state.history.append({
                "time": datetime.datetime.now(JST),
                "rate": current_rate,
                "pred": judgment,
                "status": "Pending",
                "final_rate": None
            })
            st.subheader(f"🔮 AI判定: {judgment}")
            st.write(response.text)

with col_sub:
    st.subheader("📰 最新ニュース")
    for n in news_list[:5]: st.caption(n)
    st.divider()
    st.subheader("📜 今回の予測履歴")
    for h in reversed(st.session_state.history[-5:]):
        icon = "⏳" if h['status'] == 'Pending' else "✅" if h['status'] == 'Win' else "❌"
        st.write(f"{icon} {h['time'].strftime('%H:%M')} | {h['pred']} ({h['status']})")
