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
st.set_page_config(page_title="FX AI-Analyst Dashboard", page_icon="💹", layout="wide")

# --- セッション状態の初期化（的中率トラッキング用） ---
if 'history' not in st.session_state:
    st.session_state.history = [] # 過去の予測と結果のログ

# --- データ取得関数 ---
@st.cache_data(ttl=60)
def get_extended_market_data():
    # 1. ドル円 (日足・時間足)
    fx = ticker_data.Ticker("JPY=X")
    df_d = fx.history(period="60d", interval="1d")
    df_h = fx.history(period="5d", interval="1h")
    
    # 2. 米国債10年利回り (^TNX) & 恐怖指数 (^VIX)
    tnx = ticker_data.Ticker("^TNX").history(period="1d")['Close'].iloc[-1]
    vix = ticker_data.Ticker("^VIX").history(period="1d")['Close'].iloc[-1]
    
    # 3. テクニカル指標計算 (日足)
    if not df_d.empty:
        df_d['SMA20'] = df_d['Close'].rolling(window=20).mean()
        delta = df_d['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df_d['RSI'] = 100 - (100 / (1 + (gain / loss)))
        
    return df_d, df_h, round(tnx, 3), round(vix, 2)

# --- 経済カレンダー簡易取得 (RSS流用) ---
@st.cache_data(ttl=3600)
def get_economic_calendar():
    # Googleニュースから経済指標関連を抽出
    query = urllib.parse.quote('FX 経済指標 重要 雇用統計 日銀 FOMC when:7d')
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
    feed = feedparser.parse(rss_url)
    return [e.title for e in feed.entries[:5]]

# --- AI判定カラー適用 ---
def apply_ui_style(judgment):
    colors = {"BUY": ("#e6f4ff", "#1890ff"), "SELL": ("#fff1f0", "#ff4d4f"), "HOLD": ("#f6ffed", "#52c41a")}
    bg, border = colors.get(judgment, ("#ffffff", "#cccccc"))
    st.markdown(f"<style>.stAlert {{ background-color: {bg}; border: 2px solid {border}; }}</style>", unsafe_allow_html=True)

# --- メインレイアウト ---
st.title("💹 ドル円 AI実戦司令塔 Dashboard")

df_d, df_h, us10y, vix = get_extended_market_data()
current_rate = round(df_d['Close'].iloc[-1], 3)

# 1. ステータスバー
cols = st.columns(5)
cols[0].metric("USD/JPY", f"{current_rate}円")
cols[1].metric("米10年債利回り", f"{us10y}%")
cols[2].metric("VIX(恐怖指数)", vix, delta="警戒" if vix > 20 else "安定")
# 的中率の計算
wins = sum(1 for x in st.session_state.history if x['win'])
total = len(st.session_state.history)
win_rate = (wins / total * 100) if total > 0 else 0
cols[3].metric("AI的中率", f"{win_rate:.1f}%", f"試行:{total}回")
cols[4].metric("日本時間", datetime.datetime.now(pytz.timezone('Asia/Tokyo')).strftime('%H:%M'))

# 2. マルチタイムフレーム・チャート
st.subheader("マルチタイムフレーム分析 (左:日足 / 右:時間足)")
ch_col1, ch_col2 = st.columns(2)

def create_chart(df, title):
    fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
    fig.update_layout(height=300, margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False, template="plotly_dark")
    return fig

ch_col1.plotly_chart(create_chart(df_d, "Daily"), use_container_width=True)
ch_col2.plotly_chart(create_chart(df_h, "Hourly"), use_container_width=True)

st.divider()

# 3. 解析セクション
col_main, col_sub = st.columns([2, 1])

with col_main:
    if st.button("🚀 24時間後予測・統合解析実行", use_container_width=True, type="primary"):
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-2.5-flash')
        calendar = get_economic_calendar()
        
        prompt = f"""
        現在は2026年1月、ドル円レート={current_rate}円。
        - 米10年債利回り: {us10y}% (金利差要因)
        - VIX指数: {vix} (20以上はパニック相場、テクニカル無視の傾向)
        - RSI: {round(df_d['RSI'].iloc[-1], 2)}
        - 重要イベント予定: {calendar}
        
        【指示】
        上記のデータを踏まえ、24時間後の[BUY/SELL/HOLD]を判定し、その根拠と予想価格を答えよ。
        """
        response = model.generate_content(prompt)
        res_text = response.text
        
        judgment = "BUY" if "[BUY]" in res_text.upper() else "SELL" if "[SELL]" in res_text.upper() else "HOLD"
        apply_ui_style(judgment)
        
        st.subheader(f"🔮 AI判定: {judgment}")
        st.info(res_text)
        
        # 履歴に追加（仮の結果。次のボタン押し時に前回を判定するロジックの土台）
        st.session_state.history.append({"time": datetime.datetime.now(), "rate": current_rate, "pred": judgment, "win": True})

with col_sub:
    st.subheader("🗓 経済・注目イベント")
    calendar_data = get_economic_calendar()
    for item in calendar_data:
        st.caption(f"・{item}")
    
    st.divider()
    if st.button("前回の予測を『的中』として記録"):
        # 的中率のデモ用手動トリガー
        if st.session_state.history:
            st.toast("的中として記録しました！")

# --- サイドバー ---
with st.sidebar:
    st.header("資金管理 Pro")
    balance = st.number_input("残高(円)", 1000000)
    risk_pct = st.slider("許容リスク(%)", 0.1, 5.0, 1.0)
    st.metric("最大損失許容", f"{int(balance * risk_pct / 100):,}円")
    if st.button("履歴リセット"):
        st.session_state.history = []
        st.rerun()
