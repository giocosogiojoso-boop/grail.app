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
st.set_page_config(page_title="FX AI-Analyst Pro", page_icon="🎯", layout="centered")

# --- カスタムCSS（カラー表示用） ---
def apply_custom_style(judgment):
    if judgment == "BUY":
        color = "#e6f4ff" # 薄い青
        border = "#1890ff"
    elif judgment == "SELL":
        color = "#fff1f0" # 薄い赤
        border = "#ff4d4f"
    else:
        color = "#f6ffed" # 薄い緑
        border = "#52c41a"
    
    st.markdown(f"""
        <style>
        .stAlert {{ background-color: {color}; border: 2px solid {border}; border-radius: 10px; }}
        </style>
    """, unsafe_allow_html=True)

# --- データ取得関数 ---
@st.cache_data(ttl=60)
def get_market_data():
    # ドル円データ
    fx = ticker_data.Ticker("JPY=X")
    df = fx.history(period="60d", interval="1d")
    
    # 米国債10年利回り (TNX)
    tnx = ticker_data.Ticker("^TNX")
    tnx_df = tnx.history(period="5d")
    current_yield = round(tnx_df['Close'].iloc[-1], 3) if not tnx_df.empty else "取得不可"
    
    # テクニカル指標計算
    if not df.empty:
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / loss)))
        
    return df, current_yield

# --- ニュース取得 ---
@st.cache_data(ttl=300)
def get_latest_news():
    query = urllib.parse.quote('USD JPY "forex" when:1d')
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
    feed = feedparser.parse(rss_url)
    return [f"・{e.title}" for e in feed.entries[:8]]

# --- AIモデル設定 ---
def get_ai_model():
    if "GEMINI_API_KEY" not in st.secrets: return None
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    return genai.GenerativeModel('gemini-2.5-flash')

# --- メインUI ---
st.title("🎯 ドル円 AI実戦司令塔 Pro")
jst_now = datetime.datetime.now(pytz.timezone('Asia/Tokyo'))
df, us10y = get_market_data()
current_rate = round(df['Close'].iloc[-1], 3)

# ヘッダー情報
c1, c2, c3 = st.columns(3)
c1.metric("時刻(JST)", jst_now.strftime('%H:%M'))
c2.metric("USD / JPY", f"{current_rate}円")
c3.metric("米10年債利回り", f"{us10y}%")

# --- チャート ---
fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="USD/JPY")])
fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], line=dict(color='orange', width=1), name="20日線"))
fig.update_layout(height=350, margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- 解析実行 ---
if st.button("🚀 24時間後予測・統合解析実行", use_container_width=True, type="primary"):
    with st.spinner("金利・テクニカル・ニュースを多角分析中..."):
        model = get_ai_model()
        news = get_latest_news()
        rsi = round(df['RSI'].iloc[-1], 2)
        
        prompt = f"""
        2026年1月時点のプロFXトレーダーとして分析せよ。
        現在時刻: {jst_now} / ドル円: {current_rate}円 / 米10年債利回り: {us10y}%
        テクニカル: RSI={rsi} / SMA20={round(df['SMA20'].iloc[-1],2)}
        【最新ニュース】
        {"".join(news)}
        
        【指示】
        1. 金利差と情勢から24時間後の方向性を出せ。
        2. 判定を[BUY], [SELL], [HOLD]のいずれかで始めよ。
        """
        
        try:
            response = model.generate_content(prompt)
            res_text = response.text
            
            # カラー判定
            judgment = "HOLD"
            if "[BUY]" in res_text.upper(): judgment = "BUY"
            if "[SELL]" in res_text.upper(): judgment = "SELL"
            
            apply_custom_style(judgment)
            
            st.subheader(f"🔮 AI予測結果: {judgment}")
            st.info(res_text)
            
        except Exception as e:
            st.error(f"エラー: {e}")

# --- サイドバー ---
with st.sidebar:
    st.header("資金管理")
    balance = st.number_input("残高(円)", 1000000)
    risk = st.slider("リスク(%)", 0.1, 5.0, 1.0)
    st.metric("最大損失許容", f"{int(balance * risk / 100):,}円")
