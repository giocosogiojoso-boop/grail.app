import streamlit as st
import google.generativeai as genai
import requests
import feedparser
import urllib.parse
import datetime
import pytz
import yfinance as ticker_data
import plotly.graph_objects as go
import pandas as pd

# --- アプリ基本設定 ---
st.set_page_config(page_title="FX AI-Analyst 2026", page_icon="📈", layout="centered")

# --- 日本時間 & データ取得関数 ---
def get_jst_now():
    return datetime.datetime.now(pytz.timezone('Asia/Tokyo'))

@st.cache_data(ttl=60)
def get_fx_data_and_indicators(interval="1d"):
    data = ticker_data.Ticker("JPY=X")
    period = "2d" if interval=="1h" else "60d" if interval=="1d" else "250d"
    df = data.history(period=period, interval=interval)
    
    if not df.empty:
        # テクニカル指標の計算
        df['SMA20'] = df['Close'].rolling(window=20).mean() # 20日移動平均
        # RSI計算
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
    return df

# --- AIモデル取得 ---
def get_ai_model():
    if "GEMINI_API_KEY" not in st.secrets: return None, None
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model_names = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-pro']
    for m_name in model_names:
        try: return genai.GenerativeModel(m_name), m_name
        except: continue
    return None, None

# --- ニュース取得 ---
@st.cache_data(ttl=300)
def get_latest_forex_news():
    news_list = []
    query = urllib.parse.quote('USD JPY "forex" OR "円安" OR "円高" when:1d')
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:8]: news_list.append(f"・{entry.title}")
    except: pass
    return news_list

# --- UI構築 ---
st.title("📈 ドル円 AI実戦司令塔")

jst_now = get_jst_now()
df_full = get_fx_data_and_indicators("1d")
current_rate = round(df_full['Close'].iloc[-1], 3) if not df_full.empty else 0.0

col1, col2 = st.columns(2)
with col1: st.metric("現在時刻 (日本)", jst_now.strftime('%Y/%m/%d %H:%M'))
with col2: st.metric("USD / JPY", f"{current_rate} 円")

# --- チャートエリア ---
if 'chart_interval' not in st.session_state: st.session_state.chart_interval = "1d"
df_chart = get_fx_data_and_indicators(st.session_state.chart_interval)

fig = go.Figure()
fig.add_trace(go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name="価格"))
if 'SMA20' in df_chart.columns:
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['SMA20'], line=dict(color='orange', width=1), name="SMA20"))

fig.update_layout(height=400, margin=dict(l=10, r=10, b=10, t=10), xaxis_rangeslider_visible=False)
st.plotly_chart(fig, use_container_width=True)

# チャート切り替えボタン
c1, c2, c3, c4 = st.columns([4, 1, 1, 1])
with c2: 
    if st.button("時間"): st.session_state.chart_interval = "1h"; st.rerun()
with c3: 
    if st.button("日足"): st.session_state.chart_interval = "1d"; st.rerun()
with c4: 
    if st.button("週足"): st.session_state.chart_interval = "1wk"; st.rerun()

st.divider()

# --- 解析・予測ボタン ---
if st.button("🎯 24時間後の予測を実行", use_container_width=True, type="primary"):
    with st.spinner("テクニカル＆ファンダメンタルズを統合解析中..."):
        model, m_name = get_ai_model()
        news = get_latest_forex_news()
        
        # テクニカル数値の抽出
        last_rsi = round(df_full['RSI'].iloc[-1], 2)
        last_sma = round(df_full['SMA20'].iloc[-1], 3)
        price_change = round(current_rate - df_full['Close'].iloc[-2], 3)
        
        if model:
            prompt = f"""
            あなたは2026年1月を生きる最強のFXAIアナリストです。
            現在の日本時間: {jst_now.strftime('%Y-%m-%d %H:%M')}
            
            【現在の市場データ】
            - 現在価格: {current_rate} 円
            - 前日比: {price_change} 円
            - RSI(14): {last_rsi} (70以上で買われすぎ、30以下で売られすぎ)
            - SMA20(20日移動平均): {last_sma} 円
            
            【最新ニュース】
            {chr(10).join(news)}
            
            【指令】
            高市政権下の経済政策と日銀の動向、および上記のテクニカル数値を踏まえ、
            「今から24時間後の値動き」を具体的・数値的に予測してください。
            
            【回答フォーマット】
            ■24時間後の予想価格: [XXX.XX] 円
            ■メインシナリオ: (上がるか下がるか、その理由)
            ■テクニカル判断: (RSIやSMAから見た過熱感)
            ■注意すべき経済イベント: 
            ■予測の信頼度: [0-100]%
            """
            try:
                response = model.generate_content(prompt)
                st.subheader("🔮 24時間後の予測レポート")
                st.success(f"解析成功 (AI: {m_name})")
                st.markdown(response.text)
            except Exception as e:
                st.error(f"解析エラー: {e}")

with st.sidebar:
    st.header("資金管理")
    balance = st.number_input("残高", value=1000000)
    risk = st.slider("リスク%", 0.1, 5.0, 1.0)
    st.metric("許容損失額", f"{int(balance * risk / 100):,} 円")
