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
st.set_page_config(page_title="FX AI-Analyst Pro (Auto-Check)", page_icon="💹", layout="wide")

# --- 日本時間設定 ---
JST = pytz.timezone('Asia/Tokyo')

# --- セッション状態の初期化 ---
if 'history' not in st.session_state:
    st.session_state.history = [] # 予測履歴: {time, rate, pred, status}

# --- データ取得 & 自動的中判定ロジック ---
def get_market_data():
    fx = ticker_data.Ticker("JPY=X")
    df_d = fx.history(period="60d", interval="1d")
    df_h = fx.history(period="5d", interval="1h")
    tnx = ticker_data.Ticker("^TNX").history(period="1d")['Close'].iloc[-1]
    vix = ticker_data.Ticker("^VIX").history(period="1d")['Close'].iloc[-1]
    
    # 自動的中判定 (24時間経過した予測をチェック)
    now = datetime.datetime.now(JST)
    for entry in st.session_state.history:
        # まだ「判定待ち(Pending)」かつ、予測から24時間以上経過している場合
        if entry['status'] == 'Pending' and (now - entry['time']).total_seconds() >= 86400:
            # 24時間後の正確なヒストリカルデータは取得が難しいため、現在のレートで簡易判定
            current_price = df_d['Close'].iloc[-1]
            entry['final_rate'] = current_price
            
            # 的中判定ロジック
            is_win = False
            if entry['pred'] == "BUY" and current_price > entry['rate']: is_win = True
            if entry['pred'] == "SELL" and current_price < entry['rate']: is_win = True
            if entry['pred'] == "HOLD" and abs(current_price - entry['rate']) < 0.10: is_win = True # 0.1円以内の変動なら的中
            
            entry['status'] = 'Win' if is_win else 'Loss'

    return df_d, df_h, round(tnx, 3), round(vix, 2)

# --- ニュース取得 ---
@st.cache_data(ttl=3600)
def get_economic_calendar():
    query = urllib.parse.quote('FX 経済指標 重要 when:7d')
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
    feed = feedparser.parse(rss_url)
    return [e.title for e in feed.entries[:5]]

# --- UI構築 ---
st.title("💹 ドル円 AI実戦司令塔 (自動的中判定)")

df_d, df_h, us10y, vix = get_market_data()
current_rate = round(df_d['Close'].iloc[-1], 3)

# 的中率計算
total_checked = sum(1 for x in st.session_state.history if x['status'] in ['Win', 'Loss'])
wins = sum(1 for x in st.session_state.history if x['status'] == 'Win')
win_rate = (wins / total_checked * 100) if total_checked > 0 else 0

# ステータスバー
cols = st.columns(5)
cols[0].metric("USD/JPY", f"{current_rate}円")
cols[1].metric("米10年債利回り", f"{us10y}%")
cols[2].metric("VIX(恐怖指数)", vix)
cols[3].metric("AI自動的中率", f"{win_rate:.1f}%", f"判定済:{total_checked}件")
cols[4].metric("JST時刻", datetime.datetime.now(JST).strftime('%H:%M'))

# マルチタイムフレームチャート
ch_col1, ch_col2 = st.columns(2)
def create_chart(df):
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
    fig.update_layout(height=300, margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False, template="plotly_dark")
    return fig
ch_col1.plotly_chart(create_chart(df_d), use_container_width=True)
ch_col2.plotly_chart(create_chart(df_h), use_container_width=True)

st.divider()

# --- 解析・予測実行 ---
col_main, col_sub = st.columns([2, 1])

with col_main:
    if st.button("🚀 24時間後予測を実行（履歴に保存）", use_container_width=True, type="primary"):
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"現在は2026年1月。レート={current_rate}円。ニュースと金利{us10y}%から24時間後の[BUY/SELL/HOLD]を判定せよ。"
        response = model.generate_content(prompt)
        res_text = response.text
        
        judgment = "BUY" if "[BUY]" in res_text.upper() else "SELL" if "[SELL]" in res_text.upper() else "HOLD"
        
        # 予測をセッション履歴に追加
        st.session_state.history.append({
            "time": datetime.datetime.now(JST),
            "rate": current_rate,
            "pred": judgment,
            "status": "Pending", # 24時間後に判定
            "final_rate": None
        })
        
        st.subheader(f"🔮 AI判定: {judgment}")
        st.info(res_text)

with col_sub:
    st.subheader("📝 予測ログ (直近5件)")
    for h in reversed(st.session_state.history[-5:]):
        color = "🔵" if h['status'] == 'Win' else "🔴" if h['status'] == 'Loss' else "⏳"
        st.write(f"{color} {h['time'].strftime('%m/%d %H:%M')} | {h['pred']} @ {h['rate']} ({h['status']})")
    
    if st.sidebar.button("履歴リセット"):
        st.session_state.history = []
        st.rerun()
