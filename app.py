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
st.set_page_config(page_title="FX AI-Analyst Dashboard Pro", page_icon="💹", layout="wide")

# --- 日本時間設定 ---
JST = pytz.timezone('Asia/Tokyo')

# --- セッション状態の初期化 ---
if 'history' not in st.session_state:
    st.session_state.history = []

# --- 1. 市場データ・ニュースの自動取得 ---
@st.cache_data(ttl=300)
def fetch_all_market_data():
    fx = ticker_data.Ticker("JPY=X")
    df_d = fx.history(period="60d", interval="1d")
    df_h = fx.history(period="5d", interval="1h")
    
    try:
        tnx = ticker_data.Ticker("^TNX").history(period="1d")['Close'].iloc[-1]
        vix = ticker_data.Ticker("^VIX").history(period="1d")['Close'].iloc[-1]
    except:
        tnx, vix = 0.0, 0.0
    
    # テクニカル指標 (RSI, SMA20)
    df_d['SMA20'] = df_d['Close'].rolling(window=20).mean()
    delta = df_d['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df_d['RSI'] = 100 - (100 / (1 + (gain / loss)))

    # ニュース自動検索
    search_query = 'USD JPY "ドル円" OR "為替" OR "日銀" when:1d'
    encoded_query = urllib.parse.quote(search_query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    feed = feedparser.parse(rss_url)
    news_titles = [f"・{e.title}" for e in feed.entries[:8]]
    
    return df_d, df_h, round(tnx, 3), round(vix, 2), news_titles

# --- 2. 自動的中判定ロジック ---
def auto_check_predictions(current_price):
    now = datetime.datetime.now(JST)
    updated = False
    
    for entry in st.session_state.history:
        # 【テスト用】判定時間を60秒に設定。確認できたら 86400 に変更してください。
        check_seconds = 60 
        
        if entry['status'] == 'Pending' and (now - entry['time']).total_seconds() >= check_seconds:
            is_win = False
            if entry['pred'] == "BUY" and current_price > entry['rate']: is_win = True
            elif entry['pred'] == "SELL" and current_price < entry['rate']: is_win = True
            elif entry['pred'] == "HOLD" and abs(current_price - entry['rate']) < 0.15: is_win = True
            
            entry['status'] = 'Win' if is_win else 'Loss'
            entry['final_rate'] = current_price
            updated = True
            
    if updated:
        st.toast("過去の予測を自動判定しました！")

# --- UI構築開始 ---
df_d, df_h, us10y, vix, news_list = fetch_all_market_data()
current_rate = round(df_d['Close'].iloc[-1], 3)

# 判定実行
auto_check_predictions(current_rate)

# 的中率計算
total = sum(1 for x in st.session_state.history if x['status'] in ['Win', 'Loss'])
wins = sum(1 for x in st.session_state.history if x['status'] == 'Win')
win_rate = (wins / total * 100) if total > 0 else 0

st.title("💹 ドル円 AI実戦司令塔 Dashboard Pro")

# ステータスパネル
cols = st.columns(5)
cols[0].metric("USD/JPY", f"{current_rate}円")
cols[1].metric("米10年債利回り", f"{us10y}%")
cols[2].metric("VIX(恐怖指数)", vix)
cols[3].metric("AI自動的中率", f"{win_rate:.1f}%", f"判定済:{total}件")
cols[4].metric("JST時刻", datetime.datetime.now(JST).strftime('%H:%M'))

# チャート表示
c_left, c_right = st.columns(2)
def create_candlestick(df):
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
    fig.update_layout(height=300, margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False, template="plotly_dark")
    return fig
c_left.plotly_chart(create_candlestick(df_d), use_container_width=True)
c_right.plotly_chart(create_candlestick(df_h), use_container_width=True)

st.divider()

# --- 解析・予測ボタンセクション ---
col_main, col_sub = st.columns([2, 1])

with col_main:
    # 💥 ここに予測実行ボタンを配置しました 💥
    if st.button("🚀 最新ニュースを分析して24時間予測を実行", use_container_width=True, type="primary"):
        with st.spinner("AIが最新情報を統合分析中..."):
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            rsi_val = round(df_d['RSI'].iloc[-1], 2)
            prompt = f"""
            2026年1月のプロFXトレーダーとして分析せよ。
            現在レート: {current_rate}円 / 米金利: {us10y}% / VIX: {vix} / RSI: {rsi_val}
            【最新ニュース】
            {chr(10).join(news_list)}
            
            24時間後の[BUY/SELL/HOLD]を判定し、その根拠と予想価格を答えよ。
            """
            
            try:
                response = model.generate_content(prompt)
                res_text = response.text
                judgment = "BUY" if "[BUY]" in res_text.upper() else "SELL" if "[SELL]" in res_text.upper() else "HOLD"
                
                # 履歴に追加
                st.session_state.history.append({
                    "time": datetime.datetime.now(JST),
                    "rate": current_rate,
                    "pred": judgment,
                    "status": "Pending"
                })
                
                st.subheader(f"🔮 AI判定: {judgment}")
                st.markdown(res_text)
            except Exception as e:
                st.error(f"解析エラー: {e}")

with col_sub:
    st.subheader("📰 取得ニュース & 予測履歴")
    for n in news_list[:5]:
        st.caption(n)
    
    st.divider()
    for h in reversed(st.session_state.history[-5:]):
        icon = "⏳" if h['status'] == 'Pending' else "✅" if h['status'] == 'Win' else "❌"
        st.write(f"{icon} {h['time'].strftime('%H:%M')} | {h['pred']} ({h['status']})")

with st.sidebar:
    st.header("設定")
    if st.button("履歴をクリア"):
        st.session_state.history = []
        st.rerun()
